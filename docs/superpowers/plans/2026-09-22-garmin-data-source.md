# Garmin Data Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `projects/garmin/` as a standalone data-source project — scheduled Garmin Connect fetcher, file-based storage, and a password-protected dev browse page — deployed as its own Docker stack on the Hetzner VPS at `garmin.elmarcel.com`, with a VPS-side encrypted backup.

**Architecture:** `fetch_garmin.py` moves out of `projects/coach/` into `projects/garmin/`, stripped of its Postgres coupling and adapted for unattended auth, a sync lockfile, and a `status.json` report. A small FastAPI app (`app.py`) serves a status dashboard, a raw JSON tree browser, and a manual sync trigger — all behind Caddy `basicauth`. Two containers (`garmin-web`, `garmin-cron`) share one Docker volume; `garmin-cron` also runs the daily backup job. Caddy already owns ports 80/443 for elmarcel, so this plan adds a site block to the *existing* elmarcel Caddyfile and joins both stacks to a new shared `edge` Docker network, rather than running a second Caddy.

**Tech Stack:** Python 3.12, FastAPI + uvicorn, `garminconnect`/`garth` (existing dependency), Docker Compose, Caddy 2, rclone, pytest, bash + shellcheck.

**Spec:** `docs/superpowers/specs/2026-09-22-garmin-data-source-design.md`

**Deviation from spec, noted here rather than silently:** the spec's Decisions Log says to move both `fetch_garmin.py` *and* `garmin_loader.py` out of `projects/coach`. `garmin_loader.py` only exists to extract running-specific fields (steady-state speed, warmup/cooldown trimming) for `projects/coach/analyze.py` — nothing in this project's raw-JSON browse page calls it, and coach is getting its own separate rewrite per the user. Moving dead code into the new project just to satisfy the letter of the spec would leave it unused. This plan moves only `fetch_garmin.py`; `garmin_loader.py`, `db.py`, and `schema.sql` stay in `projects/coach` untouched.

## Global Constraints

- Never put secrets in code, logs, or committed files — `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARMIN_WEB_PASSWORD` go in `.env` only; `.env.example` gets empty placeholders.
- Shell scripts must pass shellcheck (pre-commit hook enforces this).
- Unix LF line endings only.
- Data storage is file-based JSON only — no database, no `db.py`/`schema.sql` involvement.
- Garmin polling interval: every 4 hours via cron (`0 */4 * * *`), plus a manual "Sync now" button; a lockfile must prevent cron and a manual trigger from running concurrently.
- Web page access: Caddy `basicauth` only, single shared credential — no app-level auth code.
- Backup: must verify the configured rclone remote resolves to a `crypt` backend and abort loudly if not (never use a bare, unencrypted remote) — non-negotiable per `.claude/rules/backup.md`.
- Pre-commit hook runs this project's tests once files are staged — fix failures before committing, don't skip hooks.

## Review Focus

- **Path traversal in `/browse/{path}`:** a request like `/browse/../../etc/passwd` (or URL-encoded) must not escape `DATA_DIR` — expect 404, never file contents from outside the data tree. Covered in Task 3.
- **Concurrent sync attempts:** cron firing while a manual "Sync now" click is in flight (or two rapid clicks) must not launch two overlapping fetches — the second attempt must be told a sync is already running, not silently queued or double-run. Covered in Tasks 1 and 3.
- **Non-interactive auth failure:** with no cached token and no `GARMIN_EMAIL`/`GARMIN_PASSWORD` set, a cron-triggered run must fail fast with a clear error (never block forever on `input()` with no stdin attached). Covered in Task 2.
- **Missing or corrupt `status.json`:** first run before any sync, or a status file left mid-write by a crash, must not crash the dashboard route — it must render a clear "no data" / "unreadable" state instead of a 500. Covered in Task 3.
- **Backup remote misconfiguration:** if the configured rclone remote isn't type `crypt` (wrong name, unconfigured, or someone points it at the bare `hetzner:` remote), the backup script must abort with a non-zero exit and a clear message before touching the network — never fall through to an unencrypted upload. Covered in Task 5.

---

## File Structure

```
projects/garmin/
├── sync_lock.py              # fcntl-based lock helper, shared by fetch_garmin.py and app.py
├── fetch_garmin.py            # moved from projects/coach/, DB-stripped, env auth, lock+status
├── app.py                     # FastAPI: dashboard, /browse, /sync
├── requirements.txt
├── Dockerfile
├── crontab
├── docker-entrypoint-cron.sh
├── backup_garmin.sh
├── .gitignore                 # data/, __pycache__/, .venv/
└── tests/
    ├── test_sync_lock.py
    ├── test_fetch_garmin.py
    ├── test_app.py
    └── test_backup_garmin.sh

docker/garmin/
└── docker-compose.yml

docker/elmarcel/
├── Caddyfile                  # modified: new garmin.elmarcel.com site block
└── docker-compose.yml         # modified: caddy joins shared `edge` network, gets basicauth env vars

scripts/deploy/
├── setup-garmin-vps.sh        # one-time: edge network, /opt/garmin dirs, rclone config reminder
└── deploy-garmin.sh           # rsync, build, hash password, refresh elmarcel Caddy, verify

.claude/rules/garmin.md        # new per-project rules file (repo convention)
.env.example                   # modified: new GARMIN_* keys
```

---

### Task 1: Project skeleton + sync lock helper

**Files:**
- Create: `projects/garmin/sync_lock.py`
- Create: `projects/garmin/tests/test_sync_lock.py`
- Create: `projects/garmin/.gitignore`

**Interfaces:**
- Produces: `sync_lock(lock_path: Path) -> contextmanager` — acquires an exclusive non-blocking `flock` on `lock_path`, yields, releases on exit. Raises `LockHeldError` immediately if another process holds the lock. Used by `fetch_garmin.py` (Task 2) and `app.py` (Task 3).

- [ ] **Step 1: Create the project directory and gitignore**

```bash
mkdir -p /mnt/d/prg/plum-garmin-data-source/projects/garmin/tests
```

`projects/garmin/.gitignore`:
```
data/
__pycache__/
.venv/
.pytest_cache/
```

- [ ] **Step 2: Write the failing tests**

`projects/garmin/tests/test_sync_lock.py`:
```python
"""Tests for the fcntl-based sync lock helper."""
import fcntl

import pytest

from sync_lock import LockHeldError, sync_lock


def test_sync_lock_allows_single_holder(tmp_path):
    lock_path = tmp_path / ".sync.lock"
    with sync_lock(lock_path):
        assert lock_path.exists()


def test_sync_lock_raises_when_already_held(tmp_path):
    lock_path = tmp_path / ".sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(LockHeldError):
            with sync_lock(lock_path):
                pass  # pragma: no cover - must not be reached
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def test_sync_lock_releases_after_use(tmp_path):
    lock_path = tmp_path / ".sync.lock"
    with sync_lock(lock_path):
        pass
    # Lock released on exit: a second acquisition must succeed immediately,
    # not block or raise.
    with sync_lock(lock_path):
        pass
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
python3 -m venv .venv && source .venv/bin/activate
pip install pytest
pytest tests/test_sync_lock.py -v
```
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'sync_lock'`

- [ ] **Step 4: Implement `sync_lock.py`**

`projects/garmin/sync_lock.py`:
```python
"""Shared fcntl-based lock so cron and manual sync triggers never overlap."""
import fcntl
from contextlib import contextmanager
from pathlib import Path


class LockHeldError(Exception):
    """Raised when the sync lock is already held by another process."""


@contextmanager
def sync_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        fd.close()
        raise LockHeldError(f"Sync already in progress (lock held: {lock_path})") from e
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
pytest tests/test_sync_lock.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add projects/garmin/sync_lock.py projects/garmin/tests/test_sync_lock.py projects/garmin/.gitignore
git commit -m "feat(garmin): add sync lock helper"
```

---

### Task 2: Move and adapt fetch_garmin.py

**Files:**
- Create: `projects/garmin/fetch_garmin.py` (adapted from `projects/coach/fetch_garmin.py`)
- Delete: `projects/coach/fetch_garmin.py`
- Create: `projects/garmin/tests/test_fetch_garmin.py`
- Create: `projects/garmin/requirements.txt` (partial — extended in Task 4)

**Interfaces:**
- Consumes: `sync_lock(lock_path) -> contextmanager`, `LockHeldError` from Task 1's `sync_lock.py`.
- Produces: `authenticate() -> Garmin`, `main()`, module-level `DATA_DIR`, `TOKEN_DIR`, `STATUS_PATH`, `LOCK_PATH` (all `Path`), and `_run_fetch(args, started_at: str) -> None`, `_is_interactive() -> bool`, `write_status(success, started_at, counts, error=None) -> None` — `app.py` (Task 3) imports `DATA_DIR`, `STATUS_PATH`, `LOCK_PATH` and shells out to this file as a subprocess; it does not import the fetch functions directly.

- [ ] **Step 1: Copy the file into the new project and strip Postgres coupling**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git mv projects/coach/fetch_garmin.py projects/garmin/fetch_garmin.py
```

Edit `projects/garmin/fetch_garmin.py`: this file currently calls into `db.py` (coach's Postgres helper) via a module-level `_db` object, gated by `--no-db`/`init_db()`. Remove all of it — this project has no database. Specifically:

- Delete the `init_db()` function entirely.
- Delete the `_db = None` module global.
- Delete the `--no-db` argument from `parse_args()`.
- Delete every `if _db:` block (and the `_db.upsert_*` calls inside them) in `fetch_profile`, `fetch_devices`, `fetch_gear`, `fetch_badges_and_challenges`, `fetch_goals`, `fetch_workouts`, `fetch_activities`, `fetch_activity_details`, `fetch_daily`, `fetch_weekly`, `fetch_range_data`.
- Delete the `if not args.no_db: init_db()` line from `main()`.

None of the fetch/save logic itself changes — only the DB side-effects are removed. The functions still write JSON via `save_json()` exactly as before.

- [ ] **Step 2: Write the failing tests for the new auth and status behavior**

`projects/garmin/tests/test_fetch_garmin.py`:
```python
"""Tests for fetch_garmin.py's unattended-auth, lock, and status behavior."""
import fcntl
import json
import sys

import pytest

import fetch_garmin


def test_authenticate_raises_when_noninteractive_and_no_creds(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_garmin, "TOKEN_DIR", tmp_path / ".tokens")
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    monkeypatch.setattr(fetch_garmin, "_is_interactive", lambda: False)

    with pytest.raises(RuntimeError, match="non-interactively"):
        fetch_garmin.authenticate()


def test_main_skips_run_when_lock_held(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_garmin, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_garmin, "LOCK_PATH", tmp_path / ".sync.lock")
    monkeypatch.setattr(fetch_garmin, "STATUS_PATH", tmp_path / "status.json")
    monkeypatch.setattr(sys, "argv", ["fetch_garmin.py"])

    fetch_garmin.LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = open(fetch_garmin.LOCK_PATH, "w")
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(SystemExit) as exc_info:
            fetch_garmin.main()
        assert exc_info.value.code == 0
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()

    assert not fetch_garmin.STATUS_PATH.exists()


def test_main_writes_status_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_garmin, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_garmin, "LOCK_PATH", tmp_path / ".sync.lock")
    monkeypatch.setattr(fetch_garmin, "STATUS_PATH", tmp_path / "status.json")
    monkeypatch.setattr(sys, "argv", ["fetch_garmin.py"])

    def boom(args, started_at):
        raise RuntimeError("garmin api down")

    monkeypatch.setattr(fetch_garmin, "_run_fetch", boom)

    with pytest.raises(SystemExit) as exc_info:
        fetch_garmin.main()
    assert exc_info.value.code == 1

    status = json.loads(fetch_garmin.STATUS_PATH.read_text())
    assert status["success"] is False
    assert "garmin api down" in status["error"]


def test_main_writes_status_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_garmin, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_garmin, "LOCK_PATH", tmp_path / ".sync.lock")
    monkeypatch.setattr(fetch_garmin, "STATUS_PATH", tmp_path / "status.json")
    monkeypatch.setattr(sys, "argv", ["fetch_garmin.py"])

    def fake_run(args, started_at):
        fetch_garmin.write_status(True, started_at, counts={"activities": 3})

    monkeypatch.setattr(fetch_garmin, "_run_fetch", fake_run)

    fetch_garmin.main()

    status = json.loads(fetch_garmin.STATUS_PATH.read_text())
    assert status["success"] is True
    assert status["counts"] == {"activities": 3}
    assert status["error"] is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
source .venv/bin/activate
pip install garminconnect==0.2.38
pytest tests/test_fetch_garmin.py -v
```
Expected: FAIL — `_is_interactive`, `_run_fetch`, `write_status`, `STATUS_PATH`, `LOCK_PATH` don't exist yet; `authenticate()` doesn't raise `RuntimeError`.

- [ ] **Step 4: Implement the auth, lock, and status changes**

Add `import os` near the top imports (alongside the existing `argparse, getpass, json, sys, time`), and import the lock helper:

```python
from sync_lock import LockHeldError, sync_lock
```

Add two new module-level paths next to the existing `DATA_DIR`/`TOKEN_DIR`:

```python
STATUS_PATH = DATA_DIR / "status.json"
LOCK_PATH = DATA_DIR / ".sync.lock"
```

Add the interactivity check (kept as its own function so tests can monkeypatch it without fighting pytest's stdin capture):

```python
def _is_interactive() -> bool:
    return sys.stdin.isatty()
```

Replace `authenticate()`'s interactive-only login block:

```python
def authenticate() -> Garmin:
    """Authenticate with Garmin Connect. Uses cached tokens if available."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_path = str(TOKEN_DIR)

    garmin = Garmin()

    # Try cached tokens first
    if (TOKEN_DIR / "oauth1_token.json").exists():
        try:
            garmin.login(token_path)
            print(f"Authenticated as {garmin.display_name}")
            return garmin
        except Exception:
            print("Cached tokens expired, re-authenticating...")

    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not (email and password):
        if not _is_interactive():
            raise RuntimeError(
                "No cached Garmin session and no GARMIN_EMAIL/GARMIN_PASSWORD "
                "set; cannot authenticate non-interactively."
            )
        email = input("Garmin email: ")
        password = getpass.getpass("Garmin password: ")
    else:
        print("Authenticating with GARMIN_EMAIL/GARMIN_PASSWORD from environment")

    garmin = Garmin(email=email, password=password, prompt_mfa=lambda: input("MFA code: "))
    garmin.login()
    garmin.garth.dump(token_path)
    print(f"Authenticated as {garmin.display_name}")
    return garmin
```

Remove the `--no-db` argument from `parse_args()`:

```python
def parse_args():
    parser = argparse.ArgumentParser(description="Fetch all data from Garmin Connect.")
    parser.add_argument("--full", action="store_true",
                        help="Force re-fetch everything (ignore incremental cache)")
    return parser.parse_args()
```

Add `write_status()` and split `main()` into a lock-wrapped outer function plus `_run_fetch()`:

```python
def write_status(success: bool, started_at: str, counts: dict, error: str | None = None) -> None:
    status = {
        "success": success,
        "started_at": started_at,
        "finished_at": datetime.utcnow().isoformat() + "Z",
        "counts": counts,
        "error": error,
    }
    save_json(STATUS_PATH, status)


def _run_fetch(args, started_at: str) -> None:
    garmin = authenticate()
    today = date.today()

    fetch_profile(garmin)
    fetch_devices(garmin)
    fetch_gear(garmin)
    fetch_badges_and_challenges(garmin)
    fetch_goals(garmin)
    fetch_workouts(garmin)

    activities = fetch_activities(garmin, today, full=args.full)
    fetch_activity_details(garmin, activities, full=args.full)
    fetch_daily(garmin, activities, today, full=args.full)
    fetch_weekly(garmin, today, full=args.full)
    fetch_range_data(garmin, activities, today)

    total_files = sum(1 for _ in DATA_DIR.rglob("*.json"))
    total_size_mb = sum(f.stat().st_size for f in DATA_DIR.rglob("*.json")) / 1024 / 1024
    counts = {
        "activities": len(activities),
        "total_files": total_files,
        "total_size_mb": round(total_size_mb, 1),
    }
    print(f"\nTotal: {total_files} JSON files, {total_size_mb:.1f} MB")
    write_status(True, started_at, counts)
    print("\nDone.")


def main():
    args = parse_args()
    started_at = datetime.utcnow().isoformat() + "Z"
    try:
        with sync_lock(LOCK_PATH):
            _run_fetch(args, started_at)
    except LockHeldError as e:
        print(str(e))
        sys.exit(0)
    except Exception as e:
        write_status(False, started_at, counts={}, error=str(e))
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
```

Delete the old `main()` body (the one that called `init_db()`/`args.no_db` directly) — it's fully replaced by `_run_fetch()` + the new `main()` above.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
pytest tests/test_fetch_garmin.py -v
```
Expected: 4 passed

- [ ] **Step 6: Create the initial requirements.txt**

`projects/garmin/requirements.txt`:
```
garminconnect==0.2.38
```
(extended with FastAPI/uvicorn in Task 4)

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add projects/garmin/fetch_garmin.py projects/garmin/tests/test_fetch_garmin.py projects/garmin/requirements.txt
git add projects/coach/fetch_garmin.py
git commit -m "feat(garmin): move and adapt fetch_garmin.py for unattended runs"
```

---

### Task 3: FastAPI dashboard, browse, and sync app

**Files:**
- Create: `projects/garmin/app.py`
- Create: `projects/garmin/tests/test_app.py`

**Interfaces:**
- Consumes: `sync_lock`, `LockHeldError` from Task 1; `DATA_DIR`, `STATUS_PATH`, `LOCK_PATH` conventions matching Task 2's `fetch_garmin.py` (same path layout, different module instance — `app.py` defines its own module-level `DATA_DIR`/`STATUS_PATH`/`LOCK_PATH` pointing at the same on-disk location so both processes agree; it does not import `fetch_garmin.py`, it shells out to it as a subprocess).
- Produces: `app: FastAPI` (the ASGI app uvicorn serves), routes `GET /`, `GET /browse/{path:path}`, `POST /sync`.

- [ ] **Step 1: Write the failing tests**

`projects/garmin/tests/test_app.py`:
```python
"""Tests for the FastAPI dev-browse app."""
import fcntl
import json

import pytest
from fastapi.testclient import TestClient

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "garmin"
    data_dir.mkdir()
    monkeypatch.setattr(app_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(app_module, "STATUS_PATH", data_dir / "status.json")
    monkeypatch.setattr(app_module, "LOCK_PATH", data_dir / ".sync.lock")
    return TestClient(app_module.app)


def test_dashboard_with_no_status_yet(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No sync has run yet." in resp.text


def test_dashboard_with_status(client):
    status = {
        "success": True,
        "started_at": "2026-09-22T00:00:00Z",
        "finished_at": "2026-09-22T00:05:00Z",
        "counts": {"activities": 42},
        "error": None,
    }
    app_module.STATUS_PATH.write_text(json.dumps(status))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "42" in resp.text


def test_dashboard_with_corrupt_status_does_not_crash(client):
    app_module.STATUS_PATH.write_text("{not valid json")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "unreadable" in resp.text.lower()


def test_browse_lists_directory(client):
    (app_module.DATA_DIR / "activities").mkdir()
    (app_module.DATA_DIR / "activities" / "list.json").write_text("[]")
    resp = client.get("/browse/")
    assert resp.status_code == 200
    assert "activities/" in resp.json()["entries"]


def test_browse_returns_json_file_contents(client):
    (app_module.DATA_DIR / "activities").mkdir()
    (app_module.DATA_DIR / "activities" / "list.json").write_text('{"foo": "bar"}')
    resp = client.get("/browse/activities/list.json")
    assert resp.status_code == 200
    assert resp.json() == {"foo": "bar"}


def test_browse_blocks_path_traversal(client):
    resp = client.get("/browse/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code == 404


def test_browse_missing_path_is_404(client):
    resp = client.get("/browse/does/not/exist.json")
    assert resp.status_code == 404


def test_sync_starts_when_lock_is_free(client, monkeypatch):
    started = {}

    def fake_popen(cmd):
        started["cmd"] = cmd

        class _P:
            pass

        return _P()

    monkeypatch.setattr(app_module.subprocess, "Popen", fake_popen)

    resp = client.post("/sync")
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"
    assert started["cmd"][-1].endswith("fetch_garmin.py")


def test_sync_reports_already_running_when_locked(client):
    app_module.LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = open(app_module.LOCK_PATH, "w")
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        resp = client.post("/sync")
        assert resp.status_code == 409
        assert resp.json()["status"] == "already_running"
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
pip install fastapi 'uvicorn[standard]' httpx
pytest tests/test_app.py -v
```
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Implement app.py**

`projects/garmin/app.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
pytest tests/test_app.py -v
```
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add projects/garmin/app.py projects/garmin/tests/test_app.py
git commit -m "feat(garmin): add FastAPI dashboard, browse, and sync endpoints"
```

---

### Task 4: Dockerfile, cron, and requirements

**Files:**
- Modify: `projects/garmin/requirements.txt`
- Create: `projects/garmin/Dockerfile`
- Create: `projects/garmin/crontab`
- Create: `projects/garmin/docker-entrypoint-cron.sh`

**Interfaces:**
- Consumes: `app:app` (Task 3), `fetch_garmin.py` (Task 2), `backup_garmin.sh` (Task 5, referenced by path only — created next task, this task's crontab just needs the filename to match).
- Produces: a built image used by both `garmin-web` and `garmin-cron` services in Task 6's compose file (default `CMD` serves the web app; `garmin-cron` overrides `command` to run cron).

- [ ] **Step 1: Finalize requirements.txt**

`projects/garmin/requirements.txt`:
```
garminconnect==0.2.38
fastapi>=0.115
uvicorn[standard]>=0.32
```

- [ ] **Step 2: Write the crontab**

`projects/garmin/crontab`:
```cron
# Fetch fresh Garmin data every 4 hours. Cron strips the container's
# environment, so source /etc/cron.env (written by docker-entrypoint-cron.sh
# at container start) before running anything that needs GARMIN_EMAIL/
# GARMIN_PASSWORD/RCLONE_REMOTE.
0 */4 * * * . /etc/cron.env; cd /app && python fetch_garmin.py >> /proc/1/fd/1 2>&1
0 3 * * * . /etc/cron.env; cd /app && bash backup_garmin.sh >> /proc/1/fd/1 2>&1
```

- [ ] **Step 3: Write the cron entrypoint**

`projects/garmin/docker-entrypoint-cron.sh`:
```bash
#!/bin/bash
# Persist the container's environment for cron jobs, which otherwise run
# with none of it (a classic cron-in-Docker gotcha: PID 1's env is not
# inherited by cron's spawned children).
set -euo pipefail

{
    echo "export GARMIN_EMAIL='${GARMIN_EMAIL:-}'"
    echo "export GARMIN_PASSWORD='${GARMIN_PASSWORD:-}'"
    echo "export RCLONE_REMOTE='${RCLONE_REMOTE:-hetzner-crypt}'"
    echo "export GARMIN_DATA_DIR='${GARMIN_DATA_DIR:-/app/data/garmin}'"
} > /etc/cron.env
chmod 600 /etc/cron.env

exec cron -f
```

- [ ] **Step 4: Write the Dockerfile**

`projects/garmin/Dockerfile`:
```dockerfile
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron rclone zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint-cron.sh backup_garmin.sh \
    && crontab crontab

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

(`backup_garmin.sh` doesn't exist until Task 5 — this Dockerfile is only built starting in Task 6's compose setup, after Task 5 lands, so the `chmod` target will exist by then.)

- [ ] **Step 5: Verify the image builds**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
touch backup_garmin.sh  # placeholder so this build check passes before Task 5 lands
docker build -t garmin-test .
rm backup_garmin.sh
```
Expected: build succeeds (this is a manual sanity check, not part of the permanent repo state — the real `backup_garmin.sh` lands in Task 5 and the image gets rebuilt for real in Task 6's verification).

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add projects/garmin/requirements.txt projects/garmin/Dockerfile projects/garmin/crontab projects/garmin/docker-entrypoint-cron.sh
git commit -m "feat(garmin): add Dockerfile and cron scheduling"
```

---

### Task 5: Backup script

**Files:**
- Create: `projects/garmin/backup_garmin.sh`
- Create: `projects/garmin/tests/test_backup_garmin.sh`

**Interfaces:**
- Consumes: env vars `GARMIN_DATA_DIR` (defaults to `/app/data/garmin`), `RCLONE_REMOTE` (defaults to `hetzner-crypt`) — both written to `/etc/cron.env` by Task 4's entrypoint.
- Produces: nothing consumed by other tasks — this is a leaf script invoked by cron (Task 4) and manually during deploy verification (Task 10).

- [ ] **Step 1: Write the backup script**

`projects/garmin/backup_garmin.sh`:
```bash
#!/bin/bash
# Zip the Garmin data tree and upload it to Hetzner Storage Box, keeping the
# newest 3 backups. Aborts loudly if the configured rclone remote is not an
# encrypted (crypt) backend — see .claude/rules/backup.md (non-negotiable).
set -euo pipefail

DATA_DIR="${GARMIN_DATA_DIR:-/app/data/garmin}"
REMOTE="${RCLONE_REMOTE:-hetzner-crypt}"
REMOTE_DIR="bak/garmin"
KEEP=3

REMOTE_TYPE="$(rclone config show "$REMOTE" 2>/dev/null | grep '^type = ' | awk '{print $3}')"
if [ "$REMOTE_TYPE" != "crypt" ]; then
    echo "ABORT: rclone remote '$REMOTE' is not type 'crypt' (got: '${REMOTE_TYPE:-missing}')" >&2
    exit 1
fi

[ -d "$DATA_DIR" ] || { echo "ABORT: $DATA_DIR does not exist" >&2; exit 1; }

DATE="$(date +%Y-%m-%d)"
ZIP_NAME="bak_garmin_${DATE}.zip"
TMP_ZIP="/tmp/${ZIP_NAME}"

echo "Zipping $DATA_DIR -> $TMP_ZIP"
(cd "$(dirname "$DATA_DIR")" && zip -rq "$TMP_ZIP" "$(basename "$DATA_DIR")")
[ -s "$TMP_ZIP" ] || { echo "ABORT: zip produced an empty or missing file" >&2; exit 1; }

echo "Uploading to ${REMOTE}:${REMOTE_DIR}/${ZIP_NAME}"
rclone copy "$TMP_ZIP" "${REMOTE}:${REMOTE_DIR}/" || { echo "ABORT: rclone upload failed" >&2; exit 1; }
rm -f "$TMP_ZIP"

echo "Pruning to newest $KEEP backups in ${REMOTE}:${REMOTE_DIR}/"
rclone lsf "${REMOTE}:${REMOTE_DIR}/" --files-only | sort | head -n "-${KEEP}" | while read -r old; do
    [ -n "$old" ] || continue
    echo "  Deleting old backup: $old"
    rclone deletefile "${REMOTE}:${REMOTE_DIR}/${old}"
done

echo "Backup complete: ${ZIP_NAME}"
```

- [ ] **Step 2: Run shellcheck**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
shellcheck backup_garmin.sh
chmod +x backup_garmin.sh
```
Expected: no shellcheck warnings.

- [ ] **Step 3: Write the abort-on-misconfigured-remote test**

`projects/garmin/tests/test_backup_garmin.sh`:
```bash
#!/bin/bash
# Test that backup_garmin.sh aborts before touching the network when the
# configured rclone remote does not resolve to a crypt backend.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PROJECT_DIR/../.." && pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/test/test-helpers.sh"

print_header "backup_garmin.sh: abort on non-crypt remote"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

mkdir -p "$WORKDIR/bin" "$WORKDIR/data/garmin"
echo '{}' > "$WORKDIR/data/garmin/status.json"

# Fake rclone: reports the remote as type "sftp" (not crypt) and fails
# loudly if the script tries to use it for anything beyond the config check
# — proves the script aborts before any zip/upload/prune step runs.
cat > "$WORKDIR/bin/rclone" <<'EOF'
#!/bin/bash
if [ "$1" = "config" ] && [ "$2" = "show" ]; then
    echo "type = sftp"
    exit 0
fi
echo "rclone should not be invoked beyond the config check" >&2
exit 1
EOF
chmod +x "$WORKDIR/bin/rclone"

set +e
PATH="$WORKDIR/bin:$PATH" GARMIN_DATA_DIR="$WORKDIR/data/garmin" RCLONE_REMOTE="hetzner-crypt" \
    bash "$PROJECT_DIR/backup_garmin.sh" > "$WORKDIR/out.log" 2>&1
EXIT_CODE=$?
set -e

assert_eq "exits non-zero on non-crypt remote" "1" "$EXIT_CODE"
assert_contains "abort message names the wrong remote type" "$(cat "$WORKDIR/out.log")" "not type 'crypt'"

if [ "$TEST_FAILURES" -gt 0 ]; then
    echo "FAILED: $TEST_FAILURES assertion(s)"
    exit 1
fi
echo "All assertions passed."
```

- [ ] **Step 4: Run the test**

```bash
cd /mnt/d/prg/plum-garmin-data-source
chmod +x projects/garmin/tests/test_backup_garmin.sh
bash projects/garmin/tests/test_backup_garmin.sh
```
Expected: `All assertions passed.`

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add projects/garmin/backup_garmin.sh projects/garmin/tests/test_backup_garmin.sh
git commit -m "feat(garmin): add encrypted rolling backup script"
```

---

### Task 6: docker/garmin compose stack

**Files:**
- Create: `docker/garmin/docker-compose.yml`

**Interfaces:**
- Consumes: `projects/garmin/Dockerfile` (Task 4), the shared external `edge` Docker network (created by Task 9's `setup-garmin-vps.sh`, referenced here as `external: true`).
- Produces: services `garmin-web` (reachable at `garmin-web:8000` from other containers on `edge` — this is the hostname Task 7's Caddyfile reverse-proxies to) and `garmin-cron`, sharing named volume `garmin_data`.

- [ ] **Step 1: Write the compose file**

`docker/garmin/docker-compose.yml`:
```yaml
# Garmin data source: web dashboard/browser + scheduled fetch/backup cron.
# Deployed to /opt/garmin/ on the VPS by scripts/deploy/deploy-garmin.sh.
# Joins the shared `edge` network so the existing elmarcel Caddy instance
# can reverse-proxy to garmin-web without running a second Caddy.
services:
  garmin-web:
    build:
      context: ../../projects/garmin
    restart: unless-stopped
    volumes:
      - garmin_data:/app/data/garmin
    environment:
      - GARMIN_EMAIL=${GARMIN_EMAIL}
      - GARMIN_PASSWORD=${GARMIN_PASSWORD}
    networks:
      - edge

  garmin-cron:
    build:
      context: ../../projects/garmin
    restart: unless-stopped
    command: ["bash", "docker-entrypoint-cron.sh"]
    volumes:
      - garmin_data:/app/data/garmin
      - ./rclone.conf:/root/.config/rclone/rclone.conf:ro
    environment:
      - GARMIN_EMAIL=${GARMIN_EMAIL}
      - GARMIN_PASSWORD=${GARMIN_PASSWORD}
      - RCLONE_REMOTE=${RCLONE_REMOTE:-hetzner-crypt}
    networks:
      - edge

networks:
  edge:
    external: true

volumes:
  garmin_data:
```

Note: `garmin-web` is not reachable from outside the `edge` network directly (no `ports:` published) — only Caddy, also on `edge` (Task 7), can reach it. This is intentional: the only public entry point is through Caddy's `basicauth`.

- [ ] **Step 2: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add docker/garmin/docker-compose.yml
git commit -m "feat(garmin): add docker-compose stack for garmin-web and garmin-cron"
```

---

### Task 7: Wire garmin.elmarcel.com into the existing Caddy

**Files:**
- Modify: `docker/elmarcel/Caddyfile`
- Modify: `docker/elmarcel/docker-compose.yml`

**Interfaces:**
- Consumes: `garmin-web:8000` (Task 6) as the reverse-proxy target — resolvable only because both stacks join `edge`.
- Produces: the `edge` network requirement that Task 6 and Task 9 also reference (Task 9 is what actually runs `docker network create edge` on the VPS).

- [ ] **Step 1: Add the new site block to the Caddyfile**

Read `docker/elmarcel/Caddyfile` first (its current content: `www.elmarcel.com { ... }` and `elmarcel.com { redir ... }`). Append a new block:

```caddyfile
garmin.elmarcel.com {
	basicauth {
		{$GARMIN_WEB_USER} {$GARMIN_WEB_PASSWORD_HASH}
	}
	reverse_proxy garmin-web:8000
}
```

- [ ] **Step 2: Join the elmarcel Caddy service to the shared `edge` network and pass through the auth env vars**

Modify `docker/elmarcel/docker-compose.yml`'s `caddy` service to add `environment:` and `networks:`, and add the top-level `networks:` block:

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./www:/srv:ro
      - caddy_data:/data
      - caddy_config:/config
    environment:
      - GARMIN_WEB_USER=${GARMIN_WEB_USER:-admin}
      - GARMIN_WEB_PASSWORD_HASH=${GARMIN_WEB_PASSWORD_HASH}
    networks:
      - default
      - edge

networks:
  default:
  edge:
    external: true

volumes:
  caddy_data:
  caddy_config:
```

`default` is kept explicit (rather than left implicit) because adding any `networks:` key to a service opts it out of Compose's implicit default network — Caddy still needs a network for its own use even though nothing else currently depends on it.

- [ ] **Step 3: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add docker/elmarcel/Caddyfile docker/elmarcel/docker-compose.yml
git commit -m "feat(garmin): add garmin.elmarcel.com site block to shared Caddy"
```

---

### Task 8: .env.example and per-project rules doc

**Files:**
- Modify: `.env.example`
- Create: `.claude/rules/garmin.md`

- [ ] **Step 1: Add the new keys to .env.example**

Append to `.env.example` (after the existing `VPS_SSH_KEY` line, before `# Backup Locations`):

```
# Garmin Data Source
GARMIN_EMAIL=
GARMIN_PASSWORD=
GARMIN_WEB_USER=admin
GARMIN_WEB_PASSWORD=
RCLONE_REMOTE=hetzner-crypt
```

- [ ] **Step 2: Write the per-project rules file**

`.claude/rules/garmin.md`:
```markdown
---
paths:
  - "projects/garmin/**"
  - "docker/garmin/**"
---

# Garmin Data Source

Standalone Hetzner-hosted project: scheduled Garmin Connect fetcher + a
password-protected dev browse page. Deployed at `garmin.elmarcel.com`,
behind the existing elmarcel Caddy instance.

## Commands

```bash
cd projects/garmin
source .venv/bin/activate
python fetch_garmin.py            # manual fetch (incremental)
python fetch_garmin.py --full     # force re-fetch everything
uvicorn app:app --reload          # run the dev browse page locally

pytest tests/                     # Python tests
bash tests/test_backup_garmin.sh  # backup script test
```

## Architecture

- File-based storage only — no database. `fetch_garmin.py` writes the same
  raw JSON tree it always has (`data/garmin/{activities,daily,weekly,
  profile,devices,gear,goals,badges,challenges,workouts,blood_pressure,
  weight,progress}/`); `app.py` is a thin FastAPI browser over that tree,
  nothing more.
- `sync_lock.py` (fcntl-based) prevents cron and a manual "Sync now" click
  from ever running two fetches at once.
- `status.json` (written after every fetch run) is the only thing the
  dashboard reads to show sync health — never silently swallow a failed run.
- Auth: `GARMIN_EMAIL`/`GARMIN_PASSWORD` env vars for unattended login; if
  the account has MFA, the first login must be run interactively once
  (e.g. over SSH with a TTY) to establish the cached garth token.
- Access control is entirely at the Caddy layer (`basicauth` in
  `docker/elmarcel/Caddyfile`) — no app-level auth code.

## Deployment

- `scripts/deploy/setup-garmin-vps.sh` — one-time: creates the shared
  `edge` Docker network, `/opt/garmin/` on the VPS, reminds about the
  manual rclone config copy.
- `scripts/deploy/deploy-garmin.sh` — rsyncs the project + compose config,
  builds, hashes `GARMIN_WEB_PASSWORD` into the Caddyfile's basicauth,
  refreshes the elmarcel Caddy stack, verifies via `curl --fail`.

## Backup

`backup_garmin.sh` runs daily from the `garmin-cron` container: zips
`data/garmin/`, uploads to `hetzner-crypt:bak/garmin/`, keeps the newest 3.
Aborts loudly if the configured rclone remote isn't type `crypt` — see
`.claude/rules/backup.md` (non-negotiable).
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add .env.example .claude/rules/garmin.md
git commit -m "docs(garmin): add env placeholders and per-project rules"
```

---

### Task 9: One-time VPS setup script

**Files:**
- Create: `scripts/deploy/setup-garmin-vps.sh`

**Interfaces:**
- Consumes: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` from `.env` (same convention as `setup-elmarcel-vps.sh`).
- Produces: the `edge` Docker network and `/opt/garmin/` directory on the VPS that Task 10's `deploy-garmin.sh` deploys into.

- [ ] **Step 1: Write the script**

`scripts/deploy/setup-garmin-vps.sh`:
```bash
#!/bin/bash
# One-time Hetzner VPS preparation for the garmin data source stack.
# Creates the shared `edge` Docker network (so garmin-web can be reached by
# the existing elmarcel Caddy instance) and /opt/garmin/. Idempotent.
# Usage: bash scripts/deploy/setup-garmin-vps.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export SCRIPT_NAME="setup-garmin-vps"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/logging.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/load-env.sh"

: "${VPS_HOST:?VPS_HOST must be set in .env}"
: "${VPS_USER:?VPS_USER must be set in .env}"
: "${VPS_SSH_KEY:?VPS_SSH_KEY must be set in .env}"

REMOTE_ROOT="/opt/garmin"

remote() {
    # shellcheck disable=SC2029  # client-side expansion is intentional
    ssh -i "$VPS_SSH_KEY" -o BatchMode=yes "${VPS_USER}@${VPS_HOST}" "$@"
}

log_info "Checking SSH connectivity to ${VPS_USER}@${VPS_HOST}"
remote "true" || log_die "Cannot SSH to ${VPS_USER}@${VPS_HOST} with key $VPS_SSH_KEY"

log_info "Creating shared 'edge' Docker network if absent"
remote "docker network inspect edge >/dev/null 2>&1 || docker network create edge"

log_info "Creating $REMOTE_ROOT"
remote "mkdir -p $REMOTE_ROOT"

log_info "VPS setup complete."
echo "VPS setup complete."
echo ""
echo "MANUAL STEP REMAINING: copy your rclone config (containing the"
echo "hetzner-crypt remote credentials) to ${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/rclone.conf"
echo "The backup cron job will fail until this is in place — the fetch and"
echo "web dashboard work fine without it."
```

- [ ] **Step 2: Run shellcheck**

```bash
cd /mnt/d/prg/plum-garmin-data-source
shellcheck scripts/deploy/setup-garmin-vps.sh
chmod +x scripts/deploy/setup-garmin-vps.sh
```
Expected: no warnings.

- [ ] **Step 3: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add scripts/deploy/setup-garmin-vps.sh
git commit -m "feat(garmin): add one-time VPS setup script"
```

---

### Task 10: Deploy script

**Files:**
- Create: `scripts/deploy/deploy-garmin.sh`

**Interfaces:**
- Consumes: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARMIN_WEB_USER`, `GARMIN_WEB_PASSWORD`, `RCLONE_REMOTE` from `.env`; `docker/garmin/docker-compose.yml` (Task 6); `docker/elmarcel/{Caddyfile,docker-compose.yml}` (Task 7); `/opt/garmin/` and the `edge` network (Task 9, must already exist).

- [ ] **Step 1: Write the script**

`scripts/deploy/deploy-garmin.sh`:
```bash
#!/bin/bash
# Deploy the garmin data source stack to the Hetzner VPS, and refresh the
# elmarcel Caddy stack so it picks up the new garmin.elmarcel.com site
# block. Run scripts/deploy/setup-garmin-vps.sh once before the first use.
#
# Usage:
#   bash scripts/deploy/deploy-garmin.sh           # deploy to VPS
#   bash scripts/deploy/deploy-garmin.sh --check   # verify only, no deploy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export SCRIPT_NAME="deploy-garmin"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/logging.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/load-env.sh"

: "${VPS_HOST:?VPS_HOST must be set in .env}"
: "${VPS_USER:?VPS_USER must be set in .env}"
: "${VPS_SSH_KEY:?VPS_SSH_KEY must be set in .env}"
: "${GARMIN_EMAIL:?GARMIN_EMAIL must be set in .env}"
: "${GARMIN_PASSWORD:?GARMIN_PASSWORD must be set in .env}"
: "${GARMIN_WEB_PASSWORD:?GARMIN_WEB_PASSWORD must be set in .env}"
GARMIN_WEB_USER="${GARMIN_WEB_USER:-admin}"
RCLONE_REMOTE="${RCLONE_REMOTE:-hetzner-crypt}"

MODE="${1:-deploy}"
GARMIN_ROOT="/opt/garmin"
ELMARCEL_ROOT="/opt/elmarcel"
PROJECT_SRC="$SCRIPT_DIR/../../projects/garmin"
GARMIN_COMPOSE_SRC="$SCRIPT_DIR/../../docker/garmin"
ELMARCEL_COMPOSE_SRC="$SCRIPT_DIR/../../docker/elmarcel"

remote() {
    # shellcheck disable=SC2029  # client-side expansion is intentional
    ssh -i "$VPS_SSH_KEY" -o BatchMode=yes "${VPS_USER}@${VPS_HOST}" "$@"
}

rsync_up() {
    rsync -az -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" "$@"
}

if [ "$MODE" = "--check" ]; then
    log_info "Checking garmin-web responds through Caddy"
    CODE="$(curl -sS -o /dev/null -w '%{http_code}' -u "${GARMIN_WEB_USER}:${GARMIN_WEB_PASSWORD}" \
        -H "Host: garmin.elmarcel.com" "http://${VPS_HOST}/")"
    [ "$CODE" = "200" ] || log_die "Expected HTTP 200 from garmin.elmarcel.com, got $CODE"
    log_info "OK: garmin.elmarcel.com responds with 200"
    exit 0
fi

log_info "Syncing garmin project source to $GARMIN_ROOT"
remote "mkdir -p $GARMIN_ROOT/project $GARMIN_ROOT/compose"
rsync_up --delete --exclude data --exclude .venv --exclude __pycache__ --exclude .pytest_cache \
    "$PROJECT_SRC/" "${VPS_USER}@${VPS_HOST}:${GARMIN_ROOT}/project/"
rsync_up "$GARMIN_COMPOSE_SRC/docker-compose.yml" "${VPS_USER}@${VPS_HOST}:${GARMIN_ROOT}/compose/"

log_info "Syncing updated elmarcel Caddy config to $ELMARCEL_ROOT"
rsync_up "$ELMARCEL_COMPOSE_SRC/Caddyfile" "$ELMARCEL_COMPOSE_SRC/docker-compose.yml" \
    "${VPS_USER}@${VPS_HOST}:${ELMARCEL_ROOT}/"

log_info "Checking for rclone config (backup prerequisite)"
if ! remote "test -f $GARMIN_ROOT/rclone.conf"; then
    log_warn "No rclone config at ${GARMIN_ROOT}/rclone.conf — the backup cron job will fail until you copy one there. Fetch and the web dashboard are unaffected."
fi

log_info "Writing garmin .env for docker compose"
remote "cat > $GARMIN_ROOT/compose/.env" <<EOF
GARMIN_EMAIL=${GARMIN_EMAIL}
GARMIN_PASSWORD=${GARMIN_PASSWORD}
RCLONE_REMOTE=${RCLONE_REMOTE}
EOF

log_info "Hashing GARMIN_WEB_PASSWORD for Caddy basicauth"
HASH="$(remote "docker run --rm caddy:2-alpine caddy hash-password --plaintext '${GARMIN_WEB_PASSWORD}'")"
[ -n "$HASH" ] || log_die "caddy hash-password returned nothing"

log_info "Writing elmarcel .env with basicauth credentials"
remote "cat > $ELMARCEL_ROOT/.env" <<EOF
GARMIN_WEB_USER=${GARMIN_WEB_USER}
GARMIN_WEB_PASSWORD_HASH=${HASH}
EOF

log_info "Building and starting garmin-web / garmin-cron"
remote "cd $GARMIN_ROOT/compose && docker compose --project-directory $GARMIN_ROOT/project -f $GARMIN_ROOT/compose/docker-compose.yml --env-file $GARMIN_ROOT/compose/.env up -d --build" \
    || log_die "docker compose up failed for garmin stack"

log_info "Refreshing elmarcel Caddy to pick up the new site block"
remote "cd $ELMARCEL_ROOT && docker compose up -d" || log_die "docker compose up failed for elmarcel stack"

log_info "Verifying garmin.elmarcel.com responds"
CODE="$(curl -sS -o /dev/null -w '%{http_code}' -u "${GARMIN_WEB_USER}:${GARMIN_WEB_PASSWORD}" \
    -H "Host: garmin.elmarcel.com" "http://${VPS_HOST}/")"
[ "$CODE" = "200" ] || log_die "Expected HTTP 200 from garmin.elmarcel.com after deploy, got $CODE"

UNAUTH_CODE="$(curl -sS -o /dev/null -w '%{http_code}' -H "Host: garmin.elmarcel.com" "http://${VPS_HOST}/")"
[ "$UNAUTH_CODE" = "401" ] || log_die "Expected HTTP 401 without credentials, got $UNAUTH_CODE (basicauth is not enforcing!)"

log_info "Deploy complete"
echo "Deploy complete. garmin.elmarcel.com is serving behind basic auth."
echo ""
echo "If DNS does not yet point garmin.elmarcel.com at this VPS, HTTPS"
echo "certs won't issue yet — the checks above used HTTP with a Host header."
```

- [ ] **Step 2: Run shellcheck**

```bash
cd /mnt/d/prg/plum-garmin-data-source
shellcheck scripts/deploy/deploy-garmin.sh
chmod +x scripts/deploy/deploy-garmin.sh
```
Expected: no warnings.

- [ ] **Step 3: Commit**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git add scripts/deploy/deploy-garmin.sh
git commit -m "feat(garmin): add deploy script with basicauth hashing and verification"
```

---

### Task 11: Full test suite run and branch-level check

**Files:** none created — verification only.

- [ ] **Step 1: Run the full Python test suite**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
source .venv/bin/activate
pytest tests/ -v --ignore=tests/test_backup_garmin.sh
```
Expected: all tests pass (Tasks 1-3's tests: `test_sync_lock.py`, `test_fetch_garmin.py`, `test_app.py`).

- [ ] **Step 2: Run the bash backup test**

```bash
bash /mnt/d/prg/plum-garmin-data-source/projects/garmin/tests/test_backup_garmin.sh
```
Expected: `All assertions passed.`

- [ ] **Step 3: Run shellcheck across every new shell script**

```bash
cd /mnt/d/prg/plum-garmin-data-source
shellcheck projects/garmin/backup_garmin.sh projects/garmin/docker-entrypoint-cron.sh \
    scripts/deploy/setup-garmin-vps.sh scripts/deploy/deploy-garmin.sh
```
Expected: no warnings.

- [ ] **Step 4: Confirm the image builds for real with backup_garmin.sh in place**

```bash
cd /mnt/d/prg/plum-garmin-data-source/projects/garmin
docker build -t garmin-verify .
```
Expected: build succeeds.

- [ ] **Step 5: git status sanity check**

```bash
cd /mnt/d/prg/plum-garmin-data-source
git status --short
```
Expected: clean (everything committed in prior tasks).

This task intentionally has no commit step — it's a verification checkpoint before deployment, which happens manually (VPS access, real Garmin credentials, real rclone config) outside this plan's automated steps.
