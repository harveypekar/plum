# GitHub Issues Migration Design

**Created:** 2026-03-01
**Purpose:** Replace TODO.txt with GitHub Issues as the task backend, with full backup strategy

## Overview

Migrate from the homebrew TODO.txt system to GitHub Issues. All three task skills (`/plum-todo-push`, `/plum-todo-pop`, `/plum-churn`) become thin wrappers around `gh` CLI calls. A backup script periodically exports all issues to local JSON for offline access, deletion recovery, and platform portability.

## Decisions

- **Backup approach:** Periodic JSON export to local filesystem (not git-tracked mirror or SQLite)
- **Retention:** Size-based limit (configurable via `BACKUP_MAX_SIZE_MB` in `.env`), not time-based
- **Subagent access:** Orchestrator-only — subagents report new tasks in findings files, orchestrator creates issues
- **Metadata:** Full — labels, milestones, and priority labels
- **Migration:** Convert all existing TODO.txt items to Issues, then retire TODO.txt

## Components

### 1. Prerequisite: `gh` CLI

Install and authenticate the GitHub CLI in WSL2. Required for all other components.

### 2. Label and Milestone Setup

**Category labels:** `deploy`, `backup`, `monitor`, `research`, `security`, `common`
**Priority labels:** `P0-critical`, `P1-high`, `P2-normal`, `P3-low`
**Special labels:** `migrated` (for items from TODO.txt), `in-progress` (for churning tasks)

Milestones created as needed for grouping related work.

### 3. Skill Redesigns

**`/plum-todo-push <task text>`**
- Creates an issue: `gh issue create --title "<task text>"`
- Skill prompts Claude to pick appropriate labels from the standard set
- Returns the issue number (replaces the 6-letter ID)

**`/plum-todo-pop [issue-number]`**
- Without argument: fetches the oldest open issue via `gh issue list --state open --limit 1 --json number,title`
- With argument: fetches specific issue via `gh issue view <number> --json number,title,body`
- Executes the task
- When done: closes the issue with `gh issue close <number>` and a closing comment

**`/plum-churn`**
- Lists all open issues: `gh issue list --state open --json number,title,body,labels`
- Dispatches subagents using issue numbers instead of 6-letter IDs
- Adds `in-progress` label to dispatched issues
- After completion: closes issues via `gh issue close` with a status comment
- Subagent prompt template references issue number instead of task ID
- Enforcement (worktree hooks) unchanged — subagents still cannot push/merge/create PRs

### 4. Backup Script

**Script:** `scripts/backup/backup-issues.sh`

**Export command:**
```bash
gh issue list --state all --json number,title,body,state,labels,milestone,createdAt,updatedAt,closedAt,comments,author
```

**Storage layout:**
```
~/.backups/plum/issues/
├── 2026-03-01-120000.json    # Full snapshot
├── 2026-03-01-180000.json    # Full snapshot
└── latest.json               # Symlink to most recent
```

**Retention:** Size-based. After each export, checks total directory size against `BACKUP_MAX_SIZE_MB` (from `.env`). Deletes oldest snapshots until under the limit.

**Recovery scenarios:**
- **GitHub down:** Read `latest.json` locally for task list
- **Accidental close/delete:** Diff two snapshots to find missing issues, re-create with `gh issue create`
- **Platform migration:** Parse JSON, transform to target format

**Scheduling:** Can be added to cron or run manually. Uses `logging.sh` for output.

### 5. Migration Script

**Script:** `scripts/common/migrate-todo-to-issues.sh` (one-time use)

1. Read each line of TODO.txt (format: `<id> <task text>`)
2. For each: `gh issue create --title "<task text>" --label migrated`
3. Print mapping table: `old-id -> issue #N`
4. After all created successfully, delete TODO.txt
5. Script can be removed after use

### 6. Documentation Updates

Files that reference TODO.txt and need updating:
- `CLAUDE.md` — change TODO.txt reference to GitHub Issues
- `design.md` — update Project Structure tree, Skills section, add backup to scripts listing
- `MANUAL.md` — update skill descriptions
- `workflow-subagents.md` — replace TODO.txt single-writer rule with GitHub Issues equivalent
- `.env.example` — add `BACKUP_MAX_SIZE_MB=50`

### 7. Orchestrator Rules (from workflow-subagents.md)

The "single-writer rule" shifts from file-level to API-level:
- Only the orchestrator creates and closes issues
- Subagents report new tasks in commit messages or findings files
- Orchestrator creates issues from subagent reports after review
