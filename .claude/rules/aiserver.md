---
paths:
  - "projects/aiserver/**"
---

# aiserver — LLM Inference Gateway

FastAPI server proxying Ollama for streaming LLM inference with model aliasing, stats, and a plugin system.

## Commands

```bash
cd projects/aiserver
source .venv/bin/activate
python main.py            # Starts on http://127.0.0.1:8080

bash restart.sh           # Kill + restart with DB backup
bash status.sh            # Health check (process, HTTP, Ollama)

pytest test_server.py     # Integration tests (needs running server)
pytest tests/             # Unit tests (mocked)
```

## Architecture

- `main.py` — FastAPI app, routes, WebSocket dashboard, plugin loader, stats broadcaster
- `config.py` — JSON config loader, model alias resolution, WSL2 gateway detection
- `config.json` — Ollama URL, host/port, model aliases, default options, plugin list
- `models.py` — Pydantic schemas (GenerateRequest, HealthResponse, etc.)
- `ollama.py` — OllamaClient: async wrapper for `/api/generate` and `/api/chat`
- `static/` — Dashboard and playground web UIs

## Key APIs

- `POST /generate` — Stream tokens (NDJSON)
- `GET /health` — Server status + models
- `GET /defaults` — Model aliases & options
- `GET /stats` — Request stats (hourly, throughput, active streams)
- `WS /ws/dashboard` — Real-time stats events

## Conventions

- Model aliasing: short names (e.g. "q8") resolved via config to full Ollama model names
- Option merging: request options merge over defaults; None values filtered
- NDJSON streaming: JSON + newline per chunk
- Plugin system: dynamic module loading at startup; plugins get `(app, ollama, resolve_model)`
- Stats: 5-second broadcast interval to WebSocket clients; deque of 10k request records
- Thinking support: optional "think" flag for extended reasoning
