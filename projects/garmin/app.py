"""FastAPI dev browser for fetched Garmin data. Not a consumer UI — exposes
every field of every fetched file, unmodified, for debugging."""
import json
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from sync_lock import LockHeldError, sync_lock

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "garmin"
STATUS_PATH = DATA_DIR / "status.json"
LOCK_PATH = DATA_DIR / ".sync.lock"
FETCH_SCRIPT = BASE_DIR / "fetch_garmin.py"

app = FastAPI()


def read_status() -> dict:
    empty = {"success": None, "started_at": None, "finished_at": None, "counts": {}, "error": None}
    if not STATUS_PATH.exists():
        return empty
    try:
        with open(STATUS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {**empty, "success": False, "error": f"status.json unreadable: {e}"}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    status = read_status()
    if status["started_at"] is None and not status["error"]:
        summary = "<p>No sync has run yet.</p>"
    else:
        ok = "OK" if status["success"] else "FAILED"
        counts_html = "".join(f"<li>{k}: {v}</li>" for k, v in status.get("counts", {}).items())
        error_html = f"<p style='color:red'>{status['error']}</p>" if status.get("error") else ""
        summary = (
            f"<p>Last sync started: {status['started_at']} — {ok}</p>"
            f"<ul>{counts_html}</ul>"
            f"{error_html}"
        )
    html = f"""<!doctype html>
<html><head><title>Garmin Data Source</title></head>
<body>
<h1>Garmin Data Source</h1>
{summary}
<form method="post" action="/sync"><button type="submit">Sync now</button></form>
<p><a href="/browse/">Browse data</a></p>
</body></html>"""
    return HTMLResponse(html)


@app.post("/sync")
def trigger_sync():
    try:
        with sync_lock(LOCK_PATH):
            pass  # probe: lock is free, release it immediately before spawning
    except LockHeldError:
        return JSONResponse({"status": "already_running"}, status_code=409)

    subprocess.Popen([sys.executable, str(FETCH_SCRIPT)])
    return JSONResponse({"status": "started"})


def _safe_resolve(rel_path: str) -> Path:
    target = (DATA_DIR / rel_path).resolve()
    try:
        target.relative_to(DATA_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    return target


@app.get("/browse/{path:path}")
def browse(path: str = ""):
    target = _safe_resolve(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Not found")
    if target.is_dir():
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
        return JSONResponse({"path": path, "entries": entries})
    with open(target, encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data)
