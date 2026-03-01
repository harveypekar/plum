#!/bin/bash
# Test: single worktree + single Docker project
# Verifies the basic subagent workflow: worktree → Docker run → cleanup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

print_header "Test: Single Worktree + Docker"

# ── Setup names with timestamp to avoid collisions ────────────────────

TS="$(date +%s)"
BRANCH="test/single-wt-$TS"
PROJECT="test-single-wt-$TS"
WT_PATH="$REPO_ROOT/.claude/worktrees/test-single-wt"

# ── Cleanup trap ──────────────────────────────────────────────────────

cleanup() {
    print_step "Running cleanup..."
    cleanup_docker_project "$PROJECT"
    cleanup_worktree "$WT_PATH"
    cleanup_branch "$BRANCH"
}
trap cleanup EXIT

# ── Step 1: Create worktree ───────────────────────────────────────────

print_step "Creating worktree at $WT_PATH on branch $BRANCH"
mkdir -p "$(dirname "$WT_PATH")"
git -C "$REPO_ROOT" worktree add "$WT_PATH" -b "$BRANCH"
assert_dir_exists "Worktree directory created" "$WT_PATH"

# ── Step 2: Symlink .env if it exists ─────────────────────────────────

if [ -f "$REPO_ROOT/.env" ]; then
    print_step "Symlinking .env into worktree"
    ln -sf "$REPO_ROOT/.env" "$WT_PATH/.env"
else
    print_step "No .env in repo root (not required for this test)"
fi

# ── Step 3: Run test-logging.sh in Docker ─────────────────────────────

print_step "Running test-logging.sh in Docker (project: $PROJECT)"
OUTPUT=$(docker-compose -f "$REPO_ROOT/docker/docker-compose.local.yml" \
    -p "$PROJECT" run --rm plum \
    bash scripts/common/test-logging.sh 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"

# ── Step 4: Assertions ────────────────────────────────────────────────

assert_exit_zero "Docker run exited cleanly" "$EXIT_CODE"
assert_contains "Log output present" "$OUTPUT" "Log file created at"
assert_contains "Log entries written" "$OUTPUT" "Testing logging infrastructure"

# Check no leftover containers for this project
LEFTOVER=$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT" -q)
assert_eq "No leftover containers" "" "$LEFTOVER"

# ── Result ────────────────────────────────────────────────────────────

if [ "$TEST_FAILURES" -gt 0 ]; then
    echo ""
    echo "FAILED ($TEST_FAILURES failure(s))"
    exit 1
fi

echo ""
echo "All assertions passed."
