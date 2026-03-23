# Google Incremental Backup — Design Spec

**Created:** 2026-03-23
**Status:** Draft

## Goal

Automated incremental backup of Google account data to the local filesystem. Covers the six services with scriptable APIs: Gmail, Calendar, Contacts, Drive, Tasks, and YouTube.

## Architecture

Python package at `scripts/backup/google-backup/` with a bash wrapper for cron integration. Each Google service is a separate module implementing a common interface. Sync state is tracked in JSON files — no database dependency.

### Tech Stack

- Python 3.10+ with virtual environment
- `google-api-python-client` + `google-auth-oauthlib` for API access
- Bash wrapper (`run.sh`) sets `SCRIPT_NAME`, sources `scripts/common/logging.sh` and `scripts/common/load-env.sh`

## Project Structure

```
scripts/backup/google-backup/
├── run.sh                    # Bash wrapper: sets SCRIPT_NAME, sources logging/env, activates venv
├── requirements.txt          # google-api-python-client, google-auth-oauthlib
├── google_backup/
│   ├── __init__.py
│   ├── __main__.py           # CLI: python -m google_backup [--all|--gmail|--calendar|...]
│   ├── auth.py               # OAuth2: first-time browser flow + token refresh
│   ├── state.py              # Per-service sync state (tokens, timestamps) as JSON files
│   └── services/
│       ├── __init__.py       # Service registry (discovers all service modules)
│       ├── base.py           # Abstract base: sync(creds, state_dir, backup_dir) -> SyncResult
│       ├── gmail.py
│       ├── calendar.py
│       ├── contacts.py
│       ├── drive.py
│       ├── tasks.py
│       └── youtube.py
```

## Logging

`run.sh` sets `SCRIPT_NAME="google-backup"` and sources `logging.sh`, which sets up `LOG_FILE`. It passes `LOG_FILE` as an environment variable to the Python process. The Python code uses the standard `logging` module with a `FileHandler` pointing at `LOG_FILE` and a `StreamHandler` for console output. This means both the bash wrapper and Python write to the same log file at `~/.logs/plum/google-backup/YYYY-MM-DD.log`.

## CLI Usage

```bash
# First-time auth (opens browser)
bash scripts/backup/google-backup/run.sh auth

# Backup everything
bash scripts/backup/google-backup/run.sh --all

# Backup specific services
bash scripts/backup/google-backup/run.sh --gmail --contacts

# Check sync status without running
bash scripts/backup/google-backup/run.sh --status
```

## Backup Output Structure

```
~/.backups/plum/google/
├── state/
│   ├── token.json            # OAuth2 refresh token
│   ├── gmail.json            # {"history_id": "12345", "last_run": "2026-03-23T..."}
│   ├── calendar.json         # {"sync_token": "...", "last_run": "..."}
│   ├── contacts.json
│   ├── drive.json
│   ├── tasks.json
│   └── youtube.json
├── gmail/
│   ├── msg_18e3a4b2c1d/      # One dir per message (message ID as dirname)
│   │   ├── message.eml       # Raw RFC 2822 email
│   │   └── metadata.json     # Labels, threadId, internalDate
│   └── ...
├── calendar/
│   ├── primary/
│   │   ├── evt_abc123.json   # One file per event
│   │   └── ...
│   └── work/                 # One dir per calendar
├── contacts/
│   ├── person_c123.vcf       # One vCard per contact
│   └── ...
├── drive/
│   ├── by_id/                # One dir per file ID (canonical storage)
│   │   ├── file_xyz/
│   │   │   ├── content.pdf   # Actual file (or exported PDF for Google Docs)
│   │   │   └── metadata.json # Drive metadata (parents, name, mimeType, etc.)
│   │   └── ...
│   └── tree/                 # Symlinks mirroring Drive folder structure
│       ├── Documents/
│       └── ...
├── tasks/
│   ├── list_abc/
│   │   ├── task_123.json
│   │   └── ...
│   └── ...
└── youtube/
    ├── subscriptions.json    # Full list, overwritten each run
    ├── playlists/
    │   ├── playlist_abc.json # Playlist metadata + video IDs
    │   └── ...
    └── liked_videos.json     # Full list, overwritten each run
```

## Auth & Credentials

### One-Time GCP Setup

1. Create a Google Cloud project at console.cloud.google.com
2. Enable APIs: Gmail, Google Calendar, People, Google Drive, Tasks, YouTube Data API v3
3. Create OAuth 2.0 Client ID (Application type: Desktop app)
4. Download the client secret JSON (GCP names it `client_secret_<client-id>.json`)
5. Rename/place at the path specified by `GOOGLE_BACKUP_CLIENT_SECRET` in `.env`

### OAuth Flow

`run.sh auth` opens a browser for the user to consent. The resulting refresh token is saved to `~/.backups/plum/google/state/token.json`. Subsequent runs refresh silently.

### Scopes (all read-only)

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/contacts.readonly`
- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/tasks.readonly`
- `https://www.googleapis.com/auth/youtube.readonly`

### Env Variables

Added to `.env.example`:

```bash
# Google Backup
GOOGLE_BACKUP_CLIENT_SECRET=
GOOGLE_BACKUP_DIR=
GOOGLE_BACKUP_MAX_DISK_GB=
```

The client secret and token files live outside the repo. The pre-commit hook blocks secrets from being committed.

## Incremental Sync Strategy

### Gmail — `historyId`

- **First run:** List all message IDs, download each as raw EML + metadata JSON. Checkpoint state every 500 messages so a crash doesn't lose all progress (`partial_cursor` in state file). For large accounts (100K+ messages), the first run can take hours and tens of GB. No artificial limit — the user controls this by running `--gmail` alone for the initial sync.
- **Subsequent runs:** Call `history.list(startHistoryId=...)` to get only messages added/modified/deleted since last sync.
- **Deletions:** `metadata.json` gets a `"deleted": true` field. EML is kept — we never destroy backed-up data.

### Calendar — `syncToken`

- **First run:** Full list of events across all calendars.
- **Subsequent runs:** Pass `syncToken` from last run; API returns only changed/deleted events.
- **Deletions:** Event JSON gets `"status": "cancelled"` (how the API represents deletions).

### Contacts — `syncToken` (People API)

- Same pattern as Calendar — full sync first, then `syncToken` for incremental.
- **Deletions:** JSON marked with `"deleted": true`, VCF kept.

### Drive — `changes.startPageToken`

- **First run:** Walk entire Drive tree, download files, build metadata index. Checkpoint with `partial_cursor`.
- **Subsequent runs:** `changes.list(pageToken=...)` returns only changed files.
- **Google Docs/Sheets/Slides:** Exported as PDF.
- **Multi-parent files:** Drive allows a file in multiple folders. Store the file once under `by_id/<file_id>/`, with symlinks from each parent path in the `tree/` directory. Metadata JSON records all parent folder IDs.
- **Trashed files:** Metadata updated, local copy kept.

### Tasks — full dump

- No sync token available. Full dump every run (lists are small).
- Overwrite existing JSON files. Remove orphaned task files (tasks deleted on Google's side) by comparing the current task ID set against local files.

### YouTube — full dump

- No sync token available. Full dump every run.
- Before overwriting, diff against previous version and log removals (e.g., "Subscription removed: ChannelName"). This preserves a record of deletions in the log even though the JSON is overwritten.

### State Management

- Every service writes its sync token to `state/<service>.json` only after a successful run.
- If a run fails mid-way, the state file is NOT updated — next run retries from the same point.
- Gmail and Drive track `partial_cursor` for first-run checkpointing.

## Error Handling & Resilience

### Rate Limits

- Google APIs have per-user quotas (Gmail: 250 units/sec, Drive: 12,000 req/min).
- Exponential backoff on 429/5xx responses — `google-api-python-client` handles this natively.
- Large first runs (Gmail/Drive) batch in pages of 100.

### Network Failures

- Transient errors: retry with exponential backoff (3 attempts).
- Persistent failures: log the error, skip that item, continue with the rest.
- Summary at end: "Backed up 4523 messages, 3 failed (IDs: ...)".

### Token Expiry

- Refresh tokens are long-lived but can be revoked.
- If refresh fails: log "Re-run `run.sh auth` to re-authorize" and exit non-zero.

### Disk Space

- Before starting Drive sync, check if the backup directory (`GOOGLE_BACKUP_DIR`) exceeds `GOOGLE_BACKUP_MAX_DISK_GB` in total size. If so, skip Drive sync and log a warning. Other services (small data) still run.
- This is a cap on total backup size, not a free-disk check. No automatic deletion of old backup data — this is an archive, not a rotating log. The disk limit is a safety stop, not a retention policy.

### No Silent Failures

- Every service returns a `SyncResult` summary (items synced, failed, deleted).
- Exit code is non-zero if any service had errors.
- `run.sh` passes exit code through for cron alerting.

## Service Module Interface

```python
class BaseService:
    name: str                    # e.g. "gmail"
    scopes: list[str]           # OAuth scopes needed

    def sync(self, creds, state_dir: Path, backup_dir: Path) -> SyncResult:
        """Run incremental sync. Returns summary."""
        ...

@dataclass
class SyncResult:
    service: str
    items_synced: int
    items_failed: int
    items_deleted: int
    failed_ids: list[str]       # For retry/debugging
    elapsed_seconds: float
```

The CLI (`__main__.py`):
1. Parses args to determine which services to run
2. If `--status`: read each service's state file and print last sync time, item counts, and sync token status. No API calls. Exit.
3. If `auth`: run OAuth2 browser flow, save token, exit.
4. Loads auth credentials (refreshes if needed)
5. For each selected service: loads state, calls `sync()`, prints result
6. Exits 0 if all clean, exits 1 if any failures
