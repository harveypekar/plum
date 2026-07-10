# elmarcel.com Migration to Hetzner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the elmarcel.com Hugo site from the Hetzner CX23 VPS over HTTPS, built on the VPS in a pinned container, so DreamCompute can be cancelled.

**Architecture:** A single Docker Compose stack at `/opt/elmarcel/` on the VPS runs Caddy (auto-HTTPS) serving `/opt/elmarcel/www/site`. A deploy script rsyncs the Hugo *source* to the VPS, builds it there with a one-shot `hugomods/hugo:0.133.1` container into `www/site.new`, and atomically swaps it live. Spec: `docs/superpowers/specs/2026-07-10-elmarcel-hetzner-migration-design.md`.

**Tech Stack:** Bash (plum script conventions), Docker Compose, Caddy 2 (alpine), Hugo 0.133.1 (pinned container), rsync over SSH.

## Global Constraints

- All plum work happens in the existing worktree: `cd /mnt/d/prg/plum-elmarcel-hetzner` (branch `elmarcel-hetzner`). The main worktree must stay clean.
- Task 1 happens in a **different repo**: `/mnt/d/prg/bogartindustries_com_blog` (commit there directly; it has no hooks or branch rules).
- Commits: imperative mood, type prefix (`feat:`, `fix:`, `docs:`, `chore:`), author flag required: `git commit --author="Claude <noreply@anthropic.com>"`.
- Shell scripts must pass `shellcheck` (pre-commit hook enforces). Unix LF line endings.
- No secrets in code or logs. VPS connection details come from `.env` keys `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` (already present in `.env.example`; the user fills `.env` manually — never edit `.env`).
- Hugo version is pinned: `hugomods/hugo:0.133.1` (plain, not extended — matches the repo's `hugo_old.exe` v0.133.1). If that tag is unavailable at execution time, STOP and report; do not substitute another version silently.
- Canonical host: `www.elmarcel.com`. baseURL passed at build time (`--baseURL https://www.elmarcel.com/`); `config.toml` is NOT edited.
- Site source path: `/mnt/d/prg/bogartindustries_com_blog/pacifishticks` (overridable via env `ELMARCEL_SITE_SRC`).
- Verification thresholds: 118 gallery images, RSS at `/index.xml`, deep post `/blog/2008_10_19_6_changelog/`, sample image `/images/gallery/2004_01_03_13_35_42_4138319335.jpg`.
- Redirect status codes: Caddy auto-HTTPS (HTTP→HTTPS) responds **308**; the Caddyfile `redir … permanent` (apex→www) responds **301**.

---

### Task 1: Restore the photo gallery to Hugo source (blog repo)

The 87 MB gallery exists only in build output (`public/images/gallery/`); the build input (`static/images/`) lacks it, so any clean rebuild loses all photos. Restore it to `static/` and commit, making the source self-contained.

**Files:**
- Create: `/mnt/d/prg/bogartindustries_com_blog/pacifishticks/static/images/gallery/` (118 files, copied)

**Interfaces:**
- Produces: a Hugo source tree that builds the complete site from `content/ static/ layouts/ archetypes/ config.toml` alone. Task 4 rsyncs exactly those five paths.

- [ ] **Step 1: Verify the precondition (gallery missing from static)**

```bash
cd /mnt/d/prg/bogartindustries_com_blog/pacifishticks
test ! -d static/images/gallery && echo "PRECONDITION OK"
find public/images/gallery -type f | wc -l   # expect: 118
```

Expected: `PRECONDITION OK` and `118`. If `static/images/gallery` already exists, STOP — re-check state with the user before overwriting anything.

- [ ] **Step 2: Copy gallery from public/ to static/**

```bash
cd /mnt/d/prg/bogartindustries_com_blog/pacifishticks
cp -r public/images/gallery static/images/gallery
```

- [ ] **Step 3: Verify the copy is complete and identical**

```bash
cd /mnt/d/prg/bogartindustries_com_blog/pacifishticks
diff -r public/images/gallery static/images/gallery && echo "IDENTICAL"
find static/images/gallery -type f | wc -l   # expect: 118
```

Expected: `IDENTICAL` and `118`.

- [ ] **Step 4: Commit in the blog repo**

Note: this repo has pre-existing unrelated modifications (`.vscode/`, `*.pyproj`, `flickrapi-2.2.1/`, …). Stage ONLY the gallery directory.

```bash
cd /mnt/d/prg/bogartindustries_com_blog
git add pacifishticks/static/images/gallery
git commit --author="Claude <noreply@anthropic.com>" -m "fix: restore photo gallery to static/ so clean builds include images

The gallery only existed in public/ (build output). generate_photo_posts.py
shows it originally lived in static/images/gallery.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git show --stat HEAD | tail -3   # expect ~118 files changed
```

---

### Task 2: Compose stack config (`docker/elmarcel/`)

**Files:**
- Create: `docker/elmarcel/docker-compose.yml` (in `/mnt/d/prg/plum-elmarcel-hetzner`)
- Create: `docker/elmarcel/Caddyfile`

**Interfaces:**
- Produces: a compose stack whose working dir on the VPS is `/opt/elmarcel/` with layout `docker-compose.yml`, `Caddyfile`, `src/` (Hugo source), `www/site/` (live docroot). Task 4's deploy script rsyncs these two files to `/opt/elmarcel/` verbatim and runs `docker compose up -d` there.

**Key design point:** Caddy bind-mounts the *parent* `./www` at `/srv` and the Caddyfile sets `root * /srv/site`. Mounting `./site` directly would pin the container to the original directory inode, so the atomic `mv site.new site` swap would be invisible to the container. Mounting the parent means every request re-resolves the `site` path, making the swap take effect instantly with no restart.

- [ ] **Step 1: Write `docker/elmarcel/docker-compose.yml`**

```yaml
# Caddy serving the elmarcel.com static site.
# Deployed to /opt/elmarcel/ on the VPS by scripts/deploy/deploy-elmarcel.sh.
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      # Mount the parent of the docroot: the deploy script atomically swaps
      # www/site.new -> www/site, which only stays visible to the container
      # if path resolution happens inside the mount on every request.
      - ./www:/srv:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
```

- [ ] **Step 2: Write `docker/elmarcel/Caddyfile`**

```
www.elmarcel.com {
	root * /srv/site
	encode gzip
	file_server
	handle_errors {
		rewrite * /404.html
		file_server
	}
}

elmarcel.com {
	redir https://www.elmarcel.com{uri} permanent
}
```

(Caddyfile convention is tabs for indentation; `caddy fmt` output uses tabs.)

- [ ] **Step 3: Validate both files**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
docker compose -f docker/elmarcel/docker-compose.yml config -q && echo "COMPOSE OK"
docker run --rm -v "$PWD/docker/elmarcel/Caddyfile:/etc/caddy/Caddyfile:ro" \
    caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
```

Expected: `COMPOSE OK` and Caddy printing `Valid configuration`.

- [ ] **Step 4: Commit**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
git add docker/elmarcel/docker-compose.yml docker/elmarcel/Caddyfile
git commit --author="Claude <noreply@anthropic.com>" -m "feat: add Caddy compose stack for elmarcel.com on Hetzner VPS

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: One-time VPS setup script

**Files:**
- Create: `scripts/deploy/setup-elmarcel-vps.sh` (in `/mnt/d/prg/plum-elmarcel-hetzner`)

**Interfaces:**
- Consumes: `.env` keys `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`; plum's `scripts/common/logging.sh` (`log_info`, `log_die`) and `scripts/common/load-env.sh`.
- Produces: a VPS with Docker Engine + compose plugin installed and `/opt/elmarcel/www` existing. Task 4 assumes both.

- [ ] **Step 1: Write the script**

```bash
#!/bin/bash
# One-time Hetzner VPS preparation for the elmarcel.com stack.
# Installs Docker (with compose plugin) if absent and creates /opt/elmarcel.
# Idempotent: safe to re-run.
# Usage: bash scripts/deploy/setup-elmarcel-vps.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export SCRIPT_NAME="setup-elmarcel-vps"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/logging.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/load-env.sh"

: "${VPS_HOST:?VPS_HOST must be set in .env}"
: "${VPS_USER:?VPS_USER must be set in .env}"
: "${VPS_SSH_KEY:?VPS_SSH_KEY must be set in .env}"

REMOTE_ROOT="/opt/elmarcel"

remote() {
    # shellcheck disable=SC2029  # client-side expansion is intentional
    ssh -i "$VPS_SSH_KEY" -o BatchMode=yes "${VPS_USER}@${VPS_HOST}" "$@"
}

log_info "Checking SSH connectivity to ${VPS_USER}@${VPS_HOST}"
remote "true" || log_die "Cannot SSH to ${VPS_USER}@${VPS_HOST} with key $VPS_SSH_KEY"

log_info "Installing Docker if absent"
remote "command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh"

DOCKER_VERSION="$(remote 'docker --version' || true)"
[ -n "$DOCKER_VERSION" ] || log_die "Docker install failed: 'docker --version' returned nothing"
log_info "Docker present: $DOCKER_VERSION"

COMPOSE_VERSION="$(remote 'docker compose version' || true)"
[ -n "$COMPOSE_VERSION" ] || log_die "Docker compose plugin missing: 'docker compose version' returned nothing"
log_info "Compose present: $COMPOSE_VERSION"

log_info "Creating $REMOTE_ROOT/www"
remote "mkdir -p $REMOTE_ROOT/www"

log_info "VPS setup complete."
echo "VPS setup complete."
echo ""
echo "MANUAL STEP REMAINING: ensure ports 80/tcp, 443/tcp and 443/udp are open"
echo "in the Hetzner Cloud firewall (console.hetzner.cloud) or host firewall."
```

- [ ] **Step 2: Shellcheck it**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
shellcheck scripts/deploy/setup-elmarcel-vps.sh
```

Expected: no output (clean pass).

- [ ] **Step 3: Verify failure mode without .env values (no VPS needed)**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
env -u VPS_HOST bash -c 'VPS_USER=x VPS_SSH_KEY=x bash scripts/deploy/setup-elmarcel-vps.sh' 2>&1 | head -3
```

Expected: an error mentioning `VPS_HOST must be set in .env` (from the `:?` guard), non-zero exit. (If the local `.env` already defines `VPS_HOST`, this prints an SSH connectivity error instead — also an acceptable loud failure; the point is it must not proceed silently.)

- [ ] **Step 4: Commit**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
git add scripts/deploy/setup-elmarcel-vps.sh
git commit --author="Claude <noreply@anthropic.com>" -m "feat: add one-time VPS setup script for elmarcel stack

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Deploy script

**Files:**
- Create: `scripts/deploy/deploy-elmarcel.sh` (in `/mnt/d/prg/plum-elmarcel-hetzner`)

**Interfaces:**
- Consumes: `.env` keys `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` (deploy mode only); optional `ELMARCEL_SITE_SRC`; `docker/elmarcel/docker-compose.yml` + `Caddyfile` from Task 2; the self-contained Hugo source from Task 1; `logging.sh`/`load-env.sh` as in Task 3.
- Produces: three modes — `deploy` (default), `--local` (full sync+build+swap+verify against a local directory, no VPS, no Caddy), `--check` (post-cutover HTTPS verification suite, no VPS credentials needed). Task 5 consumes the `--local` output; the PR test plan runs all three.

**Mode design:** all remote operations go through one `remote()` function and one `RSYNC_DEST` variable; `--local` swaps them for local equivalents. This makes the entire build/swap pipeline (the risky logic) testable end-to-end on the workstation with real Docker and the real source tree — the only untested parts are SSH transport and Caddy/TLS, which are covered by Task 2 validation, Task 5's smoke test, and the post-cutover `--check`.

- [ ] **Step 1: Write the script**

```bash
#!/bin/bash
# Deploy the elmarcel.com Hugo site to the Hetzner VPS.
#
# Pipeline: rsync Hugo source + compose config -> build on target in a pinned
# hugomods/hugo container into www/site.new -> atomic swap to www/site ->
# docker compose up -d -> verify.
#
# Usage:
#   bash scripts/deploy/deploy-elmarcel.sh           # deploy to VPS
#   bash scripts/deploy/deploy-elmarcel.sh --local   # e2e test into a local dir (no VPS)
#   bash scripts/deploy/deploy-elmarcel.sh --check   # post-cutover HTTPS verification only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export SCRIPT_NAME="deploy-elmarcel"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/logging.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/load-env.sh"

MODE="${1:-deploy}"
case "$MODE" in
    deploy|--local|--check) ;;
    *) log_die "Unknown mode: $MODE (expected no args, --local, or --check)" ;;
esac

SITE_SRC="${ELMARCEL_SITE_SRC:-/mnt/d/prg/bogartindustries_com_blog/pacifishticks}"
COMPOSE_SRC="$SCRIPT_DIR/../../docker/elmarcel"
HUGO_IMAGE="hugomods/hugo:0.133.1"
BASE_URL="https://www.elmarcel.com/"
CANONICAL_HOST="www.elmarcel.com"
APEX_HOST="elmarcel.com"
GALLERY_MIN_FILES=118
DEEP_POST_PATH="/blog/2008_10_19_6_changelog/"
SAMPLE_IMAGE_PATH="/images/gallery/2004_01_03_13_35_42_4138319335.jpg"

# --- verification helpers -----------------------------------------------

# curl_expect <url> <expected_http_code> [extra curl args...]
curl_expect() {
    local url="$1" expected="$2"
    shift 2
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$@" "$url")" \
        || log_die "curl failed entirely for $url"
    [ "$code" = "$expected" ] \
        || log_die "Expected HTTP $expected for $url, got $code"
    log_info "OK $code $url"
}

# curl_contains <url> <needle>
curl_contains() {
    local url="$1" needle="$2"
    local body
    body="$(curl -sSf "$url")" || log_die "curl failed for $url"
    [ -n "$body" ] || log_die "Empty response body from $url"
    echo "$body" | grep -qF "$needle" \
        || log_die "Response from $url does not contain: $needle"
    log_info "OK content $url"
}

run_check() {
    log_info "Running post-cutover verification against live DNS"
    curl_contains "https://${CANONICAL_HOST}/" "PACIFISHTICKS"
    curl_contains "https://${CANONICAL_HOST}/index.xml" "https://www.elmarcel.com"
    curl_expect "https://${CANONICAL_HOST}${DEEP_POST_PATH}" 200
    curl_expect "https://${CANONICAL_HOST}${SAMPLE_IMAGE_PATH}" 200
    # Caddy auto-HTTPS redirect is 308; Caddyfile 'redir ... permanent' is 301.
    curl_expect "http://${CANONICAL_HOST}/" 308
    curl_expect "https://${APEX_HOST}/" 301
    curl_expect "https://${CANONICAL_HOST}/definitely-not-a-page" 404
    log_info "All post-cutover checks passed"
    echo "All post-cutover checks passed."
}

verify_build() {
    log_info "Verifying built site on target"
    remote "test -f $REMOTE_ROOT/www/site/index.html" \
        || log_die "Build verification failed: www/site/index.html missing"
    remote "grep -qF 'https://www.elmarcel.com' $REMOTE_ROOT/www/site/index.xml" \
        || log_die "Build verification failed: RSS lacks https baseURL"
    local count
    count="$(remote "find $REMOTE_ROOT/www/site/images/gallery -type f | wc -l")" \
        || log_die "Build verification failed: cannot count gallery files"
    [ "$count" -ge "$GALLERY_MIN_FILES" ] \
        || log_die "Build verification failed: gallery has $count files, expected >= $GALLERY_MIN_FILES"
    remote "test -f $REMOTE_ROOT/www/site${SAMPLE_IMAGE_PATH}" \
        || log_die "Build verification failed: sample gallery image missing"
    log_info "Build verified: index.html present, https RSS, $count gallery files"
}

# --- mode setup -----------------------------------------------------------

if [ "$MODE" = "--check" ]; then
    run_check
    exit 0
fi

if [ "$MODE" = "--local" ]; then
    REMOTE_ROOT="${TMPDIR:-/tmp}/elmarcel-local-deploy"
    remote() { bash -c "$*"; }
else
    : "${VPS_HOST:?VPS_HOST must be set in .env}"
    : "${VPS_USER:?VPS_USER must be set in .env}"
    : "${VPS_SSH_KEY:?VPS_SSH_KEY must be set in .env}"
    REMOTE_ROOT="/opt/elmarcel"
    remote() {
        # shellcheck disable=SC2029  # client-side expansion is intentional
        ssh -i "$VPS_SSH_KEY" -o BatchMode=yes "${VPS_USER}@${VPS_HOST}" "$@"
    }
fi

# --- main ----------------------------------------------------------------

[ -d "$SITE_SRC/content" ] || log_die "Hugo source not found at $SITE_SRC (set ELMARCEL_SITE_SRC to override)"
[ -f "$SITE_SRC/config.toml" ] || log_die "config.toml missing in $SITE_SRC"
[ -d "$SITE_SRC/static/images/gallery" ] \
    || log_die "static/images/gallery missing in $SITE_SRC — run the gallery restore first"

log_info "Syncing compose config and Hugo source to target"
if [ "$MODE" = "--local" ]; then
    mkdir -p "$REMOTE_ROOT"
    rsync -az "$COMPOSE_SRC/docker-compose.yml" "$COMPOSE_SRC/Caddyfile" \
        "$REMOTE_ROOT/"
    rsync -az --delete \
        "$SITE_SRC/content" "$SITE_SRC/static" "$SITE_SRC/layouts" \
        "$SITE_SRC/archetypes" "$SITE_SRC/config.toml" \
        "$REMOTE_ROOT/src/"
else
    rsync -az -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" \
        "$COMPOSE_SRC/docker-compose.yml" "$COMPOSE_SRC/Caddyfile" \
        "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/"
    rsync -az --delete -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" \
        "$SITE_SRC/content" "$SITE_SRC/static" "$SITE_SRC/layouts" \
        "$SITE_SRC/archetypes" "$SITE_SRC/config.toml" \
        "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/src/"
fi

log_info "Building site on target with $HUGO_IMAGE"
remote "docker run --rm \
    -v $REMOTE_ROOT/src:/src:ro \
    -v $REMOTE_ROOT/www:/target \
    $HUGO_IMAGE hugo \
    --source /src --destination /target/site.new \
    --baseURL $BASE_URL --cleanDestinationDir" \
    || log_die "Hugo build failed on target; live site untouched"

remote "test -f $REMOTE_ROOT/www/site.new/index.html" \
    || log_die "Build produced no index.html; live site untouched"

log_info "Atomically swapping site.new -> site"
remote "cd $REMOTE_ROOT/www && rm -rf site.old \
    && { [ ! -d site ] || mv site site.old; } \
    && mv site.new site" \
    || log_die "Site swap failed"

verify_build

if [ "$MODE" = "--local" ]; then
    log_info "LOCAL MODE complete (Caddy not started; serving tested separately)"
    echo "Local deploy pipeline OK: $REMOTE_ROOT/www/site"
    exit 0
fi

log_info "Starting/refreshing Caddy"
remote "cd $REMOTE_ROOT && docker compose up -d" || log_die "docker compose up failed"

# Pre-cutover we cannot fetch content over HTTPS (no cert until DNS points
# here), but Caddy answering on :80 with its auto-HTTPS redirect (308)
# proves it is up and routing.
log_info "Checking Caddy responds on port 80"
curl_expect "http://${VPS_HOST}/" 308 -H "Host: ${CANONICAL_HOST}"

log_info "Deploy complete"
echo "Deploy complete. Site is built and Caddy is serving."
echo ""
echo "If DNS does not yet point at this VPS:"
echo "  1. Set A records for ${APEX_HOST} and ${CANONICAL_HOST} to this VPS's IP."
echo "  2. Wait for propagation; Caddy will obtain certificates automatically."
echo "  3. Run: bash scripts/deploy/deploy-elmarcel.sh --check"
```

- [ ] **Step 2: Shellcheck**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
shellcheck scripts/deploy/deploy-elmarcel.sh
```

Expected: no output. Fix any findings without weakening quoting.

- [ ] **Step 3: Verify argument validation (no VPS, no Docker needed)**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
bash scripts/deploy/deploy-elmarcel.sh --bogus; echo "exit=$?"
```

Expected: `exit=1`, and `Unknown mode: --bogus` in the log file `~/.logs/plum/deploy-elmarcel/$(date +%Y-%m-%d).log` (log_die writes to the log; run with `LOG_VERBOSE=true` to also see it on the console).

- [ ] **Step 4: Run the local end-to-end pipeline**

Requires Docker on the workstation and the Task 1 gallery restore done.

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
LOG_VERBOSE=true bash scripts/deploy/deploy-elmarcel.sh --local
```

Expected: ends with `Local deploy pipeline OK: /tmp/elmarcel-local-deploy/www/site` (path varies with `$TMPDIR`). First run pulls `hugomods/hugo:0.133.1`.

- [ ] **Step 5: Verify the local build output looks right**

```bash
LOCAL_ROOT="${TMPDIR:-/tmp}/elmarcel-local-deploy"
test -f "$LOCAL_ROOT/www/site/index.html" && echo "index OK"
grep -c "https://www.elmarcel.com" "$LOCAL_ROOT/www/site/index.xml"
find "$LOCAL_ROOT/www/site/images/gallery" -type f | wc -l   # expect 118
test -f "$LOCAL_ROOT/www/site/blog/2008_10_19_6_changelog/index.html" && echo "deep post OK"
```

Expected: `index OK`, a large positive count, `118`, `deep post OK`.

- [ ] **Step 6: Verify idempotence (second run must also succeed)**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
bash scripts/deploy/deploy-elmarcel.sh --local && echo "RERUN OK"
test -d "${TMPDIR:-/tmp}/elmarcel-local-deploy/www/site.old" && echo "site.old kept as rollback"
```

Expected: `RERUN OK` and `site.old kept as rollback` (second run swaps the first run's site into `site.old`).

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
git add scripts/deploy/deploy-elmarcel.sh
git commit --author="Claude <noreply@anthropic.com>" -m "feat: add elmarcel.com deploy script (rsync, on-VPS Hugo build, atomic swap)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Local Caddy smoke test and PR

Serve the locally built site through Caddy once, proving the volume layout (`www` parent mount, `root * /srv/site`) and error handling serve real content — then open the PR.

**Files:**
- No repo files (scratch smoke config only; uses Task 4's `--local` output).

**Interfaces:**
- Consumes: `${TMPDIR:-/tmp}/elmarcel-local-deploy/www` from Task 4 Step 4; `docker/elmarcel/Caddyfile` structure (replicated in HTTP-only form).

- [ ] **Step 1: Stand up a smoke stack against the built site**

HTTPS can't work locally (no DNS/certs), so this uses a scratch compose file + HTTP-only Caddyfile on port 8088 that mirrors the production volume layout and routing. The committed `docker/elmarcel/` files are not modified.

```bash
LOCAL_ROOT="${TMPDIR:-/tmp}/elmarcel-local-deploy"
mkdir -p "$LOCAL_ROOT/smoke" && cd "$LOCAL_ROOT/smoke"
ln -sfn "$LOCAL_ROOT/www" www

cat > Caddyfile <<'EOF'
{
	auto_https off
}

http://www.elmarcel.com:80 {
	root * /srv/site
	encode gzip
	file_server
	handle_errors {
		rewrite * /404.html
		file_server
	}
}
EOF

cat > docker-compose.yml <<'EOF'
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "8088:80"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./www:/srv:ro
EOF

docker compose up -d
```

- [ ] **Step 2: Verify content through Caddy**

```bash
curl -sf -H "Host: www.elmarcel.com" http://localhost:8088/ | grep -F "PACIFISHTICKS" && echo "HOME OK"
curl -sf -H "Host: www.elmarcel.com" http://localhost:8088/blog/2008_10_19_6_changelog/ >/dev/null && echo "DEEP OK"
curl -sf -H "Host: www.elmarcel.com" http://localhost:8088/images/gallery/2004_01_03_13_35_42_4138319335.jpg >/dev/null && echo "IMG OK"
curl -s -o /dev/null -w '%{http_code}\n' -H "Host: www.elmarcel.com" http://localhost:8088/nope   # expect 404
```

Expected: `HOME OK`, `DEEP OK`, `IMG OK`, `404`.

- [ ] **Step 3: Tear down the smoke stack**

```bash
cd "${TMPDIR:-/tmp}/elmarcel-local-deploy/smoke" && docker compose down
```

- [ ] **Step 4: Push branch and open the PR**

The PR body must be self-contained (no doc references) with a single copy-pasteable shell block covering setup + test + cutover.

```bash
cd /mnt/d/prg/plum-elmarcel-hetzner
git push -u origin elmarcel-hetzner
gh pr create --title "feat: migrate elmarcel.com hosting to Hetzner VPS" --body "$(cat <<'EOF'
Serves the elmarcel.com Hugo site from the Hetzner CX23 via a Caddy Docker
Compose stack at /opt/elmarcel/. The site is built ON the VPS with pinned
hugomods/hugo:0.133.1 into www/site.new, then atomically swapped live.
Caddy handles HTTPS automatically; www is canonical, apex 301-redirects.

Companion change (separate repo, already committed there):
bogartindustries_com_blog restores the 87 MB photo gallery from public/
back to static/images/gallery so clean builds include all photos.

Prereqs: fill VPS_HOST, VPS_USER, VPS_SSH_KEY in .env (keys exist in
.env.example). DNS cutover (step 4 below) is a manual action in the DNS
provider panel; rollback = point A records back to 173.236.200.12.

```bash
# 1. Local end-to-end pipeline test (no VPS touched; needs Docker)
bash scripts/deploy/deploy-elmarcel.sh --local

# 2. One-time VPS prep (installs Docker if absent, creates /opt/elmarcel)
#    Then open ports 80/tcp, 443/tcp, 443/udp in the Hetzner firewall.
bash scripts/deploy/setup-elmarcel-vps.sh

# 3. Deploy: rsync source, build on VPS, swap live, start Caddy.
#    Ends with a port-80 check (308 redirect = Caddy up; certs come after DNS).
bash scripts/deploy/deploy-elmarcel.sh

# 4. MANUAL: set A records for elmarcel.com and www.elmarcel.com to the VPS IP.

# 5. After DNS propagates, full HTTPS verification:
bash scripts/deploy/deploy-elmarcel.sh --check
```

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Post-merge execution (not part of the PR)

Deployment itself happens after merge, from main, with the user's real `.env`:
run PR steps 2–5 in order. The user performs the DNS flip (step 4) manually.
DreamHost stays untouched as warm standby until the user decides to cancel.

## Self-review notes

- Spec coverage: source repair (Task 1), compose stack (Task 2), VPS prep (Task 3), deploy script with atomic swap + verification (Task 4), serving smoke test + cutover runbook in PR (Task 5). Cutover/rollback live in the PR body per user convention.
- `--check` implements every post-cutover check in the spec: HTTPS www content, https RSS URLs, deep post, gallery image, HTTP→HTTPS (308), apex→www (301), 404 page.
- Names consistent across tasks: `remote()`, `/opt/elmarcel/{src,www/site}`, `hugomods/hugo:0.133.1`, `${TMPDIR:-/tmp}/elmarcel-local-deploy`.
- Known execution-time risks flagged in Global Constraints: `hugomods/hugo:0.133.1` tag availability (STOP if missing), `static/images/gallery` precondition guard in both Task 1 and the deploy script.
