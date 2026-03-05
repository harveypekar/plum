-- Plum: Garmin + Intervals.icu data schema + RAG research knowledge base
-- All tables use ON CONFLICT upserts for idempotent loading.

-- ============================================================
-- Table 1: garmin_activities
-- Source: data/garmin/activities/list.json
-- ============================================================
CREATE TABLE IF NOT EXISTS garmin_activities (
    activity_id             BIGINT PRIMARY KEY,
    activity_name           TEXT,
    start_time_local        TIMESTAMP NOT NULL,
    start_time_gmt          TIMESTAMPTZ NOT NULL,
    end_time_gmt            TIMESTAMPTZ,
    activity_type           TEXT NOT NULL,
    event_type              TEXT,
    distance                NUMERIC(12,2),
    duration                NUMERIC(10,2),
    elapsed_duration        NUMERIC(10,2),
    moving_duration         NUMERIC(10,2),
    elevation_gain          NUMERIC(8,2),
    elevation_loss          NUMERIC(8,2),
    avg_speed               NUMERIC(8,4),
    max_speed               NUMERIC(8,4),
    calories                NUMERIC(8,1),
    avg_hr                  SMALLINT,
    max_hr                  SMALLINT,
    avg_cadence             NUMERIC(6,2),
    max_cadence             NUMERIC(6,2),
    steps                   INTEGER,
    avg_stride_length       NUMERIC(6,2),
    vo2max                  NUMERIC(4,1),
    training_effect_label   TEXT,
    start_lat               NUMERIC(10,6),
    start_lon               NUMERIC(10,6),
    end_lat                 NUMERIC(10,6),
    end_lon                 NUMERIC(10,6),
    location_name           TEXT,
    device_id               BIGINT,
    sport_type_id           SMALLINT,
    lap_count               SMALLINT,
    has_polyline            BOOLEAN DEFAULT FALSE,
    pr                      BOOLEAN DEFAULT FALSE,
    manual_activity         BOOLEAN DEFAULT FALSE,
    moderate_intensity_min  SMALLINT,
    vigorous_intensity_min  SMALLINT,
    min_elevation           NUMERIC(8,2),
    max_elevation           NUMERIC(8,2),
    water_estimated         NUMERIC(6,1),
    begin_timestamp         BIGINT,
    raw                     JSONB
);

CREATE INDEX IF NOT EXISTS idx_garmin_act_start ON garmin_activities(start_time_gmt);
CREATE INDEX IF NOT EXISTS idx_garmin_act_type ON garmin_activities(activity_type);


-- ============================================================
-- Table 2: intervals_activities
-- Source: data/intervals/activities/list.json
-- ============================================================
CREATE TABLE IF NOT EXISTS intervals_activities (
    id                      TEXT PRIMARY KEY,
    external_id             TEXT,
    start_date_local        TIMESTAMP NOT NULL,
    start_date              TIMESTAMPTZ NOT NULL,
    type                    TEXT NOT NULL,
    name                    TEXT,
    distance                NUMERIC(12,2),
    elapsed_time            INTEGER,
    moving_time             INTEGER,
    recording_time          INTEGER,
    total_elevation_gain    NUMERIC(8,2),
    total_elevation_loss    NUMERIC(8,2),
    avg_speed               NUMERIC(8,4),
    max_speed               NUMERIC(8,4),
    avg_hr                  SMALLINT,
    max_hr                  SMALLINT,
    avg_cadence             NUMERIC(6,2),
    calories                NUMERIC(8,1),
    gap                     NUMERIC(8,4),
    training_load           INTEGER,
    atl                     NUMERIC(8,2),
    ctl                     NUMERIC(8,2),
    weight                  NUMERIC(5,1),
    lthr                    SMALLINT,
    device_name             TEXT,
    file_type               TEXT,
    commute                 BOOLEAN DEFAULT FALSE,
    race                    BOOLEAN DEFAULT FALSE,
    trainer                 BOOLEAN,
    icu_hr_zones            INTEGER[],
    icu_power_zones         INTEGER[],
    warmup_time             INTEGER,
    cooldown_time           INTEGER,
    raw                     JSONB
);

CREATE INDEX IF NOT EXISTS idx_icu_act_start ON intervals_activities(start_date);
CREATE INDEX IF NOT EXISTS idx_icu_act_type ON intervals_activities(type);
CREATE INDEX IF NOT EXISTS idx_icu_act_external ON intervals_activities(external_id);


-- ============================================================
-- Table 3: garmin_activity_details
-- Source: data/garmin/activities/{id}/*.json
-- ============================================================
CREATE TABLE IF NOT EXISTS garmin_activity_details (
    activity_id             BIGINT PRIMARY KEY REFERENCES garmin_activities(activity_id),
    weather_temp            NUMERIC(5,1),
    weather_apparent_temp   NUMERIC(5,1),
    weather_humidity        SMALLINT,
    weather_wind_speed      NUMERIC(5,1),
    weather_wind_direction  SMALLINT,
    weather_condition       TEXT,
    hr_zone1_secs           INTEGER,
    hr_zone2_secs           INTEGER,
    hr_zone3_secs           INTEGER,
    hr_zone4_secs           INTEGER,
    hr_zone5_secs           INTEGER,
    raw_summary             JSONB,
    raw_splits              JSONB,
    raw_split_summaries     JSONB,
    raw_typed_splits        JSONB,
    raw_hr_zones            JSONB,
    raw_power_zones         JSONB,
    raw_exercise_sets       JSONB,
    raw_gear                JSONB,
    raw_weather             JSONB
);


-- ============================================================
-- Table 4: garmin_activity_streams
-- Source: data/garmin/activities/{id}/details.json -> activityDetailMetrics
-- ============================================================
CREATE TABLE IF NOT EXISTS garmin_activity_streams (
    activity_id             BIGINT PRIMARY KEY REFERENCES garmin_activities(activity_id),
    timestamps              BIGINT[],
    distances               NUMERIC[],
    heart_rates             SMALLINT[],
    cadences                NUMERIC[],
    speeds                  NUMERIC[],
    latitudes               NUMERIC[],
    longitudes              NUMERIC[],
    elevations              NUMERIC[],
    corrected_elevations    NUMERIC[],
    vertical_speeds         NUMERIC[],
    durations               NUMERIC[],
    moving_durations        NUMERIC[],
    elapsed_durations       NUMERIC[],
    body_batteries          SMALLINT[],
    fractional_cadences     NUMERIC[]
);


-- ============================================================
-- Table 5: intervals_activity_streams
-- Source: data/intervals/activities/{id}/streams.json
-- ============================================================
CREATE TABLE IF NOT EXISTS intervals_activity_streams (
    id                      TEXT PRIMARY KEY REFERENCES intervals_activities(id),
    time                    INTEGER[],
    distance                NUMERIC[],
    velocity                NUMERIC[],
    heart_rate              SMALLINT[],
    cadence                 NUMERIC[],
    power                   SMALLINT[],
    altitude                NUMERIC[],
    latitudes               NUMERIC[],
    longitudes              NUMERIC[],
    grade                   NUMERIC[],
    temp                    NUMERIC[]
);


-- ============================================================
-- Table 6: intervals_activity_details
-- Source: data/intervals/activities/{id}/detail.json
-- ============================================================
CREATE TABLE IF NOT EXISTS intervals_activity_details (
    id                      TEXT PRIMARY KEY REFERENCES intervals_activities(id),
    hr_load                 NUMERIC(8,2),
    pace_load               NUMERIC(8,2),
    power_load              NUMERIC(8,2),
    hr_load_type            TEXT,
    polarization_index      NUMERIC(6,4),
    icu_intensity           NUMERIC(8,4),
    icu_lap_count           SMALLINT,
    pace                    NUMERIC(8,4),
    decoupling              NUMERIC(6,2),
    icu_efficiency_factor   NUMERIC(8,4),
    icu_variability_index   NUMERIC(6,4),
    athlete_max_hr          SMALLINT,
    average_altitude        NUMERIC(8,2),
    min_altitude            NUMERIC(8,2),
    max_altitude            NUMERIC(8,2),
    average_weather_temp    NUMERIC(5,1),
    min_weather_temp        NUMERIC(5,1),
    max_weather_temp        NUMERIC(5,1),
    average_feels_like      NUMERIC(5,1),
    average_wind_speed      NUMERIC(5,1),
    average_wind_gust       NUMERIC(5,1),
    prevailing_wind_deg     SMALLINT,
    headwind_percent        NUMERIC(5,1),
    tailwind_percent        NUMERIC(5,1),
    average_clouds          NUMERIC(5,1),
    max_rain                NUMERIC(5,1),
    max_snow                NUMERIC(5,1),
    source                  TEXT,
    stream_types            TEXT[],
    recording_stops         INTEGER[],
    interval_summary        TEXT[],
    icu_zone_times          NUMERIC[],
    pace_zone_times         NUMERIC[],
    gap_zone_times          NUMERIC[],
    icu_intervals           JSONB,
    icu_groups              JSONB,
    raw                     JSONB NOT NULL
);


-- ============================================================
-- Table 7: garmin_daily
-- Source: data/garmin/daily/{date}/*.json
-- ============================================================
CREATE TABLE IF NOT EXISTS garmin_daily (
    date                    DATE PRIMARY KEY,
    total_kcal              NUMERIC(8,1),
    active_kcal             NUMERIC(8,1),
    bmr_kcal                NUMERIC(8,1),
    total_steps             INTEGER,
    total_distance_m        INTEGER,
    floors_ascended         SMALLINT,
    floors_descended        SMALLINT,
    highly_active_secs      INTEGER,
    active_secs             INTEGER,
    sedentary_secs          INTEGER,
    sleeping_secs           INTEGER,
    moderate_intensity_min  SMALLINT,
    vigorous_intensity_min  SMALLINT,
    min_hr                  SMALLINT,
    max_hr                  SMALLINT,
    resting_hr              SMALLINT,
    avg_resting_hr_7d       SMALLINT,
    avg_stress              SMALLINT,
    max_stress              SMALLINT,
    stress_duration         INTEGER,
    rest_stress_duration    INTEGER,
    low_stress_duration     INTEGER,
    medium_stress_duration  INTEGER,
    high_stress_duration    INTEGER,
    bb_charged              SMALLINT,
    bb_drained              SMALLINT,
    bb_highest              SMALLINT,
    bb_lowest               SMALLINT,
    bb_most_recent          SMALLINT,
    avg_respiration         NUMERIC(4,1),
    highest_respiration     NUMERIC(4,1),
    lowest_respiration      NUMERIC(4,1),
    avg_spo2                NUMERIC(4,1),
    lowest_spo2             NUMERIC(4,1),
    raw_summary             JSONB,
    raw_body_battery        JSONB,
    raw_heart_rates         JSONB,
    raw_steps               JSONB,
    raw_stress              JSONB,
    raw_stress_detail       JSONB,
    raw_hrv                 JSONB,
    raw_spo2                JSONB,
    raw_respiration         JSONB,
    raw_training_readiness  JSONB,
    raw_training_status     JSONB,
    raw_body_composition    JSONB,
    raw_hydration           JSONB,
    raw_fitness_age         JSONB,
    raw_max_metrics         JSONB,
    raw_floors              JSONB,
    raw_intensity_minutes   JSONB,
    raw_rhr                 JSONB,
    raw_lifestyle           JSONB,
    raw_weigh_ins           JSONB,
    raw_events              JSONB
);


-- ============================================================
-- Table 8: garmin_sleep
-- Source: data/garmin/daily/{date}/sleep.json
-- ============================================================
CREATE TABLE IF NOT EXISTS garmin_sleep (
    date                    DATE PRIMARY KEY,
    sleep_time_secs         INTEGER,
    nap_time_secs           INTEGER,
    deep_sleep_secs         INTEGER,
    light_sleep_secs        INTEGER,
    rem_sleep_secs          INTEGER,
    awake_sleep_secs        INTEGER,
    sleep_start_gmt         TIMESTAMPTZ,
    sleep_end_gmt           TIMESTAMPTZ,
    avg_respiration         NUMERIC(4,1),
    avg_sleep_stress        NUMERIC(5,2),
    awake_count             SMALLINT,
    sleep_score             SMALLINT,
    body_battery_change     SMALLINT,
    resting_hr              SMALLINT,
    raw                     JSONB
);


-- ============================================================
-- Table 9: intervals_daily
-- Source: data/intervals/wellness/{date}.json
-- ============================================================
CREATE TABLE IF NOT EXISTS intervals_daily (
    date                    DATE PRIMARY KEY,
    ctl                     NUMERIC(8,2),
    atl                     NUMERIC(8,2),
    ramp_rate               NUMERIC(6,2),
    weight                  NUMERIC(5,1),
    resting_hr              SMALLINT,
    hrv                     NUMERIC(6,1),
    hrv_sdnn                NUMERIC(6,1),
    sleep_secs              INTEGER,
    sleep_score             SMALLINT,
    avg_sleeping_hr         NUMERIC(5,1),
    soreness                SMALLINT,
    fatigue                 SMALLINT,
    stress                  SMALLINT,
    mood                    SMALLINT,
    motivation              SMALLINT,
    readiness               SMALLINT,
    spo2                    NUMERIC(4,1),
    steps                   INTEGER,
    respiration             SMALLINT,
    vo2max                  NUMERIC(4,1),
    body_fat                NUMERIC(4,1),
    sport_info              JSONB,
    raw                     JSONB
);


-- ============================================================
-- Table 10: garmin_reference_data
-- Source: data/garmin/ — profile, devices, gear, goals, etc.
-- ============================================================
CREATE TABLE IF NOT EXISTS garmin_reference_data (
    category                TEXT NOT NULL,
    key                     TEXT NOT NULL,
    data                    JSONB NOT NULL,
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (category, key)
);


-- ============================================================
-- Table 11: intervals_reference_data
-- Source: data/intervals/ — athlete, events, workouts
-- ============================================================
CREATE TABLE IF NOT EXISTS intervals_reference_data (
    category                TEXT NOT NULL,
    key                     TEXT NOT NULL,
    data                    JSONB NOT NULL,
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (category, key)
);


-- ============================================================
-- RAG: Research knowledge base (pgvector)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS research_documents (
    doc_id          SERIAL PRIMARY KEY,
    source_type     TEXT NOT NULL,
    file_path       TEXT NOT NULL UNIQUE,
    title           TEXT,
    url             TEXT,
    topic           TEXT,
    doc_type        TEXT,
    file_hash       TEXT NOT NULL,
    embedded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS research_chunks (
    chunk_id        SERIAL PRIMARY KEY,
    doc_id          INTEGER NOT NULL REFERENCES research_documents(doc_id) ON DELETE CASCADE,
    chunk_index     SMALLINT NOT NULL,
    section_name    TEXT,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    embedding       vector(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON research_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON research_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);
