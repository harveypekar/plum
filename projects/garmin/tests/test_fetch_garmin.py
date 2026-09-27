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
