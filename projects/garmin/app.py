"""FastAPI dev dashboard for fetched Garmin data. Not a consumer UI — shows
the last 10 days of fetched data, largely unmodified, for debugging."""
import html
import json
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from sync_lock import LockHeldError, sync_lock

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "garmin"
STATUS_PATH = DATA_DIR / "status.json"
LOCK_PATH = DATA_DIR / ".sync.lock"
FETCH_SCRIPT = BASE_DIR / "fetch_garmin.py"

RECENT_DAYS_LIMIT = 10
# Some daily endpoints (e.g. heart_rates.json) hold thousands of samples;
# truncating lists keeps the summary readable without hiding field shape.
MAX_LIST_PREVIEW = 3

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


def _summarize(value):
    """Shrink a JSON value for display: keeps every key and a few real
    values so field shape stays visible, but truncates long lists."""
    if isinstance(value, dict):
        return {k: _summarize(v) for k, v in value.items()}
    if isinstance(value, list):
        head = [_summarize(v) for v in value[:MAX_LIST_PREVIEW]]
        if len(value) > MAX_LIST_PREVIEW:
            head.append(f"... {len(value) - MAX_LIST_PREVIEW} more")
        return head
    return value


def _recent_days_html() -> str:
    daily_dir = DATA_DIR / "daily"
    if not daily_dir.is_dir():
        return "<p>No daily data yet.</p>"

    day_dirs = sorted(
        (p for p in daily_dir.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True
    )[:RECENT_DAYS_LIMIT]
    if not day_dirs:
        return "<p>No daily data yet.</p>"

    days_html = []
    for day_dir in day_dirs:
        files = sorted(f for f in day_dir.iterdir() if f.suffix == ".json")
        files_html = []
        for f in files:
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError) as e:
                body = f"unreadable: {html.escape(str(e))}"
            else:
                body = html.escape(json.dumps(_summarize(data), indent=2, default=str))
            files_html.append(
                f"<details><summary>{html.escape(f.name)}</summary><pre>{body}</pre></details>"
            )
        days_html.append(
            f"<details><summary>{html.escape(day_dir.name)} ({len(files)} files)</summary>"
            f"{''.join(files_html)}</details>"
        )
    return "".join(days_html)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    status = read_status()
    if status["started_at"] is None and not status["error"]:
        summary = "<p>No sync has run yet.</p>"
    else:
        ok = "OK" if status["success"] else "FAILED"
        counts_html = "".join(
            f"<li>{html.escape(str(k))}: {html.escape(str(v))}</li>"
            for k, v in status.get("counts", {}).items()
        )
        error_html = (
            f"<p style='color:red'>{html.escape(str(status['error']))}</p>" if status.get("error") else ""
        )
        summary = (
            f"<p>Last sync started: {html.escape(str(status['started_at']))} — {ok}</p>"
            f"<ul>{counts_html}</ul>"
            f"{error_html}"
        )
    page_html = f"""<!doctype html>
<html><head><title>Garmin Data Source</title></head>
<body>
<h1>Garmin Data Source</h1>
{summary}
<form method="post" action="/sync"><button type="submit">Sync now</button></form>
<h2>Recent daily data</h2>
{_recent_days_html()}
</body></html>"""
    return HTMLResponse(page_html)


@app.post("/sync")
def trigger_sync():
    try:
        with sync_lock(LOCK_PATH):
            pass  # probe: lock is free, release it immediately before spawning
    except LockHeldError:
        return JSONResponse({"status": "already_running"}, status_code=409)

    subprocess.Popen([sys.executable, str(FETCH_SCRIPT)])
    return JSONResponse({"status": "started"})
