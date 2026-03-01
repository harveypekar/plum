---
name: plum-postmortem
description: Use after merging a PR to check if design.md needs updating. Runs the same drift analysis as /plum-design-update.
---

# Post-Merge Design Postmortem

A PR was just merged. Let's check if design.md needs updating.

## Drift Report

!`bash scripts/common/design-drift.sh`

## Current design.md

!`cat design.md`

## Instructions

A PR was just merged. Using the drift report and current design.md above, follow the same process as /plum-design-update:

1. Scan for structural drift, tech stack drift, completed next-steps, workflow changes, and security/config drift
2. For each discrepancy: state the section, explain the issue, show proposed edit, ask accept/reject/modify
3. Apply accepted changes with the Edit tool
4. After all changes: summarize, offer to commit, tag HEAD with `design-checked-$(git rev-parse --short HEAD)`

If no discrepancies found, report that design.md is in sync and tag HEAD.
