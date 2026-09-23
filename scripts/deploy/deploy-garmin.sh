#!/bin/bash
# Deploy the garmin data source stack to the Hetzner VPS, and refresh the
# elmarcel Caddy stack so it picks up the new garmin.elmarcel.com site
# block. Run scripts/deploy/setup-garmin-vps.sh once before the first use.
#
# Usage:
#   bash scripts/deploy/deploy-garmin.sh           # deploy to VPS
#   bash scripts/deploy/deploy-garmin.sh --check   # verify only, no deploy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export SCRIPT_NAME="deploy-garmin"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/logging.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/load-env.sh"

: "${VPS_HOST:?VPS_HOST must be set in .env}"
: "${VPS_USER:?VPS_USER must be set in .env}"
: "${VPS_SSH_KEY:?VPS_SSH_KEY must be set in .env}"
: "${GARMIN_EMAIL:?GARMIN_EMAIL must be set in .env}"
: "${GARMIN_PASSWORD:?GARMIN_PASSWORD must be set in .env}"
: "${GARMIN_WEB_PASSWORD:?GARMIN_WEB_PASSWORD must be set in .env}"
GARMIN_WEB_USER="${GARMIN_WEB_USER:-admin}"
RCLONE_REMOTE="${RCLONE_REMOTE:-hetzner-crypt}"

MODE="${1:-deploy}"
GARMIN_ROOT="/opt/garmin"
ELMARCEL_ROOT="/opt/elmarcel"
PROJECT_SRC="$SCRIPT_DIR/../../projects/garmin"
GARMIN_COMPOSE_SRC="$SCRIPT_DIR/../../docker/garmin"
ELMARCEL_COMPOSE_SRC="$SCRIPT_DIR/../../docker/elmarcel"

remote() {
    # shellcheck disable=SC2029  # client-side expansion is intentional
    ssh -i "$VPS_SSH_KEY" -o BatchMode=yes "${VPS_USER}@${VPS_HOST}" "$@"
}

rsync_up() {
    rsync -az -e "ssh -i $VPS_SSH_KEY -o BatchMode=yes" "$@"
}

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

# Compose's .env format only recognizes the 2-char sequence \' as an escape
# (decoding to a literal '); every other backslash is passed through
# unchanged, and boundary-scanning pairs each \ with whatever character
# follows it. That means a value containing \' as adjacent literal
# characters, or ending in an odd run of trailing backslashes, cannot be
# represented in this grammar at all — verified empirically against
# `docker compose config` (odd-trailing-backslash always either swallows
# the closing quote as an escape, leaving the value unterminated, or a mid
# -string \' pairing closes the string early and strands the rest of the
# line as a parse error). Refuse rather than silently write something
# Compose will misparse or truncate.
env_quote() {
    local val="$1"
    local needle
    needle="$(printf '\\%s' "'")"  # backslash + single-quote, 2 literal chars
    case "$val" in
        *"$needle"*)
            log_die "Value contains a backslash immediately followed by a single quote — this cannot be safely represented in a Compose .env file. Choose a different value."
            ;;
    esac
    local tmp="$val" count=0
    while [[ "$tmp" == *\\ ]]; do
        tmp="${tmp%\\}"
        count=$((count + 1))
    done
    if (( count % 2 == 1 )); then
        log_die "Value ends in an odd number of trailing backslashes — this cannot be safely represented in a Compose .env file. Choose a different value."
    fi
    val="${val//\'/\\\'}"
    printf "'%s'" "$val"
}

if [ "$MODE" = "--check" ]; then
    # Post-cutover verification: DNS has propagated and Caddy holds a real
    # cert by the time someone runs --check (mirrors deploy-elmarcel.sh's
    # run_check, which is also only meant to be run once DNS legitimately
    # points at the VPS), so we can hit the real hostname over HTTPS
    # directly instead of faking it with a Host header over plain HTTP.
    log_info "Checking garmin-web responds through Caddy (HTTPS, real DNS)"
    curl_expect "https://garmin.elmarcel.com/" 200 -u "${GARMIN_WEB_USER}:${GARMIN_WEB_PASSWORD}"
    log_info "OK: garmin.elmarcel.com responds with 200"

    curl_expect "https://garmin.elmarcel.com/" 401
    log_info "OK: garmin.elmarcel.com rejects unauthenticated requests with 401"
    exit 0
fi

# Layout on the VPS mirrors the repo's own docker/garmin + projects/garmin
# relative structure, so docker-compose.yml's relative build context
# (../../projects/garmin) and volume mount (./rclone.conf) resolve exactly
# as they do locally — no path rewriting, no --project-directory override.
log_info "Syncing garmin project source to $GARMIN_ROOT/projects/garmin"
remote "mkdir -p $GARMIN_ROOT/docker/garmin $GARMIN_ROOT/projects/garmin"
rsync_up --delete --exclude data --exclude .venv --exclude __pycache__ --exclude .pytest_cache \
    "$PROJECT_SRC/" "${VPS_USER}@${VPS_HOST}:${GARMIN_ROOT}/projects/garmin/"
rsync_up "$GARMIN_COMPOSE_SRC/docker-compose.yml" "${VPS_USER}@${VPS_HOST}:${GARMIN_ROOT}/docker/garmin/"

log_info "Syncing updated elmarcel Caddy config to $ELMARCEL_ROOT"
rsync_up "$ELMARCEL_COMPOSE_SRC/Caddyfile" "$ELMARCEL_COMPOSE_SRC/docker-compose.yml" \
    "${VPS_USER}@${VPS_HOST}:${ELMARCEL_ROOT}/"

log_info "Checking for rclone config (backup prerequisite)"
if ! remote "test -f $GARMIN_ROOT/docker/garmin/rclone.conf"; then
    log_warn "No rclone config at ${GARMIN_ROOT}/docker/garmin/rclone.conf — the backup cron job will fail until you copy one there. Fetch and the web dashboard are unaffected."
    # docker-compose.yml mounts this path with the short bind-mount syntax
    # (./rclone.conf:/root/.config/rclone/rclone.conf:ro). If nothing exists
    # at this path, Docker auto-creates it as a DIRECTORY on first `up`,
    # which then permanently blocks copying a real rclone.conf file there
    # (can't write a file over a same-named directory) until someone
    # manually `sudo rm -r`s it on the VPS. Pre-create an empty placeholder
    # FILE so Docker's bind mount never falls into that trap.
    remote "test -f $GARMIN_ROOT/docker/garmin/rclone.conf || touch $GARMIN_ROOT/docker/garmin/rclone.conf"
fi

# umask 077 (rather than writing the file then chmod 600 after) means the
# file is never world/group-readable even for the brief window between
# creation and a follow-up chmod.
log_info "Writing garmin .env for docker compose"
Q_GARMIN_EMAIL="$(env_quote "$GARMIN_EMAIL")"
Q_GARMIN_PASSWORD="$(env_quote "$GARMIN_PASSWORD")"
Q_RCLONE_REMOTE="$(env_quote "$RCLONE_REMOTE")"
remote "umask 077 && cat > $GARMIN_ROOT/docker/garmin/.env" <<EOF
GARMIN_EMAIL=${Q_GARMIN_EMAIL}
GARMIN_PASSWORD=${Q_GARMIN_PASSWORD}
RCLONE_REMOTE=${Q_RCLONE_REMOTE}
EOF

# Pipe the plaintext over stdin rather than interpolating it into the
# remote command string as a --plaintext argument: a password containing a
# single quote would break naive shell-quoting of a --plaintext value sent
# over SSH (and worse, could inject commands into the remote shell). Caddy
# reads the plaintext from stdin when --plaintext is omitted, and strips
# the trailing newline before hashing (verified empirically).
log_info "Hashing GARMIN_WEB_PASSWORD for Caddy basicauth"
HASH="$(printf '%s\n' "$GARMIN_WEB_PASSWORD" | remote "docker run --rm -i caddy:2-alpine caddy hash-password")"
[ -n "$HASH" ] || log_die "caddy hash-password returned nothing"

log_info "Writing elmarcel .env with basicauth credentials"
Q_GARMIN_WEB_USER="$(env_quote "$GARMIN_WEB_USER")"
Q_HASH="$(env_quote "$HASH")"
remote "umask 077 && cat > $ELMARCEL_ROOT/.env" <<EOF
GARMIN_WEB_USER=${Q_GARMIN_WEB_USER}
GARMIN_WEB_PASSWORD_HASH=${Q_HASH}
EOF

log_info "Building and starting garmin-web / garmin-cron"
remote "cd $GARMIN_ROOT/docker/garmin && docker compose up -d --build" \
    || log_die "docker compose up failed for garmin stack"

log_info "Refreshing elmarcel Caddy to pick up the new site block"
remote "cd $ELMARCEL_ROOT && docker compose up -d" || log_die "docker compose up failed for elmarcel stack"

# Pre-cutover we cannot fetch content over HTTPS (no cert until DNS points
# here), and even over HTTP, Caddy's automatic HTTPS redirects every
# plain-HTTP request for a managed hostname to HTTPS with a 308 *before* any
# site directive (including basic_auth) runs — confirmed empirically with
# caddy:2-alpine against this exact Caddyfile: a 308 comes back regardless
# of whether credentials are supplied. So a 200/401 check here can never
# pass and can never prove basic_auth is wired up; instead, mirror
# deploy-elmarcel.sh's main-path check: Caddy answering on :80 with its
# auto-HTTPS redirect (308) proves it is up and has loaded the new
# garmin.elmarcel.com site block. Real auth verification happens in
# --check mode, once DNS has actually propagated.
log_info "Verifying garmin.elmarcel.com is routed by Caddy"
curl_expect "http://${VPS_HOST}/" 308 -H "Host: garmin.elmarcel.com"

log_info "Deploy complete"
echo "Deploy complete. garmin.elmarcel.com is serving behind basic auth."
echo ""
echo "If DNS does not yet point garmin.elmarcel.com at this VPS, HTTPS"
echo "certs won't issue yet — the check above only proved Caddy is up and"
echo "routing (308 auto-HTTPS redirect over HTTP with a Host header)."
echo "Once DNS has propagated, run: bash scripts/deploy/deploy-garmin.sh --check"
