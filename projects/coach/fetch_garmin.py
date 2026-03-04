"""Fetch all available data from Garmin Connect and save raw JSON locally."""

import argparse
import getpass
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data" / "garmin"
TOKEN_DIR = DATA_DIR / ".tokens"


def save_json(path: Path, data) -> None:
    """Save data as JSON, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def api_call(description: str, func, *args, **kwargs):
    """Call a Garmin API method with retry and error handling. Returns data or None."""
    for attempt in range(3):
        try:
            return func(*args, **kwargs)
        except GarminConnectAuthenticationError:
            raise  # don't retry auth errors
        except Exception as e:
            err = str(e)
            if "429" in err or "Too Many" in err:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited on {description}, waiting {wait}s...")
                time.sleep(wait)
                continue
            if attempt < 2:
                print(f"  Retry {attempt + 1} for {description}: {e}")
                time.sleep(2)
                continue
            print(f"  SKIP {description}: {e}")
            return None
    return None


def authenticate() -> Garmin:
    """Authenticate with Garmin Connect. Uses cached tokens if available."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_path = str(TOKEN_DIR)

    garmin = Garmin()

    # Try cached tokens first
    if (TOKEN_DIR / "oauth1_token.json").exists():
        try:
            garmin.login(token_path)
            print(f"Authenticated as {garmin.display_name}")
            return garmin
        except Exception:
            print("Cached tokens expired, re-authenticating...")

    # Interactive login
    email = input("Garmin email: ")
    password = getpass.getpass("Garmin password: ")
    garmin = Garmin(email=email, password=password, prompt_mfa=lambda: input("MFA code: "))
    garmin.login()
    garmin.garth.dump(token_path)
    print(f"Authenticated as {garmin.display_name}")
    return garmin


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch all data from Garmin Connect.")
    parser.add_argument("--full", action="store_true",
                        help="Force re-fetch everything (ignore incremental cache)")
    return parser.parse_args()


def fetch_profile(garmin: Garmin) -> None:
    """Fetch all profile/user data."""
    print("Fetching profile data...")
    profile_dir = DATA_DIR / "profile"

    endpoints = [
        ("user.json", "user profile", garmin.get_user_profile),
        ("settings.json", "user settings", garmin.get_userprofile_settings),
        ("full_name.json", "full name", lambda: {"full_name": garmin.get_full_name()}),
        ("units.json", "unit system", lambda: {"unit_system": garmin.get_unit_system()}),
        ("personal_records.json", "personal records", garmin.get_personal_record),
        ("activity_types.json", "activity types", garmin.get_activity_types),
        ("lactate_threshold.json", "lactate threshold", garmin.get_lactate_threshold),
        ("cycling_ftp.json", "cycling FTP", garmin.get_cycling_ftp),
    ]

    for filename, desc, func in endpoints:
        data = api_call(desc, func)
        if data is not None:
            save_json(profile_dir / filename, data)
    print(f"  Saved {len(endpoints)} profile files")


def fetch_devices(garmin: Garmin) -> None:
    """Fetch device list and per-device settings."""
    print("Fetching devices...")
    devices_dir = DATA_DIR / "devices"

    devices = api_call("device list", garmin.get_devices)
    if devices is None:
        return
    save_json(devices_dir / "list.json", devices)

    primary = api_call("primary device", garmin.get_primary_training_device)
    if primary is not None:
        save_json(devices_dir / "primary.json", primary)

    last_used = api_call("last used device", garmin.get_device_last_used)
    if last_used is not None:
        save_json(devices_dir / "last_used.json", last_used)

    for device in devices:
        device_id = str(device.get("deviceId", ""))
        if not device_id:
            continue
        dev_dir = devices_dir / device_id

        settings = api_call(f"device {device_id} settings", garmin.get_device_settings, device_id)
        if settings is not None:
            save_json(dev_dir / "settings.json", settings)

        solar = api_call(f"device {device_id} solar", garmin.get_device_solar_data,
                         device_id, str(date.today() - timedelta(days=30)), str(date.today()))
        if solar is not None:
            save_json(dev_dir / "solar.json", solar)

    print(f"  Saved data for {len(devices)} devices")


def fetch_gear(garmin: Garmin) -> None:
    """Fetch gear list and per-gear stats."""
    print("Fetching gear...")
    gear_dir = DATA_DIR / "gear"

    profile = api_call("profile for gear", garmin.get_user_profile)
    if not profile:
        print("  Could not get profile for gear lookup")
        return
    profile_number = str(profile.get("userProfileNumber", profile.get("profileNumber", "")))
    if not profile_number:
        print("  No userProfileNumber found, skipping gear")
        return

    gear_list = api_call("gear list", garmin.get_gear, profile_number)
    if gear_list is None:
        return
    save_json(gear_dir / "list.json", gear_list)

    defaults = api_call("gear defaults", garmin.get_gear_defaults, profile_number)
    if defaults is not None:
        save_json(gear_dir / "defaults.json", defaults)

    items = gear_list if isinstance(gear_list, list) else gear_list.get("gearItems", [])
    for item in items:
        gear_uuid = item.get("uuid", "")
        if not gear_uuid:
            continue
        g_dir = gear_dir / gear_uuid

        stats = api_call(f"gear {gear_uuid} stats", garmin.get_gear_stats, gear_uuid)
        if stats is not None:
            save_json(g_dir / "stats.json", stats)

        activities = api_call(f"gear {gear_uuid} activities", garmin.get_gear_activities, gear_uuid)
        if activities is not None:
            save_json(g_dir / "activities.json", activities)

    print(f"  Saved data for {len(items)} gear items")


def fetch_badges_and_challenges(garmin: Garmin) -> None:
    """Fetch all badges and challenges."""
    print("Fetching badges & challenges...")
    badges_dir = DATA_DIR / "badges"
    challenges_dir = DATA_DIR / "challenges"

    badge_endpoints = [
        ("earned.json", "earned badges", garmin.get_earned_badges),
        ("available.json", "available badges", garmin.get_available_badges),
        ("in_progress.json", "in-progress badges", garmin.get_in_progress_badges),
    ]
    for filename, desc, func in badge_endpoints:
        data = api_call(desc, func)
        if data is not None:
            save_json(badges_dir / filename, data)

    challenge_endpoints = [
        ("adhoc.json", "adhoc challenges", lambda: garmin.get_adhoc_challenges(0, 100)),
        ("badge.json", "badge challenges", lambda: garmin.get_badge_challenges(0, 100)),
        ("available_badge.json", "available badge challenges",
         lambda: garmin.get_available_badge_challenges(0, 100)),
        ("non_completed_badge.json", "non-completed badge challenges",
         lambda: garmin.get_non_completed_badge_challenges(0, 100)),
        ("virtual_in_progress.json", "virtual challenges in progress",
         lambda: garmin.get_inprogress_virtual_challenges(0, 100)),
    ]
    for filename, desc, func in challenge_endpoints:
        data = api_call(desc, func)
        if data is not None:
            save_json(challenges_dir / filename, data)

    print("  Saved badges & challenges")


def fetch_goals(garmin: Garmin) -> None:
    """Fetch all goals."""
    print("Fetching goals...")
    goals_dir = DATA_DIR / "goals"
    for status in ["active", "future", "past"]:
        data = api_call(f"{status} goals", garmin.get_goals, status, 0, 100)
        if data is not None:
            save_json(goals_dir / f"{status}.json", data)
    print("  Saved goals")


def fetch_workouts(garmin: Garmin) -> None:
    """Fetch all workouts."""
    print("Fetching workouts...")
    workouts_dir = DATA_DIR / "workouts"

    all_workouts = []
    start = 0
    while True:
        batch = api_call(f"workouts page {start}", garmin.get_workouts, start, 100)
        if not batch:
            break
        items = batch if isinstance(batch, list) else batch.get("workouts", [])
        if not items:
            break
        all_workouts.extend(items)
        start += 100
        time.sleep(0.5)

    if all_workouts:
        save_json(workouts_dir / "list.json", all_workouts)
        for w in all_workouts:
            wid = w.get("workoutId", "")
            if wid:
                detail = api_call(f"workout {wid}", garmin.get_workout_by_id, wid)
                if detail is not None:
                    save_json(workouts_dir / f"{wid}.json", detail)
                time.sleep(0.5)
    print(f"  Saved {len(all_workouts)} workouts")


def fetch_activities(garmin: Garmin, today: date, full: bool = False) -> list:
    """Fetch all activities. Returns the full list."""
    print("Fetching activities list...")
    activities_dir = DATA_DIR / "activities"
    list_path = activities_dir / "list.json"

    existing = []
    newest_date = None
    if not full and list_path.exists():
        with open(list_path, encoding="utf-8") as f:
            existing = json.load(f)
        if existing:
            dates = [a.get("startTimeLocal", "") for a in existing if a.get("startTimeLocal")]
            if dates:
                newest_date = max(dates)[:10]
                print(f"  Found {len(existing)} cached activities (newest: {newest_date})")

    start_date = newest_date if newest_date else "2000-01-01"
    end_date = str(today)
    new_activities = []
    page = 0

    while True:
        batch = api_call(
            f"activities page {page}",
            garmin.get_activities_by_date, start_date, end_date,
        )
        if not batch:
            break
        new_activities.extend(batch)
        print(f"  Fetched {len(new_activities)} activities so far...")
        if len(batch) < 100:
            break
        page += 1
        time.sleep(1)

    if newest_date and not full:
        existing_ids = {a.get("activityId") for a in existing}
        added = 0
        for a in new_activities:
            if a.get("activityId") not in existing_ids:
                existing.append(a)
                added += 1
        print(f"  Added {added} new activities (total: {len(existing)})")
        all_activities = existing
    else:
        all_activities = new_activities
        print(f"  Fetched {len(all_activities)} total activities")

    save_json(list_path, all_activities)
    return all_activities


ACTIVITY_ENDPOINTS = [
    ("summary.json", "summary", lambda g, aid: g.get_activity(aid)),
    ("details.json", "details", lambda g, aid: g.get_activity_details(aid, maxchart=10000, maxpoly=10000)),
    ("splits.json", "splits", lambda g, aid: g.get_activity_splits(aid)),
    ("typed_splits.json", "typed splits", lambda g, aid: g.get_activity_typed_splits(aid)),
    ("split_summaries.json", "split summaries", lambda g, aid: g.get_activity_split_summaries(aid)),
    ("hr_zones.json", "HR zones", lambda g, aid: g.get_activity_hr_in_timezones(aid)),
    ("power_zones.json", "power zones", lambda g, aid: g.get_activity_power_in_timezones(aid)),
    ("weather.json", "weather", lambda g, aid: g.get_activity_weather(aid)),
    ("exercise_sets.json", "exercise sets", lambda g, aid: g.get_activity_exercise_sets(aid)),
    ("gear.json", "gear", lambda g, aid: g.get_activity_gear(aid)),
]


def fetch_activity_details(garmin: Garmin, activities: list, full: bool = False) -> None:
    """Fetch all sub-endpoints for each activity."""
    total = len(activities)
    print(f"Fetching details for {total} activities...")
    activities_dir = DATA_DIR / "activities"

    for i, activity in enumerate(activities):
        aid = str(activity.get("activityId", ""))
        if not aid:
            continue

        act_dir = activities_dir / aid

        if not full and act_dir.exists():
            existing_files = set(f.name for f in act_dir.iterdir())
            expected_files = set(fname for fname, _, _ in ACTIVITY_ENDPOINTS)
            if expected_files.issubset(existing_files):
                continue

        print(f"  [{i + 1}/{total}] Activity {aid}")
        for filename, desc, func in ACTIVITY_ENDPOINTS:
            if not full and (act_dir / filename).exists():
                continue
            data = api_call(f"activity {aid} {desc}", func, garmin, aid)
            if data is not None:
                save_json(act_dir / filename, data)

        time.sleep(1)

    print("  Activity details complete")


DAILY_ENDPOINTS = [
    ("summary.json", "summary", lambda g, d: g.get_user_summary(d)),
    ("heart_rates.json", "heart rates", lambda g, d: g.get_heart_rates(d)),
    ("stress.json", "stress", lambda g, d: g.get_all_day_stress(d)),
    ("stress_detail.json", "stress detail", lambda g, d: g.get_stress_data(d)),
    ("events.json", "events", lambda g, d: g.get_all_day_events(d)),
    ("steps.json", "steps", lambda g, d: g.get_steps_data(d)),
    ("floors.json", "floors", lambda g, d: g.get_floors(d)),
    ("sleep.json", "sleep", lambda g, d: g.get_sleep_data(d)),
    ("body_battery.json", "body battery", lambda g, d: g.get_body_battery(d)),
    ("body_battery_events.json", "body battery events", lambda g, d: g.get_body_battery_events(d)),
    ("rhr.json", "resting HR", lambda g, d: g.get_rhr_day(d)),
    ("hrv.json", "HRV", lambda g, d: g.get_hrv_data(d)),
    ("spo2.json", "SpO2", lambda g, d: g.get_spo2_data(d)),
    ("respiration.json", "respiration", lambda g, d: g.get_respiration_data(d)),
    ("intensity_minutes.json", "intensity minutes", lambda g, d: g.get_intensity_minutes_data(d)),
    ("training_readiness.json", "training readiness", lambda g, d: g.get_training_readiness(d)),
    ("training_status.json", "training status", lambda g, d: g.get_training_status(d)),
    ("endurance_score.json", "endurance score", lambda g, d: g.get_endurance_score(d)),
    ("hill_score.json", "hill score", lambda g, d: g.get_hill_score(d)),
    ("max_metrics.json", "max metrics", lambda g, d: g.get_max_metrics(d)),
    ("race_predictions.json", "race predictions", lambda g, d: g.get_race_predictions(d)),
    ("body_composition.json", "body composition", lambda g, d: g.get_body_composition(d)),
    ("weigh_ins.json", "weigh-ins", lambda g, d: g.get_daily_weigh_ins(d)),
    ("hydration.json", "hydration", lambda g, d: g.get_hydration_data(d)),
    ("fitness_age.json", "fitness age", lambda g, d: g.get_fitnessage_data(d)),
    ("lifestyle.json", "lifestyle", lambda g, d: g.get_lifestyle_logging_data(d)),
]


def fetch_daily(garmin: Garmin, activities: list, today: date, full: bool = False) -> None:
    """Fetch daily wellness data for every date that has activity data, plus recent 90 days."""
    daily_dir = DATA_DIR / "daily"

    activity_dates = []
    for a in activities:
        d = a.get("startTimeLocal", "")[:10]
        if d:
            try:
                activity_dates.append(date.fromisoformat(d))
            except ValueError:
                pass

    if not activity_dates:
        start = today - timedelta(days=90)
    else:
        start = min(activity_dates)

    dates_to_fetch = set(activity_dates)
    for i in range(90):
        dates_to_fetch.add(today - timedelta(days=i))
    dates_to_fetch = sorted(dates_to_fetch)

    total = len(dates_to_fetch)
    print(f"Fetching daily data for {total} dates ({dates_to_fetch[0]} to {dates_to_fetch[-1]})...")

    for i, d in enumerate(dates_to_fetch):
        d_str = str(d)
        day_dir = daily_dir / d_str

        if not full and day_dir.exists():
            existing = set(f.name for f in day_dir.iterdir())
            expected = set(fname for fname, _, _ in DAILY_ENDPOINTS)
            if expected.issubset(existing):
                continue

        if (i + 1) % 30 == 0 or i == 0:
            print(f"  [{i + 1}/{total}] {d_str}")

        for filename, desc, func in DAILY_ENDPOINTS:
            if not full and (day_dir / filename).exists():
                continue
            data = api_call(f"{d_str} {desc}", func, garmin, d_str)
            if data is not None:
                save_json(day_dir / filename, data)

        time.sleep(0.5)

    print("  Daily data complete")


def fetch_weekly(garmin: Garmin, today: date, full: bool = False) -> None:
    """Fetch weekly aggregated data."""
    print("Fetching weekly data...")
    weekly_dir = DATA_DIR / "weekly"
    today_str = str(today)

    steps = api_call("weekly steps", garmin.get_weekly_steps, today_str, 52)
    if steps is not None:
        save_json(weekly_dir / "steps.json", steps)

    stress = api_call("weekly stress", garmin.get_weekly_stress, today_str, 52)
    if stress is not None:
        save_json(weekly_dir / "stress.json", stress)

    start_str = str(today - timedelta(weeks=52))
    intensity = api_call("weekly intensity minutes",
                         garmin.get_weekly_intensity_minutes, start_str, today_str)
    if intensity is not None:
        save_json(weekly_dir / "intensity_minutes.json", intensity)

    print("  Weekly data complete")


def fetch_range_data(garmin: Garmin, activities: list, today: date) -> None:
    """Fetch data that spans a date range (blood pressure, weight, progress)."""
    print("Fetching range data...")

    earliest = today - timedelta(days=365)
    for a in activities:
        d = a.get("startTimeLocal", "")[:10]
        if d:
            try:
                dt = date.fromisoformat(d)
                if dt < earliest:
                    earliest = dt
            except ValueError:
                pass

    earliest_str = str(earliest)
    today_str = str(today)

    bp = api_call("blood pressure", garmin.get_blood_pressure, earliest_str, today_str)
    if bp is not None:
        save_json(DATA_DIR / "blood_pressure" / "all.json", bp)

    weight = api_call("weight", garmin.get_weigh_ins, earliest_str, today_str)
    if weight is not None:
        save_json(DATA_DIR / "weight" / "all.json", weight)

    progress = api_call("progress summary",
                        garmin.get_progress_summary_between_dates, earliest_str, today_str)
    if progress is not None:
        save_json(DATA_DIR / "progress" / "summary.json", progress)

    print("  Range data complete")


def main():
    args = parse_args()
    garmin = authenticate()
    today = date.today()

    fetch_profile(garmin)
    fetch_devices(garmin)
    fetch_gear(garmin)
    fetch_badges_and_challenges(garmin)
    fetch_goals(garmin)
    fetch_workouts(garmin)

    activities = fetch_activities(garmin, today, full=args.full)
    fetch_activity_details(garmin, activities, full=args.full)
    fetch_daily(garmin, activities, today, full=args.full)
    fetch_weekly(garmin, today, full=args.full)
    fetch_range_data(garmin, activities, today)

    # Print summary
    total_files = sum(1 for _ in DATA_DIR.rglob("*.json"))
    total_size_mb = sum(f.stat().st_size for f in DATA_DIR.rglob("*.json")) / 1024 / 1024
    print(f"\nTotal: {total_files} JSON files, {total_size_mb:.1f} MB")

    print("\nDone.")


if __name__ == "__main__":
    main()
