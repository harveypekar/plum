#!/usr/bin/env bash
# Dump the plum database to a timestamped SQL file
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTFILE="$BACKUP_DIR/plum-${TIMESTAMP}.sql.gz"

docker exec plum-postgres-1 pg_dump -U plum plum | gzip > "$OUTFILE"

echo "Backup: $OUTFILE ($(du -h "$OUTFILE" | cut -f1))"
