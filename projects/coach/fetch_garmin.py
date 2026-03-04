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
