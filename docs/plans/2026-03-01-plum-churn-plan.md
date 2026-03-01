# /plum-churn Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a `/plum-churn` skill that dispatches all TODO.txt items as parallel subagents in isolated worktrees, with hard enforcement preventing merges/pushes.

**Architecture:** A SKILL.md reads TODO.txt, dispatches one background Agent per task with `isolation: "worktree"`, clears TODO.txt, waits for results, and lists branches. Two enforcement layers (git pre-push hook + Claude Code PreToolUse hook) prevent subagents from pushing or merging.

**Tech Stack:** Claude Code skills (SKILL.md), Bash (hooks), Git hooks, jq

---

### Task 1: Create the worktree guard Claude Code hook

**Files:**
- Create: `.claude/hooks/block-worktree-danger.sh`
- Modify: `.claude/settings.local.json`

**Step 1: Write the hook script**

Create `.claude/hooks/block-worktree-danger.sh`:

```bash
#!/bin/bash
# PreToolUse hook: block dangerous git commands inside worktrees
input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# Only care about Bash tool calls with a command
if [[ -z "$command" ]]; then
  exit 0
fi

# Check if we're inside a worktree
cwd=$(pwd)
if [[ "$cwd" != */.claude/worktrees/* ]]; then
  exit 0
fi

# Block dangerous commands
if echo "$command" | grep -qE '(git\s+push|git\s+merge|git\s+checkout\s+(main|master)|gh\s+pr\s+create)'; then
  reason=$(echo "$command" | grep -oE '(git\s+push|git\s+merge|git\s+checkout\s+(main|master)|gh\s+pr\s+create)' | head -1)
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: '${reason}' is not allowed inside a worktree. Commit your work on this branch — the user will review and merge manually."
  }
}
EOF
  exit 0
fi
```

**Step 2: Register the hook in settings.local.json**

Add a new entry to the `PreToolUse` array in `.claude/settings.local.json`:

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": ".claude/hooks/block-worktree-danger.sh"
    }
  ]
}
```

This goes alongside the existing `Edit|Write` matcher for `block-env.sh`.

**Step 3: Make the script executable**

Run: `chmod +x .claude/hooks/block-worktree-danger.sh`

**Step 4: Commit**

```bash
git add .claude/hooks/block-worktree-danger.sh .claude/settings.local.json
git commit -m "feat: add worktree guard hook to block push/merge/PR in worktrees"
```

---

### Task 2: Create the git pre-push hook

**Files:**
- Create: `.git/hooks/pre-push`

**Step 1: Write the pre-push hook**

Create `.git/hooks/pre-push`:

```bash
#!/bin/bash
# Pre-push hook: block pushes originating from worktree directories

cwd=$(pwd)
if [[ "$cwd" == */.claude/worktrees/* ]]; then
  echo "BLOCKED: Push not allowed from worktree directory."
  echo "Worktree branches must be reviewed before pushing."
  echo "Review the branch, then push from the main working directory."
  exit 1
fi

exit 0
```

**Step 2: Make it executable**

Run: `chmod +x .git/hooks/pre-push`

**Step 3: Verify it doesn't interfere with normal pushes**

Run from the main working directory: `git push --dry-run`
Expected: Should succeed (or fail for unrelated reasons, not "BLOCKED").

Note: `.git/hooks/pre-push` is not tracked by git (it's inside `.git/`), so no commit needed. Document its existence in MANUAL.md or CLAUDE.md.

---

### Task 3: Add `.claude/worktrees/` to `.gitignore`

**Files:**
- Modify: `.gitignore`

**Step 1: Add the entry**

Append to `.gitignore`:

```
# Claude Code worktrees (subagent isolation)
.claude/worktrees/
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .claude/worktrees/ to gitignore"
```

---

### Task 4: Create the /plum-churn skill

**Files:**
- Create: `.claude/skills/plum-churn/SKILL.md`

**Step 1: Write the skill**

Create `.claude/skills/plum-churn/SKILL.md`:

````markdown
---
name: plum-churn
description: Use when the user invokes /plum-churn to dispatch all TODO.txt items as parallel subagents in isolated worktrees
---

# Churn

Dispatch every task in TODO.txt as a parallel subagent in an isolated worktree.

## Current TODO.txt

!`cat TODO.txt`

## Instructions

**Before starting**, resolve the current commit hash:
```bash
CHECKED_HASH=$(git rev-parse HEAD)
CHECKED_SHORT=$(git rev-parse --short HEAD)
```

### Step 1: Parse tasks

Each line of TODO.txt has format `<id> <task text>`. Parse all lines into a list of (id, text) pairs. If TODO.txt is empty, tell the user there's nothing to churn.

### Step 2: Dispatch subagents

For **each** task, dispatch an Agent tool call with these parameters:
- `subagent_type: "general-purpose"`
- `isolation: "worktree"`
- `run_in_background: true`
- `description: "<task-id>: <first 3 words>"`

Use this prompt template for each subagent (fill in `{TASK_ID}` and `{TASK_TEXT}`):

```
You are working on task {TASK_ID}: {TASK_TEXT}

Read CLAUDE.md first for project conventions.

Rules:
- You are in an isolated worktree. Work ONLY on this branch.
- Do NOT run: git push, git merge, gh pr create, git checkout main/master
- These commands are blocked by hooks and will fail.

If this is a research/investigation task:
- Write your findings to docs/{TASK_ID}-findings.md
- Commit with: docs({TASK_ID}): <summary>

If this is an implementation task:
- Write the code, following CLAUDE.md conventions
- Commit with: feat({TASK_ID}): <summary>

Make small, focused commits. When done, your branch will be reviewed manually.
```

Dispatch ALL agents in a single message (one tool call per task, all in parallel).

### Step 3: Clear TODO.txt

After dispatching, remove all dispatched task lines from TODO.txt using the Edit tool. If all lines were dispatched, replace the file contents with an empty string.

### Step 4: Wait and report

As background agents complete, collect their results. After ALL agents have finished, present a summary:

```
## Churn Results

| Task ID | Description | Status | Branch |
|---------|-------------|--------|--------|
| abcdef  | Fix the ... | done   | worktree-abcdef |
| ghijkl  | Add the ... | failed | worktree-ghijkl |

Branches are local. Review with:
  git log worktree-<name> --oneline
  git diff main..worktree-<name>
```
````

**Step 2: Commit**

```bash
git add .claude/skills/plum-churn/SKILL.md
git commit -m "feat: add /plum-churn skill for parallel TODO dispatch"
```

---

### Task 5: Update MANUAL.md and design.md

**Files:**
- Modify: `MANUAL.md` — add `/plum-churn` to the project slash commands table
- Modify: `design.md` — add `/plum-churn` to the Skills list in Claude Code Integration section

**Step 1: Add to MANUAL.md**

Add a row to the project slash commands table:

```
| `/plum-churn` | Dispatches all TODO.txt items as parallel subagents in isolated worktrees |
```

**Step 2: Add to design.md**

In the `### Skills (Slash Commands)` section, add:

```
- `/plum-churn` — Dispatch all TODO.txt items as parallel subagents in isolated worktrees
```

Also add `/plum-churn` to the project structure tree under `.claude/skills/`.

**Step 3: Commit**

```bash
git add MANUAL.md design.md
git commit -m "docs: add /plum-churn to MANUAL.md and design.md"
```
