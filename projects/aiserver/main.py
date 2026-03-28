import asyncio
import importlib
import json
import subprocess
import sys
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import Config
from inference_queue import InferenceQueue, QueueFullError
from models import (
    ChatRequest,
    DefaultsResponse,
    GenerateRequest,
    HealthResponse,
    ModelInfo,
    StatsResponse,
)
from ollama import OllamaClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

config = Config()
ollama = OllamaClient(base_url=config.ollama_url)

# Server identity
_started_at = datetime.now(timezone.utc).isoformat()
try:
    _repo_root = Path(__file__).resolve().parent.parent
    _git_commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%h"], cwd=_repo_root, text=True
    ).strip()
    _git_subject = subprocess.check_output(
        ["git", "log", "-1", "--format=%s"], cwd=_repo_root, text=True
    ).strip()
except Exception:
    _git_commit = ""
    _git_subject = ""

# Stats tracking
request_log: deque[dict] = deque(maxlen=10000)
active_streams: int = 0
dashboard_clients: list[asyncio.Queue] = []


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


app = FastAPI(title="aiserver", lifespan=lifespan)


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


@app.get("/queue")
async def queue_status():
    queue: InferenceQueue = app.state.queue
    return queue.queue_snapshot()


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
    models = []
    if available:
        # Build reverse alias map: full_name -> alias
        reverse_aliases = {v: k for k, v in config.aliases.items()}
        for m in await ollama.list_models_detail():
            models.append(ModelInfo(
                alias=reverse_aliases.get(m["name"]),
                **m,
            ))
    return HealthResponse(
        status="ok" if available else "ollama_unavailable",
        ollama_connected=available,
        available_models=models,
        git_commit=_git_commit,
        git_subject=_git_subject,
        started_at=_started_at,
    )


@app.get("/.git-head")
async def git_head():
    """Return current repo HEAD commit hash (for staleness detection)."""
    try:
        head = subprocess.check_output(
            ["git", "log", "-1", "--format=%h"], cwd=_repo_root, text=True
        ).strip()
    except Exception:
        head = ""
    return {"commit": head}


@app.post("/restart")
async def restart():
    """Restart the server using restart.sh (kills this process, starts fresh)."""
    script = Path(__file__).parent / "restart.sh"
    if not script.exists():
        return {"ok": False, "message": "restart.sh not found"}
    # Launch restart.sh detached — it will kill us and start a new process
    subprocess.Popen(
        ["bash", str(script)],
        start_new_session=True,
        stdout=open("/tmp/aiserver-restart.log", "w"),
        stderr=subprocess.STDOUT,
    )
    return {"ok": True, "message": "Restarting..."}


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
    queue_depth = len(app.state.queue._entries) if hasattr(app.state, "queue") else 0
    return StatsResponse(
        total_requests=len(request_log),
        requests_last_hour=len(recent),
        avg_tokens_per_second=round(sum(tps_values) / len(tps_values), 1) if tps_values else 0,
        active_streams=active_streams,
        queue_depth=queue_depth,
    )


async def broadcast_event(event: dict):
    """Send event to all connected dashboard WebSocket clients."""
    for q in dashboard_clients:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
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


def load_plugins(app: FastAPI, ollama: OllamaClient):
    for plugin_cfg in config.plugins:
        name = plugin_cfg["name"]
        path = (Path(__file__).parent / plugin_cfg["path"]).resolve()
        sys.path.insert(0, str(path.parent))
        try:
            mod = importlib.import_module(name)
            mod.register(app, ollama, resolve_model=config.resolve_model)
        finally:
            sys.path.pop(0)


load_plugins(app, ollama)


# Static files (web UI) — mounted last so API routes take priority
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.host, port=config.port, reload=True)
