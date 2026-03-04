# VO2max Enrichment Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend analyze.py to compute per-run VO2max estimates (Uth, VDOT, HR-speed regression, composite), store them alongside Garmin's estimate in Postgres, and render a VO2max trend chart in the HTML report.

**Architecture:** analyze.py gains a new mode: when given an activity ID (or no args for latest), it loads data from Garmin + Intervals.icu JSON files, computes 4 VO2max estimates, upserts to Postgres `enriched_activities` table, and always generates the HTML report. The existing report pipeline remains intact; VO2max is additive.

**Tech Stack:** Python 3.12, psycopg2-binary (already installed), PostgreSQL 17 (running at localhost:5432, database `plum`, user `plum`, password in `/mnt/d/prg/plum/projects/db/.env`).

**Design doc:** `docs/plans/2026-03-04-vo2max-enrichment-design.md`

---

### Task 1: Create Postgres schema

**Files:**
- Create: `projects/coach/schema.sql`

**Step 1: Write the schema file**

```sql
-- VO2max enrichment pipeline schema
-- Run: docker exec db-postgres-1 psql -U plum -d plum -f /dev/stdin < schema.sql

CREATE TABLE IF NOT EXISTS enriched_activities (
    id              SERIAL PRIMARY KEY,

    -- Source backlinks
    garmin_id       BIGINT UNIQUE,
    intervals_id    TEXT UNIQUE,
    strava_id       BIGINT UNIQUE,

    -- Core activity data
    activity_date   TIMESTAMPTZ NOT NULL,
    distance_m      REAL NOT NULL,
    duration_s      REAL NOT NULL,
    moving_time_s   REAL,
    pace_minkm      REAL,
    avg_hr          REAL,
    max_hr          REAL,
    elevation_m     REAL,
    avg_cadence     REAL,
    avg_stride_m    REAL,
    training_load   REAL,

    -- Garmin VO2max (from source)
    garmin_vo2max   REAL,

    -- Intervals.icu fitness context
    intervals_ctl   REAL,
    intervals_atl   REAL,

    -- Own VO2max estimates
    vo2max_uth          REAL,
    vo2max_vdot         REAL,
    vo2max_hr_speed     REAL,
    vo2max_composite    REAL,

    -- Context
    rhr_on_day          REAL,
    hrv_on_day          REAL,
    weather_temp_f      REAL,
    weather_humidity    REAL,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ea_date ON enriched_activities(activity_date);
CREATE INDEX IF NOT EXISTS idx_ea_garmin ON enriched_activities(garmin_id);
```

**Step 2: Apply the schema**

Run: `docker exec -i db-postgres-1 psql -U plum -d plum < projects/coach/schema.sql`
Expected: `CREATE TABLE` and `CREATE INDEX` output, no errors.

**Step 3: Verify**

Run: `docker exec db-postgres-1 psql -U plum -d plum -c '\d enriched_activities'`
Expected: Table description with all columns listed.

**Step 4: Commit**

```bash
git add projects/coach/schema.sql
git commit -m "feat(coach): add enriched_activities schema for VO2max pipeline"
```

---

### Task 2: Write VO2max computation functions with tests

**Files:**
- Create: `projects/coach/vo2max.py`
- Create: `projects/coach/test_vo2max.py`

**Step 1: Write the test file**

```python
"""Tests for VO2max estimation methods."""
import math
import pytest
from vo2max import calc_uth, calc_vdot, calc_hr_speed, calc_composite


def test_uth_basic():
    """Uth formula: (HRmax/HRrest) * 15.3"""
    result = calc_uth(hr_max=179, rhr=60)
    assert abs(result - 45.6) < 0.5  # (179/60)*15.3 = 45.6


def test_uth_lower_rhr_means_higher_vo2():
    high = calc_uth(hr_max=179, rhr=50)
    low = calc_uth(hr_max=179, rhr=70)
    assert high > low


def test_vdot_5k_25min():
    """Known example from Daniels: 5K in 25:00 -> VDOT ~38.3"""
    result = calc_vdot(distance_m=5000, duration_s=25 * 60)
    assert 37 < result < 40


def test_vdot_longer_slower_gives_lower():
    fast = calc_vdot(distance_m=5000, duration_s=25 * 60)
    slow = calc_vdot(distance_m=5000, duration_s=35 * 60)
    assert fast > slow


def test_vdot_half_marathon():
    """HM in 2:10 -> VDOT ~33"""
    result = calc_vdot(distance_m=21097, duration_s=130 * 60)
    assert 32 < result < 35


def test_hr_speed_moderate_effort():
    """Moderate run: 6:30/km pace at 77% HRR should give VO2max ~30-35."""
    speed_m_per_min = 1000 / 6.5  # ~154 m/min
    result = calc_hr_speed(
        avg_speed_m_per_min=speed_m_per_min,
        avg_hr=152, hr_max=179, rhr=60
    )
    assert 28 < result < 40


def test_hr_speed_rejects_low_hr():
    """Below 40% HRR should return None (not meaningful)."""
    speed_m_per_min = 1000 / 8.0
    result = calc_hr_speed(
        avg_speed_m_per_min=speed_m_per_min,
        avg_hr=90, hr_max=179, rhr=60  # ~25% HRR
    )
    assert result is None


def test_composite_hard_effort():
    """Hard effort weights VDOT highest."""
    result = calc_composite(
        uth=46.0, vdot=38.0, hr_speed=35.0,
        pct_hrr=0.85, duration_s=1800
    )
    # Hard effort: VDOT 60% + HR-speed 30% + Uth 10%
    expected = 38.0 * 0.6 + 35.0 * 0.3 + 46.0 * 0.1
    assert abs(result - expected) < 0.1


def test_composite_easy_effort():
    """Easy effort weights HR-speed highest."""
    result = calc_composite(
        uth=46.0, vdot=30.0, hr_speed=35.0,
        pct_hrr=0.55, duration_s=3600
    )
    # Easy: HR-speed 50% + Uth 30% + VDOT 20%
    expected = 35.0 * 0.5 + 46.0 * 0.3 + 30.0 * 0.2
    assert abs(result - expected) < 0.1


def test_composite_handles_none_hr_speed():
    """When HR-speed is None (low HR), redistribute weights."""
    result = calc_composite(
        uth=46.0, vdot=30.0, hr_speed=None,
        pct_hrr=0.85, duration_s=1800
    )
    assert result is not None
    # Should be between uth and vdot
    assert 30.0 < result < 46.0
```

**Step 2: Run tests to verify they fail**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python -m pytest test_vo2max.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vo2max'`

**Step 3: Write the implementation**

```python
"""VO2max estimation methods.

Four approaches computed per run:
1. Uth ratio — (HRmax/HRrest) × 15.3
2. VDOT (Daniels) — from run distance and time
3. HR-speed regression — Firstbeat-style from HR and pace
4. Composite — weighted blend based on effort intensity
"""
import math

HR_MAX = 179  # Observed max across all runs


def calc_uth(hr_max: float, rhr: float) -> float:
    """Uth heart rate ratio method. Returns VO2max estimate."""
    return (hr_max / rhr) * 15.3


def calc_vdot(distance_m: float, duration_s: float) -> float:
    """Daniels VDOT from a single run's distance and time."""
    t_min = duration_s / 60.0
    v = distance_m / t_min  # m/min

    vo2_cost = -4.60 + 0.182258 * v + 0.000104 * v ** 2
    pct_max = (0.8
               + 0.1894393 * math.exp(-0.012778 * t_min)
               + 0.2989558 * math.exp(-0.1932605 * t_min))
    if pct_max <= 0:
        return 0.0
    return vo2_cost / pct_max


def calc_hr_speed(avg_speed_m_per_min: float, avg_hr: float,
                  hr_max: float, rhr: float) -> float | None:
    """Firstbeat-style HR-speed regression. Returns None if HR too low."""
    pct_hrr = (avg_hr - rhr) / (hr_max - rhr)
    if pct_hrr < 0.4:
        return None

    vo2_at_pace = -4.60 + 0.182258 * avg_speed_m_per_min + 0.000104 * avg_speed_m_per_min ** 2
    return vo2_at_pace / pct_hrr


def calc_composite(uth: float, vdot: float, hr_speed: float | None,
                   pct_hrr: float, duration_s: float) -> float:
    """Weighted composite from all methods. Weights depend on effort intensity."""
    is_hard = pct_hrr > 0.8 and duration_s > 1200

    if hr_speed is not None:
        if is_hard:
            return vdot * 0.6 + hr_speed * 0.3 + uth * 0.1
        else:
            return hr_speed * 0.5 + uth * 0.3 + vdot * 0.2
    else:
        # No HR-speed available — use VDOT and Uth only
        if is_hard:
            return vdot * 0.7 + uth * 0.3
        else:
            return uth * 0.6 + vdot * 0.4
```

**Step 4: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python -m pytest test_vo2max.py -v`
Expected: All 9 tests PASS.

**Step 5: Commit**

```bash
git add projects/coach/vo2max.py projects/coach/test_vo2max.py
git commit -m "feat(coach): add VO2max estimation functions with tests"
```

---

### Task 3: Add Garmin data loading functions

**Files:**
- Create: `projects/coach/garmin_loader.py`
- Create: `projects/coach/test_garmin_loader.py`

These functions read from the existing `data/garmin/` JSON files. No API calls.

**Step 1: Write the test file**

```python
"""Tests for Garmin data loading."""
import json
import os
from pathlib import Path
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


import pytest


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
    # Find a date with data
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
```

**Step 2: Run tests to verify they fail**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python -m pytest test_garmin_loader.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
"""Load and parse Garmin JSON data files."""
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data" / "garmin"

# Garmin details.json metric indices (from metricDescriptors)
_IDX_HR = 5           # directHeartRate
_IDX_SPEED = 10       # directSpeed (m/s)
_IDX_DURATION = 11    # sumDuration (seconds)
_IDX_DISTANCE = 8     # sumDistance (meters)

WARMUP_S = 600   # Skip first 10 minutes
COOLDOWN_S = 120  # Skip last 2 minutes


def load_garmin_runs() -> list[dict]:
    """Load all running activities from list.json."""
    path = DATA_DIR / "activities" / "list.json"
    with open(path, encoding="utf-8") as f:
        acts = json.load(f)
    runs = [a for a in acts
            if "running" in a.get("activityType", {}).get("typeKey", "").lower()
            and (a.get("distance") or 0) > 2000
            and (a.get("duration") or 0) > 600]
    runs.sort(key=lambda a: a.get("startTimeLocal", ""))
    return runs


def find_latest_run() -> dict | None:
    """Return the most recent running activity."""
    runs = load_garmin_runs()
    return runs[-1] if runs else None


def load_garmin_activity(garmin_id: int) -> dict:
    """Load and normalize a single Garmin activity into enrichment format."""
    # Find in list.json
    with open(DATA_DIR / "activities" / "list.json", encoding="utf-8") as f:
        acts = json.load(f)
    raw = next((a for a in acts if a.get("activityId") == garmin_id), None)
    if raw is None:
        raise ValueError(f"Activity {garmin_id} not found in list.json")

    act_dir = DATA_DIR / "activities" / str(garmin_id)

    # Parse date
    date_str = raw.get("startTimeLocal") or raw.get("startTimeGMT", "")
    activity_date = datetime.fromisoformat(date_str) if date_str else None

    # Load weather
    weather_temp = None
    weather_humidity = None
    weather_path = act_dir / "weather.json"
    if weather_path.exists():
        with open(weather_path, encoding="utf-8") as f:
            w = json.load(f)
        weather_temp = w.get("temp")
        weather_humidity = w.get("relativeHumidity")

    # Load VO2max from daily max_metrics (more precise than per-activity)
    garmin_vo2max = raw.get("vO2MaxValue")
    if activity_date:
        date_key = activity_date.strftime("%Y-%m-%d")
        mm_path = DATA_DIR / "daily" / date_key / "max_metrics.json"
        if mm_path.exists():
            with open(mm_path, encoding="utf-8") as f:
                mm = json.load(f)
            if mm and isinstance(mm, list) and mm[0].get("generic"):
                precise = mm[0]["generic"].get("vo2MaxPreciseValue")
                if precise:
                    garmin_vo2max = precise

    return {
        "garmin_id": garmin_id,
        "activity_date": activity_date,
        "distance_m": raw.get("distance", 0),
        "duration_s": raw.get("duration", 0),
        "moving_time_s": raw.get("movingDuration"),
        "avg_hr": raw.get("averageHR"),
        "max_hr": raw.get("maxHR"),
        "elevation_m": raw.get("elevationGain"),
        "avg_cadence": raw.get("averageRunningCadenceInStepsPerMinute"),
        "avg_stride_m": (raw.get("avgStrideLength") or 0) / 100.0 if raw.get("avgStrideLength") else None,
        "garmin_vo2max": garmin_vo2max,
        "weather_temp_f": weather_temp,
        "weather_humidity": weather_humidity,
    }


def load_garmin_daily_context(date_str: str) -> dict:
    """Load RHR and HRV for a given date (YYYY-MM-DD)."""
    day_dir = DATA_DIR / "daily" / date_str
    result = {"rhr": None, "hrv": None}

    # RHR
    rhr_path = day_dir / "rhr.json"
    if rhr_path.exists():
        with open(rhr_path, encoding="utf-8") as f:
            data = json.load(f)
        try:
            vals = data["allMetrics"]["metricsMap"]["WELLNESS_RESTING_HEART_RATE"]
            for v in vals:
                if v.get("value"):
                    result["rhr"] = v["value"]
                    break
        except (KeyError, TypeError):
            pass

    # HRV
    hrv_path = day_dir / "hrv.json"
    if hrv_path.exists():
        with open(hrv_path, encoding="utf-8") as f:
            data = json.load(f)
        try:
            result["hrv"] = data["hrvSummary"]["lastNightAvg"]
        except (KeyError, TypeError):
            pass

    return result


def extract_steady_state_speed(garmin_id: int) -> dict | None:
    """Extract avg speed and HR from steady-state portion of a run.

    Skips warmup (first 10 min) and cooldown (last 2 min).
    Returns dict with avg_speed_m_per_min and avg_hr, or None if data unavailable.
    """
    details_path = DATA_DIR / "activities" / str(garmin_id) / "details.json"
    if not details_path.exists():
        return None

    with open(details_path, encoding="utf-8") as f:
        data = json.load(f)

    # Build metric index map from descriptors
    idx_map = {}
    for desc in data.get("metricDescriptors", []):
        idx_map[desc["key"]] = desc["metricsIndex"]

    hr_idx = idx_map.get("directHeartRate")
    speed_idx = idx_map.get("directSpeed")
    duration_idx = idx_map.get("sumDuration")

    if hr_idx is None or speed_idx is None or duration_idx is None:
        return None

    metrics = data.get("activityDetailMetrics", [])
    if not metrics:
        return None

    total_duration = metrics[-1]["metrics"][duration_idx] if metrics else 0

    # Filter to steady state
    hrs = []
    speeds = []
    for m in metrics:
        vals = m["metrics"]
        t = vals[duration_idx] or 0
        if t < WARMUP_S or t > (total_duration - COOLDOWN_S):
            continue
        hr = vals[hr_idx]
        spd = vals[speed_idx]
        if hr and hr > 0 and spd and spd > 0:
            hrs.append(hr)
            speeds.append(spd)

    if not hrs:
        return None

    avg_hr = sum(hrs) / len(hrs)
    avg_speed_ms = sum(speeds) / len(speeds)

    return {
        "avg_speed_m_per_min": avg_speed_ms * 60,  # convert m/s to m/min
        "avg_hr": avg_hr,
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python -m pytest test_garmin_loader.py -v`
Expected: All 7 tests PASS.

**Step 5: Commit**

```bash
git add projects/coach/garmin_loader.py projects/coach/test_garmin_loader.py
git commit -m "feat(coach): add Garmin data loading for enrichment pipeline"
```

---

### Task 4: Add Postgres database layer

**Files:**
- Create: `projects/coach/db.py`
- Create: `projects/coach/test_db.py`

**Step 1: Write the test file**

```python
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
    c.commit()
    c.close()


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
```

**Step 2: Run tests to verify they fail**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python -m pytest test_db.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
"""Postgres operations for enriched activities."""
import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "plum",
    "user": "plum",
    "password": "Simatai0!",
}

# All columns that can be upserted (excluding id, created_at)
COLUMNS = [
    "garmin_id", "intervals_id", "strava_id",
    "activity_date", "distance_m", "duration_s", "moving_time_s",
    "pace_minkm", "avg_hr", "max_hr", "elevation_m",
    "avg_cadence", "avg_stride_m", "training_load",
    "garmin_vo2max", "intervals_ctl", "intervals_atl",
    "vo2max_uth", "vo2max_vdot", "vo2max_hr_speed", "vo2max_composite",
    "rhr_on_day", "hrv_on_day", "weather_temp_f", "weather_humidity",
]


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def upsert_activity(conn, row: dict) -> None:
    """Insert or update an enriched activity by garmin_id."""
    # Filter to columns that have values
    cols = [c for c in COLUMNS if c in row and row[c] is not None]
    vals = [row[c] for c in cols]

    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "garmin_id")
    updates += ", updated_at = NOW()"

    sql = f"""
        INSERT INTO enriched_activities ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (garmin_id) DO UPDATE SET {updates}
    """
    with conn.cursor() as cur:
        cur.execute(sql, vals)
    conn.commit()


def load_enriched_by_garmin_id(conn, garmin_id: int) -> dict | None:
    """Load a single enriched activity by Garmin ID."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM enriched_activities WHERE garmin_id = %s",
            (garmin_id,)
        )
        row = cur.fetchone()
    return dict(row) if row else None


def load_all_enriched(conn) -> list[dict]:
    """Load all enriched activities, ordered by date."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM enriched_activities ORDER BY activity_date"
        )
        return [dict(r) for r in cur.fetchall()]
```

**Step 4: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python -m pytest test_db.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add projects/coach/db.py projects/coach/test_db.py
git commit -m "feat(coach): add Postgres upsert/query layer for enriched activities"
```

---

### Task 5: Wire enrichment pipeline into analyze.py

**Files:**
- Modify: `projects/coach/analyze.py` (top-of-file imports, main function, CLI args)

**Step 1: Add imports at top of analyze.py (after existing imports, around line 11)**

After `from pathlib import Path`, add:

```python
from vo2max import calc_uth, calc_vdot, calc_hr_speed, calc_composite, HR_MAX
from garmin_loader import (
    load_garmin_runs, find_latest_run, load_garmin_activity,
    load_garmin_daily_context, extract_steady_state_speed,
)
from db import get_connection, upsert_activity, load_all_enriched
```

**Step 2: Add the `enrich_activity` function before `main()`**

Insert before `def main():` (around line 1920):

```python
def enrich_activity(garmin_id: int) -> dict:
    """Load a Garmin activity, compute VO2max estimates, store in Postgres."""
    # Load source data
    activity = load_garmin_activity(garmin_id)
    date_str = activity["activity_date"].strftime("%Y-%m-%d") if activity["activity_date"] else None

    # Daily context
    ctx = load_garmin_daily_context(date_str) if date_str else {"rhr": None, "hrv": None}
    rhr = ctx["rhr"]

    # Compute pace
    if activity["distance_m"] and activity["duration_s"]:
        activity["pace_minkm"] = activity["duration_s"] / activity["distance_m"] * 1000 / 60
    else:
        activity["pace_minkm"] = None

    # --- VO2max estimates ---
    # 1. Uth
    vo2_uth = calc_uth(HR_MAX, rhr) if rhr else None

    # 2. VDOT
    vo2_vdot = None
    if activity["distance_m"] > 0 and activity["duration_s"] > 0:
        vo2_vdot = calc_vdot(activity["distance_m"], activity["duration_s"])

    # 3. HR-speed regression (from steady-state time-series)
    vo2_hr_speed = None
    steady = extract_steady_state_speed(garmin_id)
    if steady and rhr:
        vo2_hr_speed = calc_hr_speed(
            avg_speed_m_per_min=steady["avg_speed_m_per_min"],
            avg_hr=steady["avg_hr"],
            hr_max=HR_MAX,
            rhr=rhr,
        )

    # 4. Composite
    vo2_composite = None
    pct_hrr = None
    if activity["avg_hr"] and rhr:
        pct_hrr = (activity["avg_hr"] - rhr) / (HR_MAX - rhr)
    if vo2_uth is not None and vo2_vdot is not None and pct_hrr is not None:
        vo2_composite = calc_composite(
            uth=vo2_uth,
            vdot=vo2_vdot,
            hr_speed=vo2_hr_speed,
            pct_hrr=pct_hrr,
            duration_s=activity["duration_s"],
        )

    # Build row
    row = {
        **activity,
        "vo2max_uth": vo2_uth,
        "vo2max_vdot": vo2_vdot,
        "vo2max_hr_speed": vo2_hr_speed,
        "vo2max_composite": vo2_composite,
        "rhr_on_day": rhr,
        "hrv_on_day": ctx["hrv"],
    }

    # Store in Postgres
    conn = get_connection()
    try:
        upsert_activity(conn, row)
    finally:
        conn.close()

    # Print summary
    name = f"{activity['distance_m']/1000:.1f}km" if activity["distance_m"] else "?"
    date = activity["activity_date"].strftime("%Y-%m-%d") if activity["activity_date"] else "?"
    pace = fmt_pace(activity["pace_minkm"]) if activity.get("pace_minkm") else "--:--"

    print(f"\nActivity: {date}, {name}, {pace}/km")
    print(f"\nVO2max estimates:")
    print(f"  Garmin Firstbeat:   {activity['garmin_vo2max'] or '—'}")
    print(f"  Uth (HR ratio):     {vo2_uth:.1f}" if vo2_uth else "  Uth (HR ratio):     —")
    if vo2_uth and rhr:
        print(f"                      (HRmax={HR_MAX}, RHR={rhr:.0f})")
    print(f"  VDOT (Daniels):     {vo2_vdot:.1f}" if vo2_vdot else "  VDOT (Daniels):     —")
    print(f"  HR-speed regress:   {vo2_hr_speed:.1f}" if vo2_hr_speed else "  HR-speed regress:   —")
    if pct_hrr:
        print(f"                      ({pct_hrr:.0%} HRR)")
    print(f"  {'─' * 25}")
    print(f"  Composite:          {vo2_composite:.1f}" if vo2_composite else "  Composite:          —")

    if activity.get("weather_temp_f") or ctx.get("hrv"):
        parts = []
        if activity.get("weather_temp_f"):
            parts.append(f"temp={activity['weather_temp_f']}°F")
        if ctx.get("hrv"):
            parts.append(f"HRV={ctx['hrv']}")
        print(f"\n  Context: {', '.join(parts)}")

    print(f"\n  Stored → enriched_activities (garmin_id={garmin_id})")
    return row
```

**Step 3: Update `main()` to support activity ID argument and always run report**

Replace the existing `main()` function:

```python
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate running coach report.")
    parser.add_argument("activity_id", nargs="?", default=None,
                        help="Garmin activity ID to enrich (default: latest run)")
    parser.add_argument("--all", action="store_true",
                        help="Enrich all running activities (backfill)")
    parser.add_argument("--no-ai", action="store_true",
                        help="Skip AI coach commentary (faster, no Claude CLI needed)")
    parser.add_argument("--model", choices=["sonnet", "haiku", "opus"], default="sonnet",
                        help="Claude model for AI commentary (default: sonnet)")
    parser.add_argument("--thinking-budget", type=int, default=10000,
                        help="Extended thinking token budget for opus (default: 10000)")
    args = parser.parse_args()

    # --- Enrichment ---
    if args.all:
        print("Enriching all activities...")
        runs = load_garmin_runs()
        for i, run in enumerate(runs):
            print(f"\n[{i + 1}/{len(runs)}]", end="")
            try:
                enrich_activity(run["activityId"])
            except Exception as e:
                print(f"  ERROR: {e}")
    else:
        if args.activity_id:
            garmin_id = int(args.activity_id)
        else:
            latest = find_latest_run()
            if not latest:
                print("No running activities found.")
                sys.exit(1)
            garmin_id = latest["activityId"]
        enrich_activity(garmin_id)

    # --- Report (always) ---
    print("\nLoading activities for report...")
    activities = load_activities()
    runs = filter_runs(activities)
    print(f"  {len(runs)} runs after filtering (>2km, >10min)")

    if not runs:
        print("No qualifying runs found.")
        sys.exit(1)

    print("Computing metrics...")
    metrics = build_metrics(runs)

    print("Saving metrics.json...")
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    panel_discussions = []
    if args.no_ai:
        print("Skipping AI coach commentary (--no-ai)")
    else:
        print(f"Getting coaching panel discussions (model: {args.model})...")
        panel_discussions = get_panel_discussions(metrics, model=args.model,
                                                    thinking_budget=args.thinking_budget)
        if panel_discussions:
            print(f"  Got {len(panel_discussions)} panel sections")
        else:
            print("  No AI commentary (claude CLI unavailable or errored)")

    print("Building report...")
    html = build_report(runs, panel_discussions)

    print(f"Writing {REPORT_PATH}...")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print("Opening in browser...")
    webbrowser.open(str(REPORT_PATH))
    print("Done.")
```

**Step 4: Test the pipeline end-to-end**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python analyze.py --no-ai`
Expected: Enrichment summary printed, then report generated. Verify with:
`docker exec db-postgres-1 psql -U plum -d plum -c "SELECT garmin_id, garmin_vo2max, vo2max_uth, vo2max_vdot, vo2max_hr_speed, vo2max_composite FROM enriched_activities LIMIT 5"`

**Step 5: Commit**

```bash
git add projects/coach/analyze.py
git commit -m "feat(coach): wire VO2max enrichment pipeline into analyze.py"
```

---

### Task 6: Add VO2max trend chart to HTML report

**Files:**
- Modify: `projects/coach/analyze.py` (add a new report section function, wire into `build_report`)

**Step 1: Find where to add the new section**

The report sections are called from `build_report()` around lines 1863-1915. Add a new section function `section_vo2max_trend()` and call it from `build_report()`.

**Step 2: Write the `section_vo2max_trend` function**

Insert before `def build_report()`:

```python
def section_vo2max_trend():
    """VO2max trend chart comparing Garmin vs own estimates over time."""
    try:
        conn = get_connection()
        rows = load_all_enriched(conn)
        conn.close()
    except Exception:
        return ""

    if not rows:
        return ""

    # Filter to rows with at least one VO2max value
    rows = [r for r in rows if r.get("garmin_vo2max") or r.get("vo2max_composite")]
    if not rows:
        return ""

    html = '<div class="section"><h2>VO2max Estimates</h2>'

    # Build chart data
    dates = []
    garmin_vals = []
    composite_vals = []
    vdot_vals = []
    uth_vals = []
    for r in rows:
        d = r["activity_date"]
        if d is None:
            continue
        day_num = (d - rows[0]["activity_date"]).total_seconds() / 86400
        dates.append(day_num)
        garmin_vals.append(r.get("garmin_vo2max"))
        composite_vals.append(r.get("vo2max_composite"))
        vdot_vals.append(r.get("vo2max_vdot"))
        uth_vals.append(r.get("vo2max_uth"))

    # Date labels for x-axis
    first_date = rows[0]["activity_date"]
    x_labels = []
    for r in rows:
        d = r["activity_date"]
        if d and d.day <= 7:  # Label ~first of each month
            day_num = (d - first_date).total_seconds() / 86400
            x_labels.append((d.strftime("%b %y"), day_num))

    # Garmin line + composite line
    chart = SvgChart(width=700, height=300)

    # Filter None values for each series
    garmin_xs = [dates[i] for i in range(len(dates)) if garmin_vals[i] is not None]
    garmin_ys = [v for v in garmin_vals if v is not None]
    comp_xs = [dates[i] for i in range(len(dates)) if composite_vals[i] is not None]
    comp_ys = [v for v in composite_vals if v is not None]
    vdot_xs = [dates[i] for i in range(len(dates)) if vdot_vals[i] is not None]
    vdot_ys = [v for v in vdot_vals if v is not None]

    extra_lines = []
    if comp_xs:
        extra_lines.append((comp_xs, comp_ys, "#FF6B35"))
    if vdot_xs:
        extra_lines.append((vdot_xs, vdot_ys, "#4ECDC4"))

    if garmin_xs:
        svg = chart.line(garmin_xs, garmin_ys, color="#00FF00",
                         title="VO2max Estimates Over Time",
                         x_labels=x_labels,
                         extra_lines=extra_lines if extra_lines else None,
                         trend=False)
        html += svg

    # Legend
    html += '<div style="text-align:center; margin-top:8px; font-size:13px;">'
    html += '<span style="color:#00FF00">&#9632; Garmin</span> &nbsp; '
    html += '<span style="color:#FF6B35">&#9632; Composite</span> &nbsp; '
    html += '<span style="color:#4ECDC4">&#9632; VDOT</span>'
    html += '</div>'

    # Latest values table
    latest = rows[-1]
    html += '<table style="margin:16px auto; border-collapse:collapse;">'
    html += '<tr><th style="padding:4px 16px; text-align:left;">Method</th>'
    html += '<th style="padding:4px 16px; text-align:right;">Latest</th></tr>'
    for label, key, color in [
        ("Garmin Firstbeat", "garmin_vo2max", "#00FF00"),
        ("Uth (HR ratio)", "vo2max_uth", "#FFD700"),
        ("VDOT (Daniels)", "vo2max_vdot", "#4ECDC4"),
        ("HR-speed regression", "vo2max_hr_speed", "#FF69B4"),
        ("Composite", "vo2max_composite", "#FF6B35"),
    ]:
        val = latest.get(key)
        val_str = f"{val:.1f}" if val else "—"
        html += f'<tr><td style="padding:4px 16px; color:{color};">{label}</td>'
        html += f'<td style="padding:4px 16px; text-align:right;">{val_str}</td></tr>'
    html += '</table>'

    html += '</div>'
    return html
```

**Step 3: Wire into `build_report()`**

Find the `build_report()` function and add a call to `section_vo2max_trend()`. Insert the VO2max section early in the report (after the coaching panel, before existing sections). Look for where sections are concatenated and add:

```python
html += section_vo2max_trend()
```

**Step 4: Test the report**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python analyze.py --no-ai`
Expected: Report opens in browser with VO2max trend chart showing Garmin (green), composite (orange), and VDOT (teal) lines plus a latest-values table.

**Step 5: Commit**

```bash
git add projects/coach/analyze.py
git commit -m "feat(coach): add VO2max trend chart to HTML report"
```

---

### Task 7: Run full backfill and verify

**Step 1: Backfill all activities**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python analyze.py --all --no-ai`
Expected: All ~291 running activities enriched and stored. Report generated with full trend chart.

**Step 2: Verify data in Postgres**

Run: `docker exec db-postgres-1 psql -U plum -d plum -c "SELECT COUNT(*) FROM enriched_activities"`
Expected: ~291 rows.

Run: `docker exec db-postgres-1 psql -U plum -d plum -c "SELECT activity_date::date, garmin_vo2max, vo2max_composite, vo2max_vdot FROM enriched_activities ORDER BY activity_date DESC LIMIT 10"`
Expected: Recent activities with all VO2max columns populated.

**Step 3: Run all tests**

Run: `cd /mnt/d/prg/plum/projects/coach && .venv/bin/python -m pytest test_vo2max.py test_garmin_loader.py test_db.py -v`
Expected: All tests PASS.

**Step 4: Final commit**

Update CLAUDE.md if needed, then:

```bash
git add -A
git commit -m "feat(coach): complete VO2max enrichment pipeline with backfill"
```
