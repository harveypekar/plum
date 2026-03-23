---
paths:
  - "projects/front/**"
---

# Front — Unified Dashboard

FastAPI plugin for aiserver. Service monitoring grid + VS Code-style dockable panel layout.

## Commands

```bash
# Run (via aiserver)
cd projects/aiserver && source .venv/bin/activate
python main.py
# Dashboard at http://localhost:8080/front/
```

## Architecture

- Plugin: `__init__.py` registers routes on aiserver at startup
- `api.py` — Service status (pgrep/HTTP health), log retrieval, restart endpoints
- `index.html` — Two-tab layout (Master monitoring + RP dockable panels)
- `app.js` — Main app (~512 lines): polling, dock system, service control
- `styles.css` — Monospace terminal theme (green on black, ~320 lines)

## Key APIs

- `GET /api/services/{service}/status` — Running check
- `GET /api/logs/{service}` — Tail log lines
- `POST /api/services/{service}/restart` — Run restart script

## Conventions

- **NEVER use sidebars** — all UI must use the dockable panel system (north/south/west/east slots)
- Panels defined in `PANELS` object with render functions returning DOM elements
- Layout state persisted to localStorage (`plum-dock-state`)
- Separate `app` object (polling/services) and `dock` object (layout/drag-drop/resize)
- `el()` helper for safe DOM creation (no innerHTML)
- Polling: status every 2s, logs every 3s
- Vanilla JS only — no frameworks, no build step
