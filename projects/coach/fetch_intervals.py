"""Fetch all available data from Intervals.icu and save raw JSON locally."""

import argparse
import getpass
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data" / "intervals"
BASE_URL = "https://intervals.icu/api/v1"


def save_json(path: Path, data) -> None:
    """Save data as JSON, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def api_get(session: requests.Session, path: str, description: str,
            params: dict | None = None):
    """GET request with retry and error handling. Returns parsed JSON or None."""
    url = f"{BASE_URL}{path}"
    for attempt in range(3):
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code in (400, 403, 404):
                print(f"  SKIP {description}: {resp.status_code} {resp.reason}")
                return None
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited on {description}, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            return resp.text if resp.ok else None
        except requests.exceptions.RequestException as e:
            if attempt < 2:
                print(f"  Retry {attempt + 1} for {description}: {e}")
                time.sleep(2)
                continue
            print(f"  SKIP {description}: {e}")
            return None
    return None


def authenticate() -> requests.Session:
    """Create authenticated session. Reads API key from file or prompts."""
    key_path = DATA_DIR / ".api_key"
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        api_key = key_path.read_text().strip()
        if api_key:
            print("Using cached API key")
    else:
        api_key = ""

    if not api_key:
        print("Get your API key from https://intervals.icu/settings -> Developer Settings")
        api_key = getpass.getpass("Intervals.icu API key: ")
        key_path.write_text(api_key)
        key_path.chmod(0o600)

    session = requests.Session()
    session.auth = ("API_KEY", api_key)

    # Verify auth
    resp = session.get(f"{BASE_URL}/athlete/0", timeout=10)
    if resp.status_code == 401:
        print("Authentication failed. Check your API key.")
        key_path.unlink(missing_ok=True)
        raise SystemExit(1)
    resp.raise_for_status()
    athlete = resp.json()
    print(f"Authenticated as {athlete.get('name', athlete.get('id', '?'))}")
    save_json(DATA_DIR / "athlete.json", athlete)
    return session


# ---------------------------------------------------------------------------
# Fetch functions
# ---------------------------------------------------------------------------

def fetch_activities(session: requests.Session, today: date, full: bool = False) -> list:
    """Fetch all activities. Returns the full list."""
    print("Fetching activities list...")
    list_path = DATA_DIR / "activities" / "list.json"

    existing = []
    newest_date = None
    if not full and list_path.exists():
        with open(list_path, encoding="utf-8") as f:
            existing = json.load(f)
        if existing:
            dates = [a.get("start_date_local", "") for a in existing if a.get("start_date_local")]
            if dates:
                newest_date = max(dates)[:10]
                print(f"  Found {len(existing)} cached activities (newest: {newest_date})")

    start_date = newest_date if newest_date else "2000-01-01"
    end_date = str(today)

    batch = api_get(session, "/athlete/0/activities",
                    "activities list",
                    params={"oldest": start_date, "newest": end_date})
    if not batch:
        batch = []

    existing_ids = {a.get("id") for a in existing}
    added = 0
    for a in batch:
        if a.get("id") not in existing_ids:
            existing.append(a)
            existing_ids.add(a.get("id"))
            added += 1

    save_json(list_path, existing)
    print(f"  Fetched {len(batch)}, {added} new (total: {len(existing)})")
    return existing


def fetch_activity_details(session: requests.Session, activities: list,
                           full: bool = False) -> None:
    """Fetch detail + streams for each activity."""
    total = len(activities)
    print(f"Fetching details for {total} activities...")

    for i, activity in enumerate(activities):
        aid = activity.get("id", "")
        if not aid:
            continue

        act_dir = DATA_DIR / "activities" / str(aid)

        # Skip if both files exist
        if not full and act_dir.exists():
            existing = set(f.name for f in act_dir.iterdir())
            if {"detail.json", "streams.json"}.issubset(existing):
                continue

        print(f"  [{i + 1}/{total}] Activity {aid}")

        if full or not (act_dir / "detail.json").exists():
            detail = api_get(session, f"/activity/{aid}",
                             f"activity {aid} detail",
                             params={"intervals": "true"})
            if detail is not None:
                save_json(act_dir / "detail.json", detail)

        if full or not (act_dir / "streams.json").exists():
            streams = api_get(session, f"/activity/{aid}/streams.json",
                              f"activity {aid} streams")
            if streams is not None:
                save_json(act_dir / "streams.json", streams)

        time.sleep(0.5)

    print("  Activity details complete")


def fetch_wellness(session: requests.Session, activities: list, today: date,
                   full: bool = False) -> None:
    """Fetch wellness data (CTL, ATL, TSB, weight, HR, sleep, etc.) for every day."""
    print("Fetching wellness data...")
    wellness_dir = DATA_DIR / "wellness"

    # Find earliest activity date
    earliest = today - timedelta(days=90)
    for a in activities:
        d = a.get("start_date_local", "")[:10]
        if d:
            try:
                from datetime import date as d_type
                dt = d_type.fromisoformat(d)
                if dt < earliest:
                    earliest = dt
            except ValueError:
                pass

    # Fetch in chunks of 90 days (API may have limits)
    chunk_start = earliest
    all_wellness = []
    while chunk_start <= today:
        chunk_end = min(chunk_start + timedelta(days=89), today)
        data = api_get(session, "/athlete/0/wellness",
                       f"wellness {chunk_start} to {chunk_end}",
                       params={"oldest": str(chunk_start), "newest": str(chunk_end)})
        if data and isinstance(data, list):
            all_wellness.extend(data)
        chunk_start = chunk_end + timedelta(days=1)
        time.sleep(0.5)

    # Save bulk file
    save_json(wellness_dir / "all.json", all_wellness)

    # Also save per-day files
    for record in all_wellness:
        day = record.get("id", "")
        if day:
            day_path = wellness_dir / f"{day}.json"
            if full or not day_path.exists():
                save_json(day_path, record)

    print(f"  Saved {len(all_wellness)} wellness records")


def fetch_events(session: requests.Session, activities: list, today: date) -> None:
    """Fetch calendar events (planned workouts, notes, etc.)."""
    print("Fetching calendar events...")

    earliest = today - timedelta(days=365)
    for a in activities:
        d = a.get("start_date_local", "")[:10]
        if d:
            try:
                from datetime import date as d_type
                dt = d_type.fromisoformat(d)
                if dt < earliest:
                    earliest = dt
            except ValueError:
                pass

    data = api_get(session, "/athlete/0/events",
                   "calendar events",
                   params={"oldest": str(earliest), "newest": str(today)})
    if data is not None:
        save_json(DATA_DIR / "events.json", data)
        print(f"  Saved {len(data) if isinstance(data, list) else '?'} events")


def fetch_workouts(session: requests.Session) -> None:
    """Fetch workout library."""
    print("Fetching workouts...")
    data = api_get(session, "/athlete/0/workouts", "workouts")
    if data is not None:
        save_json(DATA_DIR / "workouts.json", data)
        count = len(data) if isinstance(data, list) else "?"
        print(f"  Saved {count} workouts")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch all data from Intervals.icu.")
    parser.add_argument("--full", action="store_true",
                        help="Force re-fetch everything (ignore incremental cache)")
    args = parser.parse_args()

    session = authenticate()
    today = date.today()

    activities = fetch_activities(session, today, full=args.full)
    fetch_activity_details(session, activities, full=args.full)
    fetch_wellness(session, activities, today, full=args.full)
    fetch_events(session, activities, today)
    fetch_workouts(session)

    # Summary
    total_files = sum(1 for _ in DATA_DIR.rglob("*.json"))
    total_size_mb = sum(f.stat().st_size for f in DATA_DIR.rglob("*.json")) / 1024 / 1024
    print(f"\nTotal: {total_files} JSON files, {total_size_mb:.1f} MB")
    print("Done.")


if __name__ == "__main__":
    main()
