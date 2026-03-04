# VO2max Enrichment Pipeline Design

## Problem

analyze.py currently reads only Intervals.icu exports and computes metrics in-memory for a single HTML report run. Garmin data (291 runs, 280 daily VO2max readings, wellness data) sits unused. There's no persistent storage — every run recomputes from scratch.

## Solution

Extend analyze.py into an enrichment pipeline that:
1. Takes an activity ID (Garmin, Intervals.icu, or Strava) or defaults to latest
2. Loads data from all sources (Garmin + Intervals.icu)
3. Computes multiple VO2max estimates per run using different methods
4. Stores the enriched activity in Postgres (the `plum` database)
5. Always generates the HTML report (no flag needed)

## Architecture: Approach A (Activity-Centric Table)

One wide `enriched_activities` table. Each row = one run with source backlinks, raw metrics, and all computed VO2max estimates. Simple, queryable, honest.

## Database Schema

```sql
CREATE TABLE enriched_activities (
    id              SERIAL PRIMARY KEY,

    -- Source backlinks
    garmin_id       BIGINT UNIQUE,
    intervals_id    TEXT UNIQUE,
    strava_id       BIGINT UNIQUE,

    -- Core activity data (denormalized)
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

    -- Own VO2max estimates (computed)
    vo2max_uth      REAL,       -- (HRmax / RHR) × 15.3
    vo2max_vdot     REAL,       -- Daniels VDOT from run performance
    vo2max_hr_speed REAL,       -- HR-speed regression (Firstbeat-style)
    vo2max_composite REAL,      -- weighted blend

    -- Context for interpreting estimates
    rhr_on_day      REAL,
    hrv_on_day      REAL,
    weather_temp_f  REAL,
    weather_humidity REAL,

    -- Metadata
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ea_date ON enriched_activities(activity_date);
CREATE INDEX idx_ea_garmin ON enriched_activities(garmin_id);
```

UPSERT on garmin_id — re-running analyze.py updates existing records.

## VO2max Computation Methods

### Constants (from observed data)
- HRmax = 179 (observed max across 286 runs)
- HRrest = daily from `daily/*/rhr.json` (currently ~60)
- Warmup skip = 10 min, cooldown skip = 2 min (for stream analysis)

### Method 1: Uth Ratio
```
vo2max_uth = (HRmax / rhr_on_day) × 15.3
```
Same for every run on the same day. Changes only as RHR fluctuates. Baseline anchor.

### Method 2: VDOT (Daniels)
```
V = distance_m / (duration_s / 60)          # m/min
VO2cost = -4.60 + 0.182258×V + 0.000104×V²
T = duration_s / 60
%max = 0.8 + 0.189×e^(-0.0128×T) + 0.299×e^(-0.193×T)
vo2max_vdot = VO2cost / %max
```
From each run's distance and time. Easy runs produce lower VDOT than hard efforts — expected and useful.

### Method 3: HR-speed regression
```
%HRR = (avg_hr - rhr) / (HRmax - rhr)
V = speed in m/min (steady-state portion, skip first 10min)
VO2_at_pace = -4.60 + 0.182258×V + 0.000104×V²
vo2max_hr_speed = VO2_at_pace / %HRR
```
Requires %HRR > 40% to be meaningful. Uses Garmin activity details time-series for steady-state filtering.

### Method 4: Composite
```
Hard effort (>80% HRR, >20min):  VDOT 60% + HR-speed 30% + Uth 10%
Easy/moderate effort:            HR-speed 50% + Uth 30% + VDOT 20%
```
VDOT is most accurate at race-like intensity. HR-speed works best at moderate effort. Uth is the baseline.

## Data Flow

```
analyze.py [activity_id]
  │
  ├─ 1. Resolve activity ID
  │    ├─ No arg → latest run from Garmin list.json
  │    ├─ Numeric → Garmin activity ID
  │    ├─ i:xxx → Intervals.icu ID
  │    └─ s:xxx → Strava ID (future)
  │
  ├─ 2. Load source data
  │    ├─ Garmin: summary, details (streams), weather
  │    ├─ Garmin daily: RHR, HRV for that date
  │    ├─ Intervals.icu: detail (CTL/ATL), streams
  │    └─ Cross-reference by date+distance if IDs not linked
  │
  ├─ 3. Compute all VO2max estimates
  │
  ├─ 4. UPSERT to Postgres (enriched_activities)
  │
  └─ 5. Generate HTML report (always)
```

## CLI

```bash
python analyze.py                    # Enrich latest activity + report
python analyze.py 22038874815        # Enrich specific Garmin activity + report
python analyze.py --all              # Enrich all activities (backfill) + report
```

## Console Output

```
Activity: Leuven Running (2026-03-02, 8.4km, 6:50/km)

VO2max estimates:
  Garmin Firstbeat:   48.3
  Uth (HR ratio):     45.6  (HRmax=179, RHR=59)
  VDOT (Daniels):     31.2  (from this run's pace)
  HR-speed regress:   31.5  (77% HRR)
  ─────────────────────────
  Composite:          33.8

Context: temp=53°F, HRV=23 (below baseline 24-39)
Stored → enriched_activities (garmin_id=22038874815)
```

## Report Additions

New VO2max trend chart in the HTML report showing all methods over time: Garmin as one line, composite as another, VDOT as dots for hard efforts.

## Dependencies

- `psycopg2-binary` (Postgres driver) — new pip dependency
- Postgres running at localhost:5432 (plum database, already set up)

## Key Insight

Garmin says VO2max=48, but VDOT from actual performances says 30-33. The 15-point gap reveals running economy as the bottleneck — cardiovascular capacity is ahead of what the legs convert to speed. Tracking both over time shows whether economy is improving independently of cardiovascular fitness.

## Data Sources

| Source | Path | Key Fields |
|--------|------|------------|
| Garmin activities | `data/garmin/activities/list.json` | activityId, vO2MaxValue, averageHR, maxHR, distance, duration, averageRunningCadenceInStepsPerMinute |
| Garmin activity detail | `data/garmin/activities/{id}/details.json` | HR/pace/cadence time-series (17 metrics) |
| Garmin weather | `data/garmin/activities/{id}/weather.json` | temp, relativeHumidity |
| Garmin daily VO2max | `data/garmin/daily/{date}/max_metrics.json` | vo2MaxPreciseValue |
| Garmin daily RHR | `data/garmin/daily/{date}/rhr.json` | WELLNESS_RESTING_HEART_RATE |
| Garmin daily HRV | `data/garmin/daily/{date}/hrv.json` | lastNightAvg, baseline bands |
| Intervals.icu activities | `data/intervals/activities/{id}/detail.json` | icu_ctl, icu_atl, icu_training_load |
| Intervals.icu wellness | `data/intervals/wellness/all.json` | atl, ctl (vo2max field empty) |
