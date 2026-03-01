# Plum Setup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up the complete Plum framework with security enforcement, Docker environment, logging infrastructure, and documentation.

**Architecture:** Multi-layered approach - (1) Security-first with pre-commit hooks and validation, (2) Docker for local testing replicating VPS, (3) Centralized logging framework, (4) Script templates and common utilities, (5) Comprehensive documentation.

**Tech Stack:** Bash, Docker, Docker Compose, Git hooks, Python (for validation scripts)

---

## Task 1: Create Project Structure & Root Files

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `scripts/deploy/.gitkeep`
- Create: `scripts/backup/.gitkeep`
- Create: `scripts/monitor/.gitkeep`
- Create: `scripts/common/.gitkeep`
- Create: `docs/staging.md`
- Create: `docker/.gitkeep`

**Step 1: Create .gitignore with strict security rules**

```bash
# Create .gitignore
cat > /d/prg/plum/.gitignore << 'EOF'
# Environment & Secrets (NEVER commit)
.env
.env.local
.env.*.local
*.key
*.pem
secrets/
credentials/

# Logs (local only)
logs/
~/.logs/

# System files
.DS_Store
.vscode/
.idea/

# Backups & temp
*.swp
*.swo
*~
*.tmp
EOF
```

**Step 2: Create .env.example template (NO real values)**

```bash
cat > /d/prg/plum/.env.example << 'EOF'
# Copy this to .env and fill in real values (NEVER commit .env)
# Security: All values here are EXAMPLES ONLY

# Claude API (for monitoring scripts)
CLAUDE_API_KEY=your-api-key-here

# VPS Connection
VPS_HOST=your-vps-domain.com
VPS_USER=your-username
VPS_SSH_KEY=path/to/ssh/key

# Backup Locations
BACKUP_SMALL_DATA_PATH=/backups/data
BACKUP_MEDIA_PATH=/backups/media

# Logging
LOGS_DIR=~/.logs/plum
EOF
```

**Step 3: Run git status to verify .gitignore works**

```bash
cd /d/prg/plum
git status
```

Expected: .gitignore should appear, .env should not be listed (once created)

**Step 4: Create directory structure**

```bash
cd /d/prg/plum
mkdir -p scripts/{deploy,backup,monitor,common}
mkdir -p docs/plans
mkdir -p docker
touch scripts/deploy/.gitkeep scripts/backup/.gitkeep scripts/monitor/.gitkeep scripts/common/.gitkeep
touch docker/.gitkeep
```

**Step 5: Create README.md (quick start)**

```bash
cat > /d/prg/plum/README.md << 'EOF'
# Plum: Local PC & VPS Sysadmin Scripts

Small collection of sysadmin scripts for Windows/WSL2 and VPS administration.

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your real values (NEVER commit this file)

# 2. Set up Docker locally
docker-compose -f docker/docker-compose.local.yml build

# 3. Test a script locally
docker-compose -f docker/docker-compose.local.yml run [script-name]

# 4. Deploy to VPS (when ready)
# See docs/setup-guide.md
```

## Documentation

- **[design.md](../design.md)** - Architecture & design decisions
- **[staging.md](staging.md)** - VPS inventory & environment
- **[docs/setup-guide.md](setup-guide.md)** - Detailed local setup
- **[docs/docker-guide.md](docker-guide.md)** - Docker configuration
- **[docs/security.md](security.md)** - Security enforcement details

## Script Categories

- **deploy/** - Deployment automation
- **backup/** - Backup tasks (data, media)
- **monitor/** - Monitoring & reporting
- **common/** - Shared utilities

## Important: Security

⚠️ **NEVER commit:**
- `.env` (environment variables with real secrets)
- SSH keys or certificates
- Passwords or API keys in code
- PII or identifying information

See [design.md](../design.md) for security enforcement details.
EOF
```

**Step 6: Create docs/staging.md (VPS inventory template)**

```bash
cat > /d/prg/plum/docs/staging.md << 'EOF'
# VPS Staging & Inventory

This document describes your VPS environment and serves as the source of truth for what exists on the system.

**Last Updated:** [Date]
**VPS Provider:** [e.g., DigitalOcean, Linode]
**VPS OS:** [e.g., Ubuntu 22.04 LTS]

## Current Services & Deployments

### Website
- **Type:** Static HTML
- **Location:** `/var/www/html` (or similar)
- **Server:** [nginx/apache]
- **Port:** [80/443]
- **SSL:** [Yes/No, cert location]

## System Information

### Users & Accounts
- **Root access:** [SSH key location]
- **Application user:** [e.g., www-data]
- **Additional users:** [list if any]

### Installed Software
```
- Ubuntu [version]
- [List packages: nginx, docker, git, etc.]
```

### Directory Structure
```
/
├── /var/www/html/          (website content)
├── /home/[user]/           (home directory)
├── /backups/               (backup location)
└── [other important paths]
```

### Cron Jobs
```
# Current scheduled tasks
[List existing cron jobs]
```

### Networking
- **Public IP:** [X.X.X.X]
- **Hostname:** [your-vps.com]
- **Firewall Rules:** [open ports, rules]

## Backup Strategy (Current)

- **What's backed up:** [describe]
- **Backup location:** [where]
- **Frequency:** [how often]
- **Retention:** [how long kept]

## Notes & Sensitive Areas

⚠️ **Sensitive areas to be careful with:**
- [List areas containing PII, credentials, or critical data]

[Add more sections as you document your system]
EOF
```

**Step 7: Commit**

```bash
cd /d/prg/plum
git add .gitignore .env.example README.md docs/staging.md scripts/ docker/
git commit -m "feat: initialize project structure and documentation"
```

---

## Task 2: Create Security Enforcement (Pre-Commit Hook)

**Files:**
- Create: `.git/hooks/pre-commit`
- Create: `scripts/common/validate-secrets.py`

**Step 1: Create secret validation script (Python)**

```python
cat > /d/prg/plum/scripts/common/validate-secrets.py << 'EOF'
#!/usr/bin/env python3
"""
Pre-commit hook to prevent committing secrets, PII, or sensitive data.
Must pass before any commit is allowed.
"""

import re
import sys
from pathlib import Path

# Patterns that indicate secrets/PII (common formats)
DANGEROUS_PATTERNS = [
    (r'api[_-]?key\s*=\s*["\']?[a-zA-Z0-9_\-]{20,}', 'API key'),
    (r'password\s*=\s*["\']?[a-zA-Z0-9_\-@.]{8,}', 'Password'),
    (r'token\s*=\s*["\']?[a-zA-Z0-9_\-]{20,}', 'Token'),
    (r'secret\s*=\s*["\']?[a-zA-Z0-9_\-]{20,}', 'Secret'),
    (r'bearer\s+[a-zA-Z0-9_\-]{20,}', 'Bearer token'),
    (r'[\w\.-]+@[\w\.-]+\.\w+', 'Email address (PII)'),
    (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN (PII)'),
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', 'Credit card (PII)'),
]

# Files that should NEVER be committed
FORBIDDEN_FILES = [
    r'\.env$',
    r'\.env\.',
    r'.*\.key$',
    r'.*\.pem$',
    r'secrets/.*',
    r'credentials/.*',
]

def check_file(filepath):
    """Check a file for dangerous content."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return True  # Skip binary files

    # Check forbidden filenames
    for pattern in FORBIDDEN_FILES:
        if re.search(pattern, filepath):
            print(f"❌ BLOCKED: Forbidden file pattern: {filepath}")
            return False

    # Check for dangerous patterns
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            print(f"❌ BLOCKED: {description} found in {filepath}")
            print(f"   Pattern: {pattern}")
            return False

    return True

def main():
    """Check all staged files."""
    import subprocess

    # Get staged files from git
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'],
        capture_output=True,
        text=True
    )

    files = result.stdout.strip().split('\n')
    failed = False

    for filepath in files:
        if filepath and not check_file(filepath):
            failed = True

    if failed:
        print("\n⚠️  COMMIT BLOCKED: Dangerous content detected")
        print("This is a security protection. Do NOT bypass this check.")
        print("\nIf this is a false positive:")
        print("1. Review the detected pattern")
        print("2. Use generic placeholder names in code/docs")
        print("3. Put sensitive values only in .env (never committed)")
        sys.exit(1)
    else:
        print("✅ Security check passed")
        sys.exit(0)

if __name__ == '__main__':
    main()
EOF

chmod +x /d/prg/plum/scripts/common/validate-secrets.py
```

**Step 2: Create pre-commit git hook**

```bash
cat > /d/prg/plum/.git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Pre-commit hook: Enforce security rules before committing

echo "🔒 Running security checks..."

# Run Python validation script
python3 "$(git rev-parse --show-toplevel)/scripts/common/validate-secrets.py"
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo ""
    echo "❌ Commit blocked by security hook"
    exit 1
fi

echo ""
exit 0
EOF

chmod +x /d/prg/plum/.git/hooks/pre-commit
```

**Step 3: Test the hook with a safe commit**

```bash
cd /d/prg/plum
git add scripts/common/validate-secrets.py
git commit -m "feat: add security validation script"
```

Expected: Commit succeeds, hook runs and shows "✅ Security check passed"

**Step 4: Test the hook prevents dangerous commits**

```bash
# Create test file with fake API key
echo "API_KEY=sk-1234567890abcdefghij" > test_secret.txt
git add test_secret.txt
git commit -m "test: this should fail"
```

Expected: Commit blocked with "❌ BLOCKED: API key found" message

**Step 5: Clean up test file**

```bash
cd /d/prg/plum
git reset HEAD test_secret.txt
rm test_secret.txt
```

**Step 6: Commit the pre-commit hook**

```bash
cd /d/prg/plum
git add .git/hooks/pre-commit
git commit -m "feat: add security pre-commit hook"
```

---

## Task 3: Create Logging Infrastructure

**Files:**
- Create: `scripts/common/logging.sh`
- Create: `scripts/common/load-env.sh`

**Step 1: Create logging utility**

```bash
cat > /d/prg/plum/scripts/common/logging.sh << 'EOF'
#!/bin/bash
# Logging utility for all Plum scripts
# Usage: source scripts/common/logging.sh

# Configuration
LOGS_DIR="${LOGS_DIR:-$HOME/.logs/plum}"
SCRIPT_NAME="${1:-unknown}"
LOG_FILE="$LOGS_DIR/$SCRIPT_NAME/$(date +%Y-%m-%d).log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Log levels
LOG_INFO="INFO"
LOG_WARN="WARN"
LOG_ERROR="ERROR"

# Function: log message
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Convenience functions
log_info() { log "$LOG_INFO" "$@"; }
log_warn() { log "$LOG_WARN" "$@"; }
log_error() { log "$LOG_ERROR" "$@"; }

# Function: log and exit on error
log_die() {
    log "$LOG_ERROR" "$@"
    exit 1
}

export LOG_FILE LOGS_DIR SCRIPT_NAME
EOF

chmod +x /d/prg/plum/scripts/common/logging.sh
```

**Step 2: Create environment loader**

```bash
cat > /d/prg/plum/scripts/common/load-env.sh << 'EOF'
#!/bin/bash
# Load environment variables safely
# Usage: source scripts/common/load-env.sh

# Find .env in same directory as this script or parent directories
find_env_file() {
    local current_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

    while [ "$current_dir" != "/" ]; do
        if [ -f "$current_dir/.env" ]; then
            echo "$current_dir/.env"
            return 0
        fi
        current_dir="$(dirname "$current_dir")"
    done

    return 1
}

# Load .env file
ENV_FILE=$(find_env_file)

if [ -z "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found. Please create it from .env.example"
    exit 1
fi

# Source .env (with safety checks)
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo "❌ Error: Cannot read .env file"
    exit 1
fi
EOF

chmod +x /d/prg/plum/scripts/common/load-env.sh
```

**Step 3: Create test script to verify logging**

```bash
cat > /d/prg/plum/scripts/common/test-logging.sh << 'EOF'
#!/bin/bash
# Test script: verify logging works

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/logging.sh" "test-logging"

log_info "Testing logging infrastructure"
log_info "Log file: $LOG_FILE"
log_warn "This is a warning"
log_error "This is an error (but not fatal)"
log_info "Test complete"

echo ""
echo "✅ Log file created at: $LOG_FILE"
cat "$LOG_FILE"
EOF

chmod +x /d/prg/plum/scripts/common/test-logging.sh
```

**Step 4: Test logging locally**

```bash
cd /d/prg/plum
bash scripts/common/test-logging.sh
```

Expected: Creates `~/.logs/plum/test-logging/2026-03-01.log` with test messages

**Step 5: Commit**

```bash
cd /d/prg/plum
git add scripts/common/logging.sh scripts/common/load-env.sh scripts/common/test-logging.sh
git commit -m "feat: add logging infrastructure"
```

---

## Task 4: Create Docker Setup

**Files:**
- Create: `docker/Dockerfile`
- Create: `docker/docker-compose.local.yml`

**Step 1: Create Dockerfile (VPS environment replica)**

```bash
cat > /d/prg/plum/docker/Dockerfile << 'EOF'
# Plum Docker Image - Replicates VPS environment for testing
# Build: docker-compose -f docker/docker-compose.local.yml build

FROM ubuntu:22.04

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install base tools
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    wget \
    git \
    ssh \
    openssh-client \
    vim \
    jq \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /plum

# Copy scripts into container
COPY scripts/ /plum/scripts/
COPY .env.example /plum/.env.example

# Copy .env if it exists (for local development)
# Note: This is only for local testing, never in production
COPY .env /plum/.env 2>/dev/null || true

# Make scripts executable
RUN chmod +x /plum/scripts/**/*.sh

# Default command
CMD ["/bin/bash"]
EOF
```

**Step 2: Create docker-compose.local.yml**

```bash
cat > /d/prg/plum/docker/docker-compose.local.yml << 'EOF'
version: '3.8'

services:
  plum:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: plum-dev
    volumes:
      - ..:/plum              # Mount entire project
      - /plum/logs           # Exclude logs volume
    environment:
      - HOME=/root
      - LOGS_DIR=/plum/logs
    working_dir: /plum
    stdin_open: true
    tty: true
EOF
```

**Step 3: Build Docker image**

```bash
cd /d/prg/plum
docker-compose -f docker/docker-compose.local.yml build
```

Expected: Successfully builds Docker image named "plum-dev"

**Step 4: Test Docker container**

```bash
cd /d/prg/plum
docker-compose -f docker/docker-compose.local.yml run plum bash -c "echo '✅ Docker working'; ls -la /plum"
```

Expected: Lists files in /plum directory inside container

**Step 5: Commit**

```bash
cd /d/prg/plum
git add docker/Dockerfile docker/docker-compose.local.yml
git commit -m "feat: add Docker environment for VPS testing"
```

---

## Task 5: Create Script Template & Examples

**Files:**
- Create: `scripts/common/script-template.sh`
- Create: `scripts/deploy/deploy-html-example.sh`

**Step 1: Create script template**

```bash
cat > /d/prg/plum/scripts/common/script-template.sh << 'EOF'
#!/bin/bash
# Template: Use this as a starting point for new scripts
# Usage: Copy this file, replace "script-name" and implement logic

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="script-name"

# Source common utilities
source "$SCRIPT_DIR/logging.sh" "$SCRIPT_NAME"
source "$SCRIPT_DIR/load-env.sh"

# Script starts
log_info "Starting $SCRIPT_NAME"
log_info "User: $(whoami)"
log_info "Time: $(date)"

# Your implementation here
log_info "Doing work..."
# ... add your logic ...

# Success
log_info "Completed successfully"
exit 0
EOF

chmod +x /d/prg/plum/scripts/common/script-template.sh
```

**Step 2: Create example deployment script**

```bash
cat > /d/prg/plum/scripts/deploy/deploy-html-example.sh << 'EOF'
#!/bin/bash
# Deploy HTML website to VPS
# Usage: ./scripts/deploy/deploy-html-example.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="deploy-html"

# Source utilities
source "$SCRIPT_DIR/../common/logging.sh" "$SCRIPT_NAME"
source "$SCRIPT_DIR/../common/load-env.sh"

log_info "Starting HTML deployment"
log_info "VPS: $VPS_HOST"

# Validate environment
if [ -z "$VPS_HOST" ] || [ -z "$VPS_USER" ]; then
    log_die "VPS_HOST or VPS_USER not configured in .env"
fi

# Check if HTML files exist locally
if [ ! -d "./html" ]; then
    log_warn "No ./html directory found, using example"
    mkdir -p html
    echo "<h1>Plum Deployment Test</h1>" > html/index.html
fi

log_info "HTML files ready: $(ls -la ./html)"

# Example: would deploy to VPS via SSH
log_info "Ready to deploy (manual step: rsync to VPS)"
log_info "Command would be: scp -r ./html $VPS_USER@$VPS_HOST:/var/www/"

log_info "Deployment prepared successfully"
EOF

chmod +x /d/prg/plum/scripts/deploy/deploy-html-example.sh
```

**Step 3: Test example script locally in Docker**

```bash
cd /d/prg/plum
docker-compose -f docker/docker-compose.local.yml run plum bash -c "bash scripts/deploy/deploy-html-example.sh"
```

Expected: Script runs, logs "Deployment prepared successfully"

**Step 4: Commit**

```bash
cd /d/prg/plum
git add scripts/common/script-template.sh scripts/deploy/deploy-html-example.sh
git commit -m "feat: add script template and example deployment script"
```

---

## Task 6: Create Documentation Guides

**Files:**
- Create: `docs/setup-guide.md`
- Create: `docs/docker-guide.md`
- Create: `docs/security.md`

**Step 1: Create setup guide**

```bash
cat > /d/prg/plum/docs/setup-guide.md << 'EOF'
# Local Setup Guide

## Prerequisites

- Windows 11 with WSL2 and Zsh
- Docker Desktop installed
- Git installed in WSL2

## Initial Setup

### 1. Clone Repository
```bash
cd ~/projects
git clone [your-repo-url] plum
cd plum
```

### 2. Configure Environment
```bash
# Copy example configuration
cp .env.example .env

# Edit with your real values (use secure editor)
nano .env  # or vim, VS Code, etc.
```

**What to configure:**
- `CLAUDE_API_KEY`: Your Claude API key (see .env.example)
- `VPS_HOST`: Your VPS domain or IP
- `VPS_USER`: Your VPS username
- `VPS_SSH_KEY`: Path to your SSH private key
- `BACKUP_*`: Paths where backups should go

⚠️ **IMPORTANT:** Never commit `.env` file. Git will block it.

### 3. Build Docker Image
```bash
# Build the Docker image that replicates your VPS
docker-compose -f docker/docker-compose.local.yml build

# Verify it built successfully
docker-compose -f docker/docker-compose.local.yml run plum --version
```

### 4. Verify Setup
```bash
# Test logging infrastructure
bash scripts/common/test-logging.sh

# Expected: Creates ~/.logs/plum/test-logging/YYYY-MM-DD.log
cat ~/.logs/plum/test-logging/$(date +%Y-%m-%d).log
```

## Daily Workflow

### Develop a Script
1. Copy template: `cp scripts/common/script-template.sh scripts/category/my-script.sh`
2. Edit and implement your script
3. Test locally: `docker-compose -f docker/docker-compose.local.yml run plum bash scripts/category/my-script.sh`
4. Review logs: `cat ~/.logs/plum/my-script/$(date +%Y-%m-%d).log`

### Deploy to VPS
1. Commit changes: `git add scripts/category/my-script.sh && git commit -m "feat: add my-script"`
2. SSH to VPS: `ssh $VPS_USER@$VPS_HOST`
3. Pull latest: `cd ~/plum && git pull`
4. Test: `bash scripts/category/my-script.sh`
5. Add to cron if needed (for scheduled tasks)

## Troubleshooting

**"Security check failed" on commit:**
- Check what pattern was detected: See error message
- Put sensitive values in `.env` instead
- Use placeholder names in code (e.g., `your-api-key-here`)

**Docker build fails:**
- Check Docker is running: `docker --version`
- Try rebuild: `docker-compose -f docker/docker-compose.local.yml build --no-cache`

**Scripts can't find .env:**
- Verify `.env` is in project root: `ls -la .env`
- Check permissions: `chmod 600 .env`

See [docs/security.md](security.md) for security troubleshooting.
EOF
```

**Step 2: Create Docker guide**

```bash
cat > /d/prg/plum/docs/docker-guide.md << 'EOF'
# Docker Setup & Usage

## Overview

Docker allows you to test scripts in an environment that mimics your VPS before deploying.

## Architecture

- **Dockerfile**: Builds Ubuntu 22.04 image with common tools (curl, git, python, etc.)
- **docker-compose**: Orchestrates building and running the image locally
- **Volumes**: Project directory mounted into container for live editing

## Building

### Initial Build
```bash
docker-compose -f docker/docker-compose.local.yml build
```

### Rebuild After Changes
```bash
# Rebuild if you modify Dockerfile or scripts
docker-compose -f docker/docker-compose.local.yml build --no-cache
```

## Running Scripts

### Run Single Script
```bash
docker-compose -f docker/docker-compose.local.yml run plum bash scripts/deploy/my-script.sh
```

### Interactive Shell
```bash
docker-compose -f docker/docker-compose.local.yml run plum bash
# Now you're inside the container - can run commands directly
```

### Run with Environment Variables
```bash
# .env is automatically loaded by docker-compose
docker-compose -f docker/docker-compose.local.yml run plum bash -c "echo $CLAUDE_API_KEY"
```

## Viewing Logs

Logs are written to your local machine at:
```bash
~/.logs/plum/[script-name]/YYYY-MM-DD.log
```

View them:
```bash
# Today's logs for a script
cat ~/.logs/plum/deploy-html/$(date +%Y-%m-%d).log

# All recent logs
ls -ltr ~/.logs/plum/*/*
```

## Tips

1. **Don't save state in container** - Container is ephemeral. Everything goes to logs and .env
2. **Test multiple times** - Run scripts several times to ensure they're idempotent
3. **Check for PII in logs** - Security hook prevents commits, but double-check logs don't contain sensitive data
4. **Use Docker for iteration** - Fast feedback loop before VPS deployment

## Extending the Dockerfile

If you need additional tools, modify `docker/Dockerfile`:

```dockerfile
RUN apt-get update && apt-get install -y \
    # existing packages...
    new-package-name \
    && rm -rf /var/lib/apt/lists/*
```

Then rebuild:
```bash
docker-compose -f docker/docker-compose.local.yml build --no-cache
```
EOF
```

**Step 3: Create security documentation**

```bash
cat > /d/prg/plum/docs/security.md << 'EOF'
# Security Enforcement & Best Practices

## Hard Rules

### 1. Never Commit Secrets
Files automatically blocked from git:
- `.env` (environment file)
- `*.key`, `*.pem` (cryptographic keys)
- `secrets/`, `credentials/` (directories)

**Why:** Git history is permanent. Once a secret is in git, assume it's compromised.

### 2. Never Log Sensitive Data
Scripts must not write to logs:
- API keys, passwords, tokens
- PII (names, emails, IP addresses, phone numbers, SSNs)
- Credit cards or financial data
- Credentials of any kind

**Safe logging:**
```bash
# ✅ GOOD: Generic message
log_info "Validating credentials"

# ❌ BAD: Logs the actual token
log_info "Using token: $API_TOKEN"
```

### 3. Never Send Unencrypted to VPS
- Use SSH for all remote access (never telnet, HTTP)
- SSH key-based auth (never passwords)
- Use `scp` or `rsync` over SSH for file transfer
- Never HTTP for sensitive data (always HTTPS)

## Configuration Workflow

### Setting Up Secrets

1. **Create `.env` from example:**
   ```bash
   cp .env.example .env
   ```

2. **Edit with real values:**
   ```bash
   nano .env
   # Add your real API keys, passwords, VPS connection info
   ```

3. **Verify it's ignored:**
   ```bash
   git status  # Should NOT show .env
   ```

4. **Secure the file:**
   ```bash
   chmod 600 .env  # Only you can read/write
   ```

### Using Secrets in Scripts

**Load .env automatically:**
```bash
source scripts/common/load-env.sh

# Now you can use environment variables
echo "VPS: $VPS_HOST"
echo "User: $VPS_USER"
```

**Use in SSH commands:**
```bash
ssh -i "$VPS_SSH_KEY" "$VPS_USER@$VPS_HOST" "command"
```

**Never hardcode secrets:**
```bash
# ❌ NEVER do this
ssh_key="-----BEGIN PRIVATE KEY-----
MIIEvQIBA..."

# ✅ DO this instead
ssh -i "$VPS_SSH_KEY" ...
```

## Pre-Commit Hook Enforcement

The pre-commit hook blocks commits if it detects:

### Common Patterns (automatically detected)
- `api_key = "..."` or similar assignments
- `password = "..."`, `token = "..."`, `secret = "..."`
- Bearer tokens, JWT patterns
- Email addresses (PII)
- Social Security Numbers
- Credit card numbers

### If Hook Blocks Your Commit

1. **Identify what was detected:**
   ```
   ❌ BLOCKED: API key found in scripts/my-script.sh
   ```

2. **Fix it:**
   - Move the value to `.env`
   - Or use a placeholder like `your-api-key-here`
   - Or reference an environment variable instead of literal value

3. **Try again:**
   ```bash
   git add [fixed-files]
   git commit -m "fix: remove hardcoded secret"
   ```

### Bypassing Hook (⚠️ NOT RECOMMENDED)

If you genuinely have a false positive:
```bash
git commit --no-verify -m "..."  # Skips the hook
```

**But:** Do this ONLY if you're 100% certain it's not real sensitive data.

## VPS SSH Key Management

### Generate SSH Key (one-time)
```bash
ssh-keygen -t ed25519 -f ~/.ssh/vps-key -C "vps-access"
# Press Enter for no passphrase (or add one for security)
```

### Add to VPS
```bash
ssh-copy-id -i ~/.ssh/vps-key.pub user@your-vps.com
# Or manually add ~/.ssh/vps-key.pub to ~/.ssh/authorized_keys on VPS
```

### Configure .env
```bash
VPS_SSH_KEY=~/.ssh/vps-key
```

### Secure Permissions
```bash
chmod 600 ~/.ssh/vps-key      # Only you can read
chmod 644 ~/.ssh/vps-key.pub  # Public key is fine
```

## What to Do If You Accidentally Commit a Secret

**If not pushed yet:**
```bash
git reset HEAD~1      # Undo last commit (keeps changes)
# Remove the secret from your files
git add [corrected-files]
git commit -m "fix: remove sensitive data"
```

**If already pushed:**
1. **Assume the secret is compromised**
2. **Rotate the credential immediately**
   - Change password, regenerate API key, etc.
3. **Clean git history** (if needed)
   - Use `git-filter-branch` or `git filter-repo` (advanced)
4. **Notify affected services** of the compromise

## Regular Security Checklist

- [ ] .env file is secure (not shared, not committed)
- [ ] SSH keys are protected (chmod 600, not shared)
- [ ] No hardcoded credentials in scripts
- [ ] Logs don't contain sensitive data
- [ ] Pre-commit hook is working
- [ ] All secrets are in .env, not in code

See [design.md](../design.md) for more architecture details.
EOF
```

**Step 4: Commit documentation**

```bash
cd /d/prg/plum
git add docs/setup-guide.md docs/docker-guide.md docs/security.md
git commit -m "docs: add setup, Docker, and security guides"
```

---

## Task 7: Final Verification

**Step 1: Verify project structure**

```bash
cd /d/prg/plum
tree -L 2 -a  # or ls -lR
```

Expected structure:
```
plum/
├── .env.example
├── .git/
├── .gitignore
├── README.md
├── design.md
├── docs/
│   ├── docker-guide.md
│   ├── plans/
│   ├── security.md
│   ├── setup-guide.md
│   └── staging.md
├── docker/
│   ├── Dockerfile
│   └── docker-compose.local.yml
└── scripts/
    ├── backup/
    ├── common/
    ├── deploy/
    └── monitor/
```

**Step 2: Verify git status is clean**

```bash
cd /d/prg/plum
git status
```

Expected: "nothing to commit, working tree clean"

**Step 3: View git log to confirm commits**

```bash
cd /d/prg/plum
git log --oneline
```

Expected: 7 commits (project structure, security, logging, Docker, scripts, docs, final commit if any)

**Step 4: Verify Docker still works**

```bash
cd /d/prg/plum
docker-compose -f docker/docker-compose.local.yml run plum bash -c "echo '✅ Setup complete'"
```

Expected: Container runs and prints "✅ Setup complete"

**Step 5: Final commit and summary**

```bash
cd /d/prg/plum
git log --oneline --graph
```

**Summary of what you've built:**
- ✅ Project structure with all directories
- ✅ Security enforcement with pre-commit hook
- ✅ Logging infrastructure for centralized logs
- ✅ Docker environment for safe testing
- ✅ Script templates and example
- ✅ Comprehensive documentation
- ✅ VPS inventory template (docs/staging.md)

---

## Next Steps After Setup

1. **Inventory your VPS** - Fill in `docs/staging.md` with your VPS details (OS, services, directories, etc.)
2. **Create backup scripts** - Use `scripts/common/script-template.sh` as a starting point
3. **Create deployment scripts** - Test locally with Docker before deploying
4. **Set up cron jobs** - For automated monitoring/backup tasks
5. **Configure centralized logging** - Optional: aggregate logs from VPS back to local machine

See **plan.md** for next phases if you want to implement specific features.

---

**Implementation Status:** ✅ READY TO EXECUTE

This plan is complete and ready for implementation using the `superpowers:executing-plans` skill.
