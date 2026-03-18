#!/usr/bin/env bash
# Watch for database changes and back up automatically.
# Polls pg_stat_user_tables write counters every 10s.
# Backs up only when data actually changes. No triggers needed.
set -euo pipefail

export PGPASSWORD="${POSTGRES_PASSWORD}"

BACKUP_DIR="/backups"
mkdir -p "$BACKUP_DIR"
LAST_COUNT=""

get_write_count() {
    psql -h postgres -U plum -d plum -tAq \
        -c "SELECT coalesce(sum(n_tup_ins + n_tup_upd + n_tup_del), 0) FROM pg_stat_user_tables;"
}

backup() {
    local ts
    ts=$(date +%Y%m%d-%H%M%S)
    local outfile="$BACKUP_DIR/plum-${ts}.sql.gz"
    pg_dump -h postgres -U plum plum | gzip > "$outfile"
    echo "[$(date +%H:%M:%S)] Backup: $(du -h "$outfile" | cut -f1)"
}

# Wait for postgres
until psql -h postgres -U plum -d plum -c "SELECT 1" > /dev/null 2>&1; do
    sleep 2
done

echo "Watching for database changes..."
LAST_COUNT=$(get_write_count)

while true; do
    sleep 10
    count=$(get_write_count)
    if [ "$count" != "$LAST_COUNT" ]; then
        backup
        LAST_COUNT="$count"
    fi
done
