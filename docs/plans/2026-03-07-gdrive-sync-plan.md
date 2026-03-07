# Google Drive Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a script that two-way syncs a local folder with Google Drive using rclone bisync, with soft-delete trash protection.

**Architecture:** Single bash script (`projects/backup/gdrive-sync.sh`) that wraps `rclone bisync`. Local folder `~/bak/gdrive/` is the workspace. Deletions are moved to `~/bak/gdrive/.trash/` with timestamp suffixes. Trash entries older than 30 days are pruned each run. Logging uses the existing `scripts/common/logging.sh` infrastructure.

**Tech Stack:** Bash, rclone (v1.58+ for bisync), existing Plum logging/env utilities.

---

### Task 1: Add .env variables

**Files:**
- Modify: `.env.example:14` (after existing backup variables)

**Step 1: Add the new variables to .env.example**

Add these lines after the existing `BACKUP_MEDIA_PATH` line:

```bash
# Google Drive Sync
GDRIVE_LOCAL_PATH=~/bak/gdrive
GDRIVE_RCLONE_REMOTE=gdrive
GDRIVE_TRASH_DAYS=30
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "feat(backup): add Google Drive sync env variables to .env.example"
```

---

### Task 2: Create the sync script

**Files:**
- Create: `projects/backup/gdrive-sync.sh`

**Step 1: Create the script**

```bash
#!/bin/bash
# Two-way sync between local folder and Google Drive via rclone bisync
# Usage: bash projects/backup/gdrive-sync.sh [--resync]
#
# First run requires: bash projects/backup/gdrive-sync.sh --resync
# This establishes the baseline sync state.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUM_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source utilities
export SCRIPT_NAME="gdrive-sync"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/logging.sh"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/load-env.sh"

# Configuration from .env
LOCAL_PATH="${GDRIVE_LOCAL_PATH:?GDRIVE_LOCAL_PATH not set in .env}"
RCLONE_REMOTE="${GDRIVE_RCLONE_REMOTE:?GDRIVE_RCLONE_REMOTE not set in .env}"
TRASH_DAYS="${GDRIVE_TRASH_DAYS:-30}"
TRASH_DIR="$LOCAL_PATH/.trash"
REMOTE="$RCLONE_REMOTE:"

# Parse args
RESYNC_FLAG=""
if [[ "${1:-}" == "--resync" ]]; then
    RESYNC_FLAG="--resync"
    log_info "Running with --resync (first-time or reset sync)"
fi

# Verify rclone is installed
if ! command -v rclone &>/dev/null; then
    log_die "rclone not found. Install it: https://rclone.org/install/"
fi

# Verify rclone remote exists
if ! rclone listremotes | grep -q "^${RCLONE_REMOTE}:$"; then
    log_die "rclone remote '$RCLONE_REMOTE' not configured. Run: rclone config"
fi

# Create local directories
mkdir -p "$LOCAL_PATH"
mkdir -p "$TRASH_DIR"

# Run bisync
log_info "Starting bisync: $LOCAL_PATH <-> $REMOTE"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

# Note: --check-access requires a .rclone-bisync-test file on both sides.
# On first --resync run, create it: touch ~/bak/gdrive/.rclone-bisync-test
# and let it sync to Drive.
BISYNC_ARGS=(
    "$LOCAL_PATH"
    "$REMOTE"
    --backup-dir1 "$TRASH_DIR"
    --suffix ".$TIMESTAMP"
    --verbose
    --log-file "$LOG_FILE"
)

if [[ -n "$RESYNC_FLAG" ]]; then
    BISYNC_ARGS+=("--resync")
fi

# Add --check-access only if not resyncing (canary file may not exist yet)
if [[ -z "$RESYNC_FLAG" ]] && [[ -f "$LOCAL_PATH/.rclone-bisync-test" ]]; then
    BISYNC_ARGS+=("--check-access")
fi

if rclone bisync "${BISYNC_ARGS[@]}"; then
    log_info "Bisync completed successfully"
else
    EXIT_CODE=$?
    log_error "Bisync failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
fi

# Prune old trash entries
if [[ -d "$TRASH_DIR" ]]; then
    OLD_COUNT=$(find "$TRASH_DIR" -mindepth 1 -mtime +"$TRASH_DAYS" | wc -l)
    if [[ "$OLD_COUNT" -gt 0 ]]; then
        log_info "Pruning $OLD_COUNT trash entries older than $TRASH_DAYS days"
        find "$TRASH_DIR" -mindepth 1 -mtime +"$TRASH_DAYS" -delete
    fi
fi

log_info "Sync complete"
```

**Step 2: Make it executable**

Run: `chmod +x projects/backup/gdrive-sync.sh`

**Step 3: Verify shellcheck passes**

Run: `shellcheck projects/backup/gdrive-sync.sh`
Expected: No errors

**Step 4: Commit**

```bash
git add projects/backup/gdrive-sync.sh
git commit -m "feat(backup): add Google Drive bisync script"
```

---

### Task 3: Add .gitignore for bak/ directory

The `bak/` folder should never be committed. It may or may not be inside the repo tree, but if `GDRIVE_LOCAL_PATH` is set to a relative path or inside the repo, we need protection.

**Files:**
- Modify: `.gitignore`

**Step 1: Add bak/ to .gitignore**

Add this line:

```
bak/
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add bak/ to gitignore"
```

---

### Task 4: Test the script (dry run)

This is a manual verification step — no automated test since it depends on rclone config and Google OAuth.

**Step 1: Verify script runs and shows help/errors correctly**

Run without .env vars set (or with dummy values) to confirm error handling:

```bash
bash projects/backup/gdrive-sync.sh
```

Expected: Dies with "GDRIVE_LOCAL_PATH not set in .env" or "rclone remote not configured"

**Step 2: Document setup instructions**

Add a brief README or comment block in the script header explaining the one-time setup:

1. `apt install rclone` (or download from rclone.org)
2. `rclone config` → New remote → Google Drive → follow OAuth2 flow
3. Add variables to `.env`
4. `mkdir -p ~/bak/gdrive`
5. First run: `bash projects/backup/gdrive-sync.sh --resync`
6. Create canary: `touch ~/bak/gdrive/.rclone-bisync-test` then run again with `--resync`
7. Subsequent runs: `bash projects/backup/gdrive-sync.sh`
