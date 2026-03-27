#!/usr/bin/env bash
# Bring up the local dev stack: Docker PostgreSQL -> Ollama check -> aiserver
# Usage: bash scripts/dev-up.sh [--no-aiserver]
# shellcheck disable=SC1091
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AISERVER_DIR="$REPO_ROOT/projects/aiserver"
AISERVER_PORT=8080
OLLAMA_URL="http://localhost:11434"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!!]${NC} $*"; }
fail()  { echo -e "${RED}[ERR]${NC} $*"; exit 1; }
step()  { echo -e "\n${GREEN}---${NC} $* ${GREEN}---${NC}"; }

# ── PostgreSQL (Docker) ─────────────────────────────────────
step "PostgreSQL"

if ! command -v docker &>/dev/null; then
    fail "docker not found. Install Docker Desktop: https://docs.docker.com/desktop/"
fi

if ! docker info &>/dev/null 2>&1; then
    fail "Docker daemon not running. Start Docker Desktop first."
fi

docker compose -f "$REPO_ROOT/docker-compose.dev.yml" up -d --wait postgres 2>&1 | grep -v "^$"
if pg_isready -h localhost -p 5432 -q 2>/dev/null; then
    info "PostgreSQL running on port 5432 (Docker)"
else
    fail "PostgreSQL container started but not accepting connections"
fi

# ── Ollama ──────────────────────────────────────────────────
step "Ollama"

if curl -s --connect-timeout 3 "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    MODEL_COUNT=$(curl -s "$OLLAMA_URL/api/tags" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "0")
    if [ "$MODEL_COUNT" -gt 0 ]; then
        info "Ollama reachable ($MODEL_COUNT models)"
    else
        warn "Ollama reachable but 0 models loaded (check OLLAMA_MODELS env on Windows)"
    fi
else
    warn "Ollama not reachable at $OLLAMA_URL (start Ollama on Windows)"
fi

# ── aiserver ────────────────────────────────────────────────
if [[ "${1:-}" == "--no-aiserver" ]]; then
    info "Skipping aiserver (--no-aiserver)"
    exit 0
fi

step "aiserver"

# Load env so DATABASE_URL is available
source "$SCRIPT_DIR/common/load-env.sh"

# Kill stale aiserver if running
if pgrep -f "python.*main\.py" > /dev/null 2>&1; then
    warn "Killing stale aiserver (PID $(pgrep -f 'python.*main\.py' | head -1))..."
    pkill -f "python.*main\.py" || true
    sleep 2
fi

# Check port is free
if ss -tlnH 2>/dev/null | grep -q ":${AISERVER_PORT} "; then
    sleep 2
    if ss -tlnH 2>/dev/null | grep -q ":${AISERVER_PORT} "; then
        fail "Port $AISERVER_PORT still in use"
    fi
fi

# Activate venv and start
cd "$AISERVER_DIR"
source .venv/bin/activate
nohup python main.py > /tmp/aiserver.log 2>&1 &
AISERVER_PID=$!
info "aiserver starting (PID $AISERVER_PID), logs at /tmp/aiserver.log"

# Wait for health (plugins can take 20s+)
for _ in $(seq 1 30); do
    if curl -s --connect-timeout 2 "http://localhost:${AISERVER_PORT}/health" > /dev/null 2>&1; then
        info "aiserver ready at http://localhost:${AISERVER_PORT}"
        exit 0
    fi
    sleep 1
done

echo ""
warn "aiserver did not respond within 30s. Last log lines:"
tail -20 /tmp/aiserver.log
exit 1
