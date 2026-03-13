#!/usr/bin/env bash
# Check aiserver status: process, health, Ollama connectivity
set -euo pipefail

# Process check
PID=$(pgrep -f "python.*main\.py" 2>/dev/null | head -1 || true)
if [ -z "$PID" ]; then
    echo "aiserver: NOT RUNNING"
    exit 1
fi
echo "aiserver: running (PID $PID)"

# Health check
HEALTH=$(curl -s --connect-timeout 3 http://localhost:8080/health 2>/dev/null || echo "")
if [ -z "$HEALTH" ]; then
    echo "  health: NOT RESPONDING"
    exit 1
fi

STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null || echo "unknown")
OLLAMA=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['ollama_connected'])" 2>/dev/null || echo "unknown")
MODELS=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['available_models']))" 2>/dev/null || echo "0")

echo "  status: $STATUS"
echo "  ollama: $OLLAMA"
echo "  models: $MODELS"
