# Plum: Local PC & VPS Sysadmin Scripts

A lightweight framework for managing sysadmin tasks across your local machine (Windows/WSL2) and a Linux VPS.

## Quick Start

### 1. Setup Environment
```bash
cp .env.example .env
# Edit .env with your VPS connection details
```

### 2. Test in Docker (recommended)
```bash
# Build the Docker environment (replicates VPS)
docker-compose -f docker/docker-compose.local.yml build

# Run a script in the container
docker-compose -f docker/docker-compose.local.yml run [script-name]
```

### 3. Deploy to VPS
```bash
# After testing locally...
# Copy script to VPS
scp scripts/[category]/[script-name] $VPS_USER@$VPS_HOST:/path/to/scripts/

# SSH and execute
ssh $VPS_USER@$VPS_HOST ./script-name
```

## Directory Structure

```
plum/
├── scripts/
│   ├── deploy/      # Deployment automation
│   ├── backup/      # Backup tasks
│   ├── monitor/     # Monitoring & reporting
│   └── common/      # Shared utilities
├── docs/
│   └── staging.md   # VPS inventory & environment
├── docker/
│   └── [Docker files for testing]
├── .env.example     # Template (copy to .env)
├── .gitignore       # Git security rules
└── README.md        # This file
```

## Script Categories

### deploy/
Scripts for pushing changes to the VPS (HTML updates, service deployments).

### backup/
Automated backup tasks for data preservation (small data + 1TB media).

### monitor/
Monitoring scripts for health checks, API usage tracking, error detection.

### common/
Shared utilities: logging, environment loading, error handling, SSH helpers.

## Logging

All scripts log to `~/.logs/plum/[script-name]/[YYYY-MM-DD].log`

Example:
- `~/.logs/plum/deploy-html/2026-03-01.log`
- `~/.logs/plum/backup-media/2026-03-01.log`

View logs on VPS:
```bash
ssh $VPS_USER@$VPS_HOST tail -f ~/.logs/plum/[script-name]/[date].log
```

## Security Rules (CRITICAL)

✅ **DO:**
- Use `.env` for all secrets (API keys, passwords, SSH paths)
- Test scripts in Docker before VPS deployment
- Log only non-sensitive data (redact API keys, usernames)
- Use SSH-only for remote access (never HTTP for credentials)

❌ **DON'T:**
- Commit `.env` file (it's in .gitignore)
- Hardcode secrets in scripts
- Log sensitive data (API keys, passwords, personal info)
- Use plaintext transmission for credentials

## Workflow

1. **Write** - Create script in appropriate category
2. **Test** - Run in Docker container to catch issues
3. **Review** - Check docs/staging.md for system details
4. **Deploy** - Copy to VPS via SSH and execute
5. **Monitor** - Check logs for success/errors

## For More Information

See **docs/staging.md** for:
- VPS OS version, architecture, installed packages
- Directory structure and file locations
- Current deployment process
- SSH configuration
- Existing cron jobs and scheduled tasks
- Backup locations and strategy
- System resource constraints

Before implementing any script, review `staging.md` to understand your VPS environment.

## Support

- Check logs in `~/.logs/plum/` for error details
- Review script output before running in production
- Test all changes in Docker first
