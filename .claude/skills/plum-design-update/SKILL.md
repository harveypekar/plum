---
name: plum-design-update
description: Use when the user invokes /plum-design-update to detect design.md drift from git history and interactively propose updates
---

# Design Update

Detect how design.md has drifted from reality by analyzing git commits, then interactively propose and apply fixes.

## Drift Report (commits since last design-checked tag)

!`bash scripts/common/design-drift.sh`

## Current design.md

!`cat design.md`

## Instructions

You have the drift report above (commit history with diffs, current project tree, design.md section headers) and the current design.md contents.

**Your job: find every way design.md is out of sync with reality and propose fixes.**

### Detection categories

Scan for ALL of these:
1. **Structural drift** — files/dirs in the project tree that aren't in design.md's tree diagram, or listed in design.md but don't actually exist
2. **Tech stack drift** — languages, tools, or dependencies used in commits but not documented in design.md
3. **Completed next-steps** — items in the "Next Steps" section that have been done (based on commit evidence)
4. **Workflow changes** — new patterns, skills, slash commands, hooks, or processes not reflected in design.md
5. **Security/config drift** — new .env vars, gitignore patterns, or permission rules not documented

### Process

For each discrepancy found:
1. State which **section** of design.md is affected
2. Explain the **discrepancy** (what design.md says vs what's actually true)
3. Show the **proposed edit** (the exact text change)
4. Ask the user: **accept / reject / modify?**
5. If accepted, apply the change using the Edit tool

**Before starting**, resolve the current commit hash:
```bash
CHECKED_HASH=$(git rev-parse HEAD)
CHECKED_SHORT=$(git rev-parse --short HEAD)
```
Use `$CHECKED_HASH` / `$CHECKED_SHORT` everywhere below — never use HEAD directly, as it may shift if a commit is made during the process.

After processing all discrepancies:
1. Show a summary of all changes made
2. Ask if the user wants to commit the updated design.md
3. If yes, commit with message: `docs: update design.md to match current project state`
4. Tag the resolved commit: `git tag design-checked-$CHECKED_SHORT $CHECKED_HASH`
5. Confirm the tag was created so future runs skip these commits

If NO discrepancies are found:
1. Report that design.md is in sync
2. Still tag the resolved commit so these commits are skipped next time: `git tag design-checked-$CHECKED_SHORT $CHECKED_HASH`
