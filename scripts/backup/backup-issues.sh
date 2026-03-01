#!/bin/bash
# Backup all GitHub Issues to local JSON files with size-based retention
# Usage: bash scripts/backup/backup-issues.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source utilities
export SCRIPT_NAME="backup-issues"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/logging.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/load-env.sh"

BACKUP_DIR="$HOME/.backups/plum/issues"
BACKUP_MAX_SIZE_MB="${BACKUP_MAX_SIZE_MB:-50}"
TIMESTAMP="$(date +%Y-%m-%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/$TIMESTAMP.json"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Verify gh CLI is available and authenticated
if ! command -v gh &>/dev/null; then
    log_die "gh CLI not found. Install it: https://cli.github.com/"
fi

if ! gh auth status &>/dev/null; then
    log_die "gh CLI not authenticated. Run: gh auth login"
fi

# Export all issues
log_info "Exporting GitHub Issues to $BACKUP_FILE"

if ! gh issue list --state all --limit 9999 \
    --json number,title,body,state,labels,milestone,createdAt,updatedAt,closedAt,comments,author \
    > "$BACKUP_FILE"; then
    log_die "Failed to export issues"
fi

ISSUE_COUNT="$(jq length "$BACKUP_FILE")"
log_info "Exported $ISSUE_COUNT issues"

# Update latest.json symlink
ln -sf "$BACKUP_FILE" "$BACKUP_DIR/latest.json"
log_info "Updated latest.json symlink"

# Size-based retention
MAX_BYTES=$((BACKUP_MAX_SIZE_MB * 1024 * 1024))
DIR_SIZE=$(du -sb "$BACKUP_DIR" | cut -f1)

if [ "$DIR_SIZE" -gt "$MAX_BYTES" ]; then
    log_info "Backup directory size (${DIR_SIZE} bytes) exceeds limit (${MAX_BYTES} bytes), pruning old backups"

    # List JSON files sorted oldest first, excluding latest.json and the file just created
    while [ "$DIR_SIZE" -gt "$MAX_BYTES" ]; do
        OLDEST=$(find "$BACKUP_DIR" -maxdepth 1 -name '*.json' \
            ! -name 'latest.json' \
            ! -name "$(basename "$BACKUP_FILE")" \
            -printf '%T@ %p\n' | sort -n | head -n 1 | cut -d' ' -f2-)

        if [ -z "$OLDEST" ]; then
            log_warn "No more old backups to delete, directory still over limit"
            break
        fi

        log_info "Deleting old backup: $OLDEST"
        rm -f "$OLDEST"
        DIR_SIZE=$(du -sb "$BACKUP_DIR" | cut -f1)
    done
fi

log_info "Backup complete. Directory size: $(du -sh "$BACKUP_DIR" | cut -f1)"
