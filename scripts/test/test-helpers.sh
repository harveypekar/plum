#!/bin/bash
# Shared test utilities — sourced by test scripts, not run directly

# Repo root derived from this file's location (scripts/test/ -> repo root)
HELPERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HELPERS_DIR/../.." && pwd)"

# ── Output ────────────────────────────────────────────────────────────

print_header() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  $1"
    echo "═══════════════════════════════════════════════════"
    echo ""
}

print_step() {
    echo "  ▸ $1"
}

print_pass() {
    echo "  ✅ PASS: $1"
}

print_fail() {
    echo "  ❌ FAIL: $1" >&2
    TEST_FAILURES=$((TEST_FAILURES + 1))
}

# ── Assertions ────────────────────────────────────────────────────────
# All assertions increment TEST_FAILURES on failure (non-fatal).

TEST_FAILURES=0

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        print_pass "$label"
    else
        print_fail "$label (expected '$expected', got '$actual')"
    fi
}

assert_file_exists() {
    local label="$1" path="$2"
    if [ -f "$path" ]; then
        print_pass "$label"
    else
        print_fail "$label (file not found: $path)"
    fi
}

assert_dir_exists() {
    local label="$1" path="$2"
    if [ -d "$path" ]; then
        print_pass "$label"
    else
        print_fail "$label (directory not found: $path)"
    fi
}

assert_contains() {
    local label="$1" haystack="$2" needle="$3"
    if echo "$haystack" | grep -q "$needle"; then
        print_pass "$label"
    else
        print_fail "$label (output does not contain '$needle')"
    fi
}

assert_exit_zero() {
    local label="$1" exit_code="$2"
    if [ "$exit_code" -eq 0 ]; then
        print_pass "$label"
    else
        print_fail "$label (exit code: $exit_code)"
    fi
}

# ── Cleanup (idempotent) ─────────────────────────────────────────────

cleanup_docker_project() {
    local project="$1"
    print_step "Cleaning up Docker project: $project"
    docker-compose -f "$REPO_ROOT/docker/docker-compose.local.yml" \
        -p "$project" down --volumes --remove-orphans 2>/dev/null || true
}

cleanup_worktree() {
    local path="$1"
    print_step "Removing worktree: $path"
    git -C "$REPO_ROOT" worktree remove --force "$path" 2>/dev/null || true
}

cleanup_branch() {
    local branch="$1"
    print_step "Deleting branch: $branch"
    git -C "$REPO_ROOT" branch -D "$branch" 2>/dev/null || true
}
