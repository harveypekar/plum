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

As background agents complete, collect their results. After ALL agents have finished:

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
