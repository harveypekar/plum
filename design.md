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

## Project Structure

```
plum/
├── design.md                      # This document
├── docs/
│   └── staging.md                 # VPS inventory & staging environment
├── scripts/
│   ├── deploy/                    # Deployment automation
│   ├── backup/                    # Backup tasks (data, media)
│   ├── monitor/                   # Monitoring tasks (Claude usage, etc.)
│   └── common/                    # Shared utilities (logging, env loading, etc.)
├── docker/
│   ├── Dockerfile                 # VPS environment replica
│   └── docker-compose.local.yml   # Local testing setup
├── logs/                          # Local logs (not committed)
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
- Logging infrastructure
- Environment variable loading
- Error handling helpers
- SSH/remote execution utilities
- Encryption of filenames, file contents, and entire directories

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
- **Docker:** Testing environment for VPS replication
- **Git:** Version control, deployment tracking
- **SSH:** Secure remote execution
- **Cron:** Scheduled task execution on VPS

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
1. **Pre-commit hook** - Blocks commits containing:
   - Common secret patterns (API_KEY=, password=, token=, etc.)
   - .env files (except .env.example)
   - High-entropy strings that look like keys
   - PII patterns (email, credit card, SSN, etc.)

2. **Script validation** - Before deployment:
   - Scan scripts for hardcoded secrets
   - Verify no logging of $-variables containing secrets
   - Check for plaintext HTTP (enforce HTTPS)

3. **Deployment validation** - Before sending to VPS:
   - Encrypt sensitive data in transit (SSH only, never HTTP)
   - Verify .env file not included in deployment
   - Confirm all secrets source from environment variables, not files

4. **Logging sanitization** - All logging functions must:
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

### Python

Python should be preferred as a scripting language if simple shell script isn't sufficient. Create and use a virtual environment.

### Additional Considerations
1. **VPS access** - SSH key-based only (no passwords)
2. **Script permissions** - Restrictive umask, owner-only readable where applicable
3. **Change documentation** - Update staging.md noting any PII/sensitive areas
4. **Testing in Docker** - Use dummy values in .env.example, never real secrets
5. **Backup strategy** - Encrypted backups only for data containing PII

## Next Steps

0. **Set up Security Agent** - Subagent that should approve all changes
1. **Inventory the VPS** - Document in docs/staging.md
2. **Set up Docker** - Create Dockerfile replicating VPS environment
3. **Create script skeleton** - Template for new scripts with logging
4. **Implement first script** - Deploy or backup script as initial test
5. **Refine workflow** - Iterate based on what works in practice