"""Tests for the FastAPI dev dashboard."""
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


def _write_day(data_dir, day, files):
    day_dir = data_dir / "daily" / day
    day_dir.mkdir(parents=True)
    for filename, content in files.items():
        (day_dir / filename).write_text(json.dumps(content) if not isinstance(content, str) else content)
    return day_dir


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


def test_dashboard_escapes_html_in_error_field(client):
    # status.json's error field can contain text sourced from the Garmin
    # API — it must be HTML-escaped before interpolation, not injected raw.
    status = {
        "success": False,
        "started_at": "2026-09-22T00:00:00Z",
        "finished_at": None,
        "counts": {},
        "error": "<script>alert('xss')</script> & \"quoted\"",
    }
    app_module.STATUS_PATH.write_text(json.dumps(status))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<script>alert" not in resp.text
    assert "&lt;script&gt;" in resp.text


def test_dashboard_with_corrupt_status_does_not_crash(client):
    app_module.STATUS_PATH.write_text("{not valid json")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "unreadable" in resp.text.lower()


def test_dashboard_with_no_daily_data(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No daily data yet." in resp.text


def test_dashboard_shows_only_last_10_days_sorted_descending(client):
    for i in range(12):
        _write_day(app_module.DATA_DIR, f"2026-09-{i + 1:02d}", {"summary.json": {"steps": i}})

    resp = client.get("/")
    assert resp.status_code == 200
    # Newest 10 (2026-09-03 .. 2026-09-12) shown, oldest 2 excluded.
    for excluded in ("2026-09-01", "2026-09-02"):
        assert excluded not in resp.text
    for included in ("2026-09-03", "2026-09-12"):
        assert included in resp.text
    # Sorted newest-first: 09-12 must appear before 09-03 in the markup.
    assert resp.text.index("2026-09-12") < resp.text.index("2026-09-03")


def test_dashboard_recent_day_shows_fetched_filenames(client):
    _write_day(app_module.DATA_DIR, "2026-09-20", {"sleep.json": {"value": 1}, "hrv.json": {"value": 2}})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "sleep.json" in resp.text
    assert "hrv.json" in resp.text
    assert "2026-09-20 (2 files)" in resp.text


def test_dashboard_recent_day_shows_field_keys(client):
    _write_day(
        app_module.DATA_DIR,
        "2026-09-20",
        {"summary.json": {"restingHeartRate": 50, "nested": {"totalSteps": 1234}}},
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert "restingHeartRate" in resp.text
    assert "totalSteps" in resp.text


def test_dashboard_truncates_long_lists_but_keeps_field_shape(client):
    samples = [[i, 60 + i] for i in range(50)]
    _write_day(app_module.DATA_DIR, "2026-09-20", {"heart_rates.json": {"heartRateValues": samples}})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "... 47 more" in resp.text
    # Only the first MAX_LIST_PREVIEW samples are rendered verbatim.
    assert "63" not in resp.text
    assert "60" in resp.text


def test_dashboard_escapes_html_in_daily_data(client):
    _write_day(app_module.DATA_DIR, "2026-09-20", {"summary.json": {"note": "<script>alert(1)</script>"}})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<script>alert" not in resp.text
    assert "&lt;script&gt;" in resp.text


def test_dashboard_unreadable_daily_file_does_not_crash(client):
    _write_day(app_module.DATA_DIR, "2026-09-20", {"corrupt.json": "{not valid json"})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "unreadable" in resp.text.lower()


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
