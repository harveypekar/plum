# Gmail Backup & Cleanup Tool

**Created:** 2026-03-07
**Status:** Approved

## Overview

Python-based tool to back up a single Gmail account and apply automated cleanup rules to free space. Uses the Gmail API with OAuth2 for full programmatic control over backup, auditing, and deletion.

## Location

Code and data live in `projects/backup/gmail/`. Data directories are gitignored.

## Components

### Scripts

- `gmail-backup.py` — Incremental email backup
- `gmail-audit.py` — Space usage report generator
- `gmail-cleanup.py` — Rule-based deletion (trash, not permanent delete)
- `gmail-rules.yaml` — Declarative cleanup rules config
- `requirements.txt` — Python dependencies

### Data Structure

```
projects/backup/gmail/
├── gmail-backup.py
├── gmail-audit.py
├── gmail-cleanup.py
├── gmail-rules.yaml
├── requirements.txt
├── credentials.json         # OAuth2 client credentials (gitignored)
├── token.json               # OAuth2 refresh token (gitignored)
├── data/                    # Gitignored
│   ├── metadata.json        # Last sync historyId, message index (id -> path)
│   ├── attachments/         # Flat folder, all attachments
│   │   ├── <msg-id>_report.pdf
│   │   └── <msg-id>_photo.jpg
│   ├── 2024/
│   │   ├── 01/
│   │   │   ├── <msg-id>.eml
│   │   │   └── ...
│   │   └── 12/
│   └── 2026/
└── reports/                 # Gitignored
    └── 2026-03-07.json
```

### Backup Format

- Each email saved as an individual EML file (RFC 2822), organized by `YYYY/MM/` based on the email's internal date
- Attachments remain embedded in the EML and are also extracted to `data/attachments/` as `<msg-id>_<original-filename>`
- `metadata.json` tracks Gmail `historyId` for incremental sync, plus a message index mapping message IDs to file paths and Gmail labels

## Authentication

- Google Cloud project with Gmail API enabled (one-time setup)
- OAuth2 Desktop app credentials (`credentials.json`)
- First run opens browser for consent, saves refresh token to `token.json`
- Subsequent runs authenticate silently via refresh token
- Scopes: `gmail.readonly` (backup/audit) and `gmail.modify` (cleanup — trash only)
- Both credential files gitignored; token revocable from Google Account settings

## Backup Process

1. Authenticate via OAuth2
2. Check `metadata.json` for last `historyId`
3. First run: fetch all message IDs (paginated), download each as RFC 2822 EML
4. Incremental: use Gmail History API to fetch only new/changed messages
5. Extract attachments to `data/attachments/<msg-id>_<filename>`
6. Save EML to `data/YYYY/MM/<msg-id>.eml`
7. Update `metadata.json` with new `historyId`, total count, message index

Expected performance: ~50 messages/sec via batch requests. Initial backup of ~55,000 emails takes ~15-20 minutes.

## Audit Report

`gmail-audit.py` generates:
- Top 20 senders by total size
- Size breakdown by Gmail category (promotions, social, updates, forums, primary)
- Size breakdown by year
- Top 50 largest individual emails
- Attachment summary (count and total size by file type)
- Output: `reports/YYYY-MM-DD.json` + human-readable stdout summary

## Cleanup Rules

### Rules Format (`gmail-rules.yaml`)

```yaml
rules:
  - name: old-promotions
    category: promotions
    older_than_days: 365
    action: trash

  - name: old-social
    category: social
    older_than_days: 180
    action: trash

  - name: large-attachments
    larger_than_mb: 10
    older_than_days: 730
    action: trash

  - name: specific-senders
    from:
      - "noreply@linkedin.com"
      - "newsletter@medium.com"
    older_than_days: 90
    action: trash

protect:
  - starred: true
  - label: "IMPORTANT"
```

### Safety Features

- `protect` section: starred and important emails never touched
- Dry-run by default (`--dry-run`); requires explicit `--execute` to act
- Checks backup freshness before cleanup; refuses if backup is stale
- Action is `trash` (not permanent delete) — 30-day recovery window in Gmail

## CLI Interface

```bash
python projects/backup/gmail/gmail-backup.py
python projects/backup/gmail/gmail-audit.py
python projects/backup/gmail/gmail-cleanup.py           # dry-run
python projects/backup/gmail/gmail-cleanup.py --execute  # actually trash
```

## Logging

Python logging to `~/.logs/plum/gmail-backup/YYYY-MM-DD.log` (matching plum conventions).

## Dependencies

```
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
pyyaml
```

Uses `projects/backup/.venv/`.

## Future Work (Not In Scope)

- VPS rsync (backup replication to remote)
- Cron scheduling
- Multiple account support

---

# Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python tool that backs up Gmail emails as EML files with attachment extraction, generates space audit reports, and applies configurable cleanup rules.

**Architecture:** Three standalone scripts sharing a common auth/logging module. Gmail API for all operations. OAuth2 for auth. YAML for cleanup rules. All data stored locally in `projects/backup/gmail/data/`.

**Tech Stack:** Python 3.12, Gmail API (`google-api-python-client`), OAuth2 (`google-auth-oauthlib`), PyYAML, stdlib `email` module for EML parsing.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `projects/backup/gmail/requirements.txt`
- Create: `projects/backup/gmail/.gitignore`
- Create: `projects/backup/gmail/gmail-rules.yaml`

**Step 1: Create directory and requirements.txt**

```
projects/backup/gmail/requirements.txt
```
```
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
pyyaml
```

**Step 2: Create .gitignore for data and credentials**

```
projects/backup/gmail/.gitignore
```
```
credentials.json
token.json
data/
reports/
```

**Step 3: Create default gmail-rules.yaml**

```yaml
rules:
  - name: old-promotions
    category: promotions
    older_than_days: 365
    action: trash

  - name: old-social
    category: social
    older_than_days: 180
    action: trash

  - name: large-attachments
    larger_than_mb: 10
    older_than_days: 730
    action: trash

protect:
  - starred: true
  - label: "IMPORTANT"
```

**Step 4: Install dependencies**

```bash
cd projects/backup && source .venv/bin/activate && pip install -r gmail/requirements.txt
```

**Step 5: Commit**

```bash
git add projects/backup/gmail/requirements.txt projects/backup/gmail/.gitignore projects/backup/gmail/gmail-rules.yaml
git commit -m "feat(gmail): scaffold project with requirements and default rules"
```

---

### Task 2: Auth & Logging Module

**Files:**
- Create: `projects/backup/gmail/gmail_common.py`
- Test: `projects/backup/gmail/test_gmail_common.py`

This module provides two things used by all three scripts:
1. `get_gmail_service(scopes)` — handles OAuth2 flow, returns an authenticated Gmail API service object
2. `setup_logging(script_name)` — configures Python logging to `~/.logs/plum/<script_name>/YYYY-MM-DD.log` + stderr

**Step 1: Write test for logging setup**

```python
# test_gmail_common.py
import os
import logging
from unittest.mock import patch
from datetime import date

def test_setup_logging_creates_log_dir(tmp_path):
    from gmail_common import setup_logging
    with patch("gmail_common.LOG_BASE", str(tmp_path)):
        logger = setup_logging("test-script")
        log_dir = tmp_path / "test-script"
        assert log_dir.is_dir()
        assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
        log_file = log_dir / f"{date.today().isoformat()}.log"
        logger.info("hello")
        assert log_file.exists()
```

**Step 2: Run test to verify it fails**

```bash
cd projects/backup/gmail && python -m pytest test_gmail_common.py::test_setup_logging_creates_log_dir -v
```

Expected: FAIL — `gmail_common` module does not exist.

**Step 3: Implement gmail_common.py**

```python
# gmail_common.py
"""Shared auth and logging for Gmail backup tools."""

import os
import logging
from datetime import date
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCRIPT_DIR = Path(__file__).parent
LOG_BASE = os.path.expanduser("~/.logs/plum")

SCOPES_READONLY = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES_MODIFY = ["https://www.googleapis.com/auth/gmail.modify"]


def setup_logging(script_name: str) -> logging.Logger:
    """Configure logging to file + stderr, matching plum conventions."""
    log_dir = Path(LOG_BASE) / script_name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{date.today().isoformat()}.log"

    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_file)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def get_gmail_service(scopes: list[str] | None = None):
    """Authenticate and return a Gmail API service object.

    First run opens browser for OAuth consent. Subsequent runs use saved token.
    """
    if scopes is None:
        scopes = SCOPES_READONLY

    creds = None
    token_path = SCRIPT_DIR / "token.json"
    creds_path = SCRIPT_DIR / "credentials.json"

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {creds_path}. "
                    "Download OAuth2 credentials from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_data_dir() -> Path:
    """Return the data directory, creating it if needed."""
    d = SCRIPT_DIR / "data"
    d.mkdir(exist_ok=True)
    return d


def get_reports_dir() -> Path:
    """Return the reports directory, creating it if needed."""
    d = SCRIPT_DIR / "reports"
    d.mkdir(exist_ok=True)
    return d


def load_metadata() -> dict:
    """Load metadata.json or return empty default."""
    meta_path = get_data_dir() / "metadata.json"
    if meta_path.exists():
        import json
        return json.loads(meta_path.read_text())
    return {"history_id": None, "message_count": 0, "messages": {}}


def save_metadata(metadata: dict):
    """Save metadata.json."""
    import json
    meta_path = get_data_dir() / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
```

**Step 4: Run test to verify it passes**

```bash
cd projects/backup/gmail && python -m pytest test_gmail_common.py::test_setup_logging_creates_log_dir -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add projects/backup/gmail/gmail_common.py projects/backup/gmail/test_gmail_common.py
git commit -m "feat(gmail): add auth and logging module"
```

---

### Task 3: Backup Script — Message Listing & EML Download

**Files:**
- Create: `projects/backup/gmail/gmail-backup.py`
- Test: `projects/backup/gmail/test_gmail_backup.py`

**Step 1: Write test for EML saving and attachment extraction**

The core testable logic is: given raw RFC 2822 bytes, save the EML to the right path and extract attachments. The Gmail API interaction is a thin wrapper we don't unit-test.

```python
# test_gmail_backup.py
import email
from pathlib import Path

def _make_eml_with_attachment():
    """Create a minimal EML with a text attachment."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg["From"] = "test@example.com"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Test with attachment"
    msg["Date"] = "Mon, 15 Jan 2024 10:00:00 +0000"
    msg["Message-ID"] = "<test123@example.com>"

    body = MIMEText("Hello world")
    msg.attach(body)

    att = MIMEBase("application", "octet-stream")
    att.set_payload(b"fake pdf content")
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", "attachment", filename="report.pdf")
    msg.attach(att)

    return msg.as_bytes()


def test_save_message_creates_eml_and_extracts_attachments(tmp_path):
    from gmail_backup import save_message

    raw = _make_eml_with_attachment()
    msg_id = "abc123"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    attachments_dir = data_dir / "attachments"
    attachments_dir.mkdir()

    result = save_message(msg_id, raw, data_dir)

    # EML saved in YYYY/MM structure
    eml_path = data_dir / "2024" / "01" / "abc123.eml"
    assert eml_path.exists()
    assert result["path"] == str(eml_path.relative_to(data_dir))

    # Attachment extracted
    att_path = attachments_dir / "abc123_report.pdf"
    assert att_path.exists()
    assert att_path.read_bytes() == b"fake pdf content"

    # Labels stored
    assert "labels" in result


def test_save_message_no_attachment(tmp_path):
    from email.mime.text import MIMEText

    msg = MIMEText("Plain email")
    msg["From"] = "test@example.com"
    msg["Date"] = "Tue, 05 Mar 2024 12:00:00 +0000"
    raw = msg.as_bytes()

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "attachments").mkdir()

    from gmail_backup import save_message
    result = save_message("def456", raw, data_dir)

    eml_path = data_dir / "2024" / "03" / "def456.eml"
    assert eml_path.exists()
```

**Step 2: Run test to verify it fails**

```bash
cd projects/backup/gmail && python -m pytest test_gmail_backup.py -v
```

Expected: FAIL — `gmail_backup` module does not exist.

**Step 3: Implement gmail-backup.py**

```python
#!/usr/bin/env python3
"""Back up Gmail messages as EML files with attachment extraction.

Usage: python gmail-backup.py
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
```

**Step 4: Run tests to verify they pass**

```bash
cd projects/backup/gmail && python -m pytest test_gmail_backup.py -v
```

Expected: PASS (tests only exercise `save_message`, not the API calls)

**Step 5: Commit**

```bash
git add projects/backup/gmail/gmail-backup.py projects/backup/gmail/test_gmail_backup.py
git commit -m "feat(gmail): add backup script with EML save and attachment extraction"
```

---

### Task 4: Audit Script

**Files:**
- Create: `projects/backup/gmail/gmail-audit.py`
- Test: `projects/backup/gmail/test_gmail_audit.py`

**Step 1: Write test for audit aggregation logic**

```python
# test_gmail_audit.py

def test_aggregate_messages():
    from gmail_audit import aggregate_messages

    messages = [
        {
            "id": "a1",
            "sizeEstimate": 5000,
            "labelIds": ["CATEGORY_PROMOTIONS", "INBOX"],
            "internalDate": "1704067200000",  # 2024-01-01
            "payload": {
                "headers": [{"name": "From", "value": "news@shop.com"}],
                "parts": [
                    {
                        "filename": "flyer.pdf",
                        "body": {"size": 3000},
                    }
                ],
            },
        },
        {
            "id": "a2",
            "sizeEstimate": 200,
            "labelIds": ["CATEGORY_SOCIAL"],
            "internalDate": "1709596800000",  # 2024-03-05
            "payload": {
                "headers": [{"name": "From", "value": "notif@twitter.com"}],
            },
        },
    ]

    report = aggregate_messages(messages)

    assert report["by_sender"]["news@shop.com"]["total_size"] == 5000
    assert report["by_sender"]["news@shop.com"]["count"] == 1
    assert report["by_category"]["promotions"]["total_size"] == 5000
    assert report["by_category"]["social"]["count"] == 1
    assert report["by_year"]["2024"]["total_size"] == 5200
    assert len(report["largest"]) == 2
    assert report["attachments"]["pdf"]["count"] == 1
```

**Step 2: Run test to verify it fails**

```bash
cd projects/backup/gmail && python -m pytest test_gmail_audit.py -v
```

Expected: FAIL

**Step 3: Implement gmail-audit.py**

```python
#!/usr/bin/env python3
"""Generate Gmail space usage audit report.

Usage: python gmail-audit.py
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
            # Extract just the email address
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
```

**Step 4: Run tests to verify they pass**

```bash
cd projects/backup/gmail && python -m pytest test_gmail_audit.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add projects/backup/gmail/gmail-audit.py projects/backup/gmail/test_gmail_audit.py
git commit -m "feat(gmail): add audit script with space usage reporting"
```

---

### Task 5: Cleanup Script

**Files:**
- Create: `projects/backup/gmail/gmail-cleanup.py`
- Test: `projects/backup/gmail/test_gmail_cleanup.py`

**Step 1: Write tests for rule matching logic**

```python
# test_gmail_cleanup.py
from datetime import datetime, timedelta

def _make_msg(msg_id, labels, size, sender, date_ms):
    return {
        "id": msg_id,
        "labelIds": labels,
        "sizeEstimate": size,
        "internalDate": str(date_ms),
        "payload": {"headers": [{"name": "From", "value": sender}]},
    }

def test_rule_matches_category_and_age():
    from gmail_cleanup import matches_rule

    old_date = int((datetime.now() - timedelta(days=400)).timestamp() * 1000)
    msg = _make_msg("m1", ["CATEGORY_PROMOTIONS"], 100, "shop@x.com", old_date)
    rule = {"name": "old-promos", "category": "promotions", "older_than_days": 365, "action": "trash"}
    assert matches_rule(msg, rule) is True

def test_rule_does_not_match_recent():
    from gmail_cleanup import matches_rule

    recent = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
    msg = _make_msg("m2", ["CATEGORY_PROMOTIONS"], 100, "shop@x.com", recent)
    rule = {"name": "old-promos", "category": "promotions", "older_than_days": 365, "action": "trash"}
    assert matches_rule(msg, rule) is False

def test_rule_matches_size():
    from gmail_cleanup import matches_rule

    old_date = int((datetime.now() - timedelta(days=800)).timestamp() * 1000)
    msg = _make_msg("m3", ["INBOX"], 15_000_000, "big@x.com", old_date)
    rule = {"name": "large", "larger_than_mb": 10, "older_than_days": 730, "action": "trash"}
    assert matches_rule(msg, rule) is True

def test_rule_matches_sender():
    from gmail_cleanup import matches_rule

    old_date = int((datetime.now() - timedelta(days=100)).timestamp() * 1000)
    msg = _make_msg("m4", ["INBOX"], 100, "noreply@linkedin.com", old_date)
    rule = {"name": "linkedin", "from": ["noreply@linkedin.com"], "older_than_days": 90, "action": "trash"}
    assert matches_rule(msg, rule) is True

def test_protected_message_never_matched():
    from gmail_cleanup import is_protected

    msg = _make_msg("m5", ["STARRED", "INBOX"], 100, "x@x.com", 0)
    protect = [{"starred": True}]
    assert is_protected(msg, protect) is True

def test_unstarred_not_protected():
    from gmail_cleanup import is_protected

    msg = _make_msg("m6", ["INBOX"], 100, "x@x.com", 0)
    protect = [{"starred": True}]
    assert is_protected(msg, protect) is False

def test_protected_by_label():
    from gmail_cleanup import is_protected

    msg = _make_msg("m7", ["IMPORTANT", "INBOX"], 100, "x@x.com", 0)
    protect = [{"label": "IMPORTANT"}]
    assert is_protected(msg, protect) is True
```

**Step 2: Run tests to verify they fail**

```bash
cd projects/backup/gmail && python -m pytest test_gmail_cleanup.py -v
```

Expected: FAIL

**Step 3: Implement gmail-cleanup.py**

```python
#!/usr/bin/env python3
"""Apply cleanup rules to Gmail, trashing matching messages.

Usage:
    python gmail-cleanup.py             # dry-run (default)
    python gmail-cleanup.py --execute   # actually trash matching messages
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
            log.error(f"Backup is {backup_age.days} days old. Run gmail-backup.py first.")
            return
    else:
        log.error("No backup found. Run gmail-backup.py first.")
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
```

**Step 4: Run tests to verify they pass**

```bash
cd projects/backup/gmail && python -m pytest test_gmail_cleanup.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add projects/backup/gmail/gmail-cleanup.py projects/backup/gmail/test_gmail_cleanup.py
git commit -m "feat(gmail): add cleanup script with rule matching and dry-run safety"
```

---

### Task 6: Integration Test & Final Polish

**Files:**
- Modify: `projects/backup/gmail/gmail-backup.py` (if needed)
- Run all tests

**Step 1: Run all tests together**

```bash
cd projects/backup/gmail && python -m pytest -v
```

Expected: All tests PASS.

**Step 2: Verify scripts are runnable (help/import check)**

```bash
cd projects/backup/gmail && source ../../../projects/backup/.venv/bin/activate
python -c "import gmail_common; print('common OK')"
python gmail-backup.py --help 2>&1 || true  # Will fail without credentials, but should import cleanly
python gmail-audit.py --help 2>&1 || true
python gmail-cleanup.py --help
```

**Step 3: Commit any fixes**

```bash
git add -A projects/backup/gmail/
git commit -m "chore(gmail): polish and verify all scripts import cleanly"
```

---

### Task 7: Manual OAuth Setup & First Run

This task is manual — the user must do this interactively.

**Step 1: Create Google Cloud project**

1. Go to https://console.cloud.google.com/
2. Create a new project (e.g. "plum-gmail-backup")
3. Enable the Gmail API: APIs & Services > Enable APIs > search "Gmail API" > Enable
4. Create OAuth credentials: APIs & Services > Credentials > Create Credentials > OAuth client ID
   - Application type: Desktop app
   - Download the JSON, save as `projects/backup/gmail/credentials.json`

**Step 2: First backup run**

```bash
cd projects/backup/gmail && source ../.venv/bin/activate
python gmail-backup.py
```

This opens a browser for OAuth consent. Authorize, then the backup begins.

**Step 3: Run audit**

```bash
python gmail-audit.py
```

Review the report. Use it to tune `gmail-rules.yaml` with senders/categories worth cleaning.

**Step 4: Dry-run cleanup**

```bash
python gmail-cleanup.py
```

Review what would be trashed. Adjust rules. When satisfied:

```bash
python gmail-cleanup.py --execute
```
