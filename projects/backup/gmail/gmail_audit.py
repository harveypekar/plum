#!/usr/bin/env python3
"""Generate Gmail space usage audit report.

Usage: python gmail_audit.py
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from gmail_common import (
    SCOPES_READONLY,
    get_gmail_service,
    get_reports_dir,
    setup_logging,
)

log = setup_logging("gmail-audit")

CATEGORY_MAP = {
    "CATEGORY_PERSONAL": "primary",
    "CATEGORY_SOCIAL": "social",
    "CATEGORY_PROMOTIONS": "promotions",
    "CATEGORY_UPDATES": "updates",
    "CATEGORY_FORUMS": "forums",
}


def get_sender(msg: dict) -> str:
    """Extract sender email from message payload headers."""
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == "from":
            match = re.search(r"<(.+?)>", h["value"])
            return match.group(1) if match else h["value"]
    return "unknown"


def get_attachments(payload: dict) -> list[dict]:
    """Recursively find attachments in message payload."""
    attachments = []
    if payload.get("filename"):
        ext = Path(payload["filename"]).suffix.lstrip(".").lower() or "unknown"
        size = payload.get("body", {}).get("size", 0)
        attachments.append({"filename": payload["filename"], "ext": ext, "size": size})
    for part in payload.get("parts", []):
        attachments.extend(get_attachments(part))
    return attachments


def aggregate_messages(messages: list[dict]) -> dict:
    """Aggregate message metadata into an audit report."""
    by_sender = defaultdict(lambda: {"count": 0, "total_size": 0})
    by_category = defaultdict(lambda: {"count": 0, "total_size": 0})
    by_year = defaultdict(lambda: {"count": 0, "total_size": 0})
    attachments = defaultdict(lambda: {"count": 0, "total_size": 0})
    largest = []

    for msg in messages:
        size = msg.get("sizeEstimate", 0)
        labels = msg.get("labelIds", [])
        internal_date_ms = int(msg.get("internalDate", "0"))
        dt = datetime.fromtimestamp(internal_date_ms / 1000)
        sender = get_sender(msg)

        # By sender
        by_sender[sender]["count"] += 1
        by_sender[sender]["total_size"] += size

        # By category
        categorized = False
        for label in labels:
            if label in CATEGORY_MAP:
                cat = CATEGORY_MAP[label]
                by_category[cat]["count"] += 1
                by_category[cat]["total_size"] += size
                categorized = True
        if not categorized:
            by_category["uncategorized"]["count"] += 1
            by_category["uncategorized"]["total_size"] += size

        # By year
        year = str(dt.year)
        by_year[year]["count"] += 1
        by_year[year]["total_size"] += size

        # Largest
        largest.append({"id": msg["id"], "sender": sender, "size": size, "date": dt.isoformat()})

        # Attachments
        for att in get_attachments(msg.get("payload", {})):
            attachments[att["ext"]]["count"] += 1
            attachments[att["ext"]]["total_size"] += att["size"]

    # Sort largest, keep top 50
    largest.sort(key=lambda x: x["size"], reverse=True)
    largest = largest[:50]

    # Sort senders by total size, keep top 20
    top_senders = dict(
        sorted(by_sender.items(), key=lambda x: x[1]["total_size"], reverse=True)[:20]
    )

    return {
        "by_sender": top_senders,
        "by_category": dict(by_category),
        "by_year": dict(by_year),
        "largest": largest,
        "attachments": dict(attachments),
        "total_messages": len(messages),
        "total_size": sum(m.get("sizeEstimate", 0) for m in messages),
    }


def format_size(size_bytes: int) -> str:
    """Human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def print_report(report: dict):
    """Print human-readable audit summary."""
    print(f"\n{'=' * 60}")
    print(f"Gmail Audit Report — {report['total_messages']} messages, {format_size(report['total_size'])}")
    print(f"{'=' * 60}")

    print(f"\n--- By Category ---")
    for cat, data in sorted(report["by_category"].items(), key=lambda x: x[1]["total_size"], reverse=True):
        print(f"  {cat:20s}  {data['count']:6d} msgs  {format_size(data['total_size']):>10s}")

    print(f"\n--- By Year ---")
    for year, data in sorted(report["by_year"].items()):
        print(f"  {year}  {data['count']:6d} msgs  {format_size(data['total_size']):>10s}")

    print(f"\n--- Top 20 Senders by Size ---")
    for sender, data in report["by_sender"].items():
        print(f"  {sender:40s}  {data['count']:5d} msgs  {format_size(data['total_size']):>10s}")

    print(f"\n--- Attachments by Type ---")
    for ext, data in sorted(report["attachments"].items(), key=lambda x: x[1]["total_size"], reverse=True):
        print(f"  .{ext:10s}  {data['count']:5d} files  {format_size(data['total_size']):>10s}")

    print(f"\n--- Top 10 Largest Emails ---")
    for msg in report["largest"][:10]:
        print(f"  {msg['date'][:10]}  {msg['sender']:30s}  {format_size(msg['size']):>10s}  id:{msg['id']}")

    print()


def fetch_all_message_metadata(service) -> list[dict]:
    """Fetch metadata for all messages (paginated)."""
    messages = []
    request = service.users().messages().list(userId="me", maxResults=500)
    msg_ids = []
    while request:
        response = request.execute()
        if "messages" in response:
            msg_ids.extend(m["id"] for m in response["messages"])
        request = service.users().messages().list_next(request, response)
        log.info(f"Listed {len(msg_ids)} message IDs...")

    log.info(f"Fetching metadata for {len(msg_ids)} messages...")
    for i, msg_id in enumerate(msg_ids, 1):
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="metadata",
                metadataHeaders=["From"]
            ).execute()
            messages.append(msg)
            if i % 500 == 0:
                log.info(f"Fetched metadata for {i}/{len(msg_ids)}")
        except Exception as e:
            log.error(f"Failed to fetch {msg_id}: {e}")

    return messages


def main():
    log.info("Starting Gmail audit")
    service = get_gmail_service(SCOPES_READONLY)

    messages = fetch_all_message_metadata(service)
    report = aggregate_messages(messages)

    # Save JSON report
    reports_dir = get_reports_dir()
    report_path = reports_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    log.info(f"Report saved to {report_path}")

    # Print summary
    print_report(report)


if __name__ == "__main__":
    main()
