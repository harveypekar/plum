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

    print("\nDone.")


if __name__ == "__main__":
    main()
