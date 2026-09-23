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

if [ "$MODE" = "--check" ]; then
    log_info "Checking garmin-web responds through Caddy"
    CODE="$(curl -sS -o /dev/null -w '%{http_code}' -u "${GARMIN_WEB_USER}:${GARMIN_WEB_PASSWORD}" \
        -H "Host: garmin.elmarcel.com" "http://${VPS_HOST}/")"
    [ "$CODE" = "200" ] || log_die "Expected HTTP 200 from garmin.elmarcel.com, got $CODE"
    log_info "OK: garmin.elmarcel.com responds with 200"
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
fi

log_info "Writing garmin .env for docker compose"
remote "cat > $GARMIN_ROOT/docker/garmin/.env" <<EOF
GARMIN_EMAIL=${GARMIN_EMAIL}
GARMIN_PASSWORD=${GARMIN_PASSWORD}
RCLONE_REMOTE=${RCLONE_REMOTE}
EOF

log_info "Hashing GARMIN_WEB_PASSWORD for Caddy basicauth"
HASH="$(remote "docker run --rm caddy:2-alpine caddy hash-password --plaintext '${GARMIN_WEB_PASSWORD}'")"
[ -n "$HASH" ] || log_die "caddy hash-password returned nothing"

log_info "Writing elmarcel .env with basicauth credentials"
remote "cat > $ELMARCEL_ROOT/.env" <<EOF
GARMIN_WEB_USER=${GARMIN_WEB_USER}
GARMIN_WEB_PASSWORD_HASH=${HASH}
EOF

log_info "Building and starting garmin-web / garmin-cron"
remote "cd $GARMIN_ROOT/docker/garmin && docker compose up -d --build" \
    || log_die "docker compose up failed for garmin stack"

log_info "Refreshing elmarcel Caddy to pick up the new site block"
remote "cd $ELMARCEL_ROOT && docker compose up -d" || log_die "docker compose up failed for elmarcel stack"

log_info "Verifying garmin.elmarcel.com responds"
CODE="$(curl -sS -o /dev/null -w '%{http_code}' -u "${GARMIN_WEB_USER}:${GARMIN_WEB_PASSWORD}" \
    -H "Host: garmin.elmarcel.com" "http://${VPS_HOST}/")"
[ "$CODE" = "200" ] || log_die "Expected HTTP 200 from garmin.elmarcel.com after deploy, got $CODE"

UNAUTH_CODE="$(curl -sS -o /dev/null -w '%{http_code}' -H "Host: garmin.elmarcel.com" "http://${VPS_HOST}/")"
[ "$UNAUTH_CODE" = "401" ] || log_die "Expected HTTP 401 without credentials, got $UNAUTH_CODE (basicauth is not enforcing!)"

log_info "Deploy complete"
echo "Deploy complete. garmin.elmarcel.com is serving behind basic auth."
echo ""
echo "If DNS does not yet point garmin.elmarcel.com at this VPS, HTTPS"
echo "certs won't issue yet — the checks above used HTTP with a Host header."
