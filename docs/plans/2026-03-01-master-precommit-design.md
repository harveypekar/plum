# Master Pre-commit Hook Design

## Problem

The git pre-commit hook only runs `validate-secrets.py`. Shell scripts can be committed without shellcheck, Python without linting, and CRLF line endings can slip in — all violating project conventions.

## Design

Single bash script at `.git/hooks/pre-commit` that orchestrates four checks against staged files, runs all checks regardless of individual failures, and reports everything at the end.

### Checks

1. **Secrets validation** — calls existing `scripts/common/validate-secrets.py`
2. **CRLF detection** — scans staged files for `\r\n` line endings
3. **Shellcheck** — runs `shellcheck` on staged `.sh` files
4. **Python lint** — runs `ruff check` (fallback: `flake8`) on staged `.py` files

### Behavior

- Staged file list obtained once via `git diff --cached --name-only`
- All checks run unconditionally (run-all, report-all)
- Each check prefixes output with its name
- Exit 0 only if all checks pass
- Missing tools (shellcheck, ruff/flake8) cause hard failure with install instructions

### Decisions

- **Option B: Bash orchestrator + existing Python** — keeps `validate-secrets.py` as-is, bash handles the rest
- **Hard fail on missing tools** — prevents silently skipping checks on misconfigured machines
- **Single file, not hooks.d/** — four checks don't justify a plugin system

### Unchanged

- `scripts/common/validate-secrets.py` — untouched
- Claude Code hooks (`block-env.sh`, `lint-shell.sh`) — separate, unaffected
