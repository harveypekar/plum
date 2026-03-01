# /plum-design-update Slash Command Design

**Created:** 2026-03-01
**Purpose:** Detect design.md drift by analyzing git history, then interactively propose updates

## Overview

A three-part system:
1. **Helper script** (`scripts/common/design-drift.sh`) — scans unchecked commits (since last `design-checked-*` tag), extracts structural + behavioral changes with diff hunks, outputs structured markdown
2. **Skill** (`.claude/skills/plum-design-update/SKILL.md`) — injects script output + design.md into Claude Code prompt, which then interactively proposes and applies changes
3. **Post-merge skill** (`.claude/skills/plum-postmortem/SKILL.md`) — auto-triggered after PR merge, runs the same analysis as `/plum-design-update`

## Helper Script: `scripts/common/design-drift.sh`

**Output format** (structured markdown to stdout):

```
## Commit History with Diffs
For each commit (oldest to newest):
- Hash, message, date
- Files changed (added/modified/deleted)
- Diff hunks (actual code changes)

## Current Project Tree
Filtered file listing of actual project state

## design.md Section Headers
List of sections for cross-referencing
```

**Implementation:**
- Finds the most recent `design-checked-*` git tag to determine starting point
- If no tag exists, scans all commits from the beginning
- Uses `git log --reverse --format` for commit metadata (only unchecked commits)
- Uses `git show --stat` and `git show` for diff hunks per commit
- Uses `find . -not -path './.git/*'` for current tree
- Uses `grep '^##' design.md` for section headers
- No external dependencies (bash + git only)

## Skill: `/plum-design-update`

**Location:** `.claude/skills/plum-design-update/SKILL.md`

**Flow:**
1. Run helper script via `!bash scripts/common/design-drift.sh`
2. Inject `!cat design.md` for current design doc
3. Claude Code compares drift report against each design.md section
4. Detects both structural drift (file tree, directories) and behavioral drift (workflows, tech stack, completed next-steps)
5. Presents each proposed change one-by-one:
   - Which section is affected
   - What the discrepancy is
   - The proposed edit
6. User accepts / rejects / modifies each change
7. Accepted changes applied via Edit tool
8. After all changes, offer to commit updated design.md
9. Summary of all changes made

## Commit Tagging

After a successful design update run:
- Tag the HEAD commit with `design-checked-<short-hash>` (lightweight git tag)
- Subsequent runs of the script only analyze commits after the most recent `design-checked-*` tag
- If no tag exists, all commits are analyzed (first run)

## Post-Merge Hook: `/plum-postmortem`

**Location:** `.claude/skills/plum-postmortem/SKILL.md`

**Behavior:**
- Intended to run after a PR is merged
- Executes the same analysis as `/plum-design-update`
- Same interactive accept/reject flow
- Same commit tagging after completion

## Detection Categories

- **Structural:** Files/dirs that exist but aren't in design.md tree, or listed in tree but don't exist
- **Tech stack:** New languages/tools used that aren't documented (e.g., Python)
- **Completed items:** Next-steps that have been done
- **Workflow changes:** New patterns (e.g., skills, slash commands) not reflected in design
- **Security/config:** New .env vars, gitignore patterns, permission rules
