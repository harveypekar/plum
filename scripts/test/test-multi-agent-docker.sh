#!/bin/bash
# Test: two Docker projects running in parallel
# Verifies that -p project isolation prevents collisions between agents

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

print_header "Test: Multi-Agent Docker (Parallel)"

# ── Setup names with timestamp ────────────────────────────────────────

TS="$(date +%s)"
PROJECT_A="test-agent-a-$TS"
PROJECT_B="test-agent-b-$TS"
COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.local.yml"
TMP_DIR="$(mktemp -d)"

# ── Cleanup trap ──────────────────────────────────────────────────────

cleanup() {
    print_step "Running cleanup..."
    cleanup_docker_project "$PROJECT_A"
    cleanup_docker_project "$PROJECT_B"
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# ── Step 1: Build image once (avoid parallel build race) ──────────────

print_step "Building Docker image (once, before parallel runs)"
docker-compose -f "$COMPOSE_FILE" build

# ── Step 2: Launch two Docker projects in parallel ────────────────────

print_step "Launching agent A (project: $PROJECT_A)"
(
    set +e
    docker-compose -f "$COMPOSE_FILE" \
        -p "$PROJECT_A" run --rm plum \
        bash scripts/common/test-logging.sh \
        > "$TMP_DIR/output-a.txt" 2>&1
    echo $? > "$TMP_DIR/exit-a.txt"
) &

print_step "Launching agent B (project: $PROJECT_B)"
(
    set +e
    docker-compose -f "$COMPOSE_FILE" \
        -p "$PROJECT_B" run --rm plum \
        bash scripts/common/test-logging.sh \
        > "$TMP_DIR/output-b.txt" 2>&1
    echo $? > "$TMP_DIR/exit-b.txt"
) &

print_step "Waiting for both agents to finish..."
wait

# ── Step 3: Read results ──────────────────────────────────────────────

EXIT_A=$(cat "$TMP_DIR/exit-a.txt")
EXIT_B=$(cat "$TMP_DIR/exit-b.txt")
OUTPUT_A=$(cat "$TMP_DIR/output-a.txt")
OUTPUT_B=$(cat "$TMP_DIR/output-b.txt")

echo ""
echo "--- Agent A output ---"
echo "$OUTPUT_A"
echo ""
echo "--- Agent B output ---"
echo "$OUTPUT_B"
echo ""

# ── Step 4: Assertions ───────────────────────────────────────────────

assert_exit_zero "Agent A exited cleanly" "$EXIT_A"
assert_exit_zero "Agent B exited cleanly" "$EXIT_B"

assert_contains "Agent A log output" "$OUTPUT_A" "Log file created at"
assert_contains "Agent B log output" "$OUTPUT_B" "Log file created at"

assert_contains "Agent A log entries" "$OUTPUT_A" "Testing logging infrastructure"
assert_contains "Agent B log entries" "$OUTPUT_B" "Testing logging infrastructure"

# Check no leftover containers
LEFTOVER_A=$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT_A" -q)
LEFTOVER_B=$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT_B" -q)
assert_eq "No leftover containers (A)" "" "$LEFTOVER_A"
assert_eq "No leftover containers (B)" "" "$LEFTOVER_B"

# ── Result ────────────────────────────────────────────────────────────

if [ "$TEST_FAILURES" -gt 0 ]; then
    echo ""
    echo "FAILED ($TEST_FAILURES failure(s))"
    exit 1
fi

echo ""
echo "All assertions passed."
