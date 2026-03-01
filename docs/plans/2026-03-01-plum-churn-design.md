# /plum-churn Design

**Created:** 2026-03-01
**Purpose:** Dispatch all TODO.txt items as parallel subagents in isolated worktrees, with hard enforcement preventing merges/pushes

## Overview

A Claude Code skill that reads TODO.txt, dispatches one subagent per task in an isolated git worktree, and reports results. Subagents commit on their own branches but cannot merge to main, push, or create PRs. The user reviews branches manually.

## Flow

1. Read TODO.txt (injected via `!cat TODO.txt`)
2. Resolve current commit hash — pin to `$CHECKED_HASH` (never use HEAD directly)
3. For each line, dispatch an Agent tool call with:
   - `subagent_type: "general-purpose"`
   - `isolation: "worktree"`
   - `run_in_background: true`
   - Prompt containing: task ID, task text, CLAUDE.md reference, commit conventions
4. Remove all dispatched tasks from TODO.txt
5. Wait for all agents to complete (background notifications)
6. Report results: task ID, branch name, success/failure status

## Subagent Prompt

Each subagent receives:
- Task ID and description
- Instruction to read CLAUDE.md for project conventions
- Commit message format: `feat(<task-id>): <description>` (or `docs(...)` for research tasks)
- For research tasks: write findings to `docs/<task-id>-<slug>.md` and commit
- For implementation tasks: write code and commit
- **Hard rule: do NOT merge to main, do NOT push, do NOT create PRs**

## Enforcement

Two layers prevent subagents from touching main or pushing:

### Git pre-push hook (`.git/hooks/pre-push`)
- Detects if the push originates from inside `.claude/worktrees/`
- If yes, blocks with message: "Push blocked: worktree branches must be reviewed before pushing"
- Normal pushes from main working directory are unaffected

### Claude Code PreToolUse hook (`.claude/hooks/block-worktree-danger.sh`)
- Fires on Bash tool calls
- If current working directory is inside `.claude/worktrees/`, inspects command for:
  - `git merge`
  - `git checkout main` / `git checkout master`
  - `gh pr create`
  - `git push`
- Denies with explanation if matched
- No effect outside worktrees

## What It Does NOT Do

- No merging — branches sit for user review
- No pushing — stays local
- No PR creation — user decides when/if to PR
- No batching — all tasks dispatched at once
- No retry logic — failed tasks are reported, user re-queues if needed

## Task Type Handling

Both research/investigation and implementation tasks are dispatched:
- **Implementation tasks** (e.g., "write scripts/monitor/claude-usage.sh"): subagent writes code, commits
- **Research tasks** (e.g., "investigate if X is stupid"): subagent writes findings to a doc, commits

## File Locations

- Skill: `.claude/skills/plum-churn/SKILL.md`
- Worktree guard hook: `.claude/hooks/block-worktree-danger.sh`
- Git pre-push hook: `.git/hooks/pre-push` (append to existing if present)
