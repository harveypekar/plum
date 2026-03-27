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
    def __init__(self, ollama: OllamaClient)
    async def start()       # launch worker coroutine
    async def stop()        # drain and shut down

    async def enqueue(priority, model, ...) -> AsyncGenerator[dict, None]
        # yields status messages, then tokens, then done

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
2. Set the running entry's `cancel_event`
3. Worker catches the cancellation, sends `{"status": "preempted"}` to the entry's `result_stream`
4. Re-inserts the preempted entry at the front of its priority tier (with a flag to discard partial output on restart)
5. Worker immediately picks up the new high-priority entry

Preemption only triggers when the new entry has a strictly lower priority number than the running entry. Same-priority entries never preempt each other.

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

**Position updates** are sent only when position changes (not polled). Status messages have no `token` key; token messages have no `status` key. Existing parsers that only look for `token`/`done` work unchanged.

## Error Handling

**Caller disconnects mid-queue:** Queue removes the entry. If it was the active one, the Ollama stream gets cancelled and the worker moves to the next entry.

**Ollama errors:** `OllamaError` gets caught by the worker. Sends `{"error": "...", "done": true}` to the entry's result stream. Worker moves to the next entry. Failed requests are not retried.

**Preemption race conditions:** If the current generation finishes naturally before the cancel takes effect, the cancel is a no-op and the high-priority request runs next. Two same-priority requests arriving simultaneously are ordered by `created_at` (FIFO).

**Queue depth limit:** Configurable max (default 100). Beyond that, return HTTP 503 with `{"error": "queue_full"}`.

**Starvation:** Not addressed for now. Interactive requests are infrequent (human typing speed). Low-priority batch runs process steadily, occasionally paused for an interactive request.

## File Changes

| File | Change |
|---|---|
| `projects/aiserver/queue.py` | **New.** `InferenceQueue` class — priority list, worker loop, preemption, `enqueue()` async generator |
| `projects/aiserver/models.py` | Add `priority: int = 0` to `GenerateRequest`. New `ChatRequest` model. New `QueueStatusResponse` model |
| `projects/aiserver/main.py` | Create queue at startup. Wire `/generate` through queue. Add `POST /chat` and `GET /queue` endpoints. Broadcast queue events to dashboard WebSocket |
| `projects/rp/routes.py` | ~7 call sites: swap `_ollama.chat_stream()`/`_ollama.generate()` for `_queue.enqueue(priority=0, ...)` |
| `projects/rp/__init__.py` | Accept queue from `app.state` in `register()` |
| `projects/rp/eval/engine.py` | `judge()` calls aiserver `/chat` with `priority=5` instead of Ollama directly |
| `projects/rp/eval/cli.py` | Route through aiserver |
| `projects/rp/generate_examples.py` | `regenerate_response()` and `embed_text()` call aiserver instead of Ollama directly |
| `projects/aiserver/config.json` | Optional: `queue_max_depth` setting (default 100) |

**Files not changed:** `ollama.py` (stays pure), `config.py`, RP frontend `static/app.js` (existing NDJSON parser ignores unknown fields).
