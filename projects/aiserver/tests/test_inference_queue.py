"""Tests for priority queue and related models."""

import asyncio
import sys
from pathlib import Path

import pytest

# Allow imports from aiserver directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inference_queue import InferenceQueue, QueueFullError
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


# --- Queue behavior tests ---


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
    served = []

    class TrackingOllama(FakeOllamaClient):
        async def generate_stream(self, model, prompt, system=None, options=None):
            served.append(prompt)
            async for chunk in super().generate_stream(model, prompt, system, options):
                yield chunk

    fake = TrackingOllama(delay=0.05)
    q = InferenceQueue(fake, max_depth=10)
    await q.start()

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
async def test_chat_mode_flows_through():
    """Chat mode (messages instead of prompt) should work through the queue."""
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
async def test_queue_full_raises():
    """Exceeding max_depth should raise an error."""
    # Very slow fake so nothing completes during the test
    fake = FakeOllamaClient(delay=1.0)
    q = InferenceQueue(fake, max_depth=1)
    await q.start()

    # req0 starts processing (popped from _entries), req1 waits in _entries (1 entry = at limit)
    t1 = asyncio.create_task(
        q.enqueue_and_collect(priority=5, mode="generate", model="test",
                              prompt="req0", system=None, options=None)
    )
    await asyncio.sleep(0.05)
    t2 = asyncio.create_task(
        q.enqueue_and_collect(priority=5, mode="generate", model="test",
                              prompt="req1", system=None, options=None)
    )
    await asyncio.sleep(0.05)

    # 3rd should fail — _entries is full
    with pytest.raises(QueueFullError):
        async for _ in q.enqueue(priority=5, mode="generate", model="test",
                                 prompt="overflow", system=None, options=None):
            pass

    t1.cancel()
    t2.cancel()
    await q.stop()
