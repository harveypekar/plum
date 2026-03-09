# aiserver Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a FastAPI server wrapping Ollama for LLM inference, with model aliases, NDJSON streaming, a real-time dashboard, and a prompt playground.

**Architecture:** Thin proxy over Ollama's `/api/generate`. FastAPI for routing/validation, httpx for async Ollama communication, WebSocket for real-time dashboard updates. Vanilla HTML/JS frontend served as static files.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, httpx, Pydantic

---

### Task 1: Project Scaffold

**Files:**
- Create: `projects/aiserver/requirements.txt`
- Create: `projects/aiserver/config.json`

**Step 1: Create project directory and requirements**

```
projects/aiserver/requirements.txt
```

```txt
fastapi>=0.115.0
uvicorn>=0.34.0
httpx>=0.28.0
websockets>=14.0
```

**Step 2: Create config.json**

```
projects/aiserver/config.json
```

```json
{
  "ollama_url": "http://localhost:11434",
  "host": "0.0.0.0",
  "port": 8080,
  "default_model": "q8",
  "aliases": {
    "q06": "qwen3:0.6b",
    "q17": "qwen3:1.7b",
    "q4": "qwen3:4b",
    "q8": "qwen3:8b",
    "q25": "qwen2.5:7b-instruct-q3_K_M"
  },
  "default_options": {
    "temperature": 0.7,
    "num_predict": 1024,
    "top_p": 0.9,
    "top_k": 40,
    "think": false
  }
}
```

**Step 3: Create venv and install dependencies**

Run:
```bash
cd projects/aiserver
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Step 4: Commit**

```bash
git add projects/aiserver/requirements.txt projects/aiserver/config.json
git commit -m "feat(aiserver): scaffold project with dependencies and config"
```

---

### Task 2: Pydantic Models

**Files:**
- Create: `projects/aiserver/models.py`

**Step 1: Write the schemas**

```python
from pydantic import BaseModel


class GenerateOptions(BaseModel):
    temperature: float | None = None
    num_predict: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    think: bool | None = None


class GenerateRequest(BaseModel):
    prompt: str
    model: str | None = None
    system: str | None = None
    options: GenerateOptions | None = None


class DefaultsResponse(BaseModel):
    default_model: str
    aliases: dict[str, str]
    default_options: GenerateOptions


class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    available_models: list[str]


class StatsResponse(BaseModel):
    total_requests: int
    requests_last_hour: int
    avg_tokens_per_second: float
    active_streams: int
```

**Step 2: Commit**

```bash
git add projects/aiserver/models.py
git commit -m "feat(aiserver): add Pydantic request/response schemas"
```

---

### Task 3: Config Loader

**Files:**
- Create: `projects/aiserver/config.py`

**Step 1: Write config loader**

Loads `config.json`, resolves model aliases, merges per-request options with defaults.

```python
import json
from pathlib import Path
from models import GenerateOptions


CONFIG_PATH = Path(__file__).parent / "config.json"


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        with open(path) as f:
            raw = json.load(f)
        self.ollama_url: str = raw["ollama_url"]
        self.host: str = raw["host"]
        self.port: int = raw["port"]
        self.default_model: str = raw["default_model"]
        self.aliases: dict[str, str] = raw["aliases"]
        self.default_options = GenerateOptions(**raw["default_options"])

    def resolve_model(self, model: str | None) -> str:
        """Resolve alias to Ollama model name, or pass through raw name."""
        name = model or self.default_model
        return self.aliases.get(name, name)

    def merge_options(self, options: GenerateOptions | None) -> dict:
        """Merge per-request options over defaults. Returns dict for Ollama API."""
        defaults = self.default_options.model_dump(exclude_none=True)
        if options:
            overrides = options.model_dump(exclude_none=True)
            defaults.update(overrides)
        return defaults
```

**Step 2: Commit**

```bash
git add projects/aiserver/config.py
git commit -m "feat(aiserver): add config loader with alias resolution"
```

---

### Task 4: OllamaClient

**Files:**
- Create: `projects/aiserver/ollama.py`
- Reference: `projects/ts/main.py:288-350` (original implementation)

**Step 1: Write the async OllamaClient**

Extract from ts, replace `urllib.request` + thread with `httpx` async streaming.

```python
import httpx
import json
from typing import AsyncGenerator


class OllamaError(Exception):
    """Raised on Ollama connection or API errors."""
    pass


class OllamaClient:
    """Async client for Ollama's /api/generate endpoint."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def generate_stream(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream tokens from Ollama. Yields dicts with token/thinking/done keys.

        Each yielded dict:
          {"token": "...", "thinking": bool, "done": False}
          {"token": "", "done": True, "total_tokens": N, "tokens_per_second": F}
        """
        think = False
        ollama_options = {}
        if options:
            think = options.pop("think", False)
            ollama_options = {k: v for k, v in options.items() if v is not None}

        body: dict = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }
        if system:
            body["system"] = system
        if ollama_options:
            body["options"] = ollama_options
        if think:
            body["think"] = True

        total_tokens = 0
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/generate", json=body
                ) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        raise OllamaError(f"Ollama returned {resp.status_code}: {text.decode()}")
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)

                        thinking_text = data.get("thinking", "")
                        token_text = data.get("response", "")

                        if thinking_text:
                            total_tokens += 1
                            yield {"token": thinking_text, "thinking": True, "done": False}
                        if token_text:
                            total_tokens += 1
                            yield {"token": token_text, "thinking": False, "done": False}

                        if data.get("done"):
                            eval_count = data.get("eval_count", total_tokens)
                            eval_duration = data.get("eval_duration", 1)
                            tps = eval_count / (eval_duration / 1e9) if eval_duration else 0
                            yield {
                                "token": "",
                                "done": True,
                                "total_tokens": eval_count,
                                "tokens_per_second": round(tps, 1),
                            }
                            return
        except httpx.ConnectError:
            raise OllamaError(f"Cannot connect to Ollama at {self.base_url}")

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict | None = None,
    ) -> str:
        """Send prompt, return complete response (thinking tokens discarded)."""
        tokens = []
        async for chunk in self.generate_stream(model, prompt, system=system, options=options):
            if not chunk.get("thinking") and not chunk.get("done"):
                tokens.append(chunk["token"])
        return "".join(tokens)

    async def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except httpx.ConnectError:
            return False

    async def list_models(self) -> list[str]:
        """Return list of available model names from Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["name"] for m in data.get("models", [])]
        except httpx.ConnectError:
            pass
        return []

    @staticmethod
    def count_tokens(text: str) -> int:
        """Estimate token count (~4 chars per token)."""
        return len(text) // 4
```

**Step 2: Commit**

```bash
git add projects/aiserver/ollama.py
git commit -m "feat(aiserver): add async OllamaClient with httpx streaming"
```

---

### Task 5: FastAPI App — Core Endpoints

**Files:**
- Create: `projects/aiserver/main.py`

**Step 1: Write the FastAPI app with /generate, /defaults, /health, /stats**

```python
import asyncio
import json
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import Config
from models import (
    DefaultsResponse,
    GenerateOptions,
    GenerateRequest,
    HealthResponse,
    StatsResponse,
)
from ollama import OllamaClient, OllamaError


config = Config()
ollama = OllamaClient(base_url=config.ollama_url)

# Stats tracking
request_log: deque[dict] = deque(maxlen=10000)
active_streams: int = 0
dashboard_clients: list[asyncio.Queue] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="aiserver", lifespan=lifespan)


@app.post("/generate")
async def generate(req: GenerateRequest):
    global active_streams
    model = config.resolve_model(req.model)
    merged = config.merge_options(req.options)

    active_streams += 1
    start = time.time()

    async def stream():
        global active_streams
        total_tokens = 0
        try:
            async for chunk in ollama.generate_stream(
                model=model,
                prompt=req.prompt,
                system=req.system,
                options=merged.copy(),
            ):
                yield json.dumps(chunk) + "\n"
                if chunk.get("done"):
                    total_tokens = chunk.get("total_tokens", 0)
        except OllamaError as e:
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


@app.get("/defaults", response_model=DefaultsResponse)
async def defaults():
    return DefaultsResponse(
        default_model=config.default_model,
        aliases=config.aliases,
        default_options=config.default_options,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    available = await ollama.is_available()
    models = await ollama.list_models() if available else []
    return HealthResponse(
        status="ok" if available else "ollama_unavailable",
        ollama_connected=available,
        available_models=models,
    )


@app.get("/stats", response_model=StatsResponse)
async def stats():
    now = time.time()
    hour_ago = now - 3600
    recent = [r for r in request_log if r["timestamp"] > hour_ago]
    tps_values = [
        r["total_tokens"] / r["latency"]
        for r in recent
        if r["latency"] > 0 and r["total_tokens"] > 0
    ]
    return StatsResponse(
        total_requests=len(request_log),
        requests_last_hour=len(recent),
        avg_tokens_per_second=round(sum(tps_values) / len(tps_values), 1) if tps_values else 0,
        active_streams=active_streams,
    )


async def broadcast_event(event: dict):
    """Send event to all connected dashboard WebSocket clients."""
    for q in dashboard_clients:
        await q.put(event)


# Static files (web UI) — mounted last so API routes take priority
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.host, port=config.port, reload=True)
```

**Step 2: Verify the server starts**

Run:
```bash
cd projects/aiserver
source .venv/bin/activate
python main.py
```

Expected: Server starts on port 8080. `Ctrl+C` to stop.

**Step 3: Commit**

```bash
git add projects/aiserver/main.py
git commit -m "feat(aiserver): add FastAPI app with generate, defaults, health, stats"
```

---

### Task 6: WebSocket Dashboard Endpoint

**Files:**
- Modify: `projects/aiserver/main.py`

**Step 1: Add WebSocket endpoint**

Add the following to `main.py`, after the `broadcast_event` function and before the static files mount:

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue()
    dashboard_clients.append(queue)
    try:
        # Send initial stats
        s = await stats()
        await ws.send_json({"type": "stats", **s.model_dump()})

        # Send recent request log
        for entry in list(request_log)[-50:]:
            await ws.send_json({"type": "request_complete", **entry})

        # Stream events
        while True:
            event = await queue.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        dashboard_clients.remove(queue)
```

Also add a periodic stats broadcast in the lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async def stats_broadcaster():
        while True:
            await asyncio.sleep(5)
            s = await stats()
            event = {"type": "stats", **s.model_dump()}
            await broadcast_event(event)

    task = asyncio.create_task(stats_broadcaster())
    yield
    task.cancel()
```

**Step 2: Commit**

```bash
git add projects/aiserver/main.py
git commit -m "feat(aiserver): add WebSocket dashboard endpoint with stats broadcast"
```

---

### Task 7: Dashboard Web UI

**Files:**
- Create: `projects/aiserver/static/index.html`
- Create: `projects/aiserver/static/dashboard.js`

**Step 1: Create dashboard HTML**

`index.html` — single-page dashboard with sections for:
- Ollama status (green/red indicator)
- Available models list
- Aggregate stats (total requests, requests/hour, avg tokens/sec, active streams)
- Live request log table (scrolling, most recent at top)

Keep styling minimal and inline. Dark theme to match terminal aesthetics.

**Step 2: Create dashboard.js**

Connects to `ws://host/ws/dashboard`. Handles two event types:
- `stats` — updates the stats section
- `request_complete` — prepends a row to the request log table

**Step 3: Verify in browser**

Run the server, open `http://localhost:8080/static/index.html`. Dashboard should show stats and update when requests come in.

**Step 4: Commit**

```bash
git add projects/aiserver/static/index.html projects/aiserver/static/dashboard.js
git commit -m "feat(aiserver): add real-time dashboard web UI"
```

---

### Task 8: Playground Web UI

**Files:**
- Create: `projects/aiserver/static/playground.html`
- Create: `projects/aiserver/static/playground.js`

**Step 1: Create playground HTML**

Single-page prompt tester with:
- Model selector dropdown (fetched from `/defaults` on load)
- Parameter inputs: temperature, num_predict, top_p, top_k, think (checkbox)
- Prompt textarea
- "Generate" button
- Output area that renders streamed tokens live
- Thinking tokens shown in a collapsible section (dimmed/italic)

Same dark theme as dashboard.

**Step 2: Create playground.js**

On submit:
1. Build request body from form inputs
2. `fetch("/generate", { method: "POST", body: JSON.stringify(req) })`
3. Read NDJSON response line by line using `response.body.getReader()`
4. Append each token to the output area
5. Show final stats (total_tokens, tokens_per_second) when `done: true`

On page load:
1. Fetch `/defaults` to populate model dropdown and parameter defaults

**Step 3: Verify in browser**

Run the server with Ollama active. Open playground, select a model, type a prompt, hit Generate. Tokens should stream in.

**Step 4: Commit**

```bash
git add projects/aiserver/static/playground.html projects/aiserver/static/playground.js
git commit -m "feat(aiserver): add prompt playground web UI"
```

---

### Task 9: Update ts Project to Import from aiserver

**Files:**
- Modify: `projects/ts/main.py`

**Step 1: Replace inline OllamaClient with import**

In `projects/ts/main.py`:

1. Remove the `OllamaClient` class (lines 288-350)
2. Remove the `import urllib.request` (no longer needed for Ollama)
3. Add import at the top:
   ```python
   import sys
   sys.path.insert(0, str(Path(__file__).parent.parent / "aiserver"))
   from ollama import OllamaClient
   ```
4. Update all call sites — the new client takes `model` as a parameter to `generate_stream`/`generate` instead of `__init__`. Find all usages and adjust.

**Step 2: Keep MODEL_MAP in ts**

The ts project still needs its own model map for its settings UI. The `MODEL_MAP` dict (lines 353-362) stays in ts, but is now only used to resolve the model name before passing it to `OllamaClient.generate_stream(model=...)`.

**Step 3: Verify ts still works**

Run:
```bash
cd projects/ts
python main.py
```

Expected: Game starts normally, AI player responds using the aiserver OllamaClient.

**Step 4: Commit**

```bash
git add projects/ts/main.py
git commit -m "refactor(ts): use OllamaClient from aiserver"
```

---

### Task 10: Integration Testing

**Files:**
- Create: `projects/aiserver/test_server.py`

**Step 1: Write integration tests**

Tests that verify the server works end-to-end (require Ollama running):

```python
import httpx
import pytest
import json


BASE = "http://localhost:8080"


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "ollama_connected" in data


@pytest.mark.asyncio
async def test_defaults():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert "default_model" in data
        assert "aliases" in data
        assert "default_options" in data


@pytest.mark.asyncio
async def test_generate_stream():
    async with httpx.AsyncClient(timeout=30.0) as client:
        req = {"prompt": "Say hello in one word.", "model": "q06"}
        async with client.stream("POST", f"{BASE}/generate", json=req) as resp:
            assert resp.status_code == 200
            chunks = []
            async for line in resp.aiter_lines():
                if line:
                    chunks.append(json.loads(line))
            assert len(chunks) > 0
            assert chunks[-1]["done"] is True


@pytest.mark.asyncio
async def test_stats():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert "active_streams" in data
```

**Step 2: Run tests**

Run (with server and Ollama running):
```bash
cd projects/aiserver
source .venv/bin/activate
pip install pytest pytest-asyncio
pytest test_server.py -v
```

Expected: All tests pass.

**Step 3: Commit**

```bash
git add projects/aiserver/test_server.py
git commit -m "test(aiserver): add integration tests for all endpoints"
```

---

### Task 11: Final Cleanup and PR

**Step 1: Verify everything works together**

1. Start Ollama: `ollama serve`
2. Start aiserver: `cd projects/aiserver && python main.py`
3. Open dashboard: `http://localhost:8080/static/index.html`
4. Open playground: `http://localhost:8080/static/playground.html`
5. Send a test prompt in playground, verify dashboard shows the request

**Step 2: Push and create PR**

```bash
git push -u origin aiserver-design
gh pr create --title "feat(aiserver): add LLM inference server" \
  --body "Closes design from docs/plans/2026-03-09-aiserver-design.md"
```
