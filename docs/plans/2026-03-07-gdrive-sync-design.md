# Google Drive Sync Design

**Created:** 2026-03-07
**Status:** Approved

## Summary

Two-way sync between a local folder and Google Drive using rclone bisync. Local folder is the primary workspace — changes (edits, moves, deletes) propagate back to Google Drive. Soft-delete protection via trash retention.

## Architecture

```
bak/gdrive/  <──rclone bisync──>  Google Drive (10 GB)

Deletions:
  Local-side  -> moved to bak/gdrive/.trash/ (30 days)
  Drive-side  -> Google Drive trash (30 days, Google default)

Conflicts:
  Newer file wins
```

## Components

| File | Purpose |
|------|---------|
| `projects/backup/gdrive-sync.sh` | Main sync script (manual trigger) |
| `bak/gdrive/` | Local sync folder |
| `bak/gdrive/.trash/` | Soft-delete staging for local deletions |

## Workflow

1. User runs `bash projects/backup/gdrive-sync.sh`
2. Script runs `rclone bisync` between `bak/gdrive/` and `gdrive:` remote
3. Changed/new files sync both directions (newer wins on conflict)
4. Deleted files go to trash (local `.trash/` folder, Drive trash)
5. Results logged to `~/.logs/plum/gdrive-sync/`

## Configuration

### .env variables

```bash
GDRIVE_LOCAL_PATH=~/bak/gdrive
GDRIVE_RCLONE_REMOTE=gdrive
GDRIVE_TRASH_DAYS=30
```

### One-time setup

1. Install rclone (`apt install rclone` or from rclone.org)
2. Configure Google Drive remote: `rclone config` (interactive OAuth2 browser flow)
3. Create local folder: `mkdir -p ~/bak/gdrive`
4. First run with `--resync` flag to establish baseline sync state

### rclone bisync flags

```bash
rclone bisync "$LOCAL" "$REMOTE" \
  --check-access \          # canary file to verify permissions
  --backup-dir "$TRASH" \   # deleted/overwritten files go here
  --suffix "$(date +%Y%m%d-%H%M%S)" \
  --filters-file "$FILTERS" \
  --verbose
```

## Key Behaviors

- **Manual trigger only** — no cron, no daemon
- **Newer file wins** — rclone bisync default conflict resolution
- **--check-access** — creates `.rclone-bisync-test` canary file to verify both sides are reachable before syncing
- **Soft-delete** — `--backup-dir` moves deleted/overwritten files to `.trash/` with timestamp suffix
- **Trash cleanup** — script prunes `.trash/` entries older than `GDRIVE_TRASH_DAYS`

## Logging

Logs to `~/.logs/plum/gdrive-sync/YYYY-MM-DD.log` via `scripts/common/logging.sh`.

## Dependencies

- rclone (with bisync support, v1.58+)
- Google Drive OAuth2 credentials (configured via `rclone config`)
