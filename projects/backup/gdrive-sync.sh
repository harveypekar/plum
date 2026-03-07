#!/bin/bash
# Two-way sync between local folder and Google Drive via rclone bisync
# Usage: bash projects/backup/gdrive-sync.sh [--resync]
#
# First run:  bash projects/backup/gdrive-sync.sh --resync
#   Seeds rclone bisync tracking files and does initial sync.
#
# Normal run: bash projects/backup/gdrive-sync.sh
#   Syncs changes both directions. Newer file wins on conflicts.
#   Deleted/overwritten files are moved to .trash/ on Google Drive with timestamps.

set -euo pipefail

# Resolve script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUM_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Setup logging and environment
export SCRIPT_NAME="gdrive-sync"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/logging.sh"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/load-env.sh"

# Read config from .env
LOCAL_PATH="${GDRIVE_LOCAL_PATH:?GDRIVE_LOCAL_PATH is required in .env}"
RCLONE_REMOTE="${GDRIVE_RCLONE_REMOTE:?GDRIVE_RCLONE_REMOTE is required in .env}"
TRASH_DAYS="${GDRIVE_TRASH_DAYS:-30}"

REMOTE="$RCLONE_REMOTE:"
REMOTE_TRASH="$RCLONE_REMOTE:.trash"

# Parse --resync flag
RESYNC=false
if [[ "${1:-}" == "--resync" ]]; then
    RESYNC=true
fi

# Verify rclone is installed
if ! command -v rclone &>/dev/null; then
    log_die "rclone is not installed. Please install it first."
fi

# Verify rclone remote exists
if ! rclone listremotes | grep -q "^${RCLONE_REMOTE}:$"; then
    log_die "rclone remote '$RCLONE_REMOTE' not found. Configure it with: rclone config"
fi

# Create directories
mkdir -p "$LOCAL_PATH" "$TRASH_DIR"

# Build bisync args
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BISYNC_ARGS=(
    "$LOCAL_PATH" "$REMOTE"
    --backup-dir2 "$REMOTE_TRASH"
    --suffix ".$TIMESTAMP"
    --verbose
    --log-file "$LOG_FILE"
)

if [[ "$RESYNC" == "true" ]]; then
    BISYNC_ARGS+=(--resync)
    log_info "Running bisync with --resync (first-time sync)"
else
    # Only add --check-access if canary file exists
    if [[ -f "$LOCAL_PATH/.rclone-bisync-test" ]]; then
        BISYNC_ARGS+=(--check-access)
    fi
fi

# Run bisync
log_info "Starting Google Drive bisync: $LOCAL_PATH <-> $REMOTE"
if rclone bisync "${BISYNC_ARGS[@]}"; then
    log_info "Bisync completed successfully"
else
    log_error "Bisync failed with exit code $?"
    exit 1
fi

# Prune old trash entries on Google Drive
log_info "Pruning remote trash entries older than ${TRASH_DAYS}d"
rclone delete "$REMOTE_TRASH" --min-age "${TRASH_DAYS}d" --verbose 2>&1 | while read -r line; do
    log_info "trash cleanup: $line"
done

log_info "Google Drive sync complete"
