#!/bin/bash
# Test the master pre-commit hook
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

HOOK_PATH="$REPO_ROOT/scripts/common/pre-commit"

# ── Helpers ──────────────────────────────────────────────────────────

setup_test_repo() {
    local tmp
    tmp=$(mktemp -d)
    git -C "$tmp" init --quiet
    git -C "$tmp" config user.email "test@test.com"
    git -C "$tmp" config user.name "Test"
    # Initial commit so HEAD exists
    touch "$tmp/README"
    git -C "$tmp" add README
    git -C "$tmp" commit -m "init" --quiet
    # Install hook
    cp "$HOOK_PATH" "$tmp/.git/hooks/pre-commit"
    chmod +x "$tmp/.git/hooks/pre-commit"
    # Point REPO_ROOT inside the hook to our real repo (for validate-secrets.py)
    # The hook uses git rev-parse --show-toplevel, so we symlink the scripts dir
    mkdir -p "$tmp/scripts/common"
    cp "$REPO_ROOT/scripts/common/validate-secrets.py" "$tmp/scripts/common/"
    echo "$tmp"
}

cleanup_test_repo() {
    rm -rf "$1"
}

# ── Test: secrets check blocks .env ──────────────────────────────────

print_header "Test: secrets check blocks .env file"

TREPO=$(setup_test_repo)
echo "SECRET=bad" > "$TREPO/.env"
git -C "$TREPO" add .env
output=$(git -C "$TREPO" commit -m "test" 2>&1 || true)
exit_code=$?
assert_contains "blocks .env" "$output" "BLOCKED"
cleanup_test_repo "$TREPO"

# ── Test: CRLF check blocks Windows line endings ────────────────────

print_header "Test: CRLF check blocks Windows line endings"

TREPO=$(setup_test_repo)
printf "line one\r\nline two\r\n" > "$TREPO/bad.txt"
git -C "$TREPO" add bad.txt
output=$(git -C "$TREPO" commit -m "test" 2>&1 || true)
assert_contains "blocks CRLF" "$output" "CRLF"
cleanup_test_repo "$TREPO"

# ── Test: shellcheck catches errors ─────────────────────────────────

print_header "Test: shellcheck catches bad shell script"

TREPO=$(setup_test_repo)
cat > "$TREPO/bad.sh" << 'SHELL'
#!/bin/bash
echo $UNQUOTED_VAR
SHELL
git -C "$TREPO" add bad.sh
output=$(git -C "$TREPO" commit -m "test" 2>&1 || true)
assert_contains "catches shellcheck error" "$output" "shellcheck"
cleanup_test_repo "$TREPO"

# ── Test: ruff catches Python errors ────────────────────────────────

print_header "Test: ruff catches Python lint errors"

TREPO=$(setup_test_repo)
cat > "$TREPO/bad.py" << 'PYTHON'
import os
import sys
x=1
PYTHON
git -C "$TREPO" add bad.py
output=$(git -C "$TREPO" commit -m "test" 2>&1 || true)
assert_contains "catches ruff error" "$output" "ruff"
cleanup_test_repo "$TREPO"

# ── Test: clean commit passes ───────────────────────────────────────

print_header "Test: clean commit passes all checks"

TREPO=$(setup_test_repo)
printf "clean file\n" > "$TREPO/clean.txt"
git -C "$TREPO" add clean.txt
git -C "$TREPO" commit -m "test" --quiet 2>&1
exit_code=$?
assert_exit_zero "clean commit succeeds" "$exit_code"
cleanup_test_repo "$TREPO"

# ── Summary ─────────────────────────────────────────────────────────

print_header "Results"
if [ "$TEST_FAILURES" -eq 0 ]; then
    echo "  All tests passed."
    exit 0
else
    echo "  $TEST_FAILURES test(s) failed."
    exit 1
fi
