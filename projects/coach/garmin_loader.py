"""Load and parse Garmin JSON data files."""
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data" / "garmin"

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
