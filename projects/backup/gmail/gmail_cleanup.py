#!/usr/bin/env python3
"""Apply cleanup rules to Gmail, trashing matching messages.

Usage:
    python gmail_cleanup.py             # dry-run (default)
    python gmail_cleanup.py --execute   # actually trash matching messages
"""

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from gmail_common import (
    SCOPES_MODIFY,
    get_gmail_service,
    load_metadata,
    setup_logging,
)

log = setup_logging("gmail-cleanup")

SCRIPT_DIR = Path(__file__).parent
CATEGORY_MAP = {
    "promotions": "CATEGORY_PROMOTIONS",
    "social": "CATEGORY_SOCIAL",
    "updates": "CATEGORY_UPDATES",
    "forums": "CATEGORY_FORUMS",
    "primary": "CATEGORY_PERSONAL",
}


def get_sender(msg: dict) -> str:
    """Extract sender email from message."""
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == "from":
            match = re.search(r"<(.+?)>", h["value"])
            return (match.group(1) if match else h["value"]).lower()
    return ""


def is_protected(msg: dict, protect_rules: list[dict]) -> bool:
    """Check if a message is protected from cleanup."""
    labels = msg.get("labelIds", [])
    for rule in protect_rules:
        if rule.get("starred") and "STARRED" in labels:
            return True
        if rule.get("label") and rule["label"] in labels:
            return True
    return False


def matches_rule(msg: dict, rule: dict) -> bool:
    """Check if a message matches a cleanup rule."""
    labels = msg.get("labelIds", [])
    size = msg.get("sizeEstimate", 0)
    internal_date_ms = int(msg.get("internalDate", "0"))
    msg_date = datetime.fromtimestamp(internal_date_ms / 1000)
    sender = get_sender(msg)

    # Check age requirement (all rules must have older_than_days)
    if "older_than_days" in rule:
        cutoff = datetime.now() - timedelta(days=rule["older_than_days"])
        if msg_date > cutoff:
            return False

    # Check category
    if "category" in rule:
        gmail_label = CATEGORY_MAP.get(rule["category"], "")
        if gmail_label not in labels:
            return False

    # Check size
    if "larger_than_mb" in rule:
        if size < rule["larger_than_mb"] * 1024 * 1024:
            return False

    # Check sender
    if "from" in rule:
        if sender not in [s.lower() for s in rule["from"]]:
            return False

    return True


def load_rules() -> dict:
    """Load cleanup rules from gmail-rules.yaml."""
    rules_path = SCRIPT_DIR / "gmail-rules.yaml"
    if not rules_path.exists():
        raise FileNotFoundError(f"Rules file not found: {rules_path}")
    return yaml.safe_load(rules_path.read_text())


def fetch_all_message_metadata(service) -> list[dict]:
    """Fetch metadata for all messages."""
    messages = []
    request = service.users().messages().list(userId="me", maxResults=500)
    msg_ids = []
    while request:
        response = request.execute()
        if "messages" in response:
            msg_ids.extend(m["id"] for m in response["messages"])
        request = service.users().messages().list_next(request, response)

    log.info(f"Fetching metadata for {len(msg_ids)} messages...")
    for i, msg_id in enumerate(msg_ids, 1):
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="metadata",
                metadataHeaders=["From"]
            ).execute()
            messages.append(msg)
            if i % 500 == 0:
                log.info(f"Fetched {i}/{len(msg_ids)}")
        except Exception as e:
            log.error(f"Failed to fetch {msg_id}: {e}")

    return messages


def main():
    parser = argparse.ArgumentParser(description="Gmail cleanup with rules")
    parser.add_argument("--execute", action="store_true", help="Actually trash messages (default is dry-run)")
    args = parser.parse_args()

    # Check backup freshness
    metadata = load_metadata()
    last_backup = metadata.get("last_backup")
    if last_backup:
        backup_age = datetime.now() - datetime.fromisoformat(last_backup)
        if backup_age.days > 7:
            log.error(f"Backup is {backup_age.days} days old. Run gmail_backup.py first.")
            return
    else:
        log.error("No backup found. Run gmail_backup.py first.")
        return

    config = load_rules()
    rules = config.get("rules", [])
    protect = config.get("protect", [])

    if not rules:
        log.info("No cleanup rules defined.")
        return

    log.info(f"Loaded {len(rules)} rules, {len(protect)} protect rules")
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    log.info(f"Mode: {mode}")

    service = get_gmail_service(SCOPES_MODIFY)
    messages = fetch_all_message_metadata(service)

    # Apply rules
    to_trash = {}  # msg_id -> rule_name
    for msg in messages:
        if is_protected(msg, protect):
            continue
        for rule in rules:
            if matches_rule(msg, rule):
                to_trash[msg["id"]] = rule["name"]
                break  # First matching rule wins

    # Summary by rule
    rule_counts = {}
    rule_sizes = {}
    for msg_id, rule_name in to_trash.items():
        rule_counts[rule_name] = rule_counts.get(rule_name, 0) + 1
        msg = next(m for m in messages if m["id"] == msg_id)
        rule_sizes[rule_name] = rule_sizes.get(rule_name, 0) + msg.get("sizeEstimate", 0)

    print(f"\n{'=' * 50}")
    print(f"Cleanup Summary ({mode})")
    print(f"{'=' * 50}")
    total_size = 0
    for rule_name in rule_counts:
        size = rule_sizes[rule_name]
        total_size += size
        size_mb = size / (1024 * 1024)
        print(f"  {rule_name:30s}  {rule_counts[rule_name]:5d} msgs  {size_mb:.1f} MB")
    print(f"  {'TOTAL':30s}  {len(to_trash):5d} msgs  {total_size / (1024 * 1024):.1f} MB")
    print()

    if not args.execute:
        print("Dry-run complete. Use --execute to actually trash these messages.")
        return

    # Execute: trash messages
    trashed = 0
    for msg_id in to_trash:
        try:
            service.users().messages().trash(userId="me", id=msg_id).execute()
            trashed += 1
            if trashed % 100 == 0:
                log.info(f"Trashed {trashed}/{len(to_trash)}")
        except Exception as e:
            log.error(f"Failed to trash {msg_id}: {e}")

    log.info(f"Cleanup complete: trashed {trashed} messages")


if __name__ == "__main__":
    main()
