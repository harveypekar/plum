# /plum-audit Design

**Created:** 2026-03-01
**Purpose:** Comprehensive project health audit with parallelizable subsections, producing a markdown report with findings and issue-creation commands

## Overview

A slash command (`/plum-audit`) that critically audits the entire Plum project across 6 categories. Produces a timestamped markdown report at `docs/audits/YYYY-MM-DD-audit.md`. Accepts an optional section argument to run a single category.

## Usage

```
/plum-audit              # run all 6 sections
/plum-audit security     # run just the security section
/plum-audit testing      # run just the testing section
```

Single-section runs produce `docs/audits/YYYY-MM-DD-<section>.md`.

## Decisions

- **Approach:** Single skill, serial execution, with `--section` flag for individual runs. Parallelism available by running multiple sessions.
- **Output:** Markdown file committed to `docs/audits/`. No automatic issue creation.
- **Issue creation:** Each recommendation includes a copy-pasteable `gh issue create` command with pre-filled title, labels, and body.
- **Claude metrics:** Queries the Claude service (`localhost:9270`) when available. Gracefully skips metrics if the service isn't running.

## Sections

### 1. `security` — Secrets, enforcement, exposure

- Scan all files for hardcoded secrets, API keys, tokens, passwords
- Verify `.env` is gitignored and `.env.example` has no real values
- Check all enforcement layers exist and work (pre-commit hook installed? Claude hooks registered? pre-push hook present?)
- Scan for plaintext `http://` URLs in scripts
- Verify `.key`/`.pem`/`secrets/`/`credentials/` patterns are in `.gitignore`
- Check file permissions on sensitive files

### 2. `quality` — Code health beyond pre-commit

- Run shellcheck on ALL `.sh` files (not just staged)
- Run ruff on ALL `.py` files
- Check scripts follow the template pattern (source logging.sh, source load-env.sh)
- Find dead code, unused files, empty directories with only `.gitkeep`
- Check commit message convention adherence in recent history
- Flag scripts missing `set -euo pipefail`

### 3. `docs` — Documentation accuracy

- Compare design.md project structure tree against actual filesystem
- Check if MANUAL.md skill/hook descriptions match actual skill files
- Check CLAUDE.md accuracy against current conventions
- Flag stale plans in `docs/plans/` (old plans for completed work)
- Check staging.md completeness (how many fields are still placeholder?)

### 4. `infra` — Infrastructure health

- Verify Docker builds successfully
- Check `.gitignore` for gaps (anything tracked that shouldn't be?)
- Verify all hooks are registered in `.claude/settings.local.json`
- Check git hooks are installed (`.git/hooks/pre-commit` exists and delegates correctly)
- Verify `gh` CLI is authenticated
- Check for stale worktrees or branches

### 5. `claude` — Skill/hook efficiency + usage metrics

- Validate all skill SKILL.md files have correct frontmatter (name, description)
- Check for redundancy between Claude hooks and git hooks (e.g., shellcheck in both lint-shell.sh and pre-commit)
- Verify hook scripts are executable and parse valid JSON output
- Check if any skills reference deleted files or outdated conventions (e.g., TODO.txt)
- Flag skills with overly broad or vague descriptions
- **Metrics (from Claude service at localhost:9270 when available):**
  - Most used tool calls by type
  - Workload distribution between subagents when dispatched
  - Efficiency comparison between agents (commits, files changed, time)
  - Skills invoked but rarely completing successfully
  - Patterns in user hook overrides/denials

### 6. `testing` — Coverage and consistency

- Map every script to its test file (or flag as untested)
- Check test files follow consistent patterns (use test-helpers.sh, same assertion style, same cleanup approach)
- Check naming conventions: `test-*.sh` matches what it tests
- Flag tests with hardcoded paths or values that should be parameterized

## Report Format

```markdown
# Plum Audit — YYYY-MM-DD

**Ran:** all sections | Generated at: YYYY-MM-DDTHH:MM:SS

## Summary

| Section | Findings | Critical | Warning | Info |
|---------|----------|----------|---------|------|
| security | 3 | 1 | 2 | 0 |
| quality | 5 | 0 | 3 | 2 |
| docs | 4 | 0 | 1 | 3 |
| infra | 2 | 0 | 0 | 2 |
| claude | 3 | 0 | 1 | 2 |
| testing | 4 | 0 | 2 | 2 |

## Security

### [CRITICAL] Finding title
Description...

### [WARNING] Finding title
Description...

## Quality
...

## Recommendations

### 1. [CRITICAL] Remove hardcoded token from scripts/deploy/foo.sh
**Section:** security | **Line:** 12

\`\`\`bash
gh issue create --title "Remove hardcoded token from deploy/foo.sh:12" --label "security" --label "P0-critical" --body "Found by plum-audit on YYYY-MM-DD."
\`\`\`

### 2. [WARNING] Add tests for backup-issues.sh
**Section:** testing

\`\`\`bash
gh issue create --title "Add tests for backup-issues.sh" --label "backup" --label "P2-normal" --body "Found by plum-audit on YYYY-MM-DD."
\`\`\`
```

Severity levels:
- **CRITICAL** — security risk or broken enforcement, maps to `P0-critical`
- **WARNING** — quality/consistency issue, maps to `P2-normal`
- **INFO** — observation or suggestion, maps to `P3-low`

## Skill Mechanics

- **Skill file:** `.claude/skills/plum-audit/SKILL.md`
- **Argument:** Optional section name (one of: `security`, `quality`, `docs`, `infra`, `claude`, `testing`)
- **Output:** `docs/audits/YYYY-MM-DD-audit.md` (full) or `docs/audits/YYYY-MM-DD-<section>.md` (single)
- **Each section** is a self-contained prompt block in SKILL.md — extractable to subagent prompts later
- **Claude metrics** depend on the Claude service (#13); section gracefully degrades without it

## File Locations

- Skill: `.claude/skills/plum-audit/SKILL.md`
- Reports: `docs/audits/YYYY-MM-DD-*.md`
