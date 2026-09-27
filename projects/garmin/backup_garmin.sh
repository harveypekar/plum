#!/bin/bash
# Zip the Garmin data tree and upload it to Hetzner Storage Box, keeping the
# newest 3 backups. Aborts loudly if the configured rclone remote is not an
# encrypted (crypt) backend — see .claude/rules/backup.md (non-negotiable).
set -euo pipefail

DATA_DIR="${GARMIN_DATA_DIR:-/app/data/garmin}"
REMOTE="${RCLONE_REMOTE:-hetzner-crypt}"
REMOTE_DIR="bak/garmin"
KEEP=3

REMOTE_TYPE="$(rclone config show "$REMOTE" 2>/dev/null | grep '^type = ' | awk '{print $3}')"
if [ "$REMOTE_TYPE" != "crypt" ]; then
    echo "ABORT: rclone remote '$REMOTE' is not type 'crypt' (got: '${REMOTE_TYPE:-missing}')" >&2
    exit 1
fi

[ -d "$DATA_DIR" ] || { echo "ABORT: $DATA_DIR does not exist" >&2; exit 1; }

DATE="$(date +%Y-%m-%d)"
ZIP_NAME="bak_garmin_${DATE}.zip"
TMP_ZIP="/tmp/${ZIP_NAME}"

echo "Zipping $DATA_DIR -> $TMP_ZIP"
(cd "$(dirname "$DATA_DIR")" && zip -rq "$TMP_ZIP" "$(basename "$DATA_DIR")")
[ -s "$TMP_ZIP" ] || { echo "ABORT: zip produced an empty or missing file" >&2; exit 1; }

echo "Uploading to ${REMOTE}:${REMOTE_DIR}/${ZIP_NAME}"
rclone copy "$TMP_ZIP" "${REMOTE}:${REMOTE_DIR}/" || { echo "ABORT: rclone upload failed" >&2; exit 1; }
rm -f "$TMP_ZIP"

echo "Pruning to newest $KEEP backups in ${REMOTE}:${REMOTE_DIR}/"
rclone lsf "${REMOTE}:${REMOTE_DIR}/" --files-only | sort | head -n "-${KEEP}" | while read -r old; do
    [ -n "$old" ] || continue
    echo "  Deleting old backup: $old"
    rclone deletefile "${REMOTE}:${REMOTE_DIR}/${old}"
done

echo "Backup complete: ${ZIP_NAME}"
