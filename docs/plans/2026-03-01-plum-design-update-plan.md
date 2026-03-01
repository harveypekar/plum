# /plum-design-update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a slash command that detects design.md drift by scanning git commit history and interactively proposing updates.

**Architecture:** A helper bash script (`scripts/common/design-drift.sh`) scans unchecked commits and outputs a structured markdown drift report. Two Claude Code skills consume this output: `/plum-design-update` (manual) and `/plum-postmortem` (post-merge). Git tags track which commits have been analyzed.

**Tech Stack:** Bash, Git, Claude Code skills (SKILL.md with `!` command injection)

---

### Task 1: Create the design-drift helper script

**Files:**
- Create: `scripts/common/design-drift.sh`

**Step 1: Write the script**

```bash
#!/bin/bash
# Design Drift Detector for Plum
# Scans git commits since last design-checked-* tag and outputs
# a structured markdown report of all changes.
#
# Usage: bash scripts/common/design-drift.sh
# Output: Structured markdown to stdout

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# --- Find starting point ---
# Look for the most recent design-checked-* tag
LAST_TAG=$(git tag --list 'design-checked-*' --sort=-creatordate | head -1)

if [ -n "$LAST_TAG" ]; then
    SINCE_REF="$LAST_TAG"
    echo "## Design Drift Report"
    echo ""
    echo "**Analyzing commits since:** \`$LAST_TAG\`"
else
    SINCE_REF=""
    echo "## Design Drift Report"
    echo ""
    echo "**Analyzing:** all commits (no previous design-checked tag found)"
fi
echo ""

# --- Commit History with Diffs ---
echo "## Commit History with Diffs"
echo ""

if [ -n "$SINCE_REF" ]; then
    COMMITS=$(git log --reverse --format="%H" "$SINCE_REF"..HEAD)
else
    COMMITS=$(git log --reverse --format="%H")
fi

if [ -z "$COMMITS" ]; then
    echo "_No new commits to analyze._"
    echo ""
else
    while IFS= read -r hash; do
        short=$(git log -1 --format="%h" "$hash")
        msg=$(git log -1 --format="%s" "$hash")
        date=$(git log -1 --format="%ai" "$hash")

        echo "### Commit \`$short\`: $msg"
        echo "**Date:** $date"
        echo ""

        # Files changed
        echo "**Files changed:**"
        echo '```'
        git show --stat --format="" "$hash"
        echo '```'
        echo ""

        # Diff hunks
        echo "**Diff:**"
        echo '```diff'
        git show --format="" "$hash"
        echo '```'
        echo ""
    done <<< "$COMMITS"
fi

# --- Current Project Tree ---
echo "## Current Project Tree"
echo ""
echo '```'
find . -not -path './.git/*' -not -path './logs/*' -not -path './node_modules/*' -not -path './.env' -not -name '*.pyc' | sort
echo '```'
echo ""

# --- design.md Section Headers ---
echo "## design.md Section Headers"
echo ""
if [ -f "$REPO_ROOT/design.md" ]; then
    grep -n '^#' "$REPO_ROOT/design.md" | while IFS= read -r line; do
        echo "- $line"
    done
else
    echo "_design.md not found!_"
fi
echo ""
```

**Step 2: Make it executable**

Run: `chmod +x scripts/common/design-drift.sh`

**Step 3: Test the script**

Run: `bash scripts/common/design-drift.sh | head -80`
Expected: Structured markdown output with commit history, diffs, project tree, and design.md section headers. All commits should appear since no `design-checked-*` tag exists yet.

**Step 4: Commit**

```bash
git add scripts/common/design-drift.sh
git commit -m "feat: add design drift detection helper script"
```

---

### Task 2: Create the /plum-design-update skill

**Files:**
- Create: `.claude/skills/plum-design-update/SKILL.md`

**Reference:** Existing skill pattern in `.claude/skills/plum-todo-pop/SKILL.md` — uses `!` syntax for command injection.

**Step 1: Write the skill file**

```markdown
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

After processing all discrepancies:
1. Show a summary of all changes made
2. Ask if the user wants to commit the updated design.md
3. If yes, commit with message: `docs: update design.md to match current project state`
4. Tag the current HEAD commit: `git tag design-checked-$(git rev-parse --short HEAD)`
5. Confirm the tag was created so future runs skip these commits

If NO discrepancies are found:
1. Report that design.md is in sync
2. Still tag the HEAD commit so these commits are skipped next time
```

**Step 2: Verify the skill directory and file exist**

Run: `ls -la .claude/skills/plum-design-update/SKILL.md`
Expected: File exists with correct content.

**Step 3: Test the skill triggers**

Run: Invoke `/plum-design-update` in a Claude Code session. It should produce the drift report and start proposing changes interactively.

**Step 4: Commit**

```bash
git add .claude/skills/plum-design-update/SKILL.md
git commit -m "feat: add /plum-design-update slash command skill"
```

---

### Task 3: Create the /plum-postmortem skill

**Files:**
- Create: `.claude/skills/plum-postmortem/SKILL.md`

**Step 1: Write the skill file**

This is a thin wrapper that runs the same analysis as `/plum-design-update`, framed as a post-merge activity.

```markdown
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
```

**Step 2: Commit**

```bash
git add .claude/skills/plum-postmortem/SKILL.md
git commit -m "feat: add /plum-postmortem post-merge design check skill"
```

---

### Task 4: End-to-end test

**Step 1: Run the full flow**

Run `/plum-design-update` in Claude Code. Verify:
- The drift report is generated (should show all commits since no tag exists)
- design.md discrepancies are identified (e.g., project tree is outdated, Python not in tech stack, completed next-steps)
- Interactive accept/reject works
- Changes are applied correctly
- Commit and tag are offered

**Step 2: Verify tagging works**

After running, check:
Run: `git tag --list 'design-checked-*'`
Expected: One tag like `design-checked-397cb0a`

**Step 3: Verify incremental behavior**

Make a trivial change, commit it, then run `/plum-design-update` again.
Expected: Only the new commit appears in the drift report, not all previous commits.
