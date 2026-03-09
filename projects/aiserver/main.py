import asyncio
import importlib
import json
import sys
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import Config
from models import (
    DefaultsResponse,
    GenerateOptions,
    GenerateRequest,
    HealthResponse,
    ModelInfo,
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
    async def stats_broadcaster():
        while True:
            await asyncio.sleep(5)
            s = await stats()
            event = {"type": "stats", **s.model_dump()}
            await broadcast_event(event)

    task = asyncio.create_task(stats_broadcaster())
    yield
    task.cancel()


app = FastAPI(title="aiserver", lifespan=lifespan)


@app.post("/generate")
async def generate(req: GenerateRequest):
    model = config.resolve_model(req.model)
    merged = config.merge_options(req.options)
    start = time.time()

    async def stream():
        global active_streams
        active_streams += 1
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
        mod = importlib.import_module(name)
        mod.register(app, ollama)
        sys.path.pop(0)


load_plugins(app, ollama)


# Static files (web UI) — mounted last so API routes take priority
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.host, port=config.port, reload=True)
