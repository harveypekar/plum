# VPS Staging & Inventory

**Last Updated:** 2026-03-01

This document describes the VPS environment. Review before implementing any script.

## System Information

### OS & Architecture
- **OS:** [Linux distribution and version]
- **Architecture:** [x86_64, ARM, etc.]
- **Kernel Version:** [e.g., 5.15.0]
- **Hostname:** [VPS hostname]

### Resources
- **CPU:** [number of cores]
- **RAM:** [amount in GB]
- **Disk:** [total size and usage]
- **Network:** [bandwidth, IP address, networking setup]

## Installed Packages & Services

### Essential Services
- **Web Server:** [nginx/Apache/other - version]
- **Database:** [MySQL/PostgreSQL/other - version if applicable]
- **Runtime:** [Node.js/Python/Ruby version if applicable]
- **Other:** [List any other important services]

### Development Tools
- **Git:** [version]
- **Docker:** [version - if installed]
- **Python:** [version if available]
- **Node.js:** [version if available]

### System Utilities
- **SSH:** [OpenSSH version]
- **Firewall:** [iptables/ufw configuration]
- **Log Rotation:** [logrotate configuration]

## Directory Structure

### Important Paths
```
/
├── home/
│   └── [username]/
│       ├── .ssh/              # SSH keys (restrictive permissions)
│       ├── .logs/plum/        # Plum script logs (created by scripts)
│       └── website/           # [Web content, if applicable]
├── var/
│   ├── www/                   # [Web server root, if applicable]
│   ├── backups/               # Backup storage
│   │   ├── data/              # Small data backups
│   │   └── media/             # Media backups (1TB)
│   └── log/                   # System logs
└── etc/
    ├── cron.d/                # System cron jobs
    └── ssh/                   # SSH configuration
```

### Key Locations
- **Web content:** [path to website files]
- **Data to backup:** [path to important data]
- **Media to backup:** [path to 1TB media repository]
- **Log directory:** [path to application logs]

## Deployment Process

### Current Workflow
[Describe how changes are currently deployed]

### Deployment Constraints
- [Any restrictions on deployment timing]
- [Services that must not be interrupted]
- [Approval requirements]

### SSH Access
- **Username:** [username]
- **SSH Key:** [location of private key on local machine]
- **Key Permissions:** [chmod 600]
- **Port:** [SSH port number, usually 22]

## Cron Jobs & Scheduled Tasks

### Current Cron Jobs
```bash
# Run 'crontab -l' output here
# Format: minute hour day month weekday command
```

### Proposed Plum Cron Jobs
- **backup-data:** [schedule and path]
- **backup-media:** [schedule and path]
- **monitor-usage:** [schedule and path]

## Backup Configuration

### Small Data Backups
- **Source:** [path to data]
- **Destination:** [backup path]
- **Frequency:** [daily/weekly/etc.]
- **Retention:** [days/weeks to keep]
- **Size:** [estimated backup size]
- **Encryption:** [encrypted or not - should be encrypted for PII]

### Media Backups
- **Source:** [path to 1TB media]
- **Destination:** [backup path]
- **Frequency:** [daily/weekly/monthly]
- **Retention:** [days/weeks to keep]
- **Size:** [~1TB]
- **Encryption:** [encrypted or not]

### Backup Strategy
- [Incremental vs. full backups]
- [Retention policy]
- [Disaster recovery plan]

## Network Configuration

### Firewall Rules
- **Inbound:** [open ports and sources]
- **Outbound:** [restrictions if any]
- **SSH:** [restricted to specific IPs if applicable]

### DNS & Domain
- **Domain:** [domain name]
- **DNS Provider:** [provider name]
- **A Record:** [current IP address]

## User Accounts & Permissions

### System Users
- **Primary User:** [username with sudo access]
- **Service Accounts:** [any daemon/service users]
- **SSH-only Users:** [users with shell access]

### File Permissions
- **Web server runs as:** [www-data/nginx/other]
- **Script permissions:** [recommended umask and file modes]

## Logging Strategy

### System Logs
- **Location:** [/var/log path]
- **Rotation:** [logrotate configuration]
- **Retention:** [how long logs are kept]

### Plum Script Logs
- **Location:** `~/.logs/plum/[script-name]/[YYYY-MM-DD].log`
- **Format:** Timestamp, log level (INFO/WARN/ERROR), message
- **Retention:** [proposed retention period, e.g., 90 days]

## Environment Variables

### Production .env Location
- **Path:** [where .env is stored on VPS, typically in home directory]
- **Permissions:** [chmod 600 - owner read/write only]

### Required Variables
```bash
# List variables needed for scripts
VPS_HOST=...
VPS_USER=...
BACKUP_DATA_PATH=...
BACKUP_MEDIA_PATH=...
LOGS_DIR=...
```

## Monitoring & Health Checks

### Current Monitoring
- [Services currently being monitored]
- [Alert mechanisms in place]
- [Health check endpoints if applicable]

### Proposed Monitoring
- [Claude API usage tracking]
- [System resource monitoring]
- [Error/anomaly detection]

## Docker Environment (Local Testing)

### VPS Replication
- **Base Image:** [Ubuntu 22.04/Debian 11/etc. - matching VPS OS]
- **Installed Services:** [services matching production]
- **Test Data:** [dummy data for testing backups, deployments]

## Known Issues & Constraints

- [Any known limitations]
- [Workarounds for common issues]
- [Scheduled maintenance windows]

## Recent Changes

| Date | Change | Impact | Who |
|------|--------|--------|-----|
| [date] | [description] | [impact] | [person] |

## Contact & Escalation

- **Primary Admin:** [name, email]
- **Backup Admin:** [name, email]
- **Hosting Provider:** [provider contact]
- **Emergency Contact:** [escalation contact]

---

**Before implementing any Plum script, ensure:**
1. ✅ You understand the current system setup (this document)
2. ✅ You have reviewed the deployment process
3. ✅ You know what can and cannot be automated
4. ✅ You have tested in Docker first
5. ✅ You have documented any system changes here
