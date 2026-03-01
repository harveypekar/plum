# Master Pre-commit Hook Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the single-purpose pre-commit hook with a master script that runs secrets validation, CRLF detection, shellcheck, and Python linting on every commit.

**Architecture:** Single bash script at `.git/hooks/pre-commit` that orchestrates four checks in run-all/report-all mode. Calls existing `validate-secrets.py` for secrets, handles the rest inline. Hard-fails if required tools are missing.

**Tech Stack:** Bash, Python (existing `validate-secrets.py`), shellcheck, ruff

---

### Task 1: Write the test script

The pre-commit hook lives in `.git/hooks/` (not committed), so we test it by creating a standalone test that sets up a temp git repo, installs the hook, stages various bad files, and asserts the hook catches them.

**Files:**
- Create: `scripts/test/test-precommit-hook.sh`

**Step 1: Create the test script**

Uses the existing `test-helpers.sh` framework. Tests each check independently in isolated temp repos.

```bash
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
```

**Step 2: Run the test to verify it fails**

Run: `bash scripts/test/test-precommit-hook.sh`
Expected: Failures because the master hook doesn't exist yet at `scripts/common/pre-commit`.

**Step 3: Commit**

```bash
git add scripts/test/test-precommit-hook.sh
git commit -m "test: add pre-commit hook test script"
```

---

### Task 2: Write the master pre-commit script

**Files:**
- Create: `scripts/common/pre-commit`
- Modify: `.git/hooks/pre-commit` (replace contents)

**Step 1: Create the master hook at `scripts/common/pre-commit`**

We keep the canonical copy in the repo (committed) and `.git/hooks/pre-commit` just calls it. This way the hook logic is version-controlled.

```bash
#!/bin/bash
# Master pre-commit hook — runs all checks, reports all failures.
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
STAGED_FILES=$(git diff --cached --name-only)
FAILED=0

header() { echo ""; echo "── $1 ──"; }
fail()   { FAILED=1; }

# ── Check: required tools ───────────────────────────────────────────

check_tools() {
    local missing=0
    if ! command -v shellcheck &>/dev/null; then
        echo "  ERROR: shellcheck not installed (apt install shellcheck / brew install shellcheck)"
        missing=1
    fi
    if ! command -v ruff &>/dev/null && ! command -v flake8 &>/dev/null; then
        echo "  ERROR: ruff not installed (pipx install ruff)"
        missing=1
    fi
    return $missing
}

header "tool check"
if ! check_tools; then
    echo "  Install missing tools and retry."
    exit 1
fi

# ── Check 1: secrets ────────────────────────────────────────────────

header "secrets"
if ! python3 "$REPO_ROOT/scripts/common/validate-secrets.py"; then
    fail
fi

# ── Check 2: CRLF line endings ─────────────────────────────────────

header "crlf"
crlf_found=0
for f in $STAGED_FILES; do
    # Skip deleted files and binary files
    [ -f "$f" ] || continue
    if git diff --cached --diff-filter=d -- "$f" | grep -qP '\r$'; then
        echo "  CRLF detected: $f"
        crlf_found=1
    fi
done
if [ "$crlf_found" -eq 1 ]; then
    echo "  Fix: dos2unix <file> or configure git (core.autocrlf=input)"
    fail
fi

# ── Check 3: shellcheck ────────────────────────────────────────────

header "shellcheck"
sh_files=$(echo "$STAGED_FILES" | grep '\.sh$' || true)
if [ -n "$sh_files" ]; then
    sc_failed=0
    for f in $sh_files; do
        [ -f "$f" ] || continue
        if ! shellcheck "$f" 2>&1; then
            sc_failed=1
        fi
    done
    if [ "$sc_failed" -eq 1 ]; then
        fail
    fi
else
    echo "  (no .sh files staged)"
fi

# ── Check 4: Python lint ───────────────────────────────────────────

header "ruff"
py_files=$(echo "$STAGED_FILES" | grep '\.py$' || true)
if [ -n "$py_files" ]; then
    lint_failed=0
    if command -v ruff &>/dev/null; then
        for f in $py_files; do
            [ -f "$f" ] || continue
            if ! ruff check "$f" 2>&1; then
                lint_failed=1
            fi
        done
    else
        for f in $py_files; do
            [ -f "$f" ] || continue
            if ! flake8 "$f" 2>&1; then
                lint_failed=1
            fi
        done
    fi
    if [ "$lint_failed" -eq 1 ]; then
        fail
    fi
else
    echo "  (no .py files staged)"
fi

# ── Result ──────────────────────────────────────────────────────────

echo ""
if [ "$FAILED" -eq 1 ]; then
    echo "Pre-commit: FAILED (fix errors above)"
    exit 1
else
    echo "Pre-commit: OK"
    exit 0
fi
```

**Step 2: Replace `.git/hooks/pre-commit` to call the canonical copy**

```bash
#!/bin/bash
# Delegates to the version-controlled master hook
exec "$(git rev-parse --show-toplevel)/scripts/common/pre-commit"
```

**Step 3: Make both executable**

Run: `chmod +x scripts/common/pre-commit .git/hooks/pre-commit`

**Step 4: Run the test suite**

Run: `bash scripts/test/test-precommit-hook.sh`
Expected: All tests pass.

**Step 5: Manual smoke test**

Run: `git stash && echo "test" > /tmp/plum-test.txt && cp /tmp/plum-test.txt clean.txt && git add clean.txt && git commit -m "test: smoke" --dry-run`
Verify: Hook output shows all four check headers and "Pre-commit: OK"
Cleanup: `git checkout -- clean.txt` (or `git reset HEAD clean.txt`)

**Step 6: Commit**

```bash
git add scripts/common/pre-commit
git commit -m "feat: add master pre-commit hook with shellcheck, CRLF, and ruff checks"
```

Note: `.git/hooks/pre-commit` isn't tracked by git, so it's not committed. The canonical copy at `scripts/common/pre-commit` is what we commit.

---

### Task 3: Fix any test failures and iterate

**Step 1: Review test output**

If any tests failed in Task 2 Step 4, fix the hook logic and re-run.

**Step 2: Run shellcheck on the hook itself**

Run: `shellcheck scripts/common/pre-commit`
Expected: Clean (no warnings). Fix any issues.

**Step 3: Run shellcheck on the test script**

Run: `shellcheck scripts/test/test-precommit-hook.sh`
Expected: Clean. Fix any issues.

**Step 4: Commit fixes if any**

```bash
git add scripts/common/pre-commit scripts/test/test-precommit-hook.sh
git commit -m "fix: address shellcheck/test issues in pre-commit hook"
```

---

### Task 4: Add setup documentation

Since `.git/hooks/pre-commit` isn't committed, new clones need a way to install it.

**Files:**
- Create: `scripts/setup-hooks.sh`

**Step 1: Write the setup script**

```bash
#!/bin/bash
# Install git hooks from scripts/common/ into .git/hooks/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "Installing pre-commit hook..."
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
exec "$(git rev-parse --show-toplevel)/scripts/common/pre-commit"
EOF
chmod +x "$HOOKS_DIR/pre-commit"

echo "Done. Hooks installed."
```

**Step 2: Test it**

Run: `bash scripts/setup-hooks.sh`
Expected: "Installing pre-commit hook..." and "Done."
Verify: `cat .git/hooks/pre-commit` shows the delegation script.

**Step 3: Commit**

```bash
git add scripts/setup-hooks.sh
git commit -m "feat: add setup-hooks.sh for new clone hook installation"
```
