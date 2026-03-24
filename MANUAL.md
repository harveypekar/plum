# Claude Code Manual for Plum

Quick reference for all slash commands, hooks, and features configured for this project.

## Project Slash Commands

These are specific to Plum (defined in `.claude/skills/`):

| Command | What It Does |
|---------|-------------|
| `/plum-todo-pop [issue-number]` | Picks an open GitHub Issue and executes it |
| `/plum-todo-push <task>` | Creates a new GitHub Issue with labels and priority |
| `/plum-design-update` | Detects drift between design.md and git history, proposes updates |
| `/plum-postmortem` | After merging a PR, checks if design.md needs updating |
| `/plum-churn` | Dispatches all open GitHub Issues as parallel subagents in isolated worktrees |
| `/plum-audit [section]` | Runs comprehensive project health audit (security, quality, docs, infra, claude, testing) |

## Workflow Slash Commands

From installed plugins - the ones you'll use most often:

### Git & PRs

| Command | Plugin | What It Does |
|---------|--------|-------------|
| `/commit` | commit-commands | Create a git commit with proper message |
| `/commit-push-pr` | commit-commands | Commit, push, and open a PR in one step |
| `/clean-gone` | commit-commands | Delete local branches that are gone on remote |
| `/review-pr` | pr-review-toolkit | Run multi-agent PR review (silent failures, test coverage, types) |
| `/code-review` | code-review | Review a PR against project guidelines |
| `/coderabbit:review` | coderabbit | Run CodeRabbit AI code review on changes |

### Development

| Command | Plugin | What It Does |
|---------|--------|-------------|
| `/feature-dev` | feature-dev | Guided feature development with architecture analysis |
| `/simplify` | code-simplifier | Review changed code for reuse, quality, efficiency |
| `/frontend-design` | frontend-design | Build polished web UIs (not relevant for Plum) |

### Planning & Debugging

| Command | Plugin | What It Does |
|---------|--------|-------------|
| `/ralph-loop` | ralph-loop | Start autonomous development loop in current session |
| `/cancel-ralph` | ralph-loop | Stop an active Ralph Loop |

### Project Maintenance

| Command | Plugin | What It Does |
|---------|--------|-------------|
| `/revise-claude-md` | claude-md-management | Update CLAUDE.md with learnings from this session |
| `/claude-md-improver` | claude-md-management | Audit and improve CLAUDE.md files |

### Skill & Hook Management

| Command | Plugin | What It Does |
|---------|--------|-------------|
| `/hookify` | hookify | Create hooks from conversation analysis |
| `/hookify:configure` | hookify | Enable/disable hookify rules |
| `/hookify:list` | hookify | List all configured hookify rules |
| `/skill-creator` | skill-creator | Create, modify, and test skills |

## Active Hooks

Configured in `.claude/settings.local.json`. Active next session.

### PreToolUse: Block .env edits
- **Trigger:** Any Edit or Write targeting a `.env` file
- **Effect:** Blocks the operation, tells Claude to let you edit .env manually
- **Script:** `.claude/hooks/block-env.sh`

### PostToolUse: ShellCheck linting
- **Trigger:** After any Edit or Write to a `.sh` file
- **Effect:** Runs shellcheck and reports warnings to Claude for fixing
- **Script:** `.claude/hooks/lint-shell.sh`
- **Requires:** shellcheck installed at `~/.local/bin/shellcheck`

### PreToolUse: Block dangerous git in worktrees
- **Trigger:** Any Bash command inside a `.claude/worktrees/` directory
- **Effect:** Blocks git push, git merge, git checkout main/master, gh pr create
- **Script:** `.claude/hooks/block-worktree-danger.sh`

### Pre-push: Block worktree pushes
- **Trigger:** Any git push from a `.claude/worktrees/` directory
- **Effect:** Blocks the push, tells you to review and push from the main working directory
- **Script:** `.git/hooks/pre-push`

### Pre-commit: Master hook
- **Trigger:** Every git commit
- **Effect:** Runs all checks (reports all failures at once):
  1. **Secrets** — blocks `.env`, `.key`, `.pem`, `secrets/`, `credentials/` files
  2. **CRLF** — blocks Windows-style line endings
  3. **Shellcheck** — lints staged `.sh` files
  4. **Ruff** — lints staged `.py` files
- **Hard fails** if shellcheck or ruff are not installed
- **Script:** `scripts/common/pre-commit` (install via `bash scripts/setup-hooks.sh`)
- **Requires:** shellcheck, ruff (or flake8)

## MCP Servers

### Not yet installed (needs Node.js in WSL2)

**context7** - Live documentation lookup for Docker, bash, Python APIs:
```bash
# First install node in WSL2:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
nvm install --lts

# Then add the MCP server:
claude mcp add context7 -- npx -y @upwind-media/context7-mcp@latest
```

## Superpowers (Auto-Triggered)

These are NOT slash commands - Claude invokes them automatically when relevant. But you can also request them explicitly:

| Skill | When It Triggers |
|-------|-----------------|
| brainstorming | Before creative work (new features, components) |
| writing-plans | When you have specs for a multi-step task |
| executing-plans | When implementing a written plan |
| test-driven-development | When implementing any feature or bugfix |
| systematic-debugging | When encountering bugs or test failures |
| verification-before-completion | Before claiming work is done |
| dispatching-parallel-agents | When facing 2+ independent tasks |
| finishing-a-development-branch | When implementation is complete and ready to merge |
| writing-skills | When creating or editing skills |
| using-git-worktrees | When starting isolated feature work |
| requesting-code-review | After completing tasks or before merging |
| receiving-code-review | When processing code review feedback |

**Tip:** Say "use brainstorming" or "use TDD" to explicitly trigger these.

## Built-in Commands

These are part of Claude Code itself (not plugins):

| Command | What It Does |
|---------|-------------|
| `/help` | Show help |
| `/clear` | Clear conversation |
| `/compact` | Summarize and compress conversation context |
| `/cost` | Show token usage and cost |
| `/config` | View/edit settings |
| `/model` | Switch Claude model |
| `/fast` | Toggle fast mode (same model, faster output) |
| `/plugins` | Manage plugins |
| `/mcp` | Manage MCP servers |
| `/tasks` | Show background tasks |
| Shift+Tab | Toggle plan mode (explore before implementing) |

## Tips You Might Forget

1. **Start with `/plum-todo-pop`** to grab your next task
2. **Use `/commit` instead of manual git** - it handles message formatting
3. **Say "use TDD"** when building new scripts to follow test-first workflow
4. **Run `/revise-claude-md`** at the end of sessions that establish new patterns
5. **Check `docs/staging.md`** before writing scripts that touch the VPS
6. **Test in Docker first:** `docker-compose -f docker/docker-compose.local.yml run plum bash scripts/...`
7. **ShellCheck runs automatically** on .sh file edits (after next session restart)
8. **`.env` edits are blocked** - edit that file manually outside Claude
9. **Use `/simplify`** after writing a chunk of code to clean it up
10. **Use `/hookify`** when Claude keeps making a mistake you want to prevent permanently

---

## Google Backup

Automated incremental backup of Google account data to the local filesystem. Lives at `scripts/backup/google-backup/`.

### Supported Services

| Service | Sync Method | Output Format | Storage Layout |
|---------|-------------|---------------|----------------|
| Gmail | `historyId` incremental | EML + metadata JSON | `gmail/<msg_id>/message.eml` + `metadata.json` |
| Calendar | `syncToken` incremental | JSON per event | `calendar/<cal_id>/<event_id>.json` |
| Contacts | `syncToken` incremental | VCF + JSON | `contacts/<person_id>.vcf` + `.json` |
| Drive | `changes.startPageToken` | Original files + metadata | `drive/by_id/<file_id>/` + `drive/tree/` symlinks |
| Tasks | Full dump | JSON per task | `tasks/<list_id>/<task_id>.json` |
| YouTube | Full dump | JSON collections | `youtube/subscriptions.json`, `liked_videos.json`, `playlists/` |

### First-Time Setup

**1. Google Cloud Project:**
- Create project at https://console.cloud.google.com/
- Enable APIs: Gmail, Calendar, People, Drive, Tasks, YouTube Data v3
- Create OAuth 2.0 Desktop App credentials
- Download the client secret JSON file

**2. Configure `.env`:**
```bash
GOOGLE_BACKUP_CLIENT_SECRET=/path/to/client_secret.json
GOOGLE_BACKUP_DIR=~/.backups/plum/google
GOOGLE_BACKUP_MAX_DISK_GB=50  # optional safety limit
```

**3. Authorize:**
```bash
bash scripts/backup/google-backup/run.sh auth
# Opens browser for OAuth2 consent — grant read-only access
```

### Usage

```bash
# Back up everything
bash scripts/backup/google-backup/run.sh --all

# Back up specific services
bash scripts/backup/google-backup/run.sh --gmail --contacts

# Check sync status
bash scripts/backup/google-backup/run.sh --status
```

### Cron Integration

```bash
# Daily backup at 3am
0 3 * * * bash /path/to/plum/scripts/backup/google-backup/run.sh --all
```

Logs go to `~/.logs/plum/google-backup/YYYY-MM-DD.log` via Plum's `logging.sh`.

### How Incremental Sync Works

- **First run**: Full download of all items. Gmail checkpoints every 500 messages for crash recovery.
- **Subsequent runs**: Only fetches changes since the last sync token. Typically completes in seconds.
- **Deleted items**: Never removed from backup. Metadata is marked with `"deleted": true` or `"trashed": true` — the original content (EML, VCF, files) is preserved.
- **State files**: Stored at `$GOOGLE_BACKUP_DIR/state/<service>.json`. Delete a state file to force a full re-sync for that service.

### Drive Backup Layout

Drive uses a dual-directory approach:
- **`drive/by_id/<file_id>/`** — canonical storage, one directory per file containing `metadata.json` + the actual file
- **`drive/tree/`** — symlink tree mirroring your Google Drive folder structure, rebuilt after each sync
- Google Docs/Sheets/Slides are exported as PDF

### Disk Limit

Set `GOOGLE_BACKUP_MAX_DISK_GB` in `.env` to cap total backup size. When exceeded, Drive sync (the largest service) is skipped. Other services continue normally. This is a safety stop, not auto-deletion — nothing is ever removed.
