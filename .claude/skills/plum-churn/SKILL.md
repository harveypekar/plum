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
