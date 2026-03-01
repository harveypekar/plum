# Subagent + Worktree + PR + Docker Workflow

**Created:** 2026-03-01
**Purpose:** Coordinate parallel Claude subagents using git worktrees, Docker isolation, and PR-based review

## Actors

| Actor | Role |
|-------|------|
| **Orchestrator** | Main Claude session. Owns TODO.txt, dispatches subagents, merges PRs, runs `/plum-postmortem` |
| **Subagent** | Spawned via `Agent` tool with `isolation: "worktree"`. Works in `.claude/worktrees/<name>/` on its own branch |
| **Human** | Reviews PRs, edits `.env`, makes final merge decisions |

## Workflow Phases

```
PLAN → DISPATCH → WORK → TEST → PR → REVIEW → MERGE → CLEANUP
```

### 1. PLAN (Orchestrator)

- Read TODO.txt, analyze task dependencies
- Group into parallelizable batches (max 3 subagents)
- **Serialization rule:** tasks touching `scripts/common/` are never parallelized
- Tasks in different categories (`deploy/`, `backup/`, `monitor/`) are safe to parallelize

### 2. DISPATCH (Orchestrator)

- Pop tasks from TODO.txt
- Spawn subagents with `isolation: "worktree"`, passing:
  - Task ID + description
  - Branch name: `<type>/<task-id>-<short-description>` (e.g., `feat/kxmvqf-backup-small-data`)
  - Docker project name: branch name with `/` replaced by `-` (e.g., `feat-kxmvqf-backup-small-data`)
  - Constraints: don't touch TODO.txt, .env, or design.md

Example dispatch:
```
Agent(
  isolation: "worktree",
  prompt: "Task kxmvqf: implement small data backup script.
    Branch: feat/kxmvqf-backup-small-data
    Test with: docker-compose -f docker/docker-compose.local.yml -p feat-kxmvqf-backup-small-data run --rm plum bash scripts/backup/backup-small-data.sh
    Do NOT edit: TODO.txt, .env, design.md"
)
```

### 3. WORK (Subagent, in worktree)

- One task per subagent, one worktree, one branch
- Subagent works only in its worktree directory
- Shellcheck hook fires automatically on `.sh` edits
- If `.env` is needed: `ln -s /mnt/d/prg/plum/.env .env` (symlink to main repo)

### 4. TEST (Subagent)

Derive the Docker project name from the branch name (`/` → `-`):
```bash
PROJECT_NAME="${BRANCH_NAME//\//-}"
docker-compose -f docker/docker-compose.local.yml -p "$PROJECT_NAME" run --rm plum bash scripts/...
```

- Max 3 retry attempts on failure
- If all retries fail, create a **draft** PR with failure details
- Always clean up after: `docker-compose -p "$PROJECT_NAME" down --volumes --remove-orphans`

### 5. PR (Subagent)

- Push branch, create PR via `gh pr create`
- One task = one PR (no batching multiple tasks into one PR)
- PR title follows commit convention (`feat:`, `fix:`, `docs:`, `chore:`)
- If subagent discovered new tasks, list them in the PR description (orchestrator pushes to TODO.txt after merge)

### 6. REVIEW (Orchestrator)

- Run `/review-pr` for automated multi-agent review
- **Human review required** for PRs touching:
  - `scripts/common/` (shared utilities)
  - Docker config
  - Security-related code

### 7. MERGE (Orchestrator, sequential)

Merges are **strictly sequential** — one at a time:

1. Squash merge: `gh pr merge <N> --squash --delete-branch`
2. Run `/plum-postmortem` to check design.md drift
3. Tag with `design-checked-<hash>`
4. Proceed to next PR

### 8. CLEANUP (Orchestrator)

- Worktrees are auto-cleaned by Claude Code when the subagent finishes
- Run `/clean-gone` periodically to prune stale local branches
- Docker resources cleaned per-test in step 4

## Global State Management

### Logs (`~/.logs/plum/`)

- **Location:** Outside the repo, at `$HOME/.logs/plum/[script-name]/YYYY-MM-DD.log`
- **In Docker:** Each container gets its own `/plum/logs` volume. With `-p` project naming, Docker creates separate named volumes per project
- **Parallel safety:** Different scripts write to different log files (no conflict). Same-script parallel tests are isolated by Docker project name
- **No changes needed** to `logging.sh`

### TODO.txt

- **Single-writer rule:** Only the orchestrator reads/writes TODO.txt
- Other Claude panes (from `claude-quad.bat`) should not independently pop tasks
- If a subagent discovers a new task, it reports in the PR description — orchestrator pushes it after merge

### .env

- Worktrees do NOT get `.env` automatically (it's gitignored)
- **Solution:** Subagent creates a symlink at the worktree root: `ln -s /mnt/d/prg/plum/.env .env`
- `load-env.sh` walks up from `BASH_SOURCE` to find `.env` — the symlink is found
- The PreToolUse hook (`block-env.sh`) still blocks editing, even through a symlink

### design.md + design-checked tags

- **Only the orchestrator** runs `/plum-postmortem` and creates tags
- Subagents never edit design.md
- Sequential merge ensures clean tag chain: merge PR #1 → postmortem → tag → merge PR #2 → postmortem → tag

### Docker (shared daemon)

- `-p <branch-name>` (with `/` → `-`) namespaces all Docker resources (containers, networks, volumes)
- Always use `--rm` for run commands
- Always `down --volumes --remove-orphans` after testing
- **Required:** `container_name` must NOT be set in docker-compose.local.yml (hardcoded names collide with parallel `-p` runs)

### Git

- All worktrees share the same `.git` directory — this is by design and safe
- Unique branch names (containing task ID) prevent checkout conflicts
- Worktrees are created under `.claude/worktrees/<name>/`

## Scope Expansion

Plum may grow beyond scripts to include project work (websites, infra, etc.):

- **Worktrees stay per-feature, not per-domain** — avoid long-lived divergent branches
- Directory structure grows naturally: `website/`, `infra/`, etc. alongside `scripts/`
- Docker grows with additional services in compose (e.g., `web:` service)
- The `-p` project naming handles multi-service compose files
- TODO.txt, design.md drift detection, and this workflow are all domain-agnostic

## Quick Reference

| Resource | Owner | Parallel-safe? | Notes |
|----------|-------|----------------|-------|
| TODO.txt | Orchestrator only | N/A (single writer) | Subagents report new tasks in PRs |
| .env | Human only | Yes (read-only symlink) | Never edited by Claude |
| design.md | Orchestrator only | N/A (single writer) | Updated via `/plum-postmortem` |
| Logs | Per-script | Yes | Isolated by script name + Docker project |
| Docker | Shared daemon | Yes | Isolated by `-p` project flag |
| Git branches | Per-subagent | Yes | Unique names via task ID |
