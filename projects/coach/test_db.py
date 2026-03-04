"""Tests for database operations."""
import pytest
from db import get_connection, upsert_activity, load_all_enriched, load_enriched_by_garmin_id


@pytest.fixture
def conn():
    c = get_connection()
    yield c
    # Clean up test data
    with c.cursor() as cur:
        cur.execute("DELETE FROM enriched_activities WHERE garmin_id = 999999999")


def test_connection(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1


def test_upsert_insert(conn):
    row = {
        "garmin_id": 999999999,
        "activity_date": "2026-01-01T10:00:00",
        "distance_m": 5000.0,
        "duration_s": 1800.0,
        "garmin_vo2max": 48.0,
        "vo2max_uth": 45.0,
        "vo2max_vdot": 33.0,
        "vo2max_hr_speed": 35.0,
        "vo2max_composite": 36.0,
    }
    upsert_activity(conn, row)

    result = load_enriched_by_garmin_id(conn, 999999999)
    assert result is not None
    assert result["garmin_vo2max"] == 48.0
    assert result["vo2max_composite"] == 36.0


def test_upsert_updates_existing(conn):
    row = {
        "garmin_id": 999999999,
        "activity_date": "2026-01-01T10:00:00",
        "distance_m": 5000.0,
        "duration_s": 1800.0,
        "vo2max_composite": 36.0,
    }
    upsert_activity(conn, row)

    row["vo2max_composite"] = 40.0
    upsert_activity(conn, row)

    result = load_enriched_by_garmin_id(conn, 999999999)
    assert result["vo2max_composite"] == 40.0


def test_load_all_enriched(conn):
    results = load_all_enriched(conn)
    assert isinstance(results, list)
