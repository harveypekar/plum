# aiserver Priority Queue

## Problem

aiserver proxies Ollama for LLM inference, but has no request scheduling. Bulk workloads (eval runs, fewshot generation) and interactive UI chat compete for the single GPU without coordination. Bulk callers (eval, generate_examples) bypass aiserver entirely, talking to Ollama directly. There is no way to prioritize interactive requests over batch work.

## Goals

- Serialize all LLM requests through a single priority queue in aiserver
- Interactive (UI) requests preempt running batch requests for low latency
- Batch callers see transparent retry after preemption (no special handling needed)
- Queue status visible to callers via NDJSON stream and to the dashboard via WebSocket
- Route eval and generate_examples through aiserver instead of direct Ollama calls

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Queue location | Inside aiserver (Approach B: separate `queue.py` module wrapping OllamaClient) | Central gateway; OllamaClient stays pure; queue logic is isolated and testable |
| Priority signaling | Explicit `priority` field on request (numeric 0-9, lower = higher) | Simple, flexible, caller decides |
| Preemption | Yes — cancel running low-priority request when higher-priority arrives | Snappy interactive response; batch callers don't need to know |
| Preempted request handling | Silent retry — queue automatically requeues and restarts from scratch | Transparent to batch callers; no retry logic needed in clients |
| Persistence | In-memory only (no Postgres/Redis) | Queue is hot and ephemeral; durability has no value since Ollama streams die on restart anyway |
| Status reporting | Via NDJSON stream (queued/started/preempted messages) + dashboard WebSocket | Callers can show progress; existing parsers ignore unknown fields |

## Architecture

### QueueEntry

```
QueueEntry:
    id: str                              # uuid4
    priority: int                        # 0-9, lower = higher priority
    request: dict                        # model, prompt/messages, options, endpoint type
    result_stream: asyncio.Queue[dict]   # tokens/status flow back to caller
    cancel_event: asyncio.Event          # set to signal preemption
    created_at: float                    # time.time(), for FIFO within same priority
```

### InferenceQueue

```python
class InferenceQueue:
    def __init__(self, ollama: OllamaClient, max_depth: int = 100)
    async def start()       # launch worker coroutine
    async def stop()        # drain and shut down

    async def enqueue(priority, model, ...) -> AsyncGenerator[dict, None]
        # yields status messages, then tokens, then done

    async def enqueue_and_collect(priority, model, ...) -> str
        # convenience: drains the generator, returns concatenated text
        # discards status messages, collects only token text
        # used by non-streaming callers (RP generate(), eval judge())

    def queue_snapshot() -> list[dict]   # for /queue endpoint & dashboard
```

**Priority list:** A sorted list (not `asyncio.PriorityQueue`) protected by an `asyncio.Lock`, sorted by `(priority, created_at)`. Supports insert, reorder, and position inspection.

**Worker loop:** A single long-running coroutine that:

1. Pops the highest-priority entry from the list
2. Sends `{"status": "started"}` to the entry's `result_stream`
3. Streams tokens from OllamaClient into `result_stream`
4. On completion, pops the next entry
5. If idle, awaits an `asyncio.Event` that gets set on enqueue

**Preemption flow:**

1. New entry arrives with strictly higher priority (lower number) than the currently running entry
2. Worker runs the OllamaClient stream iteration inside an `asyncio.Task`. Preemption calls `task.cancel()` on this task.
3. Worker catches `asyncio.CancelledError`, closes the httpx stream, and sends `{"status": "preempted"}` to the entry's `result_stream`
4. Re-inserts the preempted entry at the front of its priority tier (with a flag to discard partial output on restart)
5. Worker immediately picks up the new high-priority entry

Preemption only triggers when the new entry has a strictly lower priority number than the running entry. Same-priority entries never preempt each other.

**Cancellation mechanism:** The worker wraps each OllamaClient stream call in an `asyncio.Task`. This is necessary because `aiter_lines()` blocks on the next chunk — a simple `cancel_event` check between chunks would only fire after the next chunk arrives, which could be seconds. Cancelling the task interrupts the `aiter_lines()` await immediately. The `async with` block in OllamaClient ensures the httpx stream is properly closed on cancellation.

## NDJSON Stream Protocol

### Normal flow

```
← {"status": "queued", "position": 3, "queue_id": "abc123"}
← {"status": "queued", "position": 1, "queue_id": "abc123"}
← {"status": "started"}
← {"token": "Once", "thinking": false, "done": false}
← {"token": " upon", "thinking": false, "done": false}
← ...
← {"token": "", "done": true, "total_tokens": 142, "tokens_per_second": 28.3}
```

### Preempted flow (seen by the preempted caller)

```
← {"status": "queued", "position": 0, "queue_id": "abc123"}
← {"status": "started"}
← {"token": "Once", "thinking": false, "done": false}
← {"token": " upon", "thinking": false, "done": false}
← {"status": "preempted"}
← {"status": "queued", "position": 0, "queue_id": "abc123"}
← {"status": "started"}
← {"token": "Once", "thinking": false, "done": false}
← ...
← {"token": "", "done": true, ...}
```

**Position updates** are sent only when position changes (not polled). Status messages have no `token` key; token messages have no `status` key.

### Preemption and streaming callers

Preemption has different implications depending on the caller type:

**HTTP streaming callers (external — eval, generate_examples via `/chat` or `/generate`):** These callers use `enqueue_and_collect()` or consume the NDJSON stream and accumulate text. On preemption, `enqueue_and_collect()` discards accumulated tokens internally and restarts cleanly — fully transparent. Raw NDJSON consumers see the `{"status": "preempted"}` message and must discard their accumulated text buffer before the restart tokens arrive.

**In-process streaming callers (RP plugin routes):** The RP plugin streams tokens directly to the browser via `StreamingResponse`. Bytes already sent to the browser cannot be unsent. On receiving `{"status": "preempted"}`, the route must yield a `{"status": "preempted"}` chunk to the frontend. The RP frontend (`app.js`) must handle this by clearing the current message content and re-rendering from the restarted tokens. **This is a required frontend change** — `app.js` needs a preemption handler.

**Non-streaming callers (RP `_ollama.generate()` sites, eval `judge()`):** Use `enqueue_and_collect()` which handles preemption transparently. No caller changes needed.

## Error Handling

**Caller disconnects mid-queue:** Queue removes the entry. If it was the active one, the Ollama stream gets cancelled and the worker moves to the next entry.

**Ollama errors:** `OllamaError` gets caught by the worker. Sends `{"error": "...", "done": true}` to the entry's result stream. Worker moves to the next entry. Failed requests are not retried.

**Preemption race conditions:** If the current generation finishes naturally before the cancel takes effect, the cancel is a no-op and the high-priority request runs next. Two same-priority requests arriving simultaneously are ordered by `created_at` (FIFO).

**Queue depth limit:** Configurable max (default 100). Beyond that, return HTTP 503 with `{"error": "queue_full"}`.

**Starvation:** Not addressed for now. Interactive requests are infrequent (human typing speed). Low-priority batch runs process steadily, occasionally paused for an interactive request.

## ChatRequest Schema

```
ChatRequest:
    messages: list[dict]          # [{"role": "system", "content": "..."}, ...]
    model: str | None = None      # alias or full name; None = default model
    options: GenerateOptions | None = None
    stop: list[str] | None = None
    stream: bool = True           # false = return single JSON response
    priority: int = 5             # default to batch priority for /chat
```

The `/chat` endpoint mirrors Ollama's `/api/chat` interface but routes through the queue. It supports both streaming (NDJSON, default) and non-streaming (`stream: false` returns a single JSON response after collecting all tokens via `enqueue_and_collect()`). Like `/generate`, the endpoint resolves model aliases and merges default options before enqueueing.

## Embedding Calls

Embedding calls (`/api/embed`) are **excluded from the queue**. They run on a different Ollama execution path (no autoregressive decoding), complete in milliseconds, and don't contend with generation for GPU compute in the same way. `generate_examples.py`'s `embed_text()` continues to call Ollama directly (or a thin passthrough `/embed` endpoint on aiserver can be added later if centralization is desired).

## Plugin Queue Access

`main.py` sets `app.state.queue = InferenceQueue(...)` before calling `load_plugins()`. The plugin loader signature does not change. Plugins access the queue via `app.state.queue` inside their `register()` function. Specifically:

- `rp/__init__.py:register(app, ollama, resolve_model)` — reads `app.state.queue` and passes it to `routes.setup()`
- `routes.setup()` gains a `queue` parameter and stores it as a module-level `_queue` (same pattern as the existing `_ollama`)

## File Changes

| File | Change |
|---|---|
| `projects/aiserver/queue.py` | **New.** `InferenceQueue` class — priority list, worker loop, preemption, `enqueue()` and `enqueue_and_collect()` |
| `projects/aiserver/models.py` | Add `priority: int = 0` to `GenerateRequest`. New `ChatRequest` model. New `QueueStatusResponse` model |
| `projects/aiserver/main.py` | Set `app.state.queue` before `load_plugins()`. Wire `/generate` through queue. Add `POST /chat` and `GET /queue` endpoints. Broadcast queue events to dashboard WebSocket |
| `projects/aiserver/config.py` | Add `queue_max_depth: int` field, loaded from `config.json` (default 100) |
| `projects/aiserver/config.json` | Add `queue_max_depth` setting (default 100) |
| `projects/rp/routes.py` | 8 call sites (4x `_ollama.generate()`, 4x `_ollama.chat_stream()`) swap to `_queue.enqueue(priority=0, ...)` / `_queue.enqueue_and_collect(priority=0, ...)`. Streaming routes forward `{"status": "preempted"}` to the frontend. |
| `projects/rp/__init__.py` | `register()` reads `app.state.queue`, passes to `routes.setup()` |
| `projects/rp/static/app.js` | Handle `{"status": "preempted"}` in NDJSON stream: clear current message content, re-render from restarted tokens |
| `projects/rp/eval/engine.py` | `judge()` calls aiserver `/chat` with `priority=5, stream=false` instead of Ollama directly. Replace the per-call `httpx.AsyncClient` with an aiserver URL parameter. |
| `projects/rp/eval/cli.py` | Route through aiserver; pass aiserver URL instead of Ollama URL |
| `projects/rp/generate_examples.py` | `regenerate_response()` calls aiserver `/chat` with `priority=5, stream=false`. The shared `httpx.AsyncClient` is reused but pointed at aiserver instead of Ollama. `embed_text()` continues to call Ollama directly (excluded from queue). |

**Files not changed:** `ollama.py` (stays pure, queue wraps it).
