# Shared Services Architecture Design

**Created:** 2026-03-01
**Issue:** #12

## Purpose

Define a shared architecture for Plum services — data providers with HTTP JSON APIs that sit between raw scripts and consumers (Claude MCPs, HTML dashboards, other scripts).

## Decisions

- Services run **locally (WSL2) or on VPS**, chosen per service
- **HTTP JSON API** is the primary interface; Claude MCPs are optional wrappers on top
- **Python + shared framework** (thin base class, not a pip package)
- **Simple bash scripts** for process management (start/stop), no watchdog for now
- **Cache strategy chosen per service** — framework defines no cache interface; each service picks JSON, SQLite, or whatever fits
- **Logs in `./logs/`** (project-local), not `~/.logs/plum/`
- **No auth for now** — base class has a hook point for future per-service auth (some services open, some closed)

## Directory Layout

```
services/
├── __init__.py
├── base.py              # PlumService base class
├── config.py            # .env loading, service config helpers
├── logging.py           # Python logging → ./logs/<service>/
├── claude_service.py    # ClaudeService(PlumService)
├── garmin_service.py    # GarminService(PlumService)
├── requirements.txt     # flask, python-dotenv, etc.
└── plum_service.py      # CLI entrypoint

scripts/services/
├── start-service.sh     # Start a service (background, PID file)
├── stop-service.sh      # Stop a service by name
└── service-status.sh    # Check running services

logs/
├── claude-service/      # Per-service log dirs (YYYY-MM-DD.log)
├── garmin-service/
└── pids/                # PID files
```

Framework files (`base.py`, `config.py`, `logging.py`) sit alongside service files. No nesting.

## PlumService Base Class

```python
class PlumService:
    name: str               # e.g., "claude", "garmin"
    default_port: int       # Each service has a default, 927x range
    service_type: str       # "static" or "dynamic"

    # Provided by base class:
    def run(port=None)      # Start the Flask app
    def health()            # GET /health → {"status": "ok", "service": name, "uptime": ...}

    # Overridden by subclasses:
    def register_routes(app)  # Add Flask routes
    def on_start()            # Optional: initialization, cache warm-up
    def on_stop()             # Optional: cleanup
```

### What the base class provides

1. **Flask HTTP server** with automatic `/health` endpoint
2. **Logging** — Python logging routed to `./logs/<service-name>/YYYY-MM-DD.log`
3. **Config** — loads `.env` from project root, service-specific vars use `<SERVICE>_<SETTING>` convention
4. **Rate limiting** — configurable per service, default 60 requests/min per IP
5. **Lifecycle hooks** — `on_start()` and `on_stop()` for subclass initialization/cleanup
6. **Localhost binding** by default (`127.0.0.1`). VPS services explicitly bind `0.0.0.0`

### Service types

- **Static** — reads from local filesystem only. No cache refresh, no external data sources.
- **Dynamic** — maintains a cache filled from an external source. Cache backend (JSON file, SQLite, etc.) chosen by each service.

## CLI Entrypoint

```
python services/plum_service.py <service-name> [--port PORT] [--host HOST]
```

Discovers services by convention: `<name>_service.py` must contain a class ending in `Service` that subclasses `PlumService`.

## Process Management

**start-service.sh <name> [--port N]:**
- Activates the shared venv
- Runs `plum_service.py <name>` in background
- Writes PID to `./logs/pids/<name>.pid`
- Sources logging.sh for script-level logging

**stop-service.sh <name>:**
- Reads PID file, sends SIGTERM
- Cleans up PID file

**service-status.sh [name]:**
- Lists running services (checks PID files against running processes)
- Optional: check a single service

## Config & Security

- `.env` in project root, loaded at startup (same as existing scripts)
- Service-specific env vars: `GARMIN_USERNAME`, `CLAUDE_API_KEY`, `GARMIN_CACHE_TTL`, etc.
- Secrets never committed (existing `validate-secrets.py` pre-commit hook)
- Rate limiting included in base class
- No authentication for now; base class has a hook point for future per-service auth middleware

## Port Convention

| Service | Default Port |
|---------|-------------|
| claude  | 9270        |
| garmin  | 9271        |
| (next)  | 9272        |

Configurable via `--port` flag.

## Concrete Services (Planned)

### Claude Service (#13)
- **Type:** Dynamic
- **Endpoints:** `get_usage()` → session/daily/weekly/monthly tokens vs limits; `get_usage_guess(work)` → estimated tokens for a task
- **Behavior:** Periodically checks usage. Below 10% remaining per day left in week → block new sessions. Below 5% → halt everything.

### Garmin Connect Service (#14)
- **Type:** Dynamic
- **Cache:** Updated from Garmin Connect API, stores all activities
- **Endpoints:** JSON API for querying activities
- **Bonus:** Quick HTML file for browsing data

## Dependencies

```
flask
python-dotenv
```

Minimal. Additional per-service dependencies added to the same `requirements.txt`.
