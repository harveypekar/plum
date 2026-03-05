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
