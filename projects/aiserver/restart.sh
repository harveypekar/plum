#!/usr/bin/env bash
# Restart aiserver: kill existing process, wait for port, start fresh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=8080

# Kill existing aiserver
if pgrep -f "python.*main\.py" > /dev/null 2>&1; then
    echo "Stopping aiserver (PID $(pgrep -f 'python.*main\.py' | head -1))..."
    pkill -f "python.*main\.py" || true
fi

# Wait for port to be released
for i in $(seq 1 10); do
    if ! ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
        break
    fi
    sleep 1
done

# Backup database before restart
bash "$SCRIPT_DIR/../db/backup.sh" 2>/dev/null || true

# Activate venv
source .venv/bin/activate

# Start aiserver in background
echo "Starting aiserver..."
DATABASE_URL="${DATABASE_URL:-postgresql://plum:Simatai0!@localhost/plum}" \
    nohup python main.py > /tmp/aiserver.log 2>&1 &

echo "aiserver started (PID $!), logs at /tmp/aiserver.log"

# Wait for it to be ready
for i in $(seq 1 15); do
    if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
        echo "aiserver is ready"
        exit 0
    fi
    sleep 1
done
echo "Warning: aiserver did not respond within 15s, check /tmp/aiserver.log"
