# GitHub Issues Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace TODO.txt with GitHub Issues as the task backend, with periodic JSON backup and size-based retention.

**Architecture:** Three skills (`plum-todo-push`, `plum-todo-pop`, `plum-churn`) are rewritten to call `gh` CLI instead of reading/writing TODO.txt. A backup script exports all issues to local JSON with size-based retention. A one-time migration script converts existing TODO.txt items to Issues.

**Tech Stack:** Bash, `gh` CLI, `jq`, GitHub Issues API

---

### Task 1: Install and authenticate `gh` CLI

**Files:**
- None created or modified (system setup only)

**Step 1: Check if `gh` is already installed**

Run: `which gh`
Expected: either a path (already installed) or "not found"

**Step 2: Install `gh` CLI**

If not installed:
```bash
sudo apt-get update && sudo apt-get install -y gh
```

If `apt` doesn't have it, use the official method:
```bash
(type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli-stable.list > /dev/null \
  && sudo apt update \
  && sudo apt install gh -y
```

**Step 3: Authenticate**

Run: `gh auth status`
If not authenticated: `gh auth login` (interactive — user must do this manually)

**Step 4: Verify repo access**

Run: `gh repo view --json name,owner`
Expected: `{"name":"plum","owner":{"login":"harveypekar"}}`

**Step 5: Verify `jq` is available**

Run: `which jq`
If not installed: `sudo apt-get install -y jq`

**No commit** — this is system setup only.

---

### Task 2: Create GitHub labels

**Files:**
- None (GitHub API only)

**Step 1: Create category labels**

```bash
gh label create deploy --color 0075ca --description "Deployment scripts" --force
gh label create backup --color 006b75 --description "Backup scripts" --force
gh label create monitor --color 1d76db --description "Monitoring scripts" --force
gh label create research --color 5319e7 --description "Research/investigation tasks" --force
gh label create security --color b60205 --description "Security-related tasks" --force
gh label create common --color e4e669 --description "Shared utilities" --force
```

**Step 2: Create priority labels**

```bash
gh label create P0-critical --color b60205 --description "Must fix immediately" --force
gh label create P1-high --color d93f0b --description "Important, do soon" --force
gh label create P2-normal --color fbca04 --description "Normal priority" --force
gh label create P3-low --color 0e8a16 --description "Nice to have" --force
```

**Step 3: Create special labels**

```bash
gh label create migrated --color c5def5 --description "Migrated from TODO.txt" --force
gh label create in-progress --color f9d0c4 --description "Currently being worked on by a subagent" --force
```

**Step 4: Verify labels**

Run: `gh label list`
Expected: all 12 labels listed

**No commit** — these are GitHub-side only.

---

### Task 3: Migrate TODO.txt items to GitHub Issues

**Files:**
- Create: `scripts/common/migrate-todo-to-issues.sh`
- Delete after use: `TODO.txt`

**Step 1: Write the migration script**

```bash
#!/bin/bash
# One-time migration: convert TODO.txt items to GitHub Issues
# Usage: bash scripts/common/migrate-todo-to-issues.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TODO_FILE="$PROJECT_ROOT/TODO.txt"

if [[ ! -f "$TODO_FILE" ]]; then
  echo "ERROR: TODO.txt not found at $TODO_FILE"
  exit 1
fi

if [[ ! -s "$TODO_FILE" ]]; then
  echo "ERROR: TODO.txt is empty, nothing to migrate"
  exit 1
fi

echo "=== Migrating TODO.txt to GitHub Issues ==="
echo ""

# Read and process each line
declare -A mapping
while IFS= read -r line; do
  # Skip empty lines
  [[ -z "$line" ]] && continue

  # Parse: first word is ID, rest is task text
  old_id="${line%% *}"
  task_text="${line#* }"

  echo "Creating issue for: $old_id — $task_text"

  # Create issue, capture the number
  issue_url=$(gh issue create --title "$task_text" --label migrated --body "Migrated from TODO.txt (old ID: $old_id)")
  issue_num=$(echo "$issue_url" | grep -oE '[0-9]+$')

  mapping["$old_id"]="$issue_num"
  echo "  -> Issue #$issue_num"
done < "$TODO_FILE"

echo ""
echo "=== Migration Complete ==="
echo ""
printf "%-10s %s\n" "OLD ID" "ISSUE #"
printf "%-10s %s\n" "------" "-------"
for old_id in "${!mapping[@]}"; do
  printf "%-10s #%s\n" "$old_id" "${mapping[$old_id]}"
done

echo ""
echo "TODO.txt can now be deleted."
echo "Run: git rm TODO.txt && git commit -m 'chore: remove TODO.txt after migration to GitHub Issues'"
```

**Step 2: Run the migration**

Run: `bash scripts/common/migrate-todo-to-issues.sh`
Expected: Each TODO.txt item creates an issue, mapping table printed

**Step 3: Verify issues exist**

Run: `gh issue list --state open --label migrated`
Expected: all migrated issues listed

**Step 4: Remove TODO.txt and commit**

```bash
git rm TODO.txt
git add scripts/common/migrate-todo-to-issues.sh
git commit -m "chore: migrate TODO.txt items to GitHub Issues"
```

---

### Task 4: Write backup-issues.sh

**Files:**
- Create: `scripts/backup/backup-issues.sh`
- Modify: `.env.example` (add `BACKUP_MAX_SIZE_MB`)

**Step 1: Add BACKUP_MAX_SIZE_MB to .env.example**

Append to `.env.example`:
```
# Issue Backup
BACKUP_MAX_SIZE_MB=50
```

**Step 2: Write the backup script**

Create `scripts/backup/backup-issues.sh`:

```bash
#!/bin/bash
# Backup all GitHub Issues to local JSON
# Usage: bash scripts/backup/backup-issues.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="backup-issues"
source "$SCRIPT_DIR/../common/logging.sh"
source "$SCRIPT_DIR/../common/load-env.sh"

BACKUP_DIR="${HOME}/.backups/plum/issues"
BACKUP_MAX_SIZE_MB="${BACKUP_MAX_SIZE_MB:-50}"
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/$TIMESTAMP.json"

mkdir -p "$BACKUP_DIR"

log_info "Starting issue backup to $BACKUP_FILE"

# Export all issues (open and closed) with full metadata
if ! gh issue list --state all --limit 9999 \
  --json number,title,body,state,labels,milestone,createdAt,updatedAt,closedAt,comments,author \
  > "$BACKUP_FILE"; then
  log_die "Failed to export issues from GitHub"
fi

issue_count=$(jq length "$BACKUP_FILE")
log_info "Exported $issue_count issues"

# Update latest symlink
ln -sf "$BACKUP_FILE" "$BACKUP_DIR/latest.json"

# Size-based retention: delete oldest files until under limit
max_bytes=$((BACKUP_MAX_SIZE_MB * 1024 * 1024))
while true; do
  current_bytes=$(du -sb "$BACKUP_DIR" | cut -f1)
  if [[ "$current_bytes" -le "$max_bytes" ]]; then
    break
  fi

  # Find oldest file (exclude latest.json symlink)
  oldest=$(find "$BACKUP_DIR" -maxdepth 1 -name '*.json' -not -name 'latest.json' -not -type l | sort | head -1)
  if [[ -z "$oldest" || "$oldest" == "$BACKUP_FILE" ]]; then
    # Don't delete the file we just created
    break
  fi

  log_warn "Pruning old backup: $oldest (directory size: $((current_bytes / 1024 / 1024))MB > ${BACKUP_MAX_SIZE_MB}MB)"
  rm "$oldest"
done

final_size=$(du -sh "$BACKUP_DIR" | cut -f1)
log_info "Backup complete. Directory size: $final_size"
```

**Step 3: Make it executable and test**

```bash
chmod +x scripts/backup/backup-issues.sh
bash scripts/backup/backup-issues.sh
```

Expected: JSON file created at `~/.backups/plum/issues/`, log output shows issue count

**Step 4: Verify the backup**

Run: `cat ~/.backups/plum/issues/latest.json | jq '.[0] | {number, title, state}'`
Expected: first issue's number, title, and state

**Step 5: Commit**

```bash
git add scripts/backup/backup-issues.sh .env.example
git commit -m "feat: add GitHub Issues backup script with size-based retention"
```

---

### Task 5: Rewrite /plum-todo-push skill

**Files:**
- Modify: `.claude/skills/plum-todo-push/SKILL.md`

**Step 1: Rewrite the skill**

Replace the entire contents of `.claude/skills/plum-todo-push/SKILL.md` with:

```markdown
---
name: plum-todo-push
description: Use when the user invokes /plum-todo-push to create a new GitHub Issue
---

# Todo Push

Create a new GitHub Issue for a task.

## Instructions

1. The user's arguments after `/plum-todo-push` are the task text to add
2. Determine appropriate labels from the standard set:
   - **Category** (pick one): `deploy`, `backup`, `monitor`, `research`, `security`, `common`
   - **Priority** (pick one): `P0-critical`, `P1-high`, `P2-normal`, `P3-low`
3. Create the issue via Bash:
   ```bash
   gh issue create --title "<task text>" --label "<category>" --label "<priority>"
   ```
4. Confirm to the user: show the issue number, title, labels, and URL
```

**Step 2: Commit**

```bash
git add .claude/skills/plum-todo-push/SKILL.md
git commit -m "feat: rewrite /plum-todo-push to use GitHub Issues"
```

---

### Task 6: Rewrite /plum-todo-pop skill

**Files:**
- Modify: `.claude/skills/plum-todo-pop/SKILL.md`

**Step 1: Rewrite the skill**

Replace the entire contents of `.claude/skills/plum-todo-pop/SKILL.md` with:

```markdown
---
name: plum-todo-pop
description: Use when the user invokes /plum-todo-pop to pick a GitHub Issue and execute it
---

# Todo Pop

Pick a GitHub Issue and execute it as a task.

## Current open issues

!`gh issue list --state open --limit 20 --json number,title,labels --template '{{range .}}#{{.number}} {{.title}} [{{range .labels}}{{.name}} {{end}}]{{"\n"}}{{end}}'`

## Instructions

**If an argument was provided** (e.g., `/plum-todo-pop 42`):
1. Fetch the issue: `gh issue view <number> --json number,title,body`
2. If the issue doesn't exist or is closed, list open issues and ask the user to pick one

**If no argument was provided:**
1. Use the oldest open issue (first in the list above)

**Then:**
1. Tell the user the issue number, title, and body
2. Execute the task fully
3. When the task is complete, close the issue with a comment summarizing what was done:
   ```bash
   gh issue close <number> --comment "Completed: <brief summary of what was done>"
   ```
```

**Step 2: Commit**

```bash
git add .claude/skills/plum-todo-pop/SKILL.md
git commit -m "feat: rewrite /plum-todo-pop to use GitHub Issues"
```

---

### Task 7: Rewrite /plum-churn skill

**Files:**
- Modify: `.claude/skills/plum-churn/SKILL.md`

**Step 1: Rewrite the skill**

Replace the entire contents of `.claude/skills/plum-churn/SKILL.md` with:

```markdown
---
name: plum-churn
description: Use when the user invokes /plum-churn to dispatch all open GitHub Issues as parallel subagents in isolated worktrees
---

# Churn

Dispatch every open GitHub Issue as a parallel subagent in an isolated worktree.

## Current open issues

!`gh issue list --state open --limit 50 --json number,title,labels --template '{{range .}}#{{.number}} {{.title}} [{{range .labels}}{{.name}} {{end}}]{{"\n"}}{{end}}'`

## Instructions

**Before starting**, resolve the current commit hash:
```bash
CHECKED_HASH=$(git rev-parse HEAD)
CHECKED_SHORT=$(git rev-parse --short HEAD)
```

### Step 1: Fetch issues

Run:
```bash
gh issue list --state open --json number,title,body,labels
```

Parse into a list of issues. If no open issues exist, tell the user there's nothing to churn.

### Step 2: Mark issues as in-progress

For each issue, add the `in-progress` label:
```bash
gh issue edit <number> --add-label "in-progress"
```

### Step 3: Dispatch subagents

For **each** issue, dispatch an Agent tool call with these parameters:
- `subagent_type: "general-purpose"`
- `isolation: "worktree"`
- `run_in_background: true`
- `description: "#<number>: <first 3 words>"`

Use this prompt template for each subagent (fill in `{NUMBER}`, `{TITLE}`, and `{BODY}`):

```
You are working on GitHub Issue #{NUMBER}: {TITLE}

Issue description:
{BODY}

Read CLAUDE.md first for project conventions.

Rules:
- You are in an isolated worktree. Work ONLY on this branch.
- Do NOT run: git push, git merge, gh pr create, git checkout main/master
- These commands are blocked by hooks and will fail.
- Do NOT create or close GitHub Issues. The orchestrator handles that.

If this is a research/investigation task:
- Write your findings to docs/{NUMBER}-findings.md
- Commit with: docs(#{NUMBER}): <summary>

If this is an implementation task:
- Write the code, following CLAUDE.md conventions
- Commit with: feat(#{NUMBER}): <summary>

Make small, focused commits. When done, your branch will be reviewed manually.
```

Dispatch ALL agents in a single message (one tool call per issue, all in parallel).

### Step 4: Wait and report

As background agents complete, collect their results. After ALL agents have finished, present a summary and close completed issues:

For each successfully completed issue:
```bash
gh issue close <number> --comment "Completed by subagent. Branch: <branch-name>"
```

Remove the `in-progress` label from any failed issues:
```bash
gh issue edit <number> --remove-label "in-progress"
```

Present the summary:

```
## Churn Results

| Issue | Description | Status | Branch |
|-------|-------------|--------|--------|
| #12   | Fix the ... | done   | worktree-abc |
| #15   | Add the ... | failed | worktree-def |

Branches are local. Review with:
  git log worktree-<name> --oneline
  git diff main..worktree-<name>
```
```

**Step 2: Commit**

```bash
git add .claude/skills/plum-churn/SKILL.md
git commit -m "feat: rewrite /plum-churn to use GitHub Issues"
```

---

### Task 8: Update all documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `design.md`
- Modify: `MANUAL.md`
- Modify: `docs/workflow-subagents.md`

**Step 1: Update CLAUDE.md**

In `CLAUDE.md`, find the line:
```
- `TODO.txt` - Task queue (use `/plum-todo-pop` and `/plum-todo-push`)
```

Replace with:
```
- Task queue managed via GitHub Issues (use `/plum-todo-pop` and `/plum-todo-push`)
```

**Step 2: Update design.md Project Structure**

In `design.md`, remove the `TODO.txt` line from the project structure tree:
```
├── TODO.txt                       # Task queue (/plum-todo-pop, /plum-todo-push)
```

Add the backup script to the scripts listing. In the `backup/` section description, add:
```
- `backup-issues.sh` — Export GitHub Issues to local JSON with size-based retention
```

Update the Skills section to reflect the new behavior:
- `/plum-todo-push` — "Create a new GitHub Issue with labels and priority"
- `/plum-todo-pop` — "Pick an open GitHub Issue and execute it"
- `/plum-churn` — "Dispatch all open GitHub Issues as parallel subagents in isolated worktrees"

**Step 3: Update MANUAL.md**

Update the Project Slash Commands table descriptions:
- `/plum-todo-pop` — "Picks an open GitHub Issue and executes it"
- `/plum-todo-push` — "Creates a new GitHub Issue with labels and priority"
- `/plum-churn` — "Dispatches all open GitHub Issues as parallel subagents in isolated worktrees"

**Step 4: Update workflow-subagents.md**

Find the `### TODO.txt` section and the single-writer rule references. Replace TODO.txt references with GitHub Issues:
- "Single-writer rule" becomes: "Only the orchestrator creates and closes issues"
- Remove "Other Claude panes should not independently pop tasks"
- Update the Quick Reference table: `TODO.txt | Orchestrator only` → `GitHub Issues | Orchestrator only`

**Step 5: Update .env.example**

Add at the end of `.env.example`:
```
# Issue Backup
BACKUP_MAX_SIZE_MB=50
```

(This may already be done in Task 4 — skip if so.)

**Step 6: Commit**

```bash
git add CLAUDE.md design.md MANUAL.md docs/workflow-subagents.md .env.example
git commit -m "docs: update all references from TODO.txt to GitHub Issues"
```

---

### Task 9: Delete migration script (cleanup)

**Files:**
- Delete: `scripts/common/migrate-todo-to-issues.sh`

**Step 1: Remove the one-time migration script**

```bash
git rm scripts/common/migrate-todo-to-issues.sh
git commit -m "chore: remove one-time TODO.txt migration script"
```

This script has served its purpose and shouldn't stay in the repo.
