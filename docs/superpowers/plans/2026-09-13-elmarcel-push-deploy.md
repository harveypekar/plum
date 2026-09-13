# elmarcel.com Push-to-Deploy — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `git push hetzner master` from the blog repo triggers a full rebuild + atomic swap on the Hetzner VPS, with no manual `deploy-elmarcel.sh` invocation needed for content changes.

**Architecture:** A bare git repo at `/opt/elmarcel/repo.git` on the VPS gains a `post-receive` hook that checks out the pushed commit to `/opt/elmarcel/src`, then calls a new shared `build-and-swap.sh` script (extracted from `deploy-elmarcel.sh`, so the manual and push-triggered paths share one build/swap/verify implementation instead of two). The hook finishes by backing up the bare repo to the existing encrypted Hetzner Storage Box via `rclone`. Spec: `docs/superpowers/specs/2026-09-13-elmarcel-push-deploy-design.md`.

**Tech Stack:** Bash (plum script conventions), git hooks, Docker, Hugo 0.133.1 (pinned container), rclone.

## Global Constraints

- All work happens in this worktree: `cd /mnt/d/prg/plum-elmarcel-push-deploy` (branch `elmarcel-push-deploy`). The main worktree must stay clean.
- Commits: imperative mood, type prefix, author flag required: `git commit --author="Claude <noreply@anthropic.com>"`.
- **If a commit is made via WSL** (`wsl.exe ... git commit ...`), also explicitly set the committer, or WSL's own git config silently attributes the commit to the human user instead of Claude:
  `GIT_COMMITTER_NAME="Claude Code" GIT_COMMITTER_EMAIL="claude@anthropic.com" git commit --author="Claude <noreply@anthropic.com>" ...`
  (The harness's own Bash tool sets this automatically; a separate `wsl.exe` process does not inherit it.)
- Shell scripts must pass shellcheck. Unix LF line endings.
- No secrets in code, logs, or commit messages.
- VPS: `root@77.42.80.52`. SSH key is passphrase-protected — every task that SSHes to the VPS needs a running `ssh-agent` with the key already loaded (ask the user to start one and `ssh-add` it interactively if none is running; do not attempt to read or guess the passphrase). Do not hardcode any particular agent socket path as if it persists across sessions — it doesn't.
- **Never push, open a PR, or merge under the user's own GitHub credentials without asking first, per-action.** Committing locally with the author/committer flags above is fine and expected; pushing this worktree's branch or opening a PR is not something to do without an explicit checkpoint.
- The Hugo source lives at a nested path inside the blog repo: `bogartindustries_com_blog/pacifishticks/`, not at the repo root. Any script that checks out the *whole* blog repo (as the post-receive hook will) must account for that nesting — the buildable source is `<checkout>/pacifishticks`, not `<checkout>` itself.

---

### Task 1: Extract shared build-and-swap script

The build → atomic-swap → verify pipeline in `deploy-elmarcel.sh` (lines ~152–172 today) needs to be callable from two places: the existing rsync-based manual deploy, and the new push-triggered hook. Factor it into a standalone script that takes its inputs as environment variables and runs entirely on the target (no SSH indirection inside it — the caller is responsible for getting it *onto* the target and invoking it there).

**Files:**
- Create: `scripts/deploy/lib/build-and-swap.sh`
- Modify: `scripts/deploy/deploy-elmarcel.sh`

**Interfaces:**
- Consumes (env vars): `TARGET_ROOT` (e.g. `/opt/elmarcel` or the `--local` tmp dir), `SRC_DIR` (the Hugo source directory, already populated — this script does not rsync or checkout anything itself), `HUGO_IMAGE`, `BASE_URL`, `GALLERY_MIN_FILES`, `GALLERY_SAMPLE_REL`.
- Produces: `$TARGET_ROOT/www/site` atomically updated, or a non-zero exit with the live site untouched. Prints the same `log_info`/`log_die` style messages the inline version did.
- Consumed by: Task 2 (`deploy-elmarcel.sh`) and Task 3 (the `post-receive` hook), both running it as `bash build-and-swap.sh` on whichever host it's staged on.

- [ ] **Step 1: Write `scripts/deploy/lib/build-and-swap.sh`**

```bash
#!/bin/bash
# Build the elmarcel.com Hugo site and atomically swap it live.
# Runs entirely on the target host (VPS or a --local tmp dir) — the caller
# is responsible for getting the source onto the target before invoking this.
#
# Required env vars: TARGET_ROOT, SRC_DIR, HUGO_IMAGE, BASE_URL,
#                     GALLERY_MIN_FILES, GALLERY_SAMPLE_REL
# Usage: bash build-and-swap.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export SCRIPT_NAME="build-and-swap"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../../common/logging.sh"

: "${TARGET_ROOT:?TARGET_ROOT must be set}"
: "${SRC_DIR:?SRC_DIR must be set}"
: "${HUGO_IMAGE:?HUGO_IMAGE must be set}"
: "${BASE_URL:?BASE_URL must be set}"
: "${GALLERY_MIN_FILES:?GALLERY_MIN_FILES must be set}"
: "${GALLERY_SAMPLE_REL:?GALLERY_SAMPLE_REL must be set}"

[ -d "$SRC_DIR/content" ] || log_die "Hugo source not found at $SRC_DIR"
[ -f "$SRC_DIR/config.toml" ] || log_die "config.toml missing in $SRC_DIR"
[ -d "$SRC_DIR/static/images/gallery" ] \
    || log_die "static/images/gallery missing in $SRC_DIR — run the gallery restore first"

log_info "Building site with $HUGO_IMAGE"
# SRC_DIR is NOT mounted :ro: Hugo writes a transient .hugo_build.lock into
# the source dir during the build and errors out on a read-only filesystem.
docker run --rm \
    -v "$SRC_DIR:/src" \
    -v "$TARGET_ROOT/www:/target" \
    "$HUGO_IMAGE" hugo \
    --source /src --destination /target/site.new \
    --baseURL "$BASE_URL" --cleanDestinationDir \
    || log_die "Hugo build failed; live site untouched"

test -f "$TARGET_ROOT/www/site.new/index.html" \
    || log_die "Build produced no index.html; live site untouched"

log_info "Atomically swapping site.new -> site"
(cd "$TARGET_ROOT/www" && rm -rf site.old \
    && { [ ! -d site ] || mv site site.old; } \
    && mv site.new site) \
    || log_die "Site swap failed"

log_info "Verifying built site"
test -f "$TARGET_ROOT/www/site/index.html" \
    || log_die "Build verification failed: www/site/index.html missing"
grep -qF 'https://www.elmarcel.com' "$TARGET_ROOT/www/site/index.xml" \
    || log_die "Build verification failed: RSS lacks https baseURL"
count="$(find "$TARGET_ROOT/www/site/images/gallery" -type f | wc -l)" \
    || log_die "Build verification failed: cannot count gallery files"
[ "$count" -ge "$GALLERY_MIN_FILES" ] \
    || log_die "Build verification failed: gallery has $count files, expected >= $GALLERY_MIN_FILES"
test -f "$TARGET_ROOT/www/site${GALLERY_SAMPLE_REL}" \
    || log_die "Build verification failed: sample gallery image missing"
log_info "Build verified: index.html present, https RSS, $count gallery files"
```

- [ ] **Step 2: Shellcheck it**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
shellcheck scripts/deploy/lib/build-and-swap.sh
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
git add scripts/deploy/lib/build-and-swap.sh
git commit --author="Claude <noreply@anthropic.com>" -m "feat: extract shared build-and-swap script for elmarcel deploys

Runs on whatever host it's staged on (VPS or a --local tmp dir) so
both the manual rsync-based deploy and the new push-to-deploy hook
call one implementation instead of two.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Point `deploy-elmarcel.sh` at the shared script

Replace the inline build/swap/verify block with: rsync the shared script alongside the source, then invoke it via the existing `remote()` abstraction. This task is a refactor — no new behavior — so the test is that both `--local` and a real deploy still work exactly as before.

**Files:**
- Modify: `scripts/deploy/deploy-elmarcel.sh`

**Interfaces:**
- Produces: identical external behavior to today (verified by re-running the exact test plan from the original migration plan's Task 4).

- [ ] **Step 1: Replace the inline build/swap/verify_build logic**

In `scripts/deploy/deploy-elmarcel.sh`:
- Delete the `verify_build()` function (now lives in `build-and-swap.sh`).
- Delete the `curl_expect`/`curl_contains`-independent `verify_build` call site.
- Change the rsync step to also copy `scripts/deploy/lib/build-and-swap.sh` and `scripts/common/logging.sh` to the target (the shared script sources `logging.sh` via a relative path — mirror the same relative layout: `<target>/lib/build-and-swap.sh` sourcing `<target>/../common/logging.sh`, i.e. copy `logging.sh` to `$REMOTE_ROOT/common/logging.sh` and the script to `$REMOTE_ROOT/lib/build-and-swap.sh`).
- Replace the `docker run ...` / atomic-swap / `verify_build` block with a single call:

```bash
log_info "Building and swapping on target"
remote "TARGET_ROOT=$REMOTE_ROOT SRC_DIR=$REMOTE_ROOT/src HUGO_IMAGE=$HUGO_IMAGE \
    BASE_URL=$BASE_URL GALLERY_MIN_FILES=$GALLERY_MIN_FILES \
    GALLERY_SAMPLE_REL=$GALLERY_SAMPLE_REL \
    bash $REMOTE_ROOT/lib/build-and-swap.sh" \
    || log_die "build-and-swap failed on target"
```

Add the corresponding rsync lines next to the existing compose-file sync (both the `--local` and real-VPS branches):

```bash
# --local branch:
mkdir -p "$REMOTE_ROOT/lib" "$REMOTE_ROOT/common"
rsync -az "$SCRIPT_DIR/lib/build-and-swap.sh" "$REMOTE_ROOT/lib/"
rsync -az "$SCRIPT_DIR/../common/logging.sh" "$REMOTE_ROOT/common/"

# real-VPS branch:
rsync -az -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" \
    "$SCRIPT_DIR/lib/build-and-swap.sh" "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/lib/"
rsync -az -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" \
    "$SCRIPT_DIR/../common/logging.sh" "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/common/"
```

- [ ] **Step 2: Shellcheck**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
shellcheck scripts/deploy/deploy-elmarcel.sh
```

Expected: no output.

- [ ] **Step 3: Regression-test `--local`**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
# clean any previous run (files may be root-owned from Docker; use a
# throwaway container to remove if a plain rm fails):
rm -rf "${TMPDIR:-/tmp}/elmarcel-local-deploy" 2>/dev/null \
    || docker run --rm -v /tmp:/tmp alpine sh -c 'rm -rf /tmp/elmarcel-local-deploy'
LOG_VERBOSE=true bash scripts/deploy/deploy-elmarcel.sh --local
```

Expected: ends with `Local deploy pipeline OK: .../www/site`, identical to before the refactor.

- [ ] **Step 4: Verify output is unchanged**

```bash
LOCAL_ROOT="${TMPDIR:-/tmp}/elmarcel-local-deploy"
test -f "$LOCAL_ROOT/www/site/index.html" && echo "index OK"
find "$LOCAL_ROOT/www/site/images/gallery" -type f | wc -l   # expect 118
test -f "$LOCAL_ROOT/www/site/posts/2008_10_19_6_changelog/index.html" && echo "deep post OK"
```

Expected: `index OK`, `118`, `deep post OK`.

- [ ] **Step 5: Regression-test the real deploy path**

Requires a running `ssh-agent` with the VPS key loaded (ask the user to confirm one is running and the key is added — do not attempt to load it yourself).

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
bash scripts/deploy/deploy-elmarcel.sh
```

Expected: `Deploy complete. Site is built and Caddy is serving.` Then confirm nothing broke:

```bash
curl -s -o /dev/null -w '%{http_code}\n' --resolve www.elmarcel.com:443:77.42.80.52 https://www.elmarcel.com/blog/
```

Expected: `200`.

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
git add scripts/deploy/deploy-elmarcel.sh
git commit --author="Claude <noreply@anthropic.com>" -m "refactor: delegate build/swap/verify to shared build-and-swap.sh

No behavior change — deploy-elmarcel.sh now stages the shared script
on the target and invokes it, instead of inlining the same logic.
Regression-tested via --local and a real deploy.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Bare repo + post-receive hook on the VPS

**Files:**
- Create: `scripts/deploy/hooks/post-receive-elmarcel.sh` (source of truth in the repo; installed onto the VPS as `/opt/elmarcel/repo.git/hooks/post-receive`)
- Modify: `scripts/deploy/setup-elmarcel-vps.sh` (one-time setup — create the bare repo, install the hook)

**Interfaces:**
- Consumes: pushed refs on stdin (git's standard `post-receive` protocol: one line per ref as `<old-sha> <new-sha> <ref-name>`).
- Produces: `/opt/elmarcel/src` populated with the pushed commit's tree, then `build-and-swap.sh` invoked against `/opt/elmarcel/src/pacifishticks` (the nested Hugo source path — see Global Constraints).
- Only acts on `refs/heads/master`; ignores pushes to any other branch.

- [ ] **Step 1: Write the hook script**

```bash
#!/bin/bash
# post-receive hook for the elmarcel.com blog bare repo.
# Installed at /opt/elmarcel/repo.git/hooks/post-receive on the VPS.
# Git invokes this automatically after `git push`, with pushed refs on stdin
# as lines of "<old-sha> <new-sha> <ref-name>". Only refs/heads/master
# triggers a rebuild.

set -euo pipefail

REPO_ROOT="/opt/elmarcel"
WORK_TREE="$REPO_ROOT/src"
GIT_DIR_PATH="$REPO_ROOT/repo.git"

while read -r _old_sha new_sha ref_name; do
    if [ "$ref_name" != "refs/heads/master" ]; then
        echo "post-receive: ignoring push to $ref_name (only master triggers a deploy)"
        continue
    fi

    echo "post-receive: deploying $new_sha"
    mkdir -p "$WORK_TREE"
    if ! GIT_DIR="$GIT_DIR_PATH" GIT_WORK_TREE="$WORK_TREE" git checkout -f "$new_sha"; then
        echo "post-receive: checkout failed; live site untouched" >&2
        exit 1
    fi

    SITE_SRC="$WORK_TREE/pacifishticks"
    if ! TARGET_ROOT="$REPO_ROOT" SRC_DIR="$SITE_SRC" \
        HUGO_IMAGE="hugomods/hugo:0.133.1" \
        BASE_URL="https://www.elmarcel.com/blog/" \
        GALLERY_MIN_FILES=118 \
        GALLERY_SAMPLE_REL="/images/gallery/2004_01_03_13_35_42_4138319335.jpg" \
        bash "$REPO_ROOT/lib/build-and-swap.sh"; then
        echo "post-receive: build/swap failed; live site untouched" >&2
        exit 1
    fi

    echo "post-receive: deploy complete"

    if ! rclone sync "$GIT_DIR_PATH" hetzner-crypt:bak/elmarcel-blog-repo; then
        echo "post-receive: WARNING backup to Storage Box failed (deploy already succeeded)" >&2
        # Do not fail the push over a backup failure — the site update already
        # happened. Surface it loudly so the user notices and can re-run it.
    fi
done
```

- [ ] **Step 2: Shellcheck**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
shellcheck scripts/deploy/hooks/post-receive-elmarcel.sh
```

Expected: no output.

- [ ] **Step 3: Extend `setup-elmarcel-vps.sh` to create the bare repo and install the hook**

Add, after the existing `mkdir -p $REMOTE_ROOT/www` step:

```bash
log_info "Setting up bare repo for push-to-deploy"
remote "git init --bare $REMOTE_ROOT/repo.git"
remote "mkdir -p $REMOTE_ROOT/lib $REMOTE_ROOT/common"

# shellcheck disable=SC2029  # client-side expansion is intentional
scp -i "$VPS_SSH_KEY" "$SCRIPT_DIR/hooks/post-receive-elmarcel.sh" \
    "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/repo.git/hooks/post-receive"
remote "chmod +x $REMOTE_ROOT/repo.git/hooks/post-receive"

# build-and-swap.sh and logging.sh: the hook calls these directly (no SSH
# indirection needed since it already runs on the VPS), so they need to be
# resident there, not just staged transiently by a deploy run.
# shellcheck disable=SC2029
scp -i "$VPS_SSH_KEY" "$SCRIPT_DIR/lib/build-and-swap.sh" \
    "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/lib/"
# shellcheck disable=SC2029
scp -i "$VPS_SSH_KEY" "$SCRIPT_DIR/../common/logging.sh" \
    "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/common/"

echo "Bare repo ready at ${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/repo.git"
echo "Add it as a remote from the blog repo checkout:"
echo "  git remote add hetzner ${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/repo.git"
```

- [ ] **Step 4: Shellcheck the modified setup script**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
shellcheck scripts/deploy/setup-elmarcel-vps.sh
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
git add scripts/deploy/hooks/post-receive-elmarcel.sh scripts/deploy/setup-elmarcel-vps.sh
git commit --author="Claude <noreply@anthropic.com>" -m "feat: add post-receive hook for elmarcel.com push-to-deploy

setup-elmarcel-vps.sh now creates a bare repo at /opt/elmarcel/repo.git
and installs a post-receive hook that checks out the pushed commit,
runs the shared build-and-swap.sh, then backs up the bare repo to the
Hetzner Storage Box. Backup failures warn but don't fail the push —
the deploy has already succeeded by that point.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: rclone + hetzner-crypt on the VPS

The hook's backup step needs `rclone` installed and the `hetzner-crypt` remote configured on the VPS — today that only exists on the workstation. This step **requires the user's own rclone config/credentials**; do not invent, guess, or synthesize any part of it.

**Files:**
- No new repo files — this is VPS-side setup plus a one-line addition to `setup-elmarcel-vps.sh`.

**Interfaces:**
- Consumes: the user's existing rclone config (contains the `hetzner-crypt` remote definition — an encrypted overlay on top of an underlying SFTP remote to the Storage Box). Workstation copy lives at `/mnt/d/keys/rclone.conf` per `.env`'s `RCLONE_CONFIG`.
- Produces: `rclone` installed on the VPS with root's config at `~/.config/rclone/rclone.conf` containing a working `hetzner-crypt` remote, verified the same way `sync-dirs.py` verifies it (`rclone config show hetzner-crypt` contains `type = crypt`).

- [ ] **Step 1: Add rclone install to `setup-elmarcel-vps.sh`**

```bash
log_info "Installing rclone if absent"
remote "command -v rclone >/dev/null || curl -fsSL https://rclone.org/install.sh | bash"
```

- [ ] **Step 2: STOP — ask the user before copying credentials to the VPS**

This step moves the contents of a secrets file (the rclone config, which contains the crypt password and the Storage Box's SFTP credentials) onto the VPS. Ask the user explicitly:

> "The backup step needs your rclone config (`D:\keys\rclone.conf`) copied onto the VPS so it can reach the Storage Box under the `hetzner-crypt` remote. OK to copy it there (to `root`'s `~/.config/rclone/rclone.conf`)?"

Only proceed past this step once the user has said yes.

- [ ] **Step 3: Copy the rclone config**

```bash
remote "mkdir -p ~/.config/rclone"
# shellcheck disable=SC2029
scp -i "$VPS_SSH_KEY" /mnt/d/keys/rclone.conf "${VPS_USER}@${VPS_HOST}:~/.config/rclone/rclone.conf"
```

- [ ] **Step 4: Verify the remote is reachable and encrypted, on the VPS**

```bash
remote "rclone config show hetzner-crypt" | grep -q "type = crypt" && echo "CRYPT OK"
remote "rclone lsd hetzner-crypt:bak" || echo "bak/ doesn't exist yet — will be created on first sync, that's fine"
```

Expected: `CRYPT OK`. The `lsd` check may show "doesn't exist yet" the first time — that's fine, `rclone sync` creates destination paths as needed.

- [ ] **Step 5: Test the backup path manually once, before relying on the hook**

```bash
remote "rclone sync $REMOTE_ROOT/repo.git hetzner-crypt:bak/elmarcel-blog-repo --progress"
remote "rclone lsd hetzner-crypt:bak/elmarcel-blog-repo"
```

Expected: sync completes without error; `lsd` lists the bare repo's internal directories (`objects`, `refs`, etc.) now present on the Storage Box.

- [ ] **Step 6: Commit the `setup-elmarcel-vps.sh` addition**

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
git add scripts/deploy/setup-elmarcel-vps.sh
git commit --author="Claude <noreply@anthropic.com>" -m "feat: install rclone on the VPS for elmarcel blog-repo backups

Config copy and remote verification are manual/confirmed steps (this
commit only adds the rclone install line) — the user's rclone config
contains real credentials and was copied to the VPS with explicit
confirmation, not automated blindly.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Run one-time setup, wire up the remote, and test end-to-end

- [ ] **Step 1: Run the updated setup script against the real VPS**

Confirm with the user before running (production action, same as the original migration's pattern):

```bash
cd /mnt/d/prg/plum-elmarcel-push-deploy
bash scripts/deploy/setup-elmarcel-vps.sh
```

Expected: creates the bare repo, installs the hook, installs `rclone`, and (from Task 4) the config copy/verification already done.

- [ ] **Step 2: Add the VPS as a remote in the blog repo**

This is a local git config change in a *different* repo (`bogartindustries_com_blog`), which has no branch-protection or worktree rules of its own (established earlier this session) — safe to do directly:

```bash
cd /mnt/d/prg/bogartindustries_com_blog
git remote add hetzner root@77.42.80.52:/opt/elmarcel/repo.git
git remote -v   # confirm it's listed
```

- [ ] **Step 3: Push and verify the happy path**

```bash
cd /mnt/d/prg/bogartindustries_com_blog
git push hetzner master
```

Expected: git's output includes the `post-receive` hook's `echo` lines (`post-receive: deploying <sha>`, `post-receive: deploy complete`), streamed live during the push.

- [ ] **Step 4: Confirm the site actually updated**

```bash
curl -s -o /dev/null -w '%{http_code}\n' --resolve www.elmarcel.com:443:77.42.80.52 https://www.elmarcel.com/blog/
```

Expected: `200`. (Forced-IP `--resolve` bypasses any local DNS caching — this pattern came up repeatedly earlier in the migration and is the reliable way to check the live server directly regardless of client-side DNS state.)

- [ ] **Step 5: Confirm the backup landed**

```bash
ssh -i /path/to/vps/key root@77.42.80.52 "rclone lsl hetzner-crypt:bak/elmarcel-blog-repo | tail -5"
```

Expected: recent timestamps, non-empty listing.

- [ ] **Step 6: Test the failure path — a deliberately broken build must not touch the live site**

```bash
cd /mnt/d/prg/bogartindustries_com_blog/pacifishticks
# Break the build: invalid TOML front matter in a scratch post.
cat > content/posts/9999_test_broken_build.md <<'EOF'
+++
title = "broken
+++
This front matter is deliberately invalid TOML (unterminated string).
EOF
git add content/posts/9999_test_broken_build.md
git commit --author="Claude <noreply@anthropic.com>" -m "test: deliberately broken front matter to verify hook aborts safely

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push hetzner master
```

Expected: the push's hook output shows the Hugo build failing and `post-receive: build/swap failed; live site untouched`, with a non-zero exit reported by git.

```bash
curl -s -o /dev/null -w '%{http_code}\n' --resolve www.elmarcel.com:443:77.42.80.52 https://www.elmarcel.com/blog/
```

Expected: still `200` — the live site is untouched by the failed push.

- [ ] **Step 7: Revert the deliberate break and push the fix**

```bash
cd /mnt/d/prg/bogartindustries_com_blog
git revert --no-edit HEAD
git push hetzner master
```

Expected: hook succeeds again (`post-receive: deploy complete`), confirming recovery after a failed push works cleanly.

---

## Post-plan note

`deploy-elmarcel.sh` still exists and still matters — it's the path for *infrastructure* changes (Caddyfile, compose file) that live in the `plum` repo, not blog content. Nothing in this plan removes or replaces it; Task 2 only changes what it delegates to internally.
