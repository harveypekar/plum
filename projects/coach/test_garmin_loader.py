"""Tests for Garmin data loading."""
import json
import os
from pathlib import Path
import pytest
from garmin_loader import (
    load_garmin_activity,
    load_garmin_daily_context,
    load_garmin_runs,
    find_latest_run,
    extract_steady_state_speed,
)

DATA_DIR = Path(__file__).resolve().parent / "data" / "garmin"


@pytest.fixture
def sample_activity_id():
    """Get a real running activity ID from the data."""
    with open(DATA_DIR / "activities" / "list.json") as f:
        acts = json.load(f)
    for a in acts:
        if "running" in a.get("activityType", {}).get("typeKey", ""):
            return a["activityId"]
    pytest.skip("No running activities in data")


def test_load_garmin_runs():
    runs = load_garmin_runs()
    assert len(runs) > 0
    assert all("activityId" in r for r in runs)
    assert all("running" in r["activityType"]["typeKey"] for r in runs)


def test_find_latest_run():
    run = find_latest_run()
    assert run is not None
    assert "activityId" in run
    assert "distance" in run


def test_load_garmin_activity(sample_activity_id):
    activity = load_garmin_activity(sample_activity_id)
    assert activity["garmin_id"] == sample_activity_id
    assert activity["distance_m"] > 0
    assert activity["duration_s"] > 0
    assert activity["activity_date"] is not None


def test_load_garmin_activity_includes_weather(sample_activity_id):
    activity = load_garmin_activity(sample_activity_id)
    # Weather may be None if file missing, but key must exist
    assert "weather_temp_f" in activity
    assert "weather_humidity" in activity


def test_load_garmin_activity_includes_vo2max(sample_activity_id):
    activity = load_garmin_activity(sample_activity_id)
    assert "garmin_vo2max" in activity


def test_load_daily_context():
    """Load RHR, HRV for a date that has data."""
    daily_dir = DATA_DIR / "daily"
    dates = sorted(os.listdir(daily_dir))
    ctx = load_garmin_daily_context(dates[-1])
    assert "rhr" in ctx
    assert "hrv" in ctx


def test_extract_steady_state_speed(sample_activity_id):
    """Extract steady-state speed from activity details (skip warmup)."""
    result = extract_steady_state_speed(sample_activity_id)
    # May be None if details.json missing, but should work for real data
    if result is not None:
        assert result["avg_speed_m_per_min"] > 0
        assert result["avg_hr"] > 0
