# /plum-audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a `/plum-audit` skill that critically audits the Plum project across 6 categories, producing a markdown report with findings and `gh issue create` commands.

**Architecture:** A single SKILL.md with 6 self-contained section prompts. The skill parses an optional argument to run one section or all. Each section uses Bash tool calls for concrete checks (shellcheck, grep, file existence) and Claude analysis for subjective assessments (documentation accuracy, code patterns). Results are collected into a markdown report and written to `docs/audits/`.

**Tech Stack:** Claude Code skill (SKILL.md), Bash (shellcheck, ruff, grep, find), `gh` CLI, `curl` (for Claude service)

---

### Task 1: Create the `docs/audits/` directory

**Files:**
- Create: `docs/audits/.gitkeep`

**Step 1: Create the directory**

```bash
mkdir -p docs/audits
touch docs/audits/.gitkeep
```

**Step 2: Add to `.gitignore` — actually don't**

Audit reports should be committed (they're the historical record). No gitignore changes needed.

**Step 3: Commit**

```bash
git add docs/audits/.gitkeep
git commit -m "chore: add docs/audits/ directory for audit reports"
```

---

### Task 2: Create the `/plum-audit` skill

**Files:**
- Create: `.claude/skills/plum-audit/SKILL.md`

**Step 1: Write the skill file**

The skill is a single SKILL.md with:
1. Frontmatter (name, description)
2. Argument parsing instructions
3. Report scaffolding instructions
4. 6 section blocks, each self-contained with specific check instructions
5. Report finalization and commit instructions

Create `.claude/skills/plum-audit/SKILL.md` with the following content:

````markdown
---
name: plum-audit
description: Use when the user invokes /plum-audit to run a comprehensive project health audit across security, quality, docs, infra, claude, and testing sections
---

# Plum Audit

Critically audit the Plum project and produce a markdown report with findings and recommendations.

## Arguments

!`echo "ARGS: $ARGS"`

## Instructions

### Step 1: Parse arguments

Valid section names: `security`, `quality`, `docs`, `infra`, `claude`, `testing`

- If an argument was provided (e.g., `/plum-audit security`), run only that section
- If no argument or `all`, run all 6 sections in order
- If invalid argument, list valid sections and ask the user to pick

### Step 2: Set up the report

Determine the output file:
- All sections: `docs/audits/YYYY-MM-DD-audit.md`
- Single section: `docs/audits/YYYY-MM-DD-<section>.md`

Use today's date. If the file already exists, append a counter (e.g., `2026-03-01-audit-2.md`).

Initialize an in-memory report with the header:

```markdown
# Plum Audit — YYYY-MM-DD

**Ran:** <all | section-name> | **Generated at:** YYYY-MM-DDTHH:MM:SS
```

Initialize counters for each section: critical, warning, info.

### Step 3: Run sections

Run each requested section using the instructions below. For each finding, classify as CRITICAL, WARNING, or INFO.

After all sections complete, write the Summary table and Recommendations section.

### Step 4: Write the report

Write the complete report to the output file using the Write tool. Then offer to commit:

```bash
git add docs/audits/<filename>
git commit -m "docs: add plum-audit report YYYY-MM-DD"
```

---

## Section: security

Run these checks and report findings:

**1. Hardcoded secrets scan**
```bash
grep -rn --include='*.sh' --include='*.py' -iE '(api_key|api_secret|password|token|secret)\s*=' scripts/ services/ 2>/dev/null || true
```
Flag any matches that aren't reading from env vars (i.e., have actual values assigned). Severity: CRITICAL.

**2. .env safety**
```bash
# Check .env is gitignored
grep -q '^\.env$' .gitignore && echo "OK" || echo "MISSING"
# Check .env.example has no real values (values after = should be empty or placeholder)
grep -E '=.+' .env.example | grep -vE '=(|your-|example-|changeme|50)' || echo "OK"
```
Missing gitignore: CRITICAL. Real values in .env.example: CRITICAL.

**3. Enforcement layers**
```bash
# Pre-commit hook installed?
test -x .git/hooks/pre-commit && echo "OK" || echo "MISSING"
# Pre-commit delegates to scripts/common/pre-commit?
grep -q 'scripts/common/pre-commit' .git/hooks/pre-commit 2>/dev/null && echo "OK" || echo "WRONG"
# Pre-push hook?
test -x .git/hooks/pre-push && echo "OK" || echo "MISSING"
# Claude hooks registered?
jq '.hooks.PreToolUse' .claude/settings.local.json
jq '.hooks.PostToolUse' .claude/settings.local.json
```
Missing hooks: WARNING. Wrong delegation: WARNING.

**4. Plaintext HTTP**
```bash
grep -rn --include='*.sh' --include='*.py' 'http://' scripts/ services/ 2>/dev/null | grep -v 'https://' | grep -v '#' || true
```
Any matches: WARNING.

**5. Gitignore coverage**
```bash
for pattern in '.env' '*.key' '*.pem' 'secrets/' 'credentials/'; do
  grep -qF "$pattern" .gitignore && echo "OK: $pattern" || echo "MISSING: $pattern"
done
```
Missing patterns: WARNING.

**6. Sensitive file permissions**
```bash
# Check if any .env, .key, .pem files exist and are world-readable
find . -name '.env' -o -name '*.key' -o -name '*.pem' 2>/dev/null | while read f; do
  stat -c '%a %n' "$f"
done
```
World-readable sensitive files: WARNING.

---

## Section: quality

**1. Shellcheck all .sh files**
```bash
find scripts/ .claude/hooks/ -name '*.sh' -exec shellcheck {} \; 2>&1
```
Any errors: WARNING per file.

**2. Ruff all .py files**
```bash
find scripts/ -name '*.py' -exec ruff check {} \; 2>&1
```
Any errors: WARNING per file.

**3. Script template adherence**
For each `.sh` file in `scripts/deploy/`, `scripts/backup/`, `scripts/monitor/`:
```bash
for f in $(find scripts/deploy scripts/backup scripts/monitor -name '*.sh' 2>/dev/null); do
  echo "--- $f ---"
  grep -c 'source.*logging.sh' "$f" || echo "MISSING: logging.sh"
  grep -c 'source.*load-env.sh' "$f" || echo "MISSING: load-env.sh"
  grep -c 'set -.*e' "$f" || echo "MISSING: set -e"
done
```
Missing sourcing or error flags: WARNING.

**4. Dead files**
```bash
# Empty dirs with only .gitkeep that could have content
find scripts/ -name '.gitkeep' -exec dirname {} \; | while read d; do
  count=$(find "$d" -maxdepth 1 -not -name '.gitkeep' -not -name '.' | wc -l)
  echo "$d: $count files besides .gitkeep"
done
```
Directories with only .gitkeep that are expected to have scripts: INFO.

**5. Commit message conventions**
```bash
git log --oneline -20 | grep -vE '^[a-f0-9]+ (feat|fix|docs|chore|test|refactor|style|perf|ci):' || true
```
Non-conforming messages: INFO.

---

## Section: docs

**1. design.md structure tree vs reality**
```bash
# Get all tracked files
git ls-files | head -80
```
Read `design.md` and compare the Project Structure tree against the actual file listing. Flag files that exist but aren't in the tree, and tree entries that no longer exist. Severity: WARNING for missing entries, INFO for extras.

**2. MANUAL.md accuracy**
Read `MANUAL.md` and cross-reference:
- Each skill listed → does the SKILL.md exist with matching description?
- Each hook listed → is it registered in `.claude/settings.local.json`?
```bash
ls .claude/skills/*/SKILL.md
```
Mismatches: WARNING.

**3. CLAUDE.md accuracy**
Read `CLAUDE.md` and verify:
- Listed directories exist
- Referenced tools/commands are correct
- Conventions match actual practice
Inaccuracies: WARNING.

**4. Stale plans**
```bash
ls -la docs/plans/
```
Read each plan file's title. Check if the work described has been completed (look for corresponding commits, files, or closed issues). Completed plans with no further use: INFO.

**5. staging.md completeness**
```bash
grep -c '\[.*\]' docs/staging.md
```
Count placeholder brackets. Report percentage filled. Many placeholders: WARNING.

---

## Section: infra

**1. Docker build**
```bash
docker-compose -f docker/docker-compose.local.yml build 2>&1 | tail -5
```
Build failure: CRITICAL. Build warnings: INFO.

**2. Gitignore gaps**
```bash
# Files that might shouldn't be tracked
git ls-files | grep -iE '(\.log|\.pid|\.env\.|node_modules|__pycache__|\.pyc)' || echo "OK"
```
Tracked files that look like they should be ignored: WARNING.

**3. Claude hooks registration**
```bash
# List all hook scripts on disk
ls .claude/hooks/*.sh
# Compare against what's registered
jq -r '.hooks | to_entries[] | .value[] | .hooks[] | .command' .claude/settings.local.json
```
Hook scripts on disk but not registered (or vice versa): WARNING.

**4. Git hooks installed**
```bash
ls -la .git/hooks/pre-commit .git/hooks/pre-push 2>&1
cat .git/hooks/pre-commit 2>/dev/null
```
Missing or wrong: WARNING.

**5. gh CLI**
```bash
gh auth status 2>&1
```
Not authenticated: WARNING.

**6. Stale worktrees and branches**
```bash
git worktree list
git branch --list | grep -v '^\*'
git branch -vv | grep ': gone]' || echo "No gone branches"
```
Stale worktrees or gone branches: INFO.

---

## Section: claude

**1. Skill frontmatter validation**
```bash
for skill in .claude/skills/*/SKILL.md; do
  echo "--- $skill ---"
  head -5 "$skill"
done
```
Check each has `name:` and `description:` in frontmatter. Missing frontmatter: WARNING.

**2. Hook/git redundancy**
Read `.claude/hooks/lint-shell.sh` and `scripts/common/pre-commit`. Identify checks that run in both (e.g., shellcheck). Redundancy isn't necessarily bad but should be documented. Severity: INFO.

**3. Hook executability and output**
```bash
for hook in .claude/hooks/*.sh; do
  echo "--- $hook ---"
  test -x "$hook" && echo "executable: yes" || echo "executable: NO"
  # Check it handles empty input gracefully
  echo '{}' | bash "$hook" 2>&1 | head -3
done
```
Non-executable hooks: WARNING. Hooks that crash on empty input: WARNING.

**4. Stale references in skills**
```bash
grep -rn 'TODO\.txt' .claude/skills/ || echo "No TODO.txt references"
grep -rn 'claude-manual\.md' .claude/skills/ || echo "No old manual references"
```
References to deleted/renamed files: WARNING.

**5. Skill description quality**
Read each skill's description field. Flag descriptions that are too vague (less than 10 words) or don't mention the trigger condition. Severity: INFO.

**6. Claude service metrics (optional)**
```bash
curl -sf http://localhost:9270/health 2>/dev/null
```
If the service is running, query usage endpoints and report:
- Recent session token counts
- Any rate limit warnings
If not running, report: INFO — "Claude service not running, metrics unavailable."

---

## Section: testing

**1. Coverage map**
```bash
# List all scripts that should have tests
find scripts/deploy scripts/backup scripts/monitor scripts/common -name '*.sh' -not -name 'test-*' 2>/dev/null
# List all test files
find scripts/test -name 'test-*.sh' 2>/dev/null
```
Build a mapping: script → test file. Flag scripts with no corresponding test. Severity: WARNING for operational scripts, INFO for utilities.

**2. Test consistency**
Read each test file in `scripts/test/`. Check:
- Does it source `test-helpers.sh`?
- Does it use the standard assertion functions (`assert_eq`, `assert_contains`, etc.)?
- Does it have a cleanup trap?
- Does it use `print_header` / `print_step` formatting?
```bash
for t in scripts/test/test-*.sh; do
  echo "--- $t ---"
  grep -c 'source.*test-helpers' "$t" || echo "MISSING: test-helpers"
  grep -c 'trap.*cleanup' "$t" || echo "MISSING: cleanup trap"
  grep -c 'assert_' "$t" || echo "MISSING: assertions"
done
```
Inconsistencies: WARNING.

**3. Naming conventions**
```bash
ls scripts/test/
```
Check that test files follow `test-<thing-being-tested>.sh` pattern and the runner is `run-*.sh`. Odd names: INFO.

**4. Hardcoded values**
```bash
grep -n '/mnt/d/prg/plum' scripts/test/*.sh || echo "OK"
grep -n 'localhost' scripts/test/*.sh || echo "OK"
```
Hardcoded absolute paths or hosts: WARNING.

---

## Report finalization

After all sections complete:

1. Build the Summary table with counts per section
2. Collect all CRITICAL and WARNING findings into the Recommendations section
3. For each recommendation, generate a `gh issue create` command:
   - CRITICAL → `--label "security" --label "P0-critical"` (or appropriate category)
   - WARNING → `--label "<category>" --label "P2-normal"`
   - INFO findings are NOT included in recommendations (report-only)
4. Write the full report to the output file
5. Offer to commit
````

**Step 2: Commit**

```bash
git add .claude/skills/plum-audit/SKILL.md
git commit -m "feat: add /plum-audit skill for comprehensive project health audits"
```

---

### Task 3: Update MANUAL.md

**Files:**
- Modify: `MANUAL.md`

**Step 1: Add /plum-audit to the Project Slash Commands table**

Find the table in MANUAL.md and add a row after `/plum-churn`:

```
| `/plum-audit [section]` | Runs comprehensive project health audit (security, quality, docs, infra, claude, testing) |
```

**Step 2: Commit**

```bash
git add MANUAL.md
git commit -m "docs: add /plum-audit to MANUAL.md"
```

---

### Task 4: Update design.md

**Files:**
- Modify: `design.md`

**Step 1: Add /plum-audit to the Skills section**

In the `### Skills (Slash Commands)` section, add after the `/plum-churn` line:

```
- `/plum-audit [section]` — Comprehensive project health audit across 6 categories
```

**Step 2: Add plum-audit to the project structure tree**

In the `.claude/skills/` section of the tree, add:

```
│       ├── plum-audit/            # /plum-audit
```

**Step 3: Commit**

```bash
git add design.md
git commit -m "docs: add /plum-audit to design.md"
```

---

### Task 5: Smoke test

**Step 1: Run a single section**

Invoke `/plum-audit security` and verify:
- It produces a report at `docs/audits/YYYY-MM-DD-security.md`
- Findings have severity tags
- Recommendations include `gh issue create` commands
- The report is well-formatted markdown

**Step 2: Review and fix**

If any section instructions are unclear or produce bad output, edit the SKILL.md to fix.

**Step 3: Commit any fixes**

```bash
git add .claude/skills/plum-audit/SKILL.md
git commit -m "fix: refine plum-audit skill instructions"
```
