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
BASE_URL="https://www.elmarcel.com/blog/"
CANONICAL_HOST="www.elmarcel.com"
APEX_HOST="elmarcel.com"
GALLERY_MIN_FILES=118
DEEP_POST_PATH="/blog/posts/2008_10_19_6_changelog/"
# On-disk path is unprefixed (Hugo's output layout doesn't nest under /blog;
# Caddy's handle_path strips the /blog prefix when serving). SAMPLE_IMAGE_PATH
# is the public URL path; GALLERY_SAMPLE_REL is the same file relative to the
# built site root, used for filesystem checks in build-and-swap.sh.
GALLERY_SAMPLE_REL="/images/gallery/2004_01_03_13_35_42_4138319335.jpg"
SAMPLE_IMAGE_PATH="/blog${GALLERY_SAMPLE_REL}"

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
    curl_expect "https://${CANONICAL_HOST}/" 301
    curl_expect "https://${CANONICAL_HOST}/blog" 301
    curl_contains "https://${CANONICAL_HOST}/blog/" "PACIFISHTICKS"
    curl_contains "https://${CANONICAL_HOST}/blog/index.xml" "https://www.elmarcel.com"
    curl_expect "https://${CANONICAL_HOST}${DEEP_POST_PATH}" 200
    curl_expect "https://${CANONICAL_HOST}${SAMPLE_IMAGE_PATH}" 200
    # Caddy auto-HTTPS redirect is 308; Caddyfile 'redir ... permanent' is 301.
    curl_expect "http://${CANONICAL_HOST}/" 308
    curl_expect "https://${APEX_HOST}/" 301
    curl_expect "https://${CANONICAL_HOST}/blog/definitely-not-a-page" 404
    log_info "All post-cutover checks passed"
    echo "All post-cutover checks passed."
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
# NOTE (applies to both branches below): build-and-swap.sh sources
# "../../common/logging.sh" relative to its own location (it lives at
# scripts/deploy/lib/ in this repo, two levels below scripts/). Staging it
# must mirror that same two-level nesting under REMOTE_ROOT
# (REMOTE_ROOT/deploy/lib/..) so its relative source path still resolves to
# REMOTE_ROOT/common/logging.sh. Do not flatten this back to
# REMOTE_ROOT/lib — that breaks the relative source and build-and-swap.sh
# fails immediately on the target.
if [ "$MODE" = "--local" ]; then
    # On the real VPS, setup-elmarcel-vps.sh pre-creates www/ as the SSH user
    # before any deploy runs. Mirror that here: if www/ doesn't exist yet,
    # Docker's bind-mount auto-creates it as root, poisoning ownership of
    # every file the Hugo container writes underneath it.
    mkdir -p "$REMOTE_ROOT/www" "$REMOTE_ROOT/deploy/lib" "$REMOTE_ROOT/common"
    rsync -az "$COMPOSE_SRC/docker-compose.yml" "$COMPOSE_SRC/Caddyfile" \
        "$REMOTE_ROOT/"
    rsync -az "$SCRIPT_DIR/lib/build-and-swap.sh" "$REMOTE_ROOT/deploy/lib/"
    rsync -az "$SCRIPT_DIR/../common/logging.sh" "$REMOTE_ROOT/common/"
    rsync -az --delete \
        "$SITE_SRC/content" "$SITE_SRC/static" "$SITE_SRC/layouts" \
        "$SITE_SRC/archetypes" "$SITE_SRC/config.toml" \
        "$REMOTE_ROOT/src/"
else
    # rsync only auto-creates the final path component on the remote side, so
    # pre-create deploy/lib (two levels) and common explicitly before
    # rsyncing into them.
    remote "mkdir -p $REMOTE_ROOT/deploy/lib $REMOTE_ROOT/common"
    rsync -az -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" \
        "$COMPOSE_SRC/docker-compose.yml" "$COMPOSE_SRC/Caddyfile" \
        "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/"
    rsync -az -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" \
        "$SCRIPT_DIR/lib/build-and-swap.sh" "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/deploy/lib/"
    rsync -az -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" \
        "$SCRIPT_DIR/../common/logging.sh" "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/common/"
    rsync -az --delete -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" \
        "$SITE_SRC/content" "$SITE_SRC/static" "$SITE_SRC/layouts" \
        "$SITE_SRC/archetypes" "$SITE_SRC/config.toml" \
        "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/src/"
fi

log_info "Building and swapping on target"
remote "TARGET_ROOT=$REMOTE_ROOT SRC_DIR=$REMOTE_ROOT/src HUGO_IMAGE=$HUGO_IMAGE \
    BASE_URL=$BASE_URL GALLERY_MIN_FILES=$GALLERY_MIN_FILES \
    GALLERY_SAMPLE_REL=$GALLERY_SAMPLE_REL \
    bash $REMOTE_ROOT/deploy/lib/build-and-swap.sh" \
    || log_die "build-and-swap failed on target; see target's ~/.logs/plum/build-and-swap/ for details"

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
