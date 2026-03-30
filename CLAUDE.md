# Plum

Monorepo: sysadmin scripts (Windows/WSL2 + Linux VPS), side projects. Bash and Python.

## Structure

- `scripts/` — Sysadmin scripts (deploy, backup, monitor, common utilities)
- `docker/` — Docker setup replicating VPS environment
- `projects/coach/` — Running analysis tool (Python)
- `projects/ts/` — Twilight Struggle engine (C++/Python)
- `projects/db/` — Database schemas
- `projects/research/` — Research notes
- `docs/` — Documentation and plans
- `design.md` — Architecture and design decisions (read before major changes)
- `.claude/rules/` — Per-project rules (auto-loaded by path)
- Task queue managed via GitHub Issues (use `/plum-todo-pop` and `/plum-todo-push`)

## Security Rules (Non-Negotiable)

- **Never** put real secrets, API keys, passwords, or PII in code or logs
- **Never** edit `.env` files (hook blocks this; user edits manually)
- Secrets go in `.env` only (sourced at runtime via load-env.sh)
- `.env.example` has empty placeholders only
- Pre-commit hook runs `scripts/common/validate-secrets.py` to block forbidden files

## Conventions

- Commit messages: imperative mood, prefixed with type (`feat:`, `fix:`, `docs:`, `chore:`)
- Line endings: use Unix LF (not Windows CRLF)
- Shell scripts: must pass shellcheck (hook runs automatically)
- Python preferred over bash when logic gets complex; use a virtual environment
- Agents commit on their own name/email, never the one for user
- **Never mix commands with English text** — put all explanatory text as comments in the command block, not mixed inline
- Design specs and implementation plans live on the **feature branch**, never duplicated on main
- Pre-commit hook runs project tests for any modified project — fix failures before committing

## Research

- Add a reference to all statements, with links at the bottom. Also add a date
- If the information comes your model knowledge, look online for a source to reference
