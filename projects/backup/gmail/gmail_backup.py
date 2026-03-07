#!/usr/bin/env python3
"""Back up Gmail messages as EML files with attachment extraction.

Usage: python gmail_backup.py
"""

import base64
import email
import email.utils
import json
import sys
from datetime import datetime
from pathlib import Path

from gmail_common import (
    SCOPES_READONLY,
    get_data_dir,
    get_gmail_service,
    load_metadata,
    save_metadata,
    setup_logging,
)

log = setup_logging("gmail-backup")


def save_message(
    msg_id: str, raw_bytes: bytes, data_dir: Path, labels: list[str] | None = None
) -> dict:
    """Save raw EML to data/YYYY/MM/<msg_id>.eml and extract attachments.

    Returns dict with path (relative to data_dir) and labels.
    """
    parsed = email.message_from_bytes(raw_bytes)

    # Determine date for directory structure
    date_str = parsed.get("Date", "")
    date_tuple = email.utils.parsedate_tz(date_str)
    if date_tuple:
        dt = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
    else:
        dt = datetime.now()

    # Save EML
    year_month_dir = data_dir / f"{dt.year:04d}" / f"{dt.month:02d}"
    year_month_dir.mkdir(parents=True, exist_ok=True)
    eml_path = year_month_dir / f"{msg_id}.eml"
    eml_path.write_bytes(raw_bytes)

    # Extract attachments
    attachments_dir = data_dir / "attachments"
    for part in parsed.walk():
        content_disposition = part.get("Content-Disposition", "")
        if "attachment" not in content_disposition:
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        safe_filename = f"{msg_id}_{filename}"
        att_path = attachments_dir / safe_filename
        att_path.write_bytes(payload)

    return {
        "path": str(eml_path.relative_to(data_dir)),
        "labels": labels or [],
    }


def fetch_all_message_ids(service) -> list[str]:
    """Fetch all message IDs via pagination."""
    ids = []
    request = service.users().messages().list(userId="me", maxResults=500)
    while request:
        response = request.execute()
        if "messages" in response:
            ids.extend(m["id"] for m in response["messages"])
        request = service.users().messages().list_next(request, response)
        log.info(f"Fetched {len(ids)} message IDs so far...")
    return ids


def fetch_message_raw(service, msg_id: str) -> tuple[bytes, list[str]]:
    """Fetch a single message in raw RFC 2822 format plus its labels."""
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="raw"
    ).execute()
    raw = base64.urlsafe_b64decode(msg["raw"])
    labels = msg.get("labelIds", [])
    return raw, labels


def fetch_new_message_ids(service, history_id: str) -> list[str]:
    """Fetch message IDs added since the given historyId."""
    ids = set()
    try:
        request = service.users().history().list(
            userId="me", startHistoryId=history_id, historyTypes=["messageAdded"]
        )
        while request:
            response = request.execute()
            if "history" in response:
                for record in response["history"]:
                    for added in record.get("messagesAdded", []):
                        ids.add(added["message"]["id"])
            request = service.users().history().list_next(request, response)
    except Exception as e:
        if "historyId is no longer valid" in str(e):
            log.warning("History expired, falling back to full sync")
            return fetch_all_message_ids(service)
        raise
    return list(ids)


def main():
    log.info("Starting Gmail backup")
    service = get_gmail_service(SCOPES_READONLY)
    data_dir = get_data_dir()
    (data_dir / "attachments").mkdir(exist_ok=True)

    metadata = load_metadata()
    history_id = metadata.get("history_id")

    # Get profile for current historyId
    profile = service.users().getProfile(userId="me").execute()
    new_history_id = profile["historyId"]

    # Determine which messages to fetch
    if history_id:
        log.info(f"Incremental sync from historyId {history_id}")
        msg_ids = fetch_new_message_ids(service, history_id)
        log.info(f"Found {len(msg_ids)} new messages")
    else:
        log.info("First run — full sync")
        msg_ids = fetch_all_message_ids(service)
        log.info(f"Found {len(msg_ids)} total messages")

    # Download and save each message
    saved = 0
    skipped = 0
    for i, msg_id in enumerate(msg_ids, 1):
        if msg_id in metadata.get("messages", {}):
            skipped += 1
            continue
        try:
            raw, labels = fetch_message_raw(service, msg_id)
            result = save_message(msg_id, raw, data_dir, labels)
            metadata.setdefault("messages", {})[msg_id] = result
            saved += 1
            if saved % 100 == 0:
                log.info(f"Saved {saved} messages ({i}/{len(msg_ids)})")
                save_metadata(metadata)  # Checkpoint
        except Exception as e:
            log.error(f"Failed to fetch message {msg_id}: {e}")

    # Final metadata update
    metadata["history_id"] = new_history_id
    metadata["message_count"] = len(metadata.get("messages", {}))
    metadata["last_backup"] = datetime.now().isoformat()
    save_metadata(metadata)

    log.info(
        f"Backup complete: {saved} saved, {skipped} skipped, "
        f"{metadata['message_count']} total"
    )


if __name__ == "__main__":
    main()
