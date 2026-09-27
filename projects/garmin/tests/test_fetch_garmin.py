"""Tests for fetch_garmin.py's unattended-auth, lock, and status behavior."""
import fcntl
import json
import sys
from datetime import date

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


def test_fetch_activities_calls_get_activities_by_date_exactly_once(tmp_path, monkeypatch):
    """get_activities_by_date() already paginates internally and returns the
    full result set in one call. fetch_activities() must not loop and re-call
    it — the real bug this pins caused an unbounded loop against the live
    Garmin API that kept re-fetching (and duplicating) the same activities
    forever, since a full-history batch is always >= 100 items and never
    triggers the old (bogus) "last page" check."""
    monkeypatch.setattr(fetch_garmin, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_garmin.time, "sleep", lambda seconds: None)

    call_count = 0

    class FakeGarmin:
        def get_activities_by_date(self, start_date, end_date):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RuntimeError("get_activities_by_date called more than once")
            return [
                {"activityId": i, "startTimeLocal": "2026-01-01 00:00:00"}
                for i in range(150)
            ]

    result = fetch_garmin.fetch_activities(FakeGarmin(), date(2026, 1, 2))

    assert call_count == 1
    assert len(result) == 150
    saved = json.loads((tmp_path / "activities" / "list.json").read_text())
    assert len(saved) == 150


def _patch_run_fetch_collaborators(monkeypatch, activities, seen):
    """Stub every _run_fetch collaborator except the ones under test, and
    record what fetch_activity_details/fetch_daily/fetch_range_data are
    actually called with, into `seen`."""
    monkeypatch.setattr(fetch_garmin, "authenticate", lambda: object())
    monkeypatch.setattr(fetch_garmin, "fetch_profile", lambda garmin: None)
    monkeypatch.setattr(fetch_garmin, "fetch_devices", lambda garmin: None)
    monkeypatch.setattr(fetch_garmin, "fetch_gear", lambda garmin: None)
    monkeypatch.setattr(fetch_garmin, "fetch_badges_and_challenges", lambda garmin: None)
    monkeypatch.setattr(fetch_garmin, "fetch_goals", lambda garmin: None)
    monkeypatch.setattr(fetch_garmin, "fetch_workouts", lambda garmin: None)
    monkeypatch.setattr(fetch_garmin, "fetch_weekly", lambda garmin, today, full: None)
    monkeypatch.setattr(
        fetch_garmin, "fetch_activities", lambda garmin, today, full: activities
    )
    monkeypatch.setattr(
        fetch_garmin, "fetch_activity_details",
        lambda garmin, acts, full: seen.setdefault("details", acts),
    )
    monkeypatch.setattr(
        fetch_garmin, "fetch_daily",
        lambda garmin, acts, today, full: seen.setdefault("daily", acts),
    )
    monkeypatch.setattr(
        fetch_garmin, "fetch_range_data",
        lambda garmin, acts, today: seen.setdefault("range", acts),
    )


class _Args:
    def __init__(self, full=False, limit=None):
        self.full = full
        self.limit = limit


def test_run_fetch_with_limit_only_fetches_details_for_most_recent_n(monkeypatch, tmp_path):
    """--limit N must restrict the expensive per-activity/per-day fetching
    to the N most recent activities, while the full activity list is still
    fetched as usual — this lets a first-time run against a real account be
    tested safely on a small slice before committing to a full historical
    backfill (each of those N activities can still trigger dozens of daily
    endpoint calls, so this must be the *count* of activities let through,
    not merely a hint)."""
    monkeypatch.setattr(fetch_garmin, "DATA_DIR", tmp_path)
    activities = [
        {"activityId": 1, "startTimeLocal": "2026-01-01 00:00:00"},
        {"activityId": 2, "startTimeLocal": "2026-03-01 00:00:00"},
        {"activityId": 3, "startTimeLocal": "2026-02-01 00:00:00"},
    ]
    seen = {}
    _patch_run_fetch_collaborators(monkeypatch, activities, seen)

    fetch_garmin._run_fetch(_Args(limit=2), "2026-01-01T00:00:00Z")

    assert [a["activityId"] for a in seen["details"]] == [2, 3]
    assert [a["activityId"] for a in seen["daily"]] == [2, 3]
    assert [a["activityId"] for a in seen["range"]] == [2, 3]


def test_run_fetch_without_limit_passes_full_activity_list(monkeypatch, tmp_path):
    """No --limit (the default, production path) must not truncate
    anything — this guards against a regression in the slicing logic
    accidentally clipping the normal unattended run."""
    monkeypatch.setattr(fetch_garmin, "DATA_DIR", tmp_path)
    activities = [
        {"activityId": i, "startTimeLocal": "2026-01-01 00:00:00"} for i in range(5)
    ]
    seen = {}
    _patch_run_fetch_collaborators(monkeypatch, activities, seen)

    fetch_garmin._run_fetch(_Args(limit=None), "2026-01-01T00:00:00Z")

    assert len(seen["details"]) == 5
    assert len(seen["daily"]) == 5
    assert len(seen["range"]) == 5
