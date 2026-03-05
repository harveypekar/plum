"""Shared DB helper module for Garmin + Intervals.icu data and RAG knowledge base.

Connection via DATABASE_URL env var, or reads projects/db/.env for password.
All upsert functions use ON CONFLICT DO UPDATE for idempotent loading.
Also provides pgvector-based RAG operations for research_chunks.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SCRIPT_DIR.parent / "db" / "schema.sql"
DB_ENV_PATH = SCRIPT_DIR.parent / "db" / ".env"

_conn = None


def _read_db_env() -> dict:
    """Read key=value pairs from projects/db/.env."""
    env = {}
    if DB_ENV_PATH.exists():
        for line in DB_ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def get_connection():
    """Get a psycopg2 connection (cached). Reads DATABASE_URL or .env."""
    global _conn
    if _conn is not None and _conn.closed == 0:
        return _conn

    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        _conn = psycopg2.connect(dsn)
    else:
        env = _read_db_env()
        _conn = psycopg2.connect(
            host=env.get("POSTGRES_HOST", "localhost"),
            port=int(env.get("POSTGRES_PORT", "5432")),
            user=env.get("POSTGRES_USER", "plum"),
            password=env.get("POSTGRES_PASSWORD", ""),
            dbname=env.get("POSTGRES_DB", "plum"),
        )
    _conn.autocommit = True
    return _conn


def ensure_schema():
    """Run schema.sql if tables don't exist."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'garmin_activities'
            )
        """)
        if cur.fetchone()[0]:
            return
    # Tables don't exist — create them
    sql = SCHEMA_PATH.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    print("Schema created.")


def _jsonb(data):
    """Wrap a dict/list for psycopg2 JSONB insertion."""
    if data is None:
        return None
    return psycopg2.extras.Json(data)


def _safe_int(val):
    """Convert to int or None."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val):
    """Convert to float or None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_bool(val):
    """Convert to bool or None."""
    if val is None:
        return None
    return bool(val)


def _safe_smallint(val):
    """Convert to smallint-safe int or None."""
    v = _safe_int(val)
    if v is not None and (v < -32768 or v > 32767):
        return None
    return v


# ── Garmin Activities ─────────────────────────────────────────

def upsert_garmin_activity(data: dict) -> None:
    """Upsert a single activity from list.json into garmin_activities."""
    conn = get_connection()
    activity_id = data.get("activityId")
    if not activity_id:
        return

    activity_type = data.get("activityType", {})
    if isinstance(activity_type, dict):
        activity_type = activity_type.get("typeKey", "unknown")

    event_type = data.get("eventType", {})
    if isinstance(event_type, dict):
        event_type = event_type.get("typeKey")

    sql = """
        INSERT INTO garmin_activities (
            activity_id, activity_name, start_time_local, start_time_gmt,
            activity_type, event_type, distance, duration,
            elapsed_duration, moving_duration, elevation_gain, elevation_loss,
            avg_speed, max_speed, calories, avg_hr, max_hr,
            avg_cadence, max_cadence, steps, avg_stride_length,
            vo2max, training_effect_label,
            start_lat, start_lon, end_lat, end_lon,
            location_name, device_id, sport_type_id, lap_count,
            has_polyline, pr, manual_activity,
            moderate_intensity_min, vigorous_intensity_min,
            min_elevation, max_elevation, water_estimated,
            begin_timestamp, raw
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (activity_id) DO UPDATE SET
            activity_name = EXCLUDED.activity_name,
            start_time_local = EXCLUDED.start_time_local,
            start_time_gmt = EXCLUDED.start_time_gmt,
            activity_type = EXCLUDED.activity_type,
            event_type = EXCLUDED.event_type,
            distance = EXCLUDED.distance,
            duration = EXCLUDED.duration,
            elapsed_duration = EXCLUDED.elapsed_duration,
            moving_duration = EXCLUDED.moving_duration,
            elevation_gain = EXCLUDED.elevation_gain,
            elevation_loss = EXCLUDED.elevation_loss,
            avg_speed = EXCLUDED.avg_speed,
            max_speed = EXCLUDED.max_speed,
            calories = EXCLUDED.calories,
            avg_hr = EXCLUDED.avg_hr,
            max_hr = EXCLUDED.max_hr,
            avg_cadence = EXCLUDED.avg_cadence,
            max_cadence = EXCLUDED.max_cadence,
            steps = EXCLUDED.steps,
            avg_stride_length = EXCLUDED.avg_stride_length,
            vo2max = EXCLUDED.vo2max,
            training_effect_label = EXCLUDED.training_effect_label,
            start_lat = EXCLUDED.start_lat,
            start_lon = EXCLUDED.start_lon,
            end_lat = EXCLUDED.end_lat,
            end_lon = EXCLUDED.end_lon,
            location_name = EXCLUDED.location_name,
            device_id = EXCLUDED.device_id,
            sport_type_id = EXCLUDED.sport_type_id,
            lap_count = EXCLUDED.lap_count,
            has_polyline = EXCLUDED.has_polyline,
            pr = EXCLUDED.pr,
            manual_activity = EXCLUDED.manual_activity,
            moderate_intensity_min = EXCLUDED.moderate_intensity_min,
            vigorous_intensity_min = EXCLUDED.vigorous_intensity_min,
            min_elevation = EXCLUDED.min_elevation,
            max_elevation = EXCLUDED.max_elevation,
            water_estimated = EXCLUDED.water_estimated,
            begin_timestamp = EXCLUDED.begin_timestamp,
            raw = EXCLUDED.raw
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            activity_id,
            data.get("activityName"),
            data.get("startTimeLocal"),
            data.get("startTimeGMT"),
            activity_type,
            event_type,
            _safe_float(data.get("distance")),
            _safe_float(data.get("duration")),
            _safe_float(data.get("elapsedDuration")),
            _safe_float(data.get("movingDuration")),
            _safe_float(data.get("elevationGain")),
            _safe_float(data.get("elevationLoss")),
            _safe_float(data.get("averageSpeed")),
            _safe_float(data.get("maxSpeed")),
            _safe_float(data.get("calories")),
            _safe_smallint(data.get("averageHR")),
            _safe_smallint(data.get("maxHR")),
            _safe_float(data.get("averageRunningCadenceInStepsPerMinute")),
            _safe_float(data.get("maxRunningCadenceInStepsPerMinute")),
            _safe_int(data.get("steps")),
            _safe_float(data.get("avgStrideLength")),
            _safe_float(data.get("vO2MaxValue")),
            data.get("trainingEffectLabel"),
            _safe_float(data.get("startLatitude")),
            _safe_float(data.get("startLongitude")),
            _safe_float(data.get("endLatitude")),
            _safe_float(data.get("endLongitude")),
            data.get("locationName"),
            _safe_int(data.get("deviceId")),
            _safe_smallint(data.get("sportTypeId")),
            _safe_smallint(data.get("lapCount")),
            _safe_bool(data.get("hasPolyline")),
            _safe_bool(data.get("pr")),
            _safe_bool(data.get("manualActivity")),
            _safe_smallint(data.get("moderateIntensityMinutes")),
            _safe_smallint(data.get("vigorousIntensityMinutes")),
            _safe_float(data.get("minElevation")),
            _safe_float(data.get("maxElevation")),
            _safe_float(data.get("waterEstimated")),
            _safe_int(data.get("beginTimestamp")),
            _jsonb(data),
        ))


# ── Garmin Activity Details ───────────────────────────────────

def upsert_garmin_activity_details(activity_id: int, files: dict) -> None:
    """Upsert garmin_activity_details from per-activity sub-files.

    files: dict mapping filename -> parsed JSON, e.g.
        {'summary.json': {...}, 'weather.json': {...}, ...}
    """
    conn = get_connection()

    weather = files.get("weather.json") or {}
    hr_zones = files.get("hr_zones.json")

    # Extract HR zone seconds
    zone_secs = [None, None, None, None, None]
    if hr_zones and isinstance(hr_zones, list):
        for i, zone in enumerate(hr_zones[:5]):
            if isinstance(zone, dict):
                zone_secs[i] = _safe_int(zone.get("secsInZone"))

    sql = """
        INSERT INTO garmin_activity_details (
            activity_id,
            weather_temp, weather_apparent_temp, weather_humidity,
            weather_wind_speed, weather_wind_direction, weather_condition,
            hr_zone1_secs, hr_zone2_secs, hr_zone3_secs,
            hr_zone4_secs, hr_zone5_secs,
            raw_summary, raw_splits, raw_split_summaries,
            raw_typed_splits, raw_hr_zones, raw_power_zones,
            raw_exercise_sets, raw_gear, raw_weather
        ) VALUES (
            %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (activity_id) DO UPDATE SET
            weather_temp = EXCLUDED.weather_temp,
            weather_apparent_temp = EXCLUDED.weather_apparent_temp,
            weather_humidity = EXCLUDED.weather_humidity,
            weather_wind_speed = EXCLUDED.weather_wind_speed,
            weather_wind_direction = EXCLUDED.weather_wind_direction,
            weather_condition = EXCLUDED.weather_condition,
            hr_zone1_secs = EXCLUDED.hr_zone1_secs,
            hr_zone2_secs = EXCLUDED.hr_zone2_secs,
            hr_zone3_secs = EXCLUDED.hr_zone3_secs,
            hr_zone4_secs = EXCLUDED.hr_zone4_secs,
            hr_zone5_secs = EXCLUDED.hr_zone5_secs,
            raw_summary = EXCLUDED.raw_summary,
            raw_splits = EXCLUDED.raw_splits,
            raw_split_summaries = EXCLUDED.raw_split_summaries,
            raw_typed_splits = EXCLUDED.raw_typed_splits,
            raw_hr_zones = EXCLUDED.raw_hr_zones,
            raw_power_zones = EXCLUDED.raw_power_zones,
            raw_exercise_sets = EXCLUDED.raw_exercise_sets,
            raw_gear = EXCLUDED.raw_gear,
            raw_weather = EXCLUDED.raw_weather
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            activity_id,
            _safe_float(weather.get("temp")),
            _safe_float(weather.get("apparentTemp")),
            _safe_smallint(weather.get("relativeHumidity")),
            _safe_float(weather.get("windSpeed")),
            _safe_smallint(weather.get("windDirection")),
            weather.get("weatherTypeDTO", {}).get("desc") if isinstance(weather.get("weatherTypeDTO"), dict) else None,
            zone_secs[0], zone_secs[1], zone_secs[2],
            zone_secs[3], zone_secs[4],
            _jsonb(files.get("summary.json")),
            _jsonb(files.get("splits.json")),
            _jsonb(files.get("split_summaries.json")),
            _jsonb(files.get("typed_splits.json")),
            _jsonb(files.get("hr_zones.json")),
            _jsonb(files.get("power_zones.json")),
            _jsonb(files.get("exercise_sets.json")),
            _jsonb(files.get("gear.json")),
            _jsonb(files.get("weather.json")),
        ))


# ── Garmin Activity Streams ───────────────────────────────────

# Maps metric descriptor keys to column names
_GARMIN_STREAM_COLS = {
    "directTimestamp":            "timestamps",
    "sumDistance":                "distances",
    "directHeartRate":           "heart_rates",
    "directDoubleCadence":       "cadences",
    "directSpeed":               "speeds",
    "directLatitude":            "latitudes",
    "directLongitude":           "longitudes",
    "directElevation":           "elevations",
    "directCorrectedElevation":  "corrected_elevations",
    "directVerticalSpeed":       "vertical_speeds",
    "sumDuration":               "durations",
    "sumMovingDuration":         "moving_durations",
    "sumElapsedDuration":        "elapsed_durations",
    "directBodyBattery":         "body_batteries",
    "directFractionalCadence":   "fractional_cadences",
}


def upsert_garmin_activity_streams(activity_id: int, details: dict) -> None:
    """Upsert garmin_activity_streams from details.json.

    details: the parsed details.json containing metricDescriptors and
             activityDetailMetrics arrays.
    """
    conn = get_connection()

    descriptors = details.get("metricDescriptors", [])
    metrics = details.get("activityDetailMetrics", [])
    if not descriptors or not metrics:
        return

    # Build key->index map
    key_to_idx = {}
    for desc in descriptors:
        key = desc.get("key", "")
        idx = desc.get("metricsIndex")
        if key and idx is not None:
            key_to_idx[key] = idx

    # Extract arrays
    arrays = {}
    for garmin_key, col_name in _GARMIN_STREAM_COLS.items():
        idx = key_to_idx.get(garmin_key)
        if idx is None:
            arrays[col_name] = None
            continue
        arr = []
        for point in metrics:
            vals = point.get("metrics", [])
            val = vals[idx] if idx < len(vals) else None
            arr.append(val)
        arrays[col_name] = arr if arr else None

    cols = list(_GARMIN_STREAM_COLS.values())
    placeholders = ", ".join(["%s"] * (len(cols) + 1))
    col_list = ", ".join(cols)
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols)

    sql = f"""
        INSERT INTO garmin_activity_streams (activity_id, {col_list})
        VALUES ({placeholders})
        ON CONFLICT (activity_id) DO UPDATE SET {update_set}
    """

    with conn.cursor() as cur:
        cur.execute(sql, [activity_id] + [arrays[c] for c in cols])


# ── Garmin Daily ──────────────────────────────────────────────

def upsert_garmin_daily(date_str: str, endpoint_data: dict) -> None:
    """Upsert garmin_daily from a dict of endpoint_name -> parsed JSON.

    endpoint_data keys: 'summary.json', 'body_battery.json', 'heart_rates.json', etc.
    """
    conn = get_connection()
    summary = endpoint_data.get("summary.json") or {}
    bb = endpoint_data.get("body_battery.json") or {}
    resp = endpoint_data.get("respiration.json") or {}
    spo2 = endpoint_data.get("spo2.json") or {}

    # Body battery: can be list or dict
    bb_charged = bb_drained = bb_highest = bb_lowest = bb_recent = None
    if isinstance(bb, dict):
        bb_charged = _safe_smallint(bb.get("charged"))
        bb_drained = _safe_smallint(bb.get("drained"))
        bb_highest = _safe_smallint(bb.get("bodyBatteryHighest") or bb.get("highest"))
        bb_lowest = _safe_smallint(bb.get("bodyBatteryLowest") or bb.get("lowest"))
        bb_recent = _safe_smallint(bb.get("bodyBatteryMostRecentValue") or bb.get("mostRecent"))
    elif isinstance(bb, list) and bb:
        # Sometimes it's a list of readings; take aggregate from first item if dict
        if isinstance(bb[0], dict):
            bb_charged = _safe_smallint(bb[0].get("charged"))
            bb_drained = _safe_smallint(bb[0].get("drained"))

    # Respiration
    avg_resp = highest_resp = lowest_resp = None
    if isinstance(resp, dict):
        avg_resp = _safe_float(resp.get("avgWakingRespirationValue"))
        highest_resp = _safe_float(resp.get("highestRespirationValue"))
        lowest_resp = _safe_float(resp.get("lowestRespirationValue"))

    # SpO2
    avg_spo2 = lowest_spo2 = None
    if isinstance(spo2, dict):
        avg_spo2 = _safe_float(spo2.get("averageSpO2"))
        lowest_spo2 = _safe_float(spo2.get("lowestSpO2"))

    sql = """
        INSERT INTO garmin_daily (
            date, total_kcal, active_kcal, bmr_kcal,
            total_steps, total_distance_m, floors_ascended, floors_descended,
            highly_active_secs, active_secs, sedentary_secs, sleeping_secs,
            moderate_intensity_min, vigorous_intensity_min,
            min_hr, max_hr, resting_hr, avg_resting_hr_7d,
            avg_stress, max_stress, stress_duration,
            rest_stress_duration, low_stress_duration,
            medium_stress_duration, high_stress_duration,
            bb_charged, bb_drained, bb_highest, bb_lowest, bb_most_recent,
            avg_respiration, highest_respiration, lowest_respiration,
            avg_spo2, lowest_spo2,
            raw_summary, raw_body_battery, raw_heart_rates, raw_steps,
            raw_stress, raw_stress_detail, raw_hrv, raw_spo2,
            raw_respiration, raw_training_readiness, raw_training_status,
            raw_body_composition, raw_hydration, raw_fitness_age,
            raw_max_metrics, raw_floors, raw_intensity_minutes,
            raw_rhr, raw_lifestyle, raw_weigh_ins, raw_events
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (date) DO UPDATE SET
            total_kcal = EXCLUDED.total_kcal,
            active_kcal = EXCLUDED.active_kcal,
            bmr_kcal = EXCLUDED.bmr_kcal,
            total_steps = EXCLUDED.total_steps,
            total_distance_m = EXCLUDED.total_distance_m,
            floors_ascended = EXCLUDED.floors_ascended,
            floors_descended = EXCLUDED.floors_descended,
            highly_active_secs = EXCLUDED.highly_active_secs,
            active_secs = EXCLUDED.active_secs,
            sedentary_secs = EXCLUDED.sedentary_secs,
            sleeping_secs = EXCLUDED.sleeping_secs,
            moderate_intensity_min = EXCLUDED.moderate_intensity_min,
            vigorous_intensity_min = EXCLUDED.vigorous_intensity_min,
            min_hr = EXCLUDED.min_hr,
            max_hr = EXCLUDED.max_hr,
            resting_hr = EXCLUDED.resting_hr,
            avg_resting_hr_7d = EXCLUDED.avg_resting_hr_7d,
            avg_stress = EXCLUDED.avg_stress,
            max_stress = EXCLUDED.max_stress,
            stress_duration = EXCLUDED.stress_duration,
            rest_stress_duration = EXCLUDED.rest_stress_duration,
            low_stress_duration = EXCLUDED.low_stress_duration,
            medium_stress_duration = EXCLUDED.medium_stress_duration,
            high_stress_duration = EXCLUDED.high_stress_duration,
            bb_charged = EXCLUDED.bb_charged,
            bb_drained = EXCLUDED.bb_drained,
            bb_highest = EXCLUDED.bb_highest,
            bb_lowest = EXCLUDED.bb_lowest,
            bb_most_recent = EXCLUDED.bb_most_recent,
            avg_respiration = EXCLUDED.avg_respiration,
            highest_respiration = EXCLUDED.highest_respiration,
            lowest_respiration = EXCLUDED.lowest_respiration,
            avg_spo2 = EXCLUDED.avg_spo2,
            lowest_spo2 = EXCLUDED.lowest_spo2,
            raw_summary = EXCLUDED.raw_summary,
            raw_body_battery = EXCLUDED.raw_body_battery,
            raw_heart_rates = EXCLUDED.raw_heart_rates,
            raw_steps = EXCLUDED.raw_steps,
            raw_stress = EXCLUDED.raw_stress,
            raw_stress_detail = EXCLUDED.raw_stress_detail,
            raw_hrv = EXCLUDED.raw_hrv,
            raw_spo2 = EXCLUDED.raw_spo2,
            raw_respiration = EXCLUDED.raw_respiration,
            raw_training_readiness = EXCLUDED.raw_training_readiness,
            raw_training_status = EXCLUDED.raw_training_status,
            raw_body_composition = EXCLUDED.raw_body_composition,
            raw_hydration = EXCLUDED.raw_hydration,
            raw_fitness_age = EXCLUDED.raw_fitness_age,
            raw_max_metrics = EXCLUDED.raw_max_metrics,
            raw_floors = EXCLUDED.raw_floors,
            raw_intensity_minutes = EXCLUDED.raw_intensity_minutes,
            raw_rhr = EXCLUDED.raw_rhr,
            raw_lifestyle = EXCLUDED.raw_lifestyle,
            raw_weigh_ins = EXCLUDED.raw_weigh_ins,
            raw_events = EXCLUDED.raw_events
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            date_str,
            _safe_float(summary.get("totalKilocalories")),
            _safe_float(summary.get("activeKilocalories")),
            _safe_float(summary.get("bmrKilocalories")),
            _safe_int(summary.get("totalSteps")),
            _safe_int(summary.get("totalDistanceMeters")),
            _safe_smallint(summary.get("floorsAscended")),
            _safe_smallint(summary.get("floorsDescended")),
            _safe_int(summary.get("highlyActiveSeconds")),
            _safe_int(summary.get("activeSeconds")),
            _safe_int(summary.get("sedentarySeconds")),
            _safe_int(summary.get("sleepingSeconds")),
            _safe_smallint(summary.get("moderateIntensityMinutes")),
            _safe_smallint(summary.get("vigorousIntensityMinutes")),
            _safe_smallint(summary.get("minHeartRate")),
            _safe_smallint(summary.get("maxHeartRate")),
            _safe_smallint(summary.get("restingHeartRate")),
            _safe_smallint(summary.get("lastSevenDaysAvgRestingHeartRate")),
            _safe_smallint(summary.get("averageStressLevel")),
            _safe_smallint(summary.get("maxStressLevel")),
            _safe_int(summary.get("stressDuration")),
            _safe_int(summary.get("restStressDuration")),
            _safe_int(summary.get("lowStressDuration")),
            _safe_int(summary.get("mediumStressDuration")),
            _safe_int(summary.get("highStressDuration")),
            bb_charged, bb_drained, bb_highest, bb_lowest, bb_recent,
            avg_resp, highest_resp, lowest_resp,
            avg_spo2, lowest_spo2,
            _jsonb(endpoint_data.get("summary.json")),
            _jsonb(endpoint_data.get("body_battery.json")),
            _jsonb(endpoint_data.get("heart_rates.json")),
            _jsonb(endpoint_data.get("steps.json")),
            _jsonb(endpoint_data.get("stress.json")),
            _jsonb(endpoint_data.get("stress_detail.json")),
            _jsonb(endpoint_data.get("hrv.json")),
            _jsonb(endpoint_data.get("spo2.json")),
            _jsonb(endpoint_data.get("respiration.json")),
            _jsonb(endpoint_data.get("training_readiness.json")),
            _jsonb(endpoint_data.get("training_status.json")),
            _jsonb(endpoint_data.get("body_composition.json")),
            _jsonb(endpoint_data.get("hydration.json")),
            _jsonb(endpoint_data.get("fitness_age.json")),
            _jsonb(endpoint_data.get("max_metrics.json")),
            _jsonb(endpoint_data.get("floors.json")),
            _jsonb(endpoint_data.get("intensity_minutes.json")),
            _jsonb(endpoint_data.get("rhr.json")),
            _jsonb(endpoint_data.get("lifestyle.json")),
            _jsonb(endpoint_data.get("weigh_ins.json")),
            _jsonb(endpoint_data.get("events.json")),
        ))


# ── Garmin Sleep ──────────────────────────────────────────────

def upsert_garmin_sleep(date_str: str, sleep_data: dict) -> None:
    """Upsert garmin_sleep from sleep.json."""
    conn = get_connection()

    # sleep.json wraps in dailySleepDTO
    dto = sleep_data.get("dailySleepDTO") or sleep_data
    if not dto:
        return

    # Convert epoch ms timestamps
    sleep_start = sleep_end = None
    start_ms = dto.get("sleepStartTimestampGMT")
    end_ms = dto.get("sleepEndTimestampGMT")
    if start_ms:
        sleep_start = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    if end_ms:
        sleep_end = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)

    # Sleep score
    sleep_score = None
    scores = dto.get("sleepScores", {})
    if isinstance(scores, dict):
        overall = scores.get("overall", {})
        if isinstance(overall, dict):
            sleep_score = _safe_smallint(overall.get("value"))

    # Body battery change
    bb_change = None
    bb_start = dto.get("sleepStartBodyBattery")
    bb_end = dto.get("sleepEndBodyBattery")
    if bb_start is not None and bb_end is not None:
        try:
            bb_change = int(bb_end) - int(bb_start)
        except (ValueError, TypeError):
            pass

    sql = """
        INSERT INTO garmin_sleep (
            date, sleep_time_secs, nap_time_secs,
            deep_sleep_secs, light_sleep_secs, rem_sleep_secs, awake_sleep_secs,
            sleep_start_gmt, sleep_end_gmt,
            avg_respiration, avg_sleep_stress, awake_count,
            sleep_score, body_battery_change, resting_hr, raw
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (date) DO UPDATE SET
            sleep_time_secs = EXCLUDED.sleep_time_secs,
            nap_time_secs = EXCLUDED.nap_time_secs,
            deep_sleep_secs = EXCLUDED.deep_sleep_secs,
            light_sleep_secs = EXCLUDED.light_sleep_secs,
            rem_sleep_secs = EXCLUDED.rem_sleep_secs,
            awake_sleep_secs = EXCLUDED.awake_sleep_secs,
            sleep_start_gmt = EXCLUDED.sleep_start_gmt,
            sleep_end_gmt = EXCLUDED.sleep_end_gmt,
            avg_respiration = EXCLUDED.avg_respiration,
            avg_sleep_stress = EXCLUDED.avg_sleep_stress,
            awake_count = EXCLUDED.awake_count,
            sleep_score = EXCLUDED.sleep_score,
            body_battery_change = EXCLUDED.body_battery_change,
            resting_hr = EXCLUDED.resting_hr,
            raw = EXCLUDED.raw
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            date_str,
            _safe_int(dto.get("sleepTimeSeconds")),
            _safe_int(dto.get("napTimeSeconds")),
            _safe_int(dto.get("deepSleepSeconds")),
            _safe_int(dto.get("lightSleepSeconds")),
            _safe_int(dto.get("remSleepSeconds")),
            _safe_int(dto.get("awakeSleepSeconds")),
            sleep_start,
            sleep_end,
            _safe_float(dto.get("averageRespirationValue")),
            _safe_float(dto.get("avgSleepStress")),
            _safe_smallint(dto.get("awakeCount")),
            sleep_score,
            bb_change,
            _safe_smallint(dto.get("avgHeartRate")),
            _jsonb(sleep_data),
        ))


# ── Intervals.icu Activities ─────────────────────────────────

def upsert_intervals_activity(data: dict) -> None:
    """Upsert a single activity from list.json into intervals_activities."""
    conn = get_connection()
    aid = data.get("id")
    if not aid:
        return

    sql = """
        INSERT INTO intervals_activities (
            id, external_id, start_date_local, start_date,
            type, name, distance, elapsed_time,
            moving_time, recording_time,
            total_elevation_gain, total_elevation_loss,
            avg_speed, max_speed, avg_hr, max_hr,
            avg_cadence, calories, gap,
            training_load, atl, ctl,
            weight, lthr, device_name, file_type,
            commute, race, trainer,
            icu_hr_zones, icu_power_zones,
            warmup_time, cooldown_time, raw
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            external_id = EXCLUDED.external_id,
            start_date_local = EXCLUDED.start_date_local,
            start_date = EXCLUDED.start_date,
            type = EXCLUDED.type,
            name = EXCLUDED.name,
            distance = EXCLUDED.distance,
            elapsed_time = EXCLUDED.elapsed_time,
            moving_time = EXCLUDED.moving_time,
            recording_time = EXCLUDED.recording_time,
            total_elevation_gain = EXCLUDED.total_elevation_gain,
            total_elevation_loss = EXCLUDED.total_elevation_loss,
            avg_speed = EXCLUDED.avg_speed,
            max_speed = EXCLUDED.max_speed,
            avg_hr = EXCLUDED.avg_hr,
            max_hr = EXCLUDED.max_hr,
            avg_cadence = EXCLUDED.avg_cadence,
            calories = EXCLUDED.calories,
            gap = EXCLUDED.gap,
            training_load = EXCLUDED.training_load,
            atl = EXCLUDED.atl,
            ctl = EXCLUDED.ctl,
            weight = EXCLUDED.weight,
            lthr = EXCLUDED.lthr,
            device_name = EXCLUDED.device_name,
            file_type = EXCLUDED.file_type,
            commute = EXCLUDED.commute,
            race = EXCLUDED.race,
            trainer = EXCLUDED.trainer,
            icu_hr_zones = EXCLUDED.icu_hr_zones,
            icu_power_zones = EXCLUDED.icu_power_zones,
            warmup_time = EXCLUDED.warmup_time,
            cooldown_time = EXCLUDED.cooldown_time,
            raw = EXCLUDED.raw
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            aid,
            str(data.get("external_id", "")) or None,
            data.get("start_date_local"),
            data.get("start_date"),
            data.get("type", "Unknown"),
            data.get("name"),
            _safe_float(data.get("distance")),
            _safe_int(data.get("elapsed_time")),
            _safe_int(data.get("moving_time")),
            _safe_int(data.get("icu_recording_time")),
            _safe_float(data.get("total_elevation_gain")),
            _safe_float(data.get("total_elevation_loss")),
            _safe_float(data.get("average_speed")),
            _safe_float(data.get("max_speed")),
            _safe_smallint(data.get("average_heartrate")),
            _safe_smallint(data.get("max_heartrate")),
            _safe_float(data.get("average_cadence")),
            _safe_float(data.get("calories")),
            _safe_float(data.get("gap")),
            _safe_int(data.get("icu_training_load")),
            _safe_float(data.get("icu_atl")),
            _safe_float(data.get("icu_ctl")),
            _safe_float(data.get("icu_weight")),
            _safe_smallint(data.get("lthr")),
            data.get("device_name"),
            data.get("file_type"),
            _safe_bool(data.get("commute")),
            _safe_bool(data.get("race")),
            _safe_bool(data.get("trainer")),
            data.get("icu_hr_zones"),
            data.get("icu_power_zones"),
            _safe_int(data.get("icu_warmup_time")),
            _safe_int(data.get("icu_cooldown_time")),
            _jsonb(data),
        ))


# ── Intervals.icu Activity Details ────────────────────────────

def upsert_intervals_activity_details(activity_id: str, detail: dict) -> None:
    """Upsert intervals_activity_details from detail.json."""
    conn = get_connection()

    sql = """
        INSERT INTO intervals_activity_details (
            id, hr_load, pace_load, power_load, hr_load_type,
            polarization_index, icu_intensity, icu_lap_count,
            pace, decoupling, icu_efficiency_factor, icu_variability_index,
            athlete_max_hr,
            average_altitude, min_altitude, max_altitude,
            average_weather_temp, min_weather_temp, max_weather_temp,
            average_feels_like, average_wind_speed, average_wind_gust,
            prevailing_wind_deg, headwind_percent, tailwind_percent,
            average_clouds, max_rain, max_snow,
            source, stream_types, recording_stops, interval_summary,
            icu_zone_times, pace_zone_times, gap_zone_times,
            icu_intervals, icu_groups, raw
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            hr_load = EXCLUDED.hr_load,
            pace_load = EXCLUDED.pace_load,
            power_load = EXCLUDED.power_load,
            hr_load_type = EXCLUDED.hr_load_type,
            polarization_index = EXCLUDED.polarization_index,
            icu_intensity = EXCLUDED.icu_intensity,
            icu_lap_count = EXCLUDED.icu_lap_count,
            pace = EXCLUDED.pace,
            decoupling = EXCLUDED.decoupling,
            icu_efficiency_factor = EXCLUDED.icu_efficiency_factor,
            icu_variability_index = EXCLUDED.icu_variability_index,
            athlete_max_hr = EXCLUDED.athlete_max_hr,
            average_altitude = EXCLUDED.average_altitude,
            min_altitude = EXCLUDED.min_altitude,
            max_altitude = EXCLUDED.max_altitude,
            average_weather_temp = EXCLUDED.average_weather_temp,
            min_weather_temp = EXCLUDED.min_weather_temp,
            max_weather_temp = EXCLUDED.max_weather_temp,
            average_feels_like = EXCLUDED.average_feels_like,
            average_wind_speed = EXCLUDED.average_wind_speed,
            average_wind_gust = EXCLUDED.average_wind_gust,
            prevailing_wind_deg = EXCLUDED.prevailing_wind_deg,
            headwind_percent = EXCLUDED.headwind_percent,
            tailwind_percent = EXCLUDED.tailwind_percent,
            average_clouds = EXCLUDED.average_clouds,
            max_rain = EXCLUDED.max_rain,
            max_snow = EXCLUDED.max_snow,
            source = EXCLUDED.source,
            stream_types = EXCLUDED.stream_types,
            recording_stops = EXCLUDED.recording_stops,
            interval_summary = EXCLUDED.interval_summary,
            icu_zone_times = EXCLUDED.icu_zone_times,
            pace_zone_times = EXCLUDED.pace_zone_times,
            gap_zone_times = EXCLUDED.gap_zone_times,
            icu_intervals = EXCLUDED.icu_intervals,
            icu_groups = EXCLUDED.icu_groups,
            raw = EXCLUDED.raw
    """

    # Extract training load data (sometimes int instead of dict)
    tld = detail.get("icu_training_load_data")
    if not isinstance(tld, dict):
        tld = {}

    with conn.cursor() as cur:
        cur.execute(sql, (
            activity_id,
            _safe_float(tld.get("hrLoad")),
            _safe_float(tld.get("paceLoad")),
            _safe_float(tld.get("powerLoad")),
            tld.get("hrLoadType"),
            _safe_float(detail.get("polarization_index")),
            _safe_float(detail.get("icu_intensity")),
            _safe_smallint(detail.get("icu_lap_count")),
            _safe_float(detail.get("pace")),
            _safe_float(detail.get("decoupling")),
            _safe_float(detail.get("icu_efficiency_factor")),
            _safe_float(detail.get("icu_variability_index")),
            _safe_smallint(detail.get("athlete_max_hr")),
            _safe_float(detail.get("average_altitude")),
            _safe_float(detail.get("min_altitude")),
            _safe_float(detail.get("max_altitude")),
            _safe_float(detail.get("average_weather_temp")),
            _safe_float(detail.get("min_weather_temp")),
            _safe_float(detail.get("max_weather_temp")),
            _safe_float(detail.get("average_feels_like")),
            _safe_float(detail.get("average_wind_speed")),
            _safe_float(detail.get("average_wind_gust")),
            _safe_smallint(detail.get("prevailing_wind_deg")),
            _safe_float(detail.get("headwind_percent")),
            _safe_float(detail.get("tailwind_percent")),
            _safe_float(detail.get("average_clouds")),
            _safe_float(detail.get("max_rain")),
            _safe_float(detail.get("max_snow")),
            detail.get("source"),
            detail.get("stream_types"),
            detail.get("recording_stops"),
            detail.get("interval_summary"),
            detail.get("icu_zone_times"),
            detail.get("pace_zone_times"),
            detail.get("gap_zone_times"),
            _jsonb(detail.get("icu_intervals")),
            _jsonb(detail.get("icu_groups")),
            _jsonb(detail),
        ))


# ── Intervals.icu Activity Streams ───────────────────────────

_ICU_STREAM_COLS = {
    "time":       "time",
    "distance":   "distance",
    "velocity_smooth": "velocity",
    "heartrate":  "heart_rate",
    "cadence":    "cadence",
    "watts":      "power",
    "altitude":   "altitude",
    "grade_smooth": "grade",
    "temp":       "temp",
}


def upsert_intervals_activity_streams(activity_id: str, streams: list) -> None:
    """Upsert intervals_activity_streams from streams.json.

    streams: list of {type: str, data: [...]} objects.
    """
    conn = get_connection()

    stream_map = {}
    for s in streams:
        stype = s.get("type", "")
        sdata = s.get("data")
        if stype and sdata is not None:
            stream_map[stype] = sdata

    # Handle latlng specially — split into latitudes and longitudes
    latlng = stream_map.get("latlng")
    lats = lons = None
    if latlng and isinstance(latlng, list):
        lats = []
        lons = []
        for pair in latlng:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                lats.append(pair[0])
                lons.append(pair[1])
            else:
                lats.append(None)
                lons.append(None)

    cols = {col: stream_map.get(stype) for stype, col in _ICU_STREAM_COLS.items()}
    cols["latitudes"] = lats
    cols["longitudes"] = lons

    col_names = list(cols.keys())
    placeholders = ", ".join(["%s"] * (len(col_names) + 1))
    col_list = ", ".join(col_names)
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in col_names)

    sql = f"""
        INSERT INTO intervals_activity_streams (id, {col_list})
        VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET {update_set}
    """

    with conn.cursor() as cur:
        cur.execute(sql, [activity_id] + [cols[c] for c in col_names])


# ── Intervals.icu Daily ──────────────────────────────────────

def upsert_intervals_daily(date_str: str, data: dict) -> None:
    """Upsert intervals_daily from a wellness record."""
    conn = get_connection()

    sql = """
        INSERT INTO intervals_daily (
            date, ctl, atl, ramp_rate, weight, resting_hr,
            hrv, hrv_sdnn, sleep_secs, sleep_score,
            avg_sleeping_hr, soreness, fatigue, stress,
            mood, motivation, readiness, spo2,
            steps, respiration, vo2max, body_fat,
            sport_info, raw
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (date) DO UPDATE SET
            ctl = EXCLUDED.ctl,
            atl = EXCLUDED.atl,
            ramp_rate = EXCLUDED.ramp_rate,
            weight = EXCLUDED.weight,
            resting_hr = EXCLUDED.resting_hr,
            hrv = EXCLUDED.hrv,
            hrv_sdnn = EXCLUDED.hrv_sdnn,
            sleep_secs = EXCLUDED.sleep_secs,
            sleep_score = EXCLUDED.sleep_score,
            avg_sleeping_hr = EXCLUDED.avg_sleeping_hr,
            soreness = EXCLUDED.soreness,
            fatigue = EXCLUDED.fatigue,
            stress = EXCLUDED.stress,
            mood = EXCLUDED.mood,
            motivation = EXCLUDED.motivation,
            readiness = EXCLUDED.readiness,
            spo2 = EXCLUDED.spo2,
            steps = EXCLUDED.steps,
            respiration = EXCLUDED.respiration,
            vo2max = EXCLUDED.vo2max,
            body_fat = EXCLUDED.body_fat,
            sport_info = EXCLUDED.sport_info,
            raw = EXCLUDED.raw
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            date_str,
            _safe_float(data.get("ctl")),
            _safe_float(data.get("atl")),
            _safe_float(data.get("rampRate")),
            _safe_float(data.get("weight")),
            _safe_smallint(data.get("restingHR")),
            _safe_float(data.get("hrv")),
            _safe_float(data.get("hrvSDNN")),
            _safe_int(data.get("sleepSecs")),
            _safe_smallint(data.get("sleepScore")),
            _safe_float(data.get("avgSleepingHR")),
            _safe_smallint(data.get("soreness")),
            _safe_smallint(data.get("fatigue")),
            _safe_smallint(data.get("stress")),
            _safe_smallint(data.get("mood")),
            _safe_smallint(data.get("motivation")),
            _safe_smallint(data.get("readiness")),
            _safe_float(data.get("spO2")),
            _safe_int(data.get("steps")),
            _safe_smallint(data.get("respiration")),
            _safe_float(data.get("vo2max")),
            _safe_float(data.get("bodyFat")),
            _jsonb(data.get("sportInfo")),
            _jsonb(data),
        ))


# ── Reference Data ────────────────────────────────────────────

def upsert_garmin_reference(category: str, key: str, data) -> None:
    """Upsert into garmin_reference_data."""
    conn = get_connection()
    sql = """
        INSERT INTO garmin_reference_data (category, key, data, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (category, key) DO UPDATE SET
            data = EXCLUDED.data,
            updated_at = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (category, key, _jsonb(data)))


def upsert_intervals_reference(category: str, key: str, data) -> None:
    """Upsert into intervals_reference_data."""
    conn = get_connection()
    sql = """
        INSERT INTO intervals_reference_data (category, key, data, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (category, key) DO UPDATE SET
            data = EXCLUDED.data,
            updated_at = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (category, key, _jsonb(data)))


# ---------------------------------------------------------------------------
# RAG document & chunk operations (pgvector)
# ---------------------------------------------------------------------------

def upsert_research_document(file_path, source_type, title, url, topic, doc_type, file_hash):
    """Insert or update a research document. Returns doc_id."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO research_documents
                (file_path, source_type, title, url, topic, doc_type, file_hash, embedded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (file_path) DO UPDATE SET
                source_type = EXCLUDED.source_type,
                title = EXCLUDED.title,
                url = EXCLUDED.url,
                topic = EXCLUDED.topic,
                doc_type = EXCLUDED.doc_type,
                file_hash = EXCLUDED.file_hash,
                embedded_at = NOW()
            RETURNING doc_id
        """, (file_path, source_type, title, url, topic, doc_type, file_hash))
        return cur.fetchone()[0]


def delete_document_chunks(doc_id):
    """Delete all chunks for a document (before re-embedding)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM research_chunks WHERE doc_id = %s", (doc_id,))


def insert_chunk(doc_id, chunk_index, section_name, content, token_count, embedding):
    """Insert a single chunk with its embedding vector."""
    conn = get_connection()
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO research_chunks
                (doc_id, chunk_index, section_name, content, token_count, embedding)
            VALUES (%s, %s, %s, %s, %s, %s::vector)
        """, (doc_id, chunk_index, section_name, content, token_count, vec_str))


def get_document_hash(file_path):
    """Get stored file hash for change detection. Returns None if not found."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT file_hash FROM research_documents WHERE file_path = %s",
            (file_path,)
        )
        row = cur.fetchone()
        return row[0] if row else None


def vector_search(embedding, top_k=5, exclude_chunk_ids=None):
    """Cosine similarity search on research_chunks."""
    conn = get_connection()
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"

    exclude_clause = ""
    params = [vec_str, vec_str, top_k]
    if exclude_chunk_ids:
        placeholders = ",".join(["%s"] * len(exclude_chunk_ids))
        exclude_clause = f"AND c.chunk_id NOT IN ({placeholders})"
        params = [vec_str] + list(exclude_chunk_ids) + [vec_str, top_k]

    if exclude_chunk_ids:
        sql = f"""
            SELECT c.chunk_id, c.content, c.section_name,
                   1 - (c.embedding <=> %s::vector) AS score,
                   d.file_path, d.title, d.topic
            FROM research_chunks c
            JOIN research_documents d ON c.doc_id = d.doc_id
            WHERE 1=1 {exclude_clause}
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """
    else:
        sql = """
            SELECT c.chunk_id, c.content, c.section_name,
                   1 - (c.embedding <=> %s::vector) AS score,
                   d.file_path, d.title, d.topic
            FROM research_chunks c
            JOIN research_documents d ON c.doc_id = d.doc_id
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
