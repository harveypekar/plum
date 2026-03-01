# Plum

Sysadmin scripts for Windows/WSL2 and a single Linux VPS. Bash and Python.

## Project Structure

- `scripts/deploy/` - Deployment scripts
- `scripts/backup/` - Backup scripts
- `scripts/monitor/` - Monitoring scripts
- `scripts/common/` - Shared utilities (logging.sh, load-env.sh, script-template.sh)
- `docker/` - Docker setup replicating VPS environment
- `docs/` - Documentation and plans
- `design.md` - Architecture and design decisions (read before major changes)
- `TODO.txt` - Task queue (use `/plum-todo-pop` and `/plum-todo-push`)

## Writing Scripts

- New scripts: copy `scripts/common/script-template.sh` and modify
- Always `source` logging.sh and load-env.sh at the top
- Test in Docker before deploying: `docker-compose -f docker/docker-compose.local.yml run plum bash scripts/...`
- Python preferred over bash when logic gets complex; use a virtual environment

## Security Rules (Non-Negotiable)

- **Never** put real secrets, API keys, passwords, or PII in code or logs
- **Never** edit `.env` files (hook blocks this; user edits manually)
- Secrets go in `.env` only (sourced at runtime via load-env.sh)
- `.env.example` has empty placeholders only
- Pre-commit hook runs `scripts/common/validate-secrets.py` to block forbidden files

## Logging

All scripts log to `~/.logs/plum/[script-name]/YYYY-MM-DD.log` using:
```bash
source "$SCRIPT_DIR/../common/logging.sh" "script-name"
log_info "message"
log_warn "message"
log_error "message"
```

## Conventions

- Commit messages: imperative mood, prefixed with type (`feat:`, `fix:`, `docs:`, `chore:`)
- Line endings: use Unix LF (not Windows CRLF)
- Shell scripts: must pass shellcheck (hook runs automatically)
- Review `docs/staging.md` before writing scripts that touch VPS systems
