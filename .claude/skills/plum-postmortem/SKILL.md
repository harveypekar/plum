---
name: plum-postmortem
description: Use after merging a PR to check if design.md and MANUAL.md need updating. Runs drift analysis against recent changes.
---

# Post-Merge Design Postmortem

A PR was just merged. Let's check if design.md and MANUAL.md need updating.

## Drift Report

!`bash scripts/common/design-drift.sh`

## Current design.md

!`cat design.md`

## Current MANUAL.md

!`cat MANUAL.md`

## Instructions

**Before starting**, resolve the current commit hash:
```bash
CHECKED_HASH=$(git rev-parse HEAD)
CHECKED_SHORT=$(git rev-parse --short HEAD)
```
Use `$CHECKED_HASH` / `$CHECKED_SHORT` everywhere below — never use HEAD directly, as it may shift if a commit is made during the process.

A PR was just merged. Using the drift report and current files above:

### Phase 1: design.md

Follow the same process as /plum-design-update:

1. Scan for structural drift, tech stack drift, completed next-steps, workflow changes, and security/config drift
2. For each discrepancy: state the section, explain the issue, show proposed edit, ask accept/reject/modify
3. Apply accepted changes with the Edit tool

### Phase 2: MANUAL.md

Check MANUAL.md for drift from current project state:

1. Scan for outdated hook descriptions, missing/removed slash commands, changed tool requirements, and stale tips
2. For each discrepancy: state the section, explain the issue, show proposed edit, ask accept/reject/modify
3. Apply accepted changes with the Edit tool

### Finish

After all changes: summarize, offer to commit, tag the resolved commit with `git tag design-checked-$CHECKED_SHORT $CHECKED_HASH`

If no discrepancies found in either file, report that both are in sync and tag the resolved commit: `git tag design-checked-$CHECKED_SHORT $CHECKED_HASH`
