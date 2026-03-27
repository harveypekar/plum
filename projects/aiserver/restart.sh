#!/usr/bin/env bash
# Restart aiserver: kill existing process, wait for port, start fresh
# For full stack startup (postgres + ollama + aiserver), use scripts/dev-up.sh
# shellcheck disable=SC1091
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

PORT=8080

# Load env (DATABASE_URL etc.)
source "$REPO_ROOT/scripts/common/load-env.sh"

# Kill existing aiserver
if pgrep -f "python.*main\.py" > /dev/null 2>&1; then
    echo "Stopping aiserver (PID $(pgrep -f 'python.*main\.py' | head -1))..."
    pkill -f "python.*main\.py" || true
fi

# Wait for port to be released
for _ in $(seq 1 10); do
    if ! ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
        break
    fi
    sleep 1
done

# Activate venv
source .venv/bin/activate

# Start aiserver in background
echo "Starting aiserver..."
nohup python main.py > /tmp/aiserver.log 2>&1 &

echo "aiserver started (PID $!), logs at /tmp/aiserver.log"

# Wait for it to be ready
for _ in $(seq 1 30); do
    if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
        echo "aiserver is ready"
        exit 0
    fi
    sleep 1
done
echo "Warning: aiserver did not respond within 30s, check /tmp/aiserver.log"
