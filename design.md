# Plum: Sysadmin Scripts Project Design

**Created:** 2026-03-01
**Purpose:** Small collection of sysadmin scripts for local PC (Windows/WSL2) and VPS administration

## Overview

Plum is a lightweight framework for managing sysadmin tasks across two environments:
- **Local:** Windows machine with Zsh in WSL2
- **Remote:** Single Linux VPS (currently running static HTML website)

## Use Cases

1. **Deployments** - Push changes to VPS
2. **Backups** - Small data and 1TB media repositories
3. **Monitoring** - Claude API usage tracking and other metrics
4. **Maintenance** - System updates, cleanup, health checks

## Core Principles

1. **Safe-first for VPS changes** - Test locally before deploying
2. **Centralized logging** - All tasks log to a central location
3. **Secrets security** - API keys and credentials never committed to git
4. **Mixed execution** - Some scripts manual, some automated/scheduled
5. **Reproducibility** - Docker ensures consistency between local and remote

## Services

As much as possible, things should be implemented as services, that can be queried for data. StaticData services only fetch from local file system. Dynamic data maintain a cache filled from somewhere else. Claude MCP's should be implemented on top

## Project Structure

```
plum/
├── design.md                      # This document
├── CLAUDE.md                      # Claude Code project instructions
├── claude-quad.bat                # Windows Terminal multi-pane launcher
├── .claude/
│   ├── hooks/                     # Claude Code hooks (block-env, lint-shell)
│   └── skills/                    # Slash command skills
│       ├── plum-design-update/    # /plum-design-update
│       ├── plum-postmortem/       # /plum-postmortem
│       ├── plum-todo-pop/         # /plum-todo-pop
│       ├── plum-todo-push/        # /plum-todo-push
│       └── plum-churn/            # /plum-churn
├── MANUAL.md                      # Claude Code command reference
├── docs/
│   ├── staging.md                 # VPS inventory & staging environment
│   ├── workflow-subagents.md      # Subagent + worktree + PR + Docker workflow
│   └── plans/                     # Implementation plans
├── scripts/
│   ├── deploy/                    # Deployment automation
│   ├── backup/                    # Backup tasks (data, media)
│   │   └── backup-issues.sh       # GitHub Issues backup with size-based retention
│   ├── monitor/                   # Monitoring tasks (Claude usage, etc.)
│   └── common/                    # Shared utilities
│       ├── logging.sh             # Logging infrastructure
│       ├── load-env.sh            # Environment variable loader
│       ├── design-drift.sh        # Design drift detection helper
│       ├── validate-secrets.py    # Pre-commit secret file blocker
│       └── test-logging.sh        # Logging test script
├── docker/
│   ├── Dockerfile                 # VPS environment replica
│   └── docker-compose.local.yml   # Local testing setup
├── .env.example                   # Template for environment variables
├── .gitignore                     # Exclude .env, logs, secrets
└── README.md                      # Quick start & usage guide
```

## Workflow: Safe Script Development & Deployment

### Phase 1: Development
1. **Write script locally** in appropriate category (deploy/, backup/, monitor/)
2. **Test in Docker container** - Docker replicates VPS environment
   - `docker-compose -f docker/docker-compose.local.yml run [script]`
   - Catches most issues before touching production
3. **Document changes** - Update docs/staging.md if touching system areas

### Phase 2: Deployment
1. **Manual review** - SSH to VPS, verify it's safe to run
2. **Copy to VPS** - Via git push or secure copy
3. **Execute** - Either:
   - **Manual execution** - SSH and run with confirmation prompts
   - **Scheduled execution** - Add to cron for automated tasks
   - **Triggered execution** - Scripts triggered by external event

### Phase 3: Logging & Monitoring
1. **All scripts log** - To `~/.logs/plum/[task-name]/` on VPS
2. **Centralized access** - Can query/aggregate logs from local machine
3. **Retention** - Keep logs for debugging, archive older logs

### Phase 4: Forensic Investigation

Read-only access to the VPS for debugging, incident response, or auditing. Two complementary approaches:

**Primary: Pull-based forensic snapshots**
- Script (`scripts/monitor/forensic-snapshot.sh`) SSHes to VPS and collects a read-only snapshot locally
- Snapshot stored at `~/.forensics/plum/YYYY-MM-DD-HHMMSS/` with: system info, logs, configs (not contents of .env), file tree, open ports, and sha256 checksums of key files
- Zero risk of modifying VPS state — all examination happens locally
- Can diff snapshots over time to detect changes or tampering

**Secondary: Read-only SSH user for live investigation**
- Dedicated `plum-readonly` user on VPS with `rbash` (restricted bash)
- Read access to logs, configs, and web root via group membership
- No sudo, no write permissions, restricted PATH
- Separate SSH key stored in `.env` as `VPS_RO_SSH_KEY`
- Use only when a live snapshot isn't sufficient

## Secrets Management

### Local Development
- Create `.env` file (copy from `.env.example`)
- Scripts source `.env` at runtime
- `.env` never committed (in .gitignore)
- Docker container has access to .env for testing

### VPS Production
- VPS has its own `.env` file with production credentials
- Scripts source this for API keys, tokens, passwords
- Managed separately from code repository
- SSH securely to update if needed

## VPS Staging & Inventory

All VPS system information documented in `docs/staging.md`:
- OS version, architecture
- Installed packages & services
- Directory structure & file locations
- Current deployment process
- User accounts & SSH configuration
- Existing cron jobs / scheduled tasks
- Backup locations and strategy
- Network configuration
- System resource constraints

**Before implementing any script, review staging.md to understand what you're working with.**

## Script Organization

### deploy/
- Deployment scripts for pushing changes to VPS
- Example: push HTML updates, deploy new versions of services
- Likely manual or semi-automated (require confirmation)

### backup/
- Backup scripts for data preservation
- Small data backups (configs, databases, etc.)
- Large media repository backups (1TB)
- Likely scheduled (cron) or manual
- Should include verification & cleanup

### monitor/
- Monitoring and reporting scripts
- Claude API tracking: usage, commands requiring prompts, 
- System health checks
- Error/anomaly detection
- Likely scheduled (runs periodically)

### common/
- Shared utilities used across categories
- `logging.sh` — Log to `~/.logs/plum/[name]/YYYY-MM-DD.log` with INFO/WARN/ERROR levels
- `load-env.sh` — Find and source `.env` from project root
- `design-drift.sh` — Scan git history for design.md drift (used by `/plum-design-update`)
- `validate-secrets.py` — Pre-commit hook blocking forbidden file types
- `test-logging.sh` — Verify logging infrastructure works
- Future: SSH/remote execution utilities, encryption helpers

## Logging Strategy

### Format
```
~/.logs/plum/[script-name]/[YYYY-MM-DD].log

Example:
~/.logs/plum/deploy-html/2026-03-01.log
~/.logs/plum/backup-media/2026-03-01.log
~/.logs/plum/monitor-claude/2026-02-28.log
```

### Content
- Timestamp, log level (INFO, WARN, ERROR)
- What was done, results, any errors
- Actionable error messages for debugging
- Include script version/commit hash if possible

### Access
- View logs locally via SSH
- Can aggregate/search across logs
- Archive old logs to save space (keep 90 days?)

## Technology Stack

- **Scripting:** Bash (compatible with both local WSL2 Zsh and VPS)
- **Python:** Preferred over Bash for complex logic; used for pre-commit validation
- **Claude Code:** Development workflow via skills (slash commands), hooks, and CLAUDE.md
- **Docker:** Testing environment for VPS replication
- **Git:** Version control, deployment tracking
- **SSH:** Secure remote execution
- **Cron:** Scheduled task execution on VPS

## Claude Code Integration

### Skills (Slash Commands)
Custom skills in `.claude/skills/`:
- `/plum-todo-pop [issue-number]` — Pick an open GitHub Issue and execute it
- `/plum-todo-push <task>` — Create a new GitHub Issue with labels and priority
- `/plum-design-update` — Detect design.md drift from git history, interactively propose fixes
- `/plum-postmortem` — Same as design-update, intended for post-merge checks
- `/plum-churn` — Dispatch all open GitHub Issues as parallel subagents in isolated worktrees

### Hooks
Automated guardrails in `.claude/hooks/`:
- `block-env.sh` (PreToolUse) — Prevents Claude from editing `.env` files
- `block-worktree-danger.sh` (PreToolUse) — Blocks git push/merge/checkout main inside worktrees
- `lint-shell.sh` (PostToolUse) — Runs shellcheck after `.sh` file edits

### Git Hooks
- `pre-push` — Blocks pushes originating from `.claude/worktrees/` directories
- `pre-commit` — Runs `validate-secrets.py` to block forbidden file types

### Design Drift Detection
Keeps design.md in sync with reality:
1. `scripts/common/design-drift.sh` scans commits since last `design-checked-*` tag
2. Outputs structured markdown: commit diffs, project tree, design.md section headers
3. Skills consume this output and propose section-by-section fixes
4. After review, the analyzed commit is tagged `design-checked-<short-hash>` so future runs skip it

### Project Documentation
- `CLAUDE.md` — Concise project rules for Claude Code (structure, conventions, security)
- `MANUAL.md` — Full reference of all slash commands, hooks, and superpowers

## Security & Data Protection: Hard Enforcement

### Non-Negotiable Rules
1. **NO unencrypted PII/secrets to VPS or GitHub** - EVER
   - PII: names, emails, IP addresses, usernames, account IDs
   - Secrets: API keys, passwords, tokens, SSH keys, credentials
   - Identifying info: anything that could identify you/system
2. **NO logging of sensitive data** - Scripts must never write PII/keys to logs
3. **NO secrets in .env.example** - Only template variable names (e.g., `CLAUDE_API_KEY=` with empty value)
4. **NO plaintext secret transmission** - Use encrypted channels only

### Enforcement Mechanisms
1. **Pre-commit hook** — Blocks commits containing forbidden file types:
   - `.env` files (except `.env.example`)
   - `.key` and `.pem` files
   - Files in `secrets/` or `credentials/` directories
   - Also scans file contents for exact personal identifiers (real email, etc.) stored in `.env`
   - Implemented in `scripts/common/validate-secrets.py`

2. **Claude Code hooks** — Automated guardrails during development:
   - `block-env.sh` (PreToolUse) — Denies any Claude edit/write to `.env` files
   - `lint-shell.sh` (PostToolUse) — Runs shellcheck on `.sh` files after edits

3. **Script validation** - Before deployment:
   - Scan scripts for hardcoded secrets
   - Verify no logging of $-variables containing secrets
   - Check for plaintext HTTP (enforce HTTPS)

4. **Deployment validation** - Before sending to VPS:
   - Encrypt sensitive data in transit (SSH only, never HTTP)
   - Verify .env file not included in deployment
   - Confirm all secrets source from environment variables, not files

5. **Logging sanitization** - All logging functions must:
   - Never log variables from .env
   - Redact API keys, tokens, passwords before logging
   - Log only safe, non-identifying data

### Git Configuration
```bash
# .gitignore: hard block on secrets
.env
*.key
*.pem
secrets/
credentials/
```

### Additional Considerations
1. **VPS access** - SSH key-based only (no passwords)
2. **Script permissions** - Restrictive umask, owner-only readable where applicable
3. **Change documentation** - Update staging.md noting any PII/sensitive areas
4. **Testing in Docker** - Use dummy values in .env.example, never real secrets
5. **Backup strategy** - Encrypted backups only for data containing PII

## Next Steps

0. ~~**Set up Security Agent**~~ — Done: pre-commit hook (`validate-secrets.py`) blocks forbidden files; Claude Code hook (`block-env.sh`) blocks .env edits
1. **Inventory the VPS** — Document in docs/staging.md (template exists, needs real data)
2. ~~**Set up Docker**~~ — Done: Dockerfile and docker-compose.local.yml created
3. ~~**Create script skeleton**~~ — Done: logging.sh, load-env.sh, and common utilities created
4. **Implement first script** — Deploy or backup script as initial test
5. **Refine workflow** — Iterate based on what works in practice