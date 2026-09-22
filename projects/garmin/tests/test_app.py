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


# Note: variants below use percent-encoded dot/slash segments (%2e, %2f), not
# literal "../". httpx's URL parser applies RFC 3986 dot-segment removal to
# literal ".." *client-side*, before the request is ever sent — a request for
# "/browse/../../etc/passwd" never reaches the server as that path at all, so
# a test built on it would pass without exercising _safe_resolve(). Percent
# encoding the "." and "/" bytes defeats that client-side normalization, so
# the string actually arrives at the ASGI app (Starlette decodes it while
# routing the {path:path} parameter) and genuinely exercises the guard.
@pytest.mark.parametrize(
    "attack_path",
    [
        "%2e%2e/%2e%2e/etc/passwd",  # doubled ../ , percent-encoded
        "....//....//etc/passwd",  # defeats naive "strip '../' once" sanitizers
        "/etc/passwd",  # absolute path: DATA_DIR / "/etc/passwd" == Path("/etc/passwd")
        "//etc/passwd",  # leading double slash
        "activities/..%2F..%2F..%2Fetc%2Fpasswd",  # traversal from inside a real subdir
        "..%2Foutside_secret.json",  # a file that actually exists just above DATA_DIR
    ],
)
def test_browse_blocks_path_traversal_variants(client, tmp_path, attack_path):
    # Plant a real file just outside DATA_DIR so a bypass would actually leak
    # content, not just 404 because nothing happens to exist at that path.
    (tmp_path / "outside_secret.json").write_text('{"leaked": true}')

    resp = client.get(f"/browse/{attack_path}")
    assert resp.status_code == 404
    # Pin the detail to the app's own guard (_safe_resolve's HTTPException),
    # not Starlette's router-level "Not Found" for an unmatched route — a
    # plain status-code check can't tell those apart, and a future routing
    # change could silently stop exercising _safe_resolve() while this test
    # kept passing for the wrong reason.
    assert resp.json()["detail"] == "Not found"


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
