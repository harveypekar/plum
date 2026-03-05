"""One-time bulk loader: read all existing JSON from data/ dirs and insert into Postgres."""

import json
import sys
from pathlib import Path

import db

SCRIPT_DIR = Path(__file__).resolve().parent
GARMIN_DIR = SCRIPT_DIR / "data" / "garmin"
INTERVALS_DIR = SCRIPT_DIR / "data" / "intervals"


def load_json(path: Path):
    """Load a JSON file, return None on error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARN: Could not read {path}: {e}")
        return None


def load_garmin_activities():
    """Step 1: Load garmin_activities from list.json."""
    path = GARMIN_DIR / "activities" / "list.json"
    if not path.exists():
        print("  No garmin activities list.json found")
        return 0
    activities = load_json(path)
    if not activities:
        return 0
    count = 0
    for a in activities:
        try:
            db.upsert_garmin_activity(a)
            count += 1
        except Exception as e:
            print(f"  ERR activity {a.get('activityId')}: {e}")
    return count


def load_intervals_activities():
    """Step 2: Load intervals_activities from list.json."""
    path = INTERVALS_DIR / "activities" / "list.json"
    if not path.exists():
        print("  No intervals activities list.json found")
        return 0
    activities = load_json(path)
    if not activities:
        return 0
    count = 0
    for a in activities:
        try:
            db.upsert_intervals_activity(a)
            count += 1
        except Exception as e:
            print(f"  ERR activity {a.get('id')}: {e}")
    return count


def load_garmin_activity_details():
    """Step 3: Load garmin_activity_details from per-activity dirs."""
    activities_dir = GARMIN_DIR / "activities"
    if not activities_dir.exists():
        return 0
    count = 0
    for act_dir in sorted(activities_dir.iterdir()):
        if not act_dir.is_dir():
            continue
        try:
            activity_id = int(act_dir.name)
        except ValueError:
            continue

        files = {}
        for fname in ["summary.json", "splits.json", "split_summaries.json",
                       "typed_splits.json", "hr_zones.json", "power_zones.json",
                       "exercise_sets.json", "gear.json", "weather.json"]:
            fpath = act_dir / fname
            if fpath.exists():
                files[fname] = load_json(fpath)

        if files:
            try:
                db.upsert_garmin_activity_details(activity_id, files)
                count += 1
            except Exception as e:
                print(f"  ERR details {activity_id}: {e}")
    return count


def load_garmin_activity_streams():
    """Step 4: Load garmin_activity_streams from details.json."""
    activities_dir = GARMIN_DIR / "activities"
    if not activities_dir.exists():
        return 0
    count = 0
    for act_dir in sorted(activities_dir.iterdir()):
        if not act_dir.is_dir():
            continue
        try:
            activity_id = int(act_dir.name)
        except ValueError:
            continue

        details_path = act_dir / "details.json"
        if not details_path.exists():
            continue

        details = load_json(details_path)
        if not details:
            continue

        try:
            db.upsert_garmin_activity_streams(activity_id, details)
            count += 1
        except Exception as e:
            print(f"  ERR streams {activity_id}: {e}")
    return count


def load_intervals_activity_details():
    """Step 5: Load intervals_activity_details from detail.json."""
    activities_dir = INTERVALS_DIR / "activities"
    if not activities_dir.exists():
        return 0
    count = 0
    for act_dir in sorted(activities_dir.iterdir()):
        if not act_dir.is_dir():
            continue
        detail_path = act_dir / "detail.json"
        if not detail_path.exists():
            continue
        detail = load_json(detail_path)
        if not detail:
            continue
        try:
            db.upsert_intervals_activity_details(act_dir.name, detail)
            count += 1
        except Exception as e:
            print(f"  ERR detail {act_dir.name}: {e}")
    return count


def load_intervals_activity_streams():
    """Step 6: Load intervals_activity_streams from streams.json."""
    activities_dir = INTERVALS_DIR / "activities"
    if not activities_dir.exists():
        return 0
    count = 0
    for act_dir in sorted(activities_dir.iterdir()):
        if not act_dir.is_dir():
            continue
        streams_path = act_dir / "streams.json"
        if not streams_path.exists():
            continue
        streams = load_json(streams_path)
        if not streams or not isinstance(streams, list):
            continue
        try:
            db.upsert_intervals_activity_streams(act_dir.name, streams)
            count += 1
        except Exception as e:
            print(f"  ERR streams {act_dir.name}: {e}")
    return count


def load_garmin_daily():
    """Step 7: Load garmin_daily from daily/{date}/ dirs."""
    daily_dir = GARMIN_DIR / "daily"
    if not daily_dir.exists():
        return 0
    count = 0
    for day_dir in sorted(daily_dir.iterdir()):
        if not day_dir.is_dir():
            continue
        date_str = day_dir.name

        endpoint_data = {}
        for fpath in day_dir.iterdir():
            if fpath.suffix == ".json":
                endpoint_data[fpath.name] = load_json(fpath)

        if endpoint_data:
            try:
                db.upsert_garmin_daily(date_str, endpoint_data)
                count += 1
            except Exception as e:
                print(f"  ERR daily {date_str}: {e}")
    return count


def load_garmin_sleep():
    """Step 8: Load garmin_sleep from daily/{date}/sleep.json."""
    daily_dir = GARMIN_DIR / "daily"
    if not daily_dir.exists():
        return 0
    count = 0
    for day_dir in sorted(daily_dir.iterdir()):
        if not day_dir.is_dir():
            continue
        sleep_path = day_dir / "sleep.json"
        if not sleep_path.exists():
            continue
        sleep_data = load_json(sleep_path)
        if not sleep_data:
            continue
        try:
            db.upsert_garmin_sleep(day_dir.name, sleep_data)
            count += 1
        except Exception as e:
            print(f"  ERR sleep {day_dir.name}: {e}")
    return count


def load_intervals_daily():
    """Step 9: Load intervals_daily from wellness/ per-date files."""
    wellness_dir = INTERVALS_DIR / "wellness"
    if not wellness_dir.exists():
        return 0
    count = 0
    for fpath in sorted(wellness_dir.iterdir()):
        if fpath.suffix != ".json" or fpath.name == "all.json":
            continue
        date_str = fpath.stem
        data = load_json(fpath)
        if not data:
            continue
        try:
            db.upsert_intervals_daily(date_str, data)
            count += 1
        except Exception as e:
            print(f"  ERR wellness {date_str}: {e}")
    return count


def load_garmin_reference():
    """Step 10: Load garmin_reference_data from profile, devices, gear, etc."""
    count = 0

    # Mapping: (directory, category) for dirs with JSON files
    ref_dirs = [
        ("profile", "profile"),
        ("devices", "devices"),
        ("gear", "gear"),
        ("badges", "badges"),
        ("challenges", "challenges"),
        ("goals", "goals"),
        ("workouts", "workouts"),
        ("weekly", "weekly"),
        ("blood_pressure", "blood_pressure"),
        ("weight", "weight"),
        ("progress", "progress"),
    ]

    for dirname, category in ref_dirs:
        ref_dir = GARMIN_DIR / dirname
        if not ref_dir.exists():
            continue
        for fpath in ref_dir.rglob("*.json"):
            data = load_json(fpath)
            if data is None:
                continue
            # Key = relative path from category dir
            key = str(fpath.relative_to(ref_dir))
            try:
                db.upsert_garmin_reference(category, key, data)
                count += 1
            except Exception as e:
                print(f"  ERR ref {category}/{key}: {e}")
    return count


def load_intervals_reference():
    """Step 11: Load intervals_reference_data from athlete, events, workouts."""
    count = 0
    ref_files = [
        ("athlete", "athlete.json", INTERVALS_DIR / "athlete.json"),
        ("events", "events.json", INTERVALS_DIR / "events.json"),
        ("workouts", "workouts.json", INTERVALS_DIR / "workouts.json"),
    ]

    for category, key, fpath in ref_files:
        if not fpath.exists():
            continue
        data = load_json(fpath)
        if data is None:
            continue
        try:
            db.upsert_intervals_reference(category, key, data)
            count += 1
        except Exception as e:
            print(f"  ERR ref {category}/{key}: {e}")
    return count


def main():
    print("Ensuring schema exists...")
    db.ensure_schema()

    steps = [
        ("garmin_activities",           load_garmin_activities),
        ("intervals_activities",        load_intervals_activities),
        ("garmin_activity_details",     load_garmin_activity_details),
        ("garmin_activity_streams",     load_garmin_activity_streams),
        ("intervals_activity_details",  load_intervals_activity_details),
        ("intervals_activity_streams",  load_intervals_activity_streams),
        ("garmin_daily",                load_garmin_daily),
        ("garmin_sleep",                load_garmin_sleep),
        ("intervals_daily",            load_intervals_daily),
        ("garmin_reference_data",       load_garmin_reference),
        ("intervals_reference_data",    load_intervals_reference),
    ]

    total = 0
    for name, func in steps:
        print(f"\nLoading {name}...")
        count = func()
        print(f"  -> {count} rows")
        total += count

    print(f"\nDone. Total: {total} rows loaded.")


if __name__ == "__main__":
    main()
