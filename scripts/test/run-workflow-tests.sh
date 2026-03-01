#!/bin/bash
# Runner: execute workflow integration tests sequentially
# No set -e — we need to continue after individual test failures

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

print_header "Workflow Integration Tests"

TESTS=(
    "$SCRIPT_DIR/test-single-worktree-docker.sh"
    "$SCRIPT_DIR/test-multi-agent-docker.sh"
)

PASSED=0
FAILED=0
RESULTS=()

for test_script in "${TESTS[@]}"; do
    name="$(basename "$test_script")"
    print_step "Running: $name"

    if bash "$test_script"; then
        RESULTS+=("  ✅ PASS  $name")
        PASSED=$((PASSED + 1))
    else
        RESULTS+=("  ❌ FAIL  $name")
        FAILED=$((FAILED + 1))
    fi
    echo ""
done

# ── Summary ───────────────────────────────────────────────────────────

TOTAL=$((PASSED + FAILED))

print_header "Summary: $PASSED/$TOTAL passed"

for line in "${RESULTS[@]}"; do
    echo "$line"
done
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "$FAILED test(s) failed."
    exit 1
fi

echo "All tests passed."
