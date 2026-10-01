#!/bin/bash
# Mirror the Garmin data tree to Hetzner Storage Box — this is the
# canonical off-VPS copy of the data, not a dated/rotated backup archive,
# so the remote is kept in sync (deletions included), not accumulated.
# Aborts loudly if the configured rclone remote is not an encrypted (crypt)
# backend — see .claude/rules/backup.md (non-negotiable).
set -euo pipefail

DATA_DIR="${GARMIN_DATA_DIR:-/app/data/garmin}"
REMOTE="${RCLONE_REMOTE:-hetzner-crypt}"
REMOTE_DIR="data_sources/garmin"

REMOTE_TYPE="$(rclone config show "$REMOTE" 2>/dev/null | grep '^type = ' | awk '{print $3}')"
if [ "$REMOTE_TYPE" != "crypt" ]; then
    echo "ABORT: rclone remote '$REMOTE' is not type 'crypt' (got: '${REMOTE_TYPE:-missing}')" >&2
    exit 1
fi

[ -d "$DATA_DIR" ] || { echo "ABORT: $DATA_DIR does not exist" >&2; exit 1; }

echo "Syncing $DATA_DIR -> ${REMOTE}:${REMOTE_DIR}/"
rclone sync "$DATA_DIR" "${REMOTE}:${REMOTE_DIR}/" || { echo "ABORT: rclone sync failed" >&2; exit 1; }

echo "Sync complete"
