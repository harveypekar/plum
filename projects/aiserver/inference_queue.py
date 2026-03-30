"""Priority queue for serializing LLM inference requests.

Wraps OllamaClient to ensure only one request runs at a time, with
priority ordering and preemption support for interactive requests.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator


# Priority levels — lower number = higher priority (served first).
# Interactive requests preempt bulk work via _maybe_preempt().
PRIORITY_INTERACTIVE = 0   # UI chat: /message, /continue, /regenerate, /auto-reply
PRIORITY_BACKGROUND = 5    # card generation, scene state, summaries
PRIORITY_EVAL = 10         # eval judge calls — lowest, always yields to real usage


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

        now = time.time()
        entry = QueueEntry(
            sort_key=(priority, now),
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
            created_at=now,
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
