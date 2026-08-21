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
    # On the real VPS, setup-elmarcel-vps.sh pre-creates www/ as the SSH user
    # before any deploy runs. Mirror that here: if www/ doesn't exist yet,
    # Docker's bind-mount auto-creates it as root, poisoning ownership of
    # every file the Hugo container writes underneath it.
    mkdir -p "$REMOTE_ROOT/www"
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
# src is NOT mounted :ro: Hugo writes a transient .hugo_build.lock into the
# source dir during the build and errors out on a read-only filesystem.
remote "docker run --rm \
    -v $REMOTE_ROOT/src:/src \
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
