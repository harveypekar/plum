# aiserver Priority Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a priority queue to aiserver that serializes all LLM requests, supports preemption of low-priority batch work by interactive UI requests, and routes all callers (eval, generate_examples, RP plugin) through a single gateway.

**Architecture:** New `inference_queue.py` module wraps the existing `OllamaClient` with an `InferenceQueue` class. A single async worker coroutine processes entries by priority. Preemption uses `asyncio.Task` cancellation. Callers get status updates via the same NDJSON stream that carries tokens.

**Tech Stack:** Python 3.12, asyncio, FastAPI, httpx, Pydantic

**Spec:** `docs/superpowers/specs/2026-03-27-aiserver-priority-queue-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `projects/aiserver/inference_queue.py` | **New.** InferenceQueue: priority list, worker loop, preemption, enqueue/enqueue_and_collect |
| `projects/aiserver/tests/test_inference_queue.py` | **New.** Unit tests for queue module (mocked OllamaClient) |
| `projects/aiserver/models.py` | Add priority to GenerateRequest, new ChatRequest, QueueStatusResponse |
| `projects/aiserver/config.py` | Add queue_max_depth field |
| `projects/aiserver/config.json` | Add queue_max_depth setting |
| `projects/aiserver/main.py` | Wire queue into lifespan, /generate, new /chat, /queue endpoints |
| `projects/rp/__init__.py` | No changes needed — queue accessed lazily via `app.state` |
| `projects/rp/routes.py` | 8 call sites swap to queue.enqueue/enqueue_and_collect. `research_dispatch` and `get_fewshot_messages` excluded (see note below). |
| `projects/rp/static/app.js` | Handle preempted status in NDJSON stream |
| `projects/rp/eval/engine.py` | judge() calls aiserver /chat instead of Ollama directly |
| `projects/rp/eval/cli.py` | --ollama-url becomes --aiserver-url, warmup through aiserver |
| `projects/rp/generate_examples.py` | regenerate_response() calls aiserver /chat |

**Excluded from queue (not migrated):**
- `research_dispatch()` (`research.py`) — uses `ollama.chat()` with native **tool calling** (returns structured `tool_calls` dict, not streamable text). Lightweight dispatch decision + summary. Tool-calling responses can't flow through the queue's text-oriented `enqueue_and_collect`.
- `get_fewshot_messages()` (`fewshot.py`) — uses `ollama.embed()` only. Embeddings excluded per spec.

---

## Task 1: Models — Add priority field and new request/response schemas

**Files:**
- Modify: `projects/aiserver/models.py`
- Test: `projects/aiserver/tests/test_inference_queue.py` (created here, expanded later)

- [ ] **Step 1: Write failing test for ChatRequest model**

```python
# projects/aiserver/tests/test_inference_queue.py
"""Tests for priority queue and related models."""

import sys
from pathlib import Path

# Allow imports from aiserver directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import ChatRequest, GenerateRequest, QueueStatusResponse


def test_generate_request_has_priority_default_zero():
    req = GenerateRequest(prompt="hello")
    assert req.priority == 0


def test_chat_request_defaults():
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
    assert req.priority == 5
    assert req.stream is True
    assert req.model is None
    assert req.stop is None


def test_chat_request_custom():
    req = ChatRequest(
        messages=[{"role": "user", "content": "hi"}],
        model="q8",
        priority=0,
        stream=False,
        stop=["User:"],
    )
    assert req.priority == 0
    assert req.stream is False
    assert req.stop == ["User:"]


def test_queue_status_response():
    resp = QueueStatusResponse(
        entries=[],
        active=None,
        total=0,
    )
    assert resp.total == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd projects/aiserver && python -m pytest tests/test_inference_queue.py -v`
Expected: ImportError — ChatRequest, QueueStatusResponse not defined yet

- [ ] **Step 3: Implement model changes**

In `projects/aiserver/models.py`, add to `GenerateRequest`:

```python
class GenerateRequest(BaseModel):
    prompt: str
    model: str | None = None
    system: str | None = None
    options: GenerateOptions | None = None
    priority: int = 0
```

Add new models at the end of the file:

```python
class ChatRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    options: GenerateOptions | None = None
    stop: list[str] | None = None
    stream: bool = True
    priority: int = 5


class QueueEntryStatus(BaseModel):
    id: str
    priority: int
    model: str
    status: str  # "queued" or "active"
    position: int
    created_at: float


class QueueStatusResponse(BaseModel):
    entries: list[QueueEntryStatus]
    active: QueueEntryStatus | None
    total: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd projects/aiserver && python -m pytest tests/test_inference_queue.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add projects/aiserver/models.py projects/aiserver/tests/test_inference_queue.py
git commit -m "feat(aiserver): add priority field to GenerateRequest, new ChatRequest and QueueStatusResponse models"
```

---

## Task 2: Config — Add queue_max_depth

**Files:**
- Modify: `projects/aiserver/config.py`
- Modify: `projects/aiserver/config.json`

- [ ] **Step 1: Add queue_max_depth to config.json**

Add after `"default_options": { ... }` block, before `"plugins"`:

```json
  "queue_max_depth": 100,
```

- [ ] **Step 2: Add queue_max_depth to Config class**

In `projects/aiserver/config.py`, inside `Config.__init__()`, after line 50 (`self.plugins`):

```python
        self.queue_max_depth: int = raw.get("queue_max_depth", 100)
```

- [ ] **Step 3: Verify config loads without error**

Run: `cd projects/aiserver && python -c "from config import Config; c = Config(); print(f'queue_max_depth={c.queue_max_depth}')"`
Expected: `queue_max_depth=100`

- [ ] **Step 4: Commit**

```bash
git add projects/aiserver/config.py projects/aiserver/config.json
git commit -m "feat(aiserver): add queue_max_depth config option"
```

---

## Task 3: InferenceQueue — Core queue with basic enqueue/dequeue (no preemption yet)

**Files:**
- Create: `projects/aiserver/inference_queue.py`
- Modify: `projects/aiserver/tests/test_inference_queue.py`

- [ ] **Step 1: Write failing tests for basic queue behavior**

Append to `projects/aiserver/tests/test_inference_queue.py`:

```python
import asyncio
import pytest


class FakeOllamaClient:
    """Mock OllamaClient that yields predictable chunks."""

    def __init__(self, chunks=None, delay=0):
        self.chunks = chunks or [
            {"token": "Hello", "thinking": False, "done": False},
            {"token": " world", "thinking": False, "done": False},
            {"token": "", "done": True, "total_tokens": 2, "tokens_per_second": 10.0},
        ]
        self.delay = delay
        self.calls = []

    async def generate_stream(self, model, prompt, system=None, options=None):
        self.calls.append({"type": "generate", "model": model, "prompt": prompt})
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield chunk

    async def chat_stream(self, model, messages, options=None, stop=None):
        self.calls.append({"type": "chat", "model": model, "messages": messages})
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield chunk


@pytest.mark.asyncio
async def test_single_request_flows_through():
    """A single enqueued request should yield status + tokens + done."""
    from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib

    fake = FakeOllamaClient()
    q = InferenceQueue(fake, max_depth=10)
    await q.start()

    chunks = []
    async for chunk in q.enqueue(
        priority=0, mode="generate", model="test",
        prompt="hi", system=None, options=None,
    ):
        chunks.append(chunk)

    await q.stop()

    # Should have: queued status, started status, 2 tokens, 1 done
    statuses = [c for c in chunks if "status" in c]
    tokens = [c for c in chunks if "token" in c and not c.get("done")]
    dones = [c for c in chunks if c.get("done")]

    assert any(s["status"] == "started" for s in statuses)
    assert len(tokens) == 2
    assert tokens[0]["token"] == "Hello"
    assert len(dones) == 1
    assert fake.calls[0]["model"] == "test"


@pytest.mark.asyncio
async def test_priority_ordering():
    """Lower priority number should be served first."""
    from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib

    served = []

    class TrackingOllama(FakeOllamaClient):
        async def generate_stream(self, model, prompt, system=None, options=None):
            served.append(prompt)
            async for chunk in super().generate_stream(model, prompt, system, options):
                yield chunk

    fake = TrackingOllama()
    q = InferenceQueue(fake, max_depth=10)
    # Don't start yet — enqueue several, then start so they race

    # We need the queue running to process, but we want to test ordering.
    # Enqueue with worker paused by not starting, then start.
    await q.start()

    # Enqueue low-priority first, then high-priority
    # The worker picks up the first immediately, so instead we pause the worker
    # by giving the first request a slow fake
    slow_fake_chunks = [
        {"token": "slow", "thinking": False, "done": False},
        {"token": "", "done": True, "total_tokens": 1, "tokens_per_second": 1.0},
    ]
    fake.chunks = slow_fake_chunks
    fake.delay = 0.05

    results = {}

    async def consume(name, priority, prompt):
        chunks = []
        async for chunk in q.enqueue(
            priority=priority, mode="generate", model="test",
            prompt=prompt, system=None, options=None,
        ):
            chunks.append(chunk)
        results[name] = chunks

    # Start three concurrent requests
    t1 = asyncio.create_task(consume("low", 5, "low-priority"))
    await asyncio.sleep(0.01)  # let it start processing
    t2 = asyncio.create_task(consume("medium", 3, "medium-priority"))
    t3 = asyncio.create_task(consume("high", 1, "high-priority"))

    await asyncio.gather(t1, t2, t3)
    await q.stop()

    # First served is "low" (was already running), then "high" (pri 1), then "medium" (pri 3)
    assert served[0] == "low-priority"
    assert served[1] == "high-priority"
    assert served[2] == "medium-priority"


@pytest.mark.asyncio
async def test_enqueue_and_collect():
    """enqueue_and_collect should return concatenated token text."""
    from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib

    fake = FakeOllamaClient()
    q = InferenceQueue(fake, max_depth=10)
    await q.start()

    result = await q.enqueue_and_collect(
        priority=0, mode="generate", model="test",
        prompt="hi", system=None, options=None,
    )

    await q.stop()
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_queue_full_raises():
    """Exceeding max_depth should raise an error."""
    from inference_queue import InferenceQueue, QueueFullError

    fake = FakeOllamaClient(delay=0.1)
    q = InferenceQueue(fake, max_depth=2)
    await q.start()

    # Fill queue: 1 active + 2 queued = over limit
    tasks = []
    for i in range(3):
        tasks.append(asyncio.create_task(
            q.enqueue_and_collect(priority=5, mode="generate", model="test",
                                  prompt=f"req{i}", system=None, options=None)
        ))
    await asyncio.sleep(0.05)

    # 4th should fail
    with pytest.raises(QueueFullError):
        async for _ in q.enqueue(priority=5, mode="generate", model="test",
                                 prompt="overflow", system=None, options=None):
            pass

    # Clean up
    for t in tasks:
        t.cancel()
    await q.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd projects/aiserver && python -m pytest tests/test_inference_queue.py -v -k "test_single or test_priority or test_enqueue_and_collect or test_queue_full"`
Expected: ImportError — `queue` module doesn't exist yet

- [ ] **Step 3: Implement InferenceQueue core**

Create `projects/aiserver/inference_queue.py`:

```python
"""Priority queue for serializing LLM inference requests.

Wraps OllamaClient to ensure only one request runs at a time, with
priority ordering and preemption support for interactive requests.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator


class QueueFullError(Exception):
    """Raised when the queue exceeds its max depth."""
    pass


@dataclass(order=True)
class QueueEntry:
    sort_key: tuple = field(compare=True, repr=False)
    id: str = field(compare=False)
    priority: int = field(compare=False)
    mode: str = field(compare=False)           # "generate" or "chat"
    model: str = field(compare=False)
    prompt: str | None = field(compare=False, default=None)
    system: str | None = field(compare=False, default=None)
    messages: list[dict] | None = field(compare=False, default=None)
    options: dict | None = field(compare=False, default=None)
    stop: list[str] | None = field(compare=False, default=None)
    result_stream: asyncio.Queue = field(compare=False, default=None)
    cancel_event: asyncio.Event = field(compare=False, default=None)
    created_at: float = field(compare=False, default=0.0)


_SENTINEL = {"_sentinel": True}


class InferenceQueue:
    """Priority queue that serializes OllamaClient calls."""

    def __init__(self, ollama, max_depth: int = 100):
        self._ollama = ollama
        self._max_depth = max_depth
        self._entries: list[QueueEntry] = []
        self._lock = asyncio.Lock()
        self._work_event = asyncio.Event()
        self._worker_task: asyncio.Task | None = None
        self._active: QueueEntry | None = None
        self._stream_task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Launch the worker coroutine."""
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self):
        """Shut down the worker."""
        self._running = False
        self._work_event.set()
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def enqueue(
        self,
        priority: int,
        mode: str,
        model: str,
        prompt: str | None = None,
        system: str | None = None,
        messages: list[dict] | None = None,
        options: dict | None = None,
        stop: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Add a request to the queue. Yields status messages then tokens."""
        async with self._lock:
            if len(self._entries) >= self._max_depth:
                raise QueueFullError(
                    f"Queue full ({self._max_depth} entries)"
                )

        entry = QueueEntry(
            sort_key=(priority, time.time()),
            id=uuid.uuid4().hex[:12],
            priority=priority,
            mode=mode,
            model=model,
            prompt=prompt,
            system=system,
            messages=messages,
            options=options,
            stop=stop,
            result_stream=asyncio.Queue(),
            cancel_event=asyncio.Event(),
            created_at=time.time(),
        )

        async with self._lock:
            self._entries.append(entry)
            self._entries.sort()
            position = self._entries.index(entry)

        # Check if we should preempt the active request
        await self._maybe_preempt(entry)

        self._work_event.set()

        # Yield initial queued status
        yield {"status": "queued", "position": position, "queue_id": entry.id}

        # Read from result stream until sentinel
        while True:
            chunk = await entry.result_stream.get()
            if chunk.get("_sentinel"):
                break
            yield chunk

    async def enqueue_and_collect(
        self,
        priority: int,
        mode: str,
        model: str,
        prompt: str | None = None,
        system: str | None = None,
        messages: list[dict] | None = None,
        options: dict | None = None,
        stop: list[str] | None = None,
    ) -> str:
        """Enqueue and return concatenated text. Handles preemption transparently."""
        tokens = []
        async for chunk in self.enqueue(
            priority=priority, mode=mode, model=model,
            prompt=prompt, system=system, messages=messages,
            options=options, stop=stop,
        ):
            if chunk.get("status") == "preempted":
                tokens.clear()
            elif "token" in chunk and not chunk.get("done") and not chunk.get("thinking"):
                tokens.append(chunk["token"])
        return "".join(tokens)

    def queue_snapshot(self) -> dict:
        """Return current queue state for /queue endpoint."""
        entries = []
        for i, e in enumerate(self._entries):
            entries.append({
                "id": e.id,
                "priority": e.priority,
                "model": e.model,
                "status": "queued",
                "position": i,
                "created_at": e.created_at,
            })
        active = None
        if self._active:
            active = {
                "id": self._active.id,
                "priority": self._active.priority,
                "model": self._active.model,
                "status": "active",
                "position": -1,
                "created_at": self._active.created_at,
            }
        return {
            "entries": entries,
            "active": active,
            "total": len(entries) + (1 if active else 0),
        }

    async def _maybe_preempt(self, new_entry: QueueEntry):
        """Cancel the active stream if new_entry has strictly higher priority."""
        if (
            self._active
            and new_entry.priority < self._active.priority
            and self._stream_task
            and not self._stream_task.done()
        ):
            self._stream_task.cancel()

    async def _worker(self):
        """Main worker loop: process entries one at a time."""
        while self._running:
            # Wait for work
            entry = None
            async with self._lock:
                if self._entries:
                    entry = self._entries.pop(0)

            if entry is None:
                self._work_event.clear()
                await self._work_event.wait()
                continue

            self._active = entry

            # Notify position updates for remaining entries
            await self._broadcast_positions()

            # Send started status
            await entry.result_stream.put({"status": "started"})

            # Run the Ollama stream in a cancellable task
            try:
                self._stream_task = asyncio.create_task(
                    self._run_stream(entry)
                )
                await self._stream_task
            except asyncio.CancelledError:
                # Preempted — notify caller and requeue
                await entry.result_stream.put({"status": "preempted"})
                async with self._lock:
                    # Re-insert at front of its priority tier
                    entry.sort_key = (entry.priority, 0)  # timestamp 0 = front
                    self._entries.append(entry)
                    self._entries.sort()
                self._active = None
                self._work_event.set()
                continue

            # Done — send sentinel and clean up
            await entry.result_stream.put(_SENTINEL)
            self._active = None

    async def _run_stream(self, entry: QueueEntry):
        """Stream tokens from OllamaClient into the entry's result queue."""
        try:
            if entry.mode == "generate":
                gen = self._ollama.generate_stream(
                    model=entry.model,
                    prompt=entry.prompt,
                    system=entry.system,
                    options=entry.options,
                )
            else:
                gen = self._ollama.chat_stream(
                    model=entry.model,
                    messages=entry.messages,
                    options=entry.options,
                    stop=entry.stop,
                )

            async for chunk in gen:
                await entry.result_stream.put(chunk)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await entry.result_stream.put({"error": str(e), "done": True})

    async def _broadcast_positions(self):
        """Send position updates to all queued entries."""
        async with self._lock:
            for i, entry in enumerate(self._entries):
                try:
                    entry.result_stream.put_nowait(
                        {"status": "queued", "position": i, "queue_id": entry.id}
                    )
                except asyncio.QueueFull:
                    pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd projects/aiserver && python -m pytest tests/test_inference_queue.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add projects/aiserver/inference_queue.py projects/aiserver/tests/test_inference_queue.py
git commit -m "feat(aiserver): add InferenceQueue with priority ordering and enqueue_and_collect"
```

---

## Task 4: InferenceQueue — Preemption

**Files:**
- Modify: `projects/aiserver/tests/test_inference_queue.py`
- Modify: `projects/aiserver/inference_queue.py` (if needed — preemption logic is already in core, this task adds test coverage)

- [ ] **Step 1: Write failing test for preemption**

Append to `projects/aiserver/tests/test_inference_queue.py`:

```python
@pytest.mark.asyncio
async def test_preemption_cancels_low_priority():
    """A high-priority request should preempt a running low-priority one."""
    from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib

    served_prompts = []

    class SlowOllama(FakeOllamaClient):
        async def generate_stream(self, model, prompt, system=None, options=None):
            served_prompts.append(prompt)
            for i in range(20):
                await asyncio.sleep(0.02)
                yield {"token": f"t{i}", "thinking": False, "done": False}
            yield {"token": "", "done": True, "total_tokens": 20, "tokens_per_second": 5.0}

    fake = SlowOllama()
    q = InferenceQueue(fake, max_depth=10)
    await q.start()

    low_chunks = []
    high_chunks = []

    async def consume_low():
        async for chunk in q.enqueue(
            priority=5, mode="generate", model="test",
            prompt="batch-job", system=None, options=None,
        ):
            low_chunks.append(chunk)

    async def consume_high():
        # Wait for low-priority to start generating
        await asyncio.sleep(0.1)
        async for chunk in q.enqueue(
            priority=0, mode="generate", model="test",
            prompt="interactive", system=None, options=None,
        ):
            high_chunks.append(chunk)

    await asyncio.gather(
        asyncio.create_task(consume_low()),
        asyncio.create_task(consume_high()),
    )
    await q.stop()

    # Low-priority should have been preempted and restarted
    low_statuses = [c for c in low_chunks if c.get("status") == "preempted"]
    assert len(low_statuses) == 1, f"Expected 1 preemption, got {low_statuses}"

    # High-priority should have completed
    high_dones = [c for c in high_chunks if c.get("done")]
    assert len(high_dones) == 1

    # batch-job should appear twice in served_prompts (started, preempted, restarted)
    assert served_prompts.count("batch-job") == 2
    # interactive should appear once, and be served after first batch-job start
    assert served_prompts.count("interactive") == 1
    assert served_prompts[1] == "interactive"


@pytest.mark.asyncio
async def test_chat_mode_flows_through():
    """Chat mode (messages instead of prompt) should work through the queue."""
    from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib

    fake = FakeOllamaClient()
    q = InferenceQueue(fake, max_depth=10)
    await q.start()

    result = await q.enqueue_and_collect(
        priority=0, mode="chat", model="test",
        messages=[{"role": "user", "content": "hi"}],
        options=None, stop=None,
    )

    await q.stop()
    assert result == "Hello world"
    assert fake.calls[0]["type"] == "chat"
    assert fake.calls[0]["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_enqueue_and_collect_clears_on_preemption():
    """enqueue_and_collect should discard partial tokens on preemption and return only final text."""
    from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib

    call_count = 0

    class PreemptableOllama(FakeOllamaClient):
        async def generate_stream(self, model, prompt, system=None, options=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1 and prompt == "batch-job":
                # First run: yield some tokens then get cancelled
                for i in range(20):
                    await asyncio.sleep(0.02)
                    yield {"token": f"OLD{i}", "thinking": False, "done": False}
                yield {"token": "", "done": True, "total_tokens": 20, "tokens_per_second": 5.0}
            elif prompt == "interactive":
                yield {"token": "fast", "thinking": False, "done": False}
                yield {"token": "", "done": True, "total_tokens": 1, "tokens_per_second": 10.0}
            else:
                # Second run of batch-job after preemption
                yield {"token": "FINAL", "thinking": False, "done": False}
                yield {"token": "", "done": True, "total_tokens": 1, "tokens_per_second": 5.0}

    fake = PreemptableOllama()
    q = InferenceQueue(fake, max_depth=10)
    await q.start()

    results = {}

    async def batch():
        results["batch"] = await q.enqueue_and_collect(
            priority=5, mode="generate", model="test",
            prompt="batch-job", system=None, options=None,
        )

    async def interactive():
        await asyncio.sleep(0.1)
        results["interactive"] = await q.enqueue_and_collect(
            priority=0, mode="generate", model="test",
            prompt="interactive", system=None, options=None,
        )

    await asyncio.gather(
        asyncio.create_task(batch()),
        asyncio.create_task(interactive()),
    )
    await q.stop()

    # Batch result should contain ONLY the final run's tokens, not OLD0, OLD1, etc.
    assert "OLD" not in results["batch"]
    assert results["batch"] == "FINAL"
    assert results["interactive"] == "fast"


@pytest.mark.asyncio
async def test_same_priority_no_preemption():
    """Same-priority requests should NOT preempt each other."""
    from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib

    preempted = []

    class SlowOllama(FakeOllamaClient):
        async def generate_stream(self, model, prompt, system=None, options=None):
            for i in range(5):
                await asyncio.sleep(0.02)
                yield {"token": f"t{i}", "thinking": False, "done": False}
            yield {"token": "", "done": True, "total_tokens": 5, "tokens_per_second": 5.0}

    fake = SlowOllama()
    q = InferenceQueue(fake, max_depth=10)
    await q.start()

    async def consume(prompt):
        chunks = []
        async for chunk in q.enqueue(
            priority=5, mode="generate", model="test",
            prompt=prompt, system=None, options=None,
        ):
            chunks.append(chunk)
            if chunk.get("status") == "preempted":
                preempted.append(prompt)
        return chunks

    t1 = asyncio.create_task(consume("first"))
    await asyncio.sleep(0.01)
    t2 = asyncio.create_task(consume("second"))

    await asyncio.gather(t1, t2)
    await q.stop()

    assert len(preempted) == 0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd projects/aiserver && python -m pytest tests/test_inference_queue.py -v -k "preempt"`
Expected: Both preemption tests PASS (logic is already in the core from Task 3)

- [ ] **Step 3: Commit**

```bash
git add projects/aiserver/tests/test_inference_queue.py
git commit -m "test(aiserver): add preemption test coverage for InferenceQueue"
```

---

## Task 5: Wire queue into main.py — /generate, /chat, /queue endpoints

**Files:**
- Modify: `projects/aiserver/main.py`

- [ ] **Step 1: Add queue to lifespan and app.state**

In `main.py`, add import at top:

```python
from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib
```

In the `lifespan()` function, before `yield`, add queue startup. After `yield`, add queue shutdown. Also set `app.state.queue` before `load_plugins()`.

Replace the lifespan and the line after `app = FastAPI(...)`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    inference_queue = InferenceQueue(ollama, max_depth=config.queue_max_depth)
    app.state.queue = inference_queue
    await inference_queue.start()

    async def stats_broadcaster():
        while True:
            await asyncio.sleep(5)
            s = await stats()
            event = {"type": "stats", **s.model_dump()}
            await broadcast_event(event)

    task = asyncio.create_task(stats_broadcaster())
    yield
    task.cancel()
    await inference_queue.stop()
```

`load_plugins()` is called at module level (line 234), before the lifespan runs. The queue is created inside the lifespan. So plugins cannot receive the queue at registration time. The RP plugin accesses it lazily via `app.state.queue` at request time (see Task 7).

- [ ] **Step 2: Wire /generate through queue**

Replace the existing `generate()` endpoint:

```python
from inference_queue import InferenceQueue, QueueFullError  # not 'queue' — avoids shadowing stdlib
from models import ChatRequest, QueueStatusResponse, QueueEntryStatus

@app.post("/generate")
async def generate(req: GenerateRequest):
    model = config.resolve_model(req.model)
    merged = config.merge_options(req.options)
    queue: InferenceQueue = app.state.queue
    start = time.time()

    async def stream():
        global active_streams
        active_streams += 1
        total_tokens = 0
        try:
            async for chunk in queue.enqueue(
                priority=req.priority,
                mode="generate",
                model=model,
                prompt=req.prompt,
                system=req.system,
                options=merged.copy(),
            ):
                yield json.dumps(chunk) + "\n"
                if chunk.get("done"):
                    total_tokens = chunk.get("total_tokens", 0)
        except QueueFullError as e:
            yield json.dumps({"error": str(e), "done": True}) + "\n"
        finally:
            active_streams -= 1
            elapsed = time.time() - start
            entry = {
                "model": model,
                "prompt": req.prompt[:100],
                "total_tokens": total_tokens,
                "latency": round(elapsed, 2),
                "timestamp": time.time(),
            }
            request_log.append(entry)
            await broadcast_event({"type": "request_complete", **entry})

    return StreamingResponse(stream(), media_type="application/x-ndjson")
```

- [ ] **Step 3: Add /chat endpoint**

```python
@app.post("/chat")
async def chat(req: ChatRequest):
    model = config.resolve_model(req.model)
    merged = config.merge_options(req.options)
    queue: InferenceQueue = app.state.queue
    start = time.time()

    if not req.stream:
        # Non-streaming: collect all tokens and return JSON
        try:
            text = await queue.enqueue_and_collect(
                priority=req.priority,
                mode="chat",
                model=model,
                messages=req.messages,
                options=merged.copy(),
                stop=req.stop,
            )
        except QueueFullError as e:
            raise HTTPException(status_code=503, detail=str(e))
        elapsed = time.time() - start
        entry = {
            "model": model,
            "prompt": str(req.messages[-1].get("content", ""))[:100] if req.messages else "",
            "total_tokens": len(text) // 4,
            "latency": round(elapsed, 2),
            "timestamp": time.time(),
        }
        request_log.append(entry)
        await broadcast_event({"type": "request_complete", **entry})
        return {"message": {"content": text}, "model": model}

    # Streaming mode
    async def stream():
        global active_streams
        active_streams += 1
        total_tokens = 0
        try:
            async for chunk in queue.enqueue(
                priority=req.priority,
                mode="chat",
                model=model,
                messages=req.messages,
                options=merged.copy(),
                stop=req.stop,
            ):
                yield json.dumps(chunk) + "\n"
                if chunk.get("done"):
                    total_tokens = chunk.get("total_tokens", 0)
        except QueueFullError as e:
            yield json.dumps({"error": str(e), "done": True}) + "\n"
        finally:
            active_streams -= 1
            elapsed = time.time() - start
            entry = {
                "model": model,
                "prompt": str(req.messages[-1].get("content", ""))[:100] if req.messages else "",
                "total_tokens": total_tokens,
                "latency": round(elapsed, 2),
                "timestamp": time.time(),
            }
            request_log.append(entry)
            await broadcast_event({"type": "request_complete", **entry})

    return StreamingResponse(stream(), media_type="application/x-ndjson")
```

- [ ] **Step 4: Add /queue status endpoint**

```python
@app.get("/queue")
async def queue_status():
    queue: InferenceQueue = app.state.queue
    snap = queue.queue_snapshot()
    return snap
```

- [ ] **Step 5: Verify server starts without error**

Run: `cd projects/aiserver && timeout 5 python main.py 2>&1 || true`
Expected: Server starts (may fail to connect to Ollama, but no import/startup errors)

- [ ] **Step 6: Commit**

```bash
git add projects/aiserver/main.py
git commit -m "feat(aiserver): wire InferenceQueue into /generate, add /chat and /queue endpoints"
```

---

## Task 6: Update StatsResponse with queue info

**Files:**
- Modify: `projects/aiserver/models.py`
- Modify: `projects/aiserver/main.py`

- [ ] **Step 1: Add queue_depth to StatsResponse**

In `models.py`, update `StatsResponse`:

```python
class StatsResponse(BaseModel):
    total_requests: int
    requests_last_hour: int
    avg_tokens_per_second: float
    active_streams: int
    queue_depth: int = 0
```

- [ ] **Step 2: Update stats() in main.py to include queue_depth**

In the `stats()` function, add queue depth:

```python
    queue_depth = len(app.state.queue._entries) if hasattr(app.state, 'queue') else 0
```

And include `queue_depth=queue_depth` in the StatsResponse constructor.

- [ ] **Step 3: Commit**

```bash
git add projects/aiserver/models.py projects/aiserver/main.py
git commit -m "feat(aiserver): add queue_depth to stats endpoint"
```

---

## Task 7: RP plugin — Wire routes through queue

**Files:**
- Modify: `projects/rp/__init__.py`
- Modify: `projects/rp/routes.py`

- [ ] **Step 1: Update routes.setup() to accept queue**

In `projects/rp/routes.py`, add `_queue = None` at module level (line 26 area, alongside `_ollama = None`):

```python
_queue = None
```

Update `setup()` (line 42):

```python
def setup(app: FastAPI, ollama, resolve_model=None):
    global _ollama, _pipeline, _resolve_model, _queue
    _ollama = ollama
    _pipeline = create_default_pipeline()
    _resolve_model = resolve_model or (lambda m: m)
    _queue = getattr(app.state, 'queue', None)
```

Wait — `setup()` is called by `register()` which runs at module import time via `load_plugins()`. At that point `app.state.queue` doesn't exist yet (it's created in the lifespan). So we need lazy access.

**Better approach:** Read queue lazily from `app.state` in the routes that need it:

```python
def _get_queue():
    """Get InferenceQueue from app state. Available after lifespan starts."""
    from main import app
    return getattr(app.state, 'queue', None)
```

Actually, the routes are FastAPI route functions that receive `Request` — but they're defined as closures inside `setup()`, not standard FastAPI dependency-injected routes. Let me re-check.

Looking at `routes.py`, the routes are defined inside `setup()` as `@app.post(...)` decorated functions. They close over `_ollama`. We can similarly close over a lazy queue reference.

**Simplest approach:** Add a `_queue` global that gets set in the RP lifespan (which runs after the main lifespan creates the queue):

**Timing constraint:** `register()` is called at module import time by `load_plugins()`, before the app lifespan runs. The queue is created inside the lifespan. So we cannot pass the queue at registration time. Instead, routes read it lazily from `app.state` at request time.

In `projects/rp/__init__.py` — **no changes needed**. Keep existing code as-is.

In `projects/rp/routes.py`, add a helper and a module-level `_app` reference:

```python
_app = None  # set by setup(), used for lazy queue access

def _get_queue():
    """Get InferenceQueue from app state. Available after lifespan starts."""
    if _app and hasattr(_app.state, 'queue'):
        return _app.state.queue
    return None
```

Update `setup()` to store the app reference:

```python
def setup(app: FastAPI, ollama, resolve_model=None):
    global _ollama, _pipeline, _resolve_model, _app
    _ollama = ollama
    _pipeline = create_default_pipeline()
    _resolve_model = resolve_model or (lambda m: m)
    _app = app
```

Then in all call sites, use `_get_queue()` instead of `_queue`. For example: `await _get_queue().enqueue_and_collect(...)`. If the queue is None (shouldn't happen in normal operation), fall back to `_ollama` directly — this keeps the server functional even without the queue during testing.

- [ ] **Step 2: Swap 4x _ollama.generate() call sites to _queue.enqueue_and_collect()**

These are non-streaming calls at lines 183, 215, 539, 636. Each needs to change from:

```python
result = await _ollama.generate(model=model, prompt=..., system=..., options=...)
```

To:

```python
result = await _get_queue().enqueue_and_collect(
    priority=0, mode="generate", model=model,
    prompt=..., system=..., options=...,
)
```

Line 539 is wrapped in `asyncio.wait_for()` — keep the timeout wrapper:

```python
result = await asyncio.wait_for(
    _get_queue().enqueue_and_collect(
        priority=0, mode="generate", model=model,
        prompt=full_prompt,
        system=f"You are writing the opening narration for {char_name}. Stay in character.",
        options={"temperature": 1.05, "num_predict": 768, "min_p": 0.1, "repeat_penalty": 1.08},
    ),
    timeout=120,
)
```

- [ ] **Step 3: Swap 4x _ollama.chat_stream() call sites to _queue.enqueue()**

These are streaming calls at lines 731, 843, 899, 1003. Each currently looks like:

```python
async for chunk in _ollama.chat_stream(
    model=model, messages=cur_messages,
    options=ollama_options, stop=[f"{user_name}:"],
):
    yield json.dumps(chunk) + "\n"
    ...
```

Change to:

```python
async for chunk in _get_queue().enqueue(
    priority=0, mode="chat", model=model,
    messages=cur_messages,
    options=ollama_options, stop=[f"{user_name}:"],
):
    # Forward status messages (queued, started, preempted) to frontend
    if chunk.get("status"):
        yield json.dumps(chunk) + "\n"
        if chunk["status"] == "preempted":
            tokens.clear()  # discard partial tokens from cancelled generation
        continue
    # Normal token/done handling — unchanged from original
    yield json.dumps(chunk) + "\n"
    ...
```

**Important for the MCP tool-calling loop (line 728):** The `send_message` route has a multi-round loop where `tokens` accumulates text, and after the stream completes, it checks for tool calls. Status messages don't have a `"token"` key, so the `continue` ensures they skip the `tokens.append(chunk["token"])` line. On preemption, `tokens.clear()` discards partial output so the restarted generation builds clean text. The tool-call check after the inner loop runs only on the final complete generation.

Apply this same pattern to all 4 `chat_stream` call sites (lines 731, 843, 899, 1003). Each has a `tokens = []` accumulator that needs clearing on preemption.

- [ ] **Step 4: Verify no import errors**

Run: `cd projects/aiserver && python -c "from rp import register; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add projects/rp/__init__.py projects/rp/routes.py
git commit -m "feat(rp): wire all Ollama calls through InferenceQueue"
```

---

## Task 8: RP frontend — Handle preemption in app.js

**Files:**
- Modify: `projects/rp/static/app.js`

- [ ] **Step 1: Add preemption handler to NDJSON stream parser**

In `app.js`, the streaming handler is around line 600-660. The chunk processing currently handles `chunk.error`, `chunk.thinking`, `chunk.done`, and the default token case. Add preemption handling before the token case:

After the `chunk.error` block (around line 615) and before the thinking check, add:

```javascript
          // Queue status messages
          if (chunk.status) {
            if (chunk.status === "preempted") {
              // Clear partial text — generation will restart
              bubble.textContent = "";
              if (thinkingContent) thinkingContent.textContent = "";
            }
            // Ignore other status messages (queued, started)
            continue;
          }
```

This goes right after the error handling block and before `if (chunk.thinking)`.

- [ ] **Step 2: Test manually**

Open the RP UI, send a message. The status messages should be silently ignored (no visible effect for non-preempted requests). Preemption can be tested by starting a batch job and then sending a UI message.

- [ ] **Step 3: Commit**

```bash
git add projects/rp/static/app.js
git commit -m "feat(rp): handle preemption status in frontend NDJSON stream"
```

---

## Task 9: Eval system — Route through aiserver

**Files:**
- Modify: `projects/rp/eval/engine.py`
- Modify: `projects/rp/eval/cli.py`

- [ ] **Step 1: Update engine.py judge() to call aiserver /chat**

Replace the `judge()` function's HTTP call (lines 230-244) to use aiserver instead of Ollama directly:

```python
async def judge(
    aiserver_url: str,
    model: str,
    rubric: Rubric,
    context: dict,
    evaluator: str = "",
    target_id: str = "",
    target_label: str = "",
) -> EvalResult:
    """Run the LLM judge on a single item and return structured scores."""
    system_prompt, user_message = build_judge_prompt(rubric, context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{aiserver_url}/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "priority": 5,
                "options": {"temperature": 0.3, "num_predict": 2048, "think": False},
            },
            timeout=900.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"aiserver {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"aiserver error: {data['error']}")
        raw_output = data["message"]["content"]

    scores = parse_scores(raw_output, rubric)
    weighted_avg = compute_weighted_average(scores, rubric)

    return EvalResult(
        evaluator=evaluator,
        target_id=target_id,
        target_label=target_label,
        scores=scores,
        weighted_average=weighted_avg,
        raw_judge_output=raw_output,
        model=model,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )
```

Note: parameter renamed from `ollama_url` to `aiserver_url`. All callers of `judge()` need updating.

- [ ] **Step 2: Update cli.py**

Change `--ollama-url` to `--aiserver-url` with default `http://localhost:8080`:

In `_add_common_args()`:

```python
    sub.add_argument(
        "--aiserver-url",
        default=os.environ.get("AISERVER_URL", "http://localhost:8080"),
    )
```

Remove the old `--ollama-url` argument.

Update `_warmup_model()` to use aiserver:

```python
async def _warmup_model(aiserver_url: str, model: str):
    """Send a throwaway request to load the model into memory."""
    print("Loading judge model...", end="", flush=True)
    t_load = time.time()
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{aiserver_url}/chat",
                json={"model": model, "messages": [
                    {"role": "user", "content": "hi"}
                ], "stream": False, "priority": 5},
                timeout=600.0,
            )
    except Exception:
        pass
    print(f" {time.time() - t_load:.1f}s\n")
```

In `main()`, change `ollama_url = resolve_url(args.ollama_url)` to `aiserver_url = args.aiserver_url`.

Update all `run_*()` function signatures and calls: `ollama_url` → `aiserver_url`. These are: `run_fewshot`, `run_card`, `run_response`, `run_scene_state`, `run_scenario`.

Also update the evaluator modules that receive `ollama_url` — check each evaluator's `evaluate_single`/`evaluate_batch`/`evaluate_conversation` to pass through `aiserver_url` instead of `ollama_url` to `judge()`.

- [ ] **Step 3: Update evaluator modules**

The evaluator modules in `projects/rp/eval/evaluators/` (fewshot.py, card.py, response.py, scene_state.py, scenario.py) each have functions that take `ollama_url` and pass it to `judge()`. Rename the parameter in each.

- [ ] **Step 4: Verify eval CLI help works**

Run: `cd /mnt/d/prg/plum && python -m projects.rp.eval --help`
Expected: Shows `--aiserver-url` instead of `--ollama-url`

- [ ] **Step 5: Commit**

```bash
git add projects/rp/eval/engine.py projects/rp/eval/cli.py projects/rp/eval/evaluators/
git commit -m "feat(eval): route judge calls through aiserver /chat with priority=5"
```

---

## Task 10: generate_examples.py — Route through aiserver

**Files:**
- Modify: `projects/rp/generate_examples.py`

- [ ] **Step 1: Update regenerate_response() to call aiserver /chat**

Replace the current `regenerate_response()` function:

```python
async def regenerate_response(
    client: httpx.AsyncClient,
    aiserver_url: str,
    model: str,
    system_prompt: str,
    context_msgs: list[dict],
    user_message: str,
) -> str | None:
    """Send the user message + card context to aiserver and get a regenerated response."""
    messages = [{"role": "system", "content": system_prompt}]
    for msg in context_msgs:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    resp = await client.post(
        f"{aiserver_url}/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "priority": 5,
        },
        timeout=600.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"aiserver {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"aiserver error: {data['error']}")
    return data["message"]["content"]
```

- [ ] **Step 2: Update CLI args and main()**

Change `--ollama-url` to `--aiserver-url` with default `http://localhost:8080`:

```python
    parser.add_argument(
        "--aiserver-url",
        default=os.environ.get("AISERVER_URL", "http://localhost:8080"),
    )
```

Keep `--ollama-url` as a hidden alias that maps to the same dest for backwards compatibility? No — YAGNI, just rename it.

Update `embed_text()` — this still calls Ollama directly (excluded from queue per spec). Add a separate `--ollama-url` arg just for embeddings:

```python
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        help="Ollama URL for embedding calls (not routed through queue)",
    )
```

Update `main()`: use `args.aiserver_url` for `regenerate_response()` and `args.ollama_url` for `embed_text()`. The warmup request should go through aiserver too.

- [ ] **Step 3: Verify CLI help works**

Run: `cd /mnt/d/prg/plum && python projects/rp/generate_examples.py --help`
Expected: Shows both `--aiserver-url` and `--ollama-url`

- [ ] **Step 4: Commit**

```bash
git add projects/rp/generate_examples.py
git commit -m "feat(generate-examples): route regeneration through aiserver /chat with priority=5"
```

---

## Task 11: Integration test

**Files:**
- Modify: `projects/aiserver/tests/test_inference_queue.py`

- [ ] **Step 1: Add end-to-end test with FastAPI TestClient**

Append to `projects/aiserver/tests/test_inference_queue.py`:

```python
import json as json_mod
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_generate_endpoint_uses_queue():
    """The /generate endpoint should route through the queue."""
    from fastapi.testclient import TestClient

    # Patch OllamaClient methods used during startup
    with patch("ollama.OllamaClient") as MockOllama:
        mock = MockOllama.return_value
        mock.is_available = AsyncMock(return_value=True)
        mock.list_models_detail = AsyncMock(return_value=[])

        chunks = [
            {"token": "hi", "thinking": False, "done": False},
            {"token": "", "done": True, "total_tokens": 1, "tokens_per_second": 5.0},
        ]

        async def fake_generate_stream(model, prompt, system=None, options=None):
            for c in chunks:
                yield c

        mock.generate_stream = fake_generate_stream

        import main
        main.ollama = mock

        # Need to set up queue in app.state
        from inference_queue import InferenceQueue  # not 'queue' — avoids shadowing stdlib
        q = InferenceQueue(mock, max_depth=10)
        await q.start()
        main.app.state.queue = q

        with TestClient(main.app, raise_server_exceptions=False) as client:
            resp = client.post("/generate", json={"prompt": "test", "priority": 3})
            assert resp.status_code == 200
            lines = [l for l in resp.text.strip().split("\n") if l]
            parsed = [json_mod.loads(l) for l in lines]

            # Should contain status messages and tokens
            has_started = any(p.get("status") == "started" for p in parsed)
            has_token = any(p.get("token") == "hi" for p in parsed)
            has_done = any(p.get("done") for p in parsed)
            assert has_started
            assert has_token
            assert has_done

        await q.stop()
```

- [ ] **Step 2: Run all tests**

Run: `cd projects/aiserver && python -m pytest tests/test_inference_queue.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add projects/aiserver/tests/test_inference_queue.py
git commit -m "test(aiserver): add integration test for /generate through queue"
```

---

## Task 12: Final verification

- [ ] **Step 1: Run full test suite**

Run: `cd projects/aiserver && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Verify server starts clean**

Run: `cd projects/aiserver && timeout 5 python main.py 2>&1 || true`
Expected: No import errors, server binds to port

- [ ] **Step 3: Verify queue endpoint responds**

Run (with server running): `curl -s http://localhost:8080/queue | python -m json.tool`
Expected: `{"entries": [], "active": null, "total": 0}`

- [ ] **Step 4: Final commit with any cleanup**

```bash
git add -A && git commit -m "chore(aiserver): priority queue final cleanup"
```
