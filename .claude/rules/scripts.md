---
paths:
  - "scripts/**"
---

# Sysadmin Scripts

Bash scripts for Windows/WSL2 and Linux VPS administration.

## Creating New Scripts

1. Copy `scripts/common/script-template.sh`
2. Source logging.sh and load-env.sh at the top:
   ```bash
   source "$SCRIPT_DIR/../common/logging.sh" "script-name"
   source "$SCRIPT_DIR/../common/load-env.sh"
   ```
3. Must pass shellcheck (pre-commit hook enforces this)
4. Test in Docker first: `docker-compose -f docker/docker-compose.local.yml run plum bash scripts/...`

## Logging

All scripts log to `~/.logs/plum/[script-name]/YYYY-MM-DD.log`.
Use `log_info`, `log_warn`, `log_error` from logging.sh.

## Before Touching VPS

Read `docs/staging.md` first. Understand what runs where before modifying deploy/monitor scripts.
