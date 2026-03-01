---
name: plum-audit
description: Use when the user invokes /plum-audit to run a comprehensive project health audit covering security, quality, docs, infra, claude, and testing sections
---

# Project Health Audit

Run a comprehensive health audit of the Plum project. Checks six areas: security (secrets/enforcement/exposure), quality (code health beyond pre-commit), docs (documentation accuracy), infra (infrastructure health), claude (skill/hook efficiency), and testing (coverage and consistency).

## Current project state

!`git log --oneline -5`

## Instructions

### Argument parsing

The user may provide an optional argument after `/plum-audit`:

- **No argument** or **`all`**: run all six sections
- **A section name** (`security`, `quality`, `docs`, `infra`, `claude`, `testing`): run only that section

If the argument doesn't match any valid section name, list the valid options and ask the user to pick one.

### Setup

Determine today's date and the output file path:
```bash
AUDIT_DATE=$(date +%Y-%m-%d)
```

- If running **all** sections: output to `docs/audits/${AUDIT_DATE}-audit.md`
- If running a **single** section: output to `docs/audits/${AUDIT_DATE}-<section>.md`

If the output file already exists, append a counter (e.g., `2026-03-01-audit-2.md`) to avoid overwriting a previous run.

Create the `docs/audits/` directory if it doesn't exist:
```bash
mkdir -p docs/audits
```

Initialize counters for CRITICAL, WARNING, and INFO findings across all sections. Track every finding as a tuple of (severity, section, description) for the summary table and recommendations.

---

## Section: security — Secrets, enforcement, exposure

### Check 1: Hardcoded secrets scan

Scan all tracked files for hardcoded secrets, API keys, tokens, and passwords:
```bash
git ls-files | xargs -d '\n' grep -inE '(api[_-]?key|secret[_-]?key|password|token|bearer)\s*[:=]\s*["\x27][^"\x27]{8,}' -- 2>/dev/null || true
```
Exclude `.env.example` lines that have empty values. Flag any match as [CRITICAL].

### Check 2: .env gitignored and .env.example clean

```bash
git check-ignore .env
```
If `.env` is NOT gitignored, flag as [CRITICAL].

Check `.env.example` for non-empty values:
```bash
grep -vE '^\s*#|^\s*$' .env.example 2>/dev/null | grep -E '=.+' | grep -vE '=\s*$|=your-|=example-|=changeme|=placeholder|=path/to' || true
```
Any line with a real-looking value (not just `=` or `=""`) is [CRITICAL].

### Check 3: Enforcement layers

Check pre-commit hook is installed:
```bash
test -f .git/hooks/pre-commit && echo "pre-commit hook: installed" || echo "pre-commit hook: MISSING"
```
Missing pre-commit hook is [CRITICAL].

Check Claude hooks are registered in `.claude/settings.local.json`:
```bash
jq '.hooks' .claude/settings.local.json 2>/dev/null
```
If hooks section is missing or empty, flag as [WARNING].

Check pre-push hook:
```bash
test -f .git/hooks/pre-push && echo "pre-push hook: installed" || echo "pre-push hook: not installed"
```
Missing pre-push hook is [INFO].

### Check 4: Plaintext HTTP URLs in scripts

```bash
grep -rnE 'http://' scripts/ --include='*.sh' --include='*.py' 2>/dev/null | grep -v 'localhost\|127\.0\.0\.1\|0\.0\.0\.0' || true
```
Any match is [WARNING].

### Check 5: Sensitive file patterns in .gitignore

Check that `.gitignore` covers sensitive patterns:
```bash
for pattern in '*.key' '*.pem' '*.p12' 'secrets/' 'credentials/' '.env'; do
  grep -qF "$pattern" .gitignore && echo "COVERED: $pattern" || echo "MISSING: $pattern"
done
```
Any missing pattern is [WARNING].

### Check 6: Sensitive file permissions

```bash
find . -name '*.key' -o -name '*.pem' -o -name '*.env' 2>/dev/null | while read f; do
  stat -c '%a %n' "$f" 2>/dev/null || stat -f '%Lp %N' "$f" 2>/dev/null
done
```
Files with permissions more open than 600 are [WARNING].

---

## Section: quality — Code health beyond pre-commit

### Check 1: Shellcheck on all .sh files

```bash
find . -name '*.sh' -not -path './.git/*' -not -path './node_modules/*' | sort | while read f; do
  shellcheck "$f" 2>&1 || true
done
```
Any error is [WARNING]. Any SC error in scripts/ directory with severity "error" is [CRITICAL].

### Check 2: Ruff on all .py files

```bash
find . -name '*.py' -not -path './.git/*' -not -path './node_modules/*' -not -path './.venv/*' | sort | while read f; do
  ruff check "$f" 2>&1 || true
done
```
Any finding is [WARNING].

### Check 3: Template pattern adherence

Check that scripts in `scripts/` source logging.sh and load-env.sh:
```bash
for f in $(find scripts/ -name '*.sh' -not -path 'scripts/common/*' -not -name 'test-*'); do
  echo "--- $f ---"
  grep -l 'source.*logging.sh' "$f" >/dev/null 2>&1 || echo "  MISSING: source logging.sh"
  grep -l 'source.*load-env.sh' "$f" >/dev/null 2>&1 || echo "  MISSING: source load-env.sh"
done
```
Missing sourcing is [WARNING].

### Check 4: Dead code and unused files

Look for empty `.gitkeep`-only directories:
```bash
find . -name '.gitkeep' -not -path './.git/*' | while read f; do
  dir=$(dirname "$f")
  count=$(ls -A "$dir" | wc -l)
  if [ "$count" -eq 1 ]; then
    echo "Empty dir (gitkeep only): $dir"
  fi
done
```
Flag as [INFO].

Look for scripts not referenced anywhere else:
```bash
git ls-files scripts/ | while read f; do
  base=$(basename "$f")
  refs=$(git ls-files | xargs -d '\n' grep -l "$base" 2>/dev/null | grep -v "$f" | head -1)
  if [ -z "$refs" ]; then
    echo "Possibly unreferenced: $f"
  fi
done
```
Flag as [INFO] — these need human review.

### Check 5: Commit message conventions

```bash
git log --oneline -20 | grep -vE '^[a-f0-9]+ (feat|fix|docs|chore|refactor|test|ci|style|perf)\(?.*\)?:' || true
```
Non-conforming messages are [INFO].

### Check 6: Missing set -euo pipefail

```bash
for f in $(find scripts/ -name '*.sh' -not -path 'scripts/common/script-template.sh'); do
  head -5 "$f" | grep -q 'set -euo pipefail\|set -e' || echo "Missing set -e: $f"
done
```
Missing safety flags are [WARNING].

---

## Section: docs — Documentation accuracy

### Check 1: design.md project structure vs actual filesystem

```bash
git ls-files | head -200
```
Compare the directory tree listed in `design.md` against actual `git ls-files` output. Flag directories in design.md that don't exist as [WARNING]. Flag significant directories on disk not mentioned in design.md as [INFO].

Read `design.md` with the Read tool and compare.

### Check 2: MANUAL.md skill/hook descriptions

Read `MANUAL.md` with the Read tool. Cross-reference:
```bash
ls .claude/skills/*/SKILL.md 2>/dev/null
ls .claude/hooks/* 2>/dev/null
```
Skills or hooks mentioned in MANUAL.md that no longer exist are [WARNING]. Skills or hooks that exist but aren't in MANUAL.md are [WARNING].

### Check 3: CLAUDE.md accuracy

Read `CLAUDE.md` with the Read tool. Check if the conventions described (logging path, commit message format, script template, etc.) match actual project practices. Flag discrepancies as [WARNING].

### Check 4: Stale plans in docs/plans/

```bash
ls -la docs/plans/ 2>/dev/null
```
For each plan file, check its age and whether the feature it describes has been implemented. Plans older than 30 days for completed features are [INFO].

### Check 5: staging.md completeness

```bash
grep -cE '\[.*TODO.*\]|\[.*TBD.*\]|\[.*PLACEHOLDER.*\]|\[.*FIXME.*\]' docs/staging.md 2>/dev/null || echo "0"
```
If count > 0, flag as [WARNING] with the count of placeholder brackets.

---

## Section: infra — Infrastructure health

### Check 1: Docker build

```bash
docker-compose -f docker/docker-compose.local.yml build --no-cache 2>&1 | tail -5
```
If build fails, flag as [CRITICAL]. If build succeeds, flag as [INFO] with build time.

### Check 2: .gitignore coverage

Check for tracked files that probably shouldn't be:
```bash
git ls-files | grep -iE '\.log$|\.tmp$|\.bak$|\.swp$|__pycache__|\.pyc$|node_modules|\.DS_Store' || true
```
Any match is [WARNING].

### Check 3: Hooks registered in settings

```bash
jq -r '.hooks | keys[]' .claude/settings.local.json 2>/dev/null
```
Compare against expected hook events (PreToolUse, PostToolUse, etc.). Verify each registered hook script exists:
```bash
jq -r '.hooks | to_entries[] | .value[] | .hooks[] | .command' .claude/settings.local.json 2>/dev/null | while read cmd; do
  test -f "$cmd" && echo "OK: $cmd" || echo "MISSING: $cmd"
done
```
Missing hook scripts are [CRITICAL].

### Check 4: Git hooks installation

```bash
test -f .git/hooks/pre-commit && echo "pre-commit: OK" || echo "pre-commit: MISSING"
```
Check it delegates correctly (contains expected content):
```bash
head -10 .git/hooks/pre-commit 2>/dev/null
```
Missing or empty pre-commit hook is [CRITICAL].

### Check 5: gh CLI authentication

```bash
gh auth status 2>&1
```
If not authenticated, flag as [WARNING].

### Check 6: Stale worktrees and branches

```bash
git worktree list 2>/dev/null
git branch --merged master 2>/dev/null | grep -v 'master\|main\|\*' || true
```
Stale worktrees or fully-merged branches that haven't been cleaned up are [INFO].

---

## Section: claude — Skill/hook efficiency and usage metrics

### Check 1: Skill frontmatter validation

```bash
for skill in .claude/skills/*/SKILL.md; do
  echo "--- $skill ---"
  head -5 "$skill"
  echo ""
done
```
Each SKILL.md must have `---` delimited frontmatter with `name:` and `description:` fields. Missing frontmatter is [WARNING]. Missing name or description is [WARNING].

### Check 2: Hook/git hook redundancy

Read `.claude/settings.local.json` hooks section and `.git/hooks/pre-commit`. Identify overlapping checks (e.g., both running shellcheck, both checking for secrets). Flag overlaps as [INFO] with an explanation of whether the redundancy is intentional safety layering or wasteful duplication.

### Check 3: Hook script executability and empty-input handling

```bash
jq -r '.hooks | to_entries[] | .value[] | .hooks[] | .command' .claude/settings.local.json 2>/dev/null | sort -u | while read cmd; do
  if [ -f "$cmd" ]; then
    test -x "$cmd" && echo "Executable: $cmd" || echo "NOT executable: $cmd"
    echo '{}' | bash "$cmd" >/dev/null 2>&1
    echo "Empty input exit code: $?"
  else
    echo "MISSING: $cmd"
  fi
done
```
Non-executable hook scripts are [WARNING]. Scripts that crash on empty input are [WARNING].

### Check 4: Skills referencing deleted files or outdated conventions

```bash
for skill in .claude/skills/*/SKILL.md; do
  echo "--- $skill ---"
  grep -inE 'TODO\.txt|todo\.txt' "$skill" 2>/dev/null && echo "  References deleted TODO.txt" || true
done
```
Also check for references to files that no longer exist in the repo. Flag as [WARNING].

### Check 5: Vague skill descriptions

```bash
for skill in .claude/skills/*/SKILL.md; do
  desc=$(grep '^description:' "$skill" | sed 's/^description: *//')
  wordcount=$(echo "$desc" | wc -w)
  echo "$skill: $wordcount words — $desc"
done
```
Descriptions under 10 words or that don't mention what the skill does are [WARNING].

### Check 6: Claude service metrics (optional)

```bash
curl -sf http://localhost:9270/metrics 2>/dev/null || echo "Claude metrics endpoint not available (skipping)"
```
If available, report interesting metrics as [INFO]. If not available, silently skip — this is not a finding.

---

## Section: testing — Coverage and consistency

### Check 1: Script-to-test mapping

```bash
echo "=== Scripts ==="
find scripts/ -name '*.sh' -not -path 'scripts/common/test-helpers.sh' -not -name 'test-*' | sort

echo "=== Tests ==="
find . -name 'test-*.sh' -not -path './.git/*' | sort
```
For each script, check if a corresponding `test-*.sh` exists. Scripts without tests are [WARNING].

### Check 2: Test file patterns

For each test file found:
```bash
find . -name 'test-*.sh' -not -path './.git/*' | while read t; do
  echo "--- $t ---"
  grep -c 'test-helpers.sh' "$t" || echo "  Missing test-helpers.sh import"
  grep -cE 'assert_|expect_' "$t" || echo "  No assertions found"
  grep -c 'trap.*cleanup\|trap.*EXIT' "$t" || echo "  No cleanup trap"
done
```
Tests missing helpers import, assertions, or cleanup traps are [WARNING].

### Check 3: Naming conventions

```bash
find . -name 'test-*.sh' -not -path './.git/*' | while read t; do
  base=$(basename "$t" | sed 's/^test-//' | sed 's/\.sh$//')
  match=$(find scripts/ -name "${base}.sh" -o -name "${base}" 2>/dev/null | head -1)
  if [ -z "$match" ]; then
    echo "No matching script for test: $t"
  fi
done
```
Tests that don't correspond to any script are [INFO].

### Check 4: Hardcoded absolute paths

```bash
find . -name 'test-*.sh' -not -path './.git/*' | xargs -d '\n' grep -nE '/(home|Users|mnt|tmp)/[a-zA-Z]' 2>/dev/null || true
find . -name 'test-*.sh' -not -path './.git/*' | xargs -d '\n' grep -nE 'localhost|127\.0\.0\.1' 2>/dev/null || true
```
Hardcoded absolute paths or localhost references in tests are [WARNING].

---

## Report finalization

### Summary table

Write the audit report to the output file. Start with a summary table:

```markdown
# Plum Project Audit — YYYY-MM-DD

## Summary

| Section   | Critical | Warning | Info |
|-----------|----------|---------|------|
| security  |        0 |       1 |    2 |
| quality   |        0 |       3 |    1 |
| ...       |      ... |     ... |  ... |
| **Total** |    **0** |   **4** | **3** |
```

If running a single section, the table has only that section's row plus a total.

### Detailed findings

Below the summary, write each section's findings grouped under `## Section: <name>` headings. Each finding is a bullet prefixed with its severity tag:

```markdown
## Section: security

- [CRITICAL] `.env` is not in .gitignore
- [WARNING] Missing `*.pem` pattern in .gitignore
- [INFO] Pre-push hook not installed (optional)
```

### Recommendations

At the end, add a `## Recommendations` section. For every CRITICAL and WARNING finding, generate a copy-pasteable `gh issue create` command:

- **CRITICAL** findings:
  ```bash
  gh issue create --title "AUDIT: <brief description>" --body "<details>" --label "security" --label "P0-critical"
  ```
- **WARNING** findings:
  ```bash
  gh issue create --title "AUDIT: <brief description>" --body "<details>" --label "<relevant-category>" --label "P2-normal"
  ```

Choose the category label (`security`, `deploy`, `backup`, `monitor`, `common`, `research`) based on the section and nature of the finding.

**INFO findings are NOT included in recommendations** — they are informational only.

### Commit

After writing the report, tell the user the results and offer to commit:
```bash
git add docs/audits/<report-file>.md
git commit -m "docs: add project health audit for YYYY-MM-DD"
```
