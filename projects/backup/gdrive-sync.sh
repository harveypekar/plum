#!/bin/bash
# Two-way sync between local folder and Google Drive via rclone bisync
# Usage: bash projects/backup/gdrive-sync.sh [--resync]
#
# First run:  bash projects/backup/gdrive-sync.sh --resync
#   Seeds rclone bisync tracking files and does initial sync.
#
# Normal run: bash projects/backup/gdrive-sync.sh
#   Syncs changes both directions. Newer file wins on conflicts.
#   Deleted/overwritten files are moved to local .trash/ with timestamps.

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

TRASH_DIR="$LOCAL_PATH/.trash"
REMOTE="$RCLONE_REMOTE:"

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
    --backup-dir1 "$TRASH_DIR"
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

# Prune old trash entries
if [[ -d "$TRASH_DIR" ]]; then
    OLD_COUNT=$(find "$TRASH_DIR" -mindepth 1 -mtime +"$TRASH_DAYS" | wc -l)
    if [[ "$OLD_COUNT" -gt 0 ]]; then
        log_info "Pruning $OLD_COUNT trash entries older than ${TRASH_DAYS} days"
        find "$TRASH_DIR" -mindepth 1 -mtime +"$TRASH_DAYS" -delete
    fi
fi

log_info "Google Drive sync complete"
