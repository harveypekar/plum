#!/bin/bash
# One-time Hetzner VPS preparation for the garmin data source stack.
# Creates the shared `edge` Docker network (so garmin-web can be reached by
# the existing elmarcel Caddy instance), /opt/garmin/, and /opt/shared/rclone
# (rclone credentials shared by every data-source project, not garmin-only).
# Idempotent.
# Usage: bash scripts/deploy/setup-garmin-vps.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export SCRIPT_NAME="setup-garmin-vps"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/logging.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../common/load-env.sh"

: "${VPS_HOST:?VPS_HOST must be set in .env}"
: "${VPS_USER:?VPS_USER must be set in .env}"
: "${VPS_SSH_KEY:?VPS_SSH_KEY must be set in .env}"

REMOTE_ROOT="/opt/garmin"

remote() {
    # shellcheck disable=SC2029  # client-side expansion is intentional
    ssh -i "$VPS_SSH_KEY" -o BatchMode=yes "${VPS_USER}@${VPS_HOST}" "$@"
}

log_info "Checking SSH connectivity to ${VPS_USER}@${VPS_HOST}"
remote "true" || log_die "Cannot SSH to ${VPS_USER}@${VPS_HOST} with key $VPS_SSH_KEY"

log_info "Creating shared 'edge' Docker network if absent"
remote "docker network inspect edge >/dev/null 2>&1 || docker network create edge"

# Mirrors the repo's own docker/garmin + projects/garmin relative layout, so
# the compose file's relative build context (../../projects/garmin) resolves
# without any path rewriting at deploy time. Do not flatten this — see
# docker-compose.yml's context path. (The rclone mount is a separate,
# absolute /opt/shared/rclone path, unaffected by this layout.)
log_info "Creating $REMOTE_ROOT/docker/garmin and $REMOTE_ROOT/projects/garmin"
remote "mkdir -p $REMOTE_ROOT/docker/garmin $REMOTE_ROOT/projects/garmin"

# Shared by every data-source project on this VPS (not garmin-specific),
# so a future project's setup only needs this same mkdir, not its own copy.
log_info "Creating /opt/shared/rclone (shared rclone config, used by all data-source projects)"
remote "mkdir -p /opt/shared/rclone"

log_info "VPS setup complete."
echo "VPS setup complete."
echo ""
echo "MANUAL STEP REMAINING: copy your rclone config (containing the"
echo "hetzner-crypt remote credentials, plus any backend key files it"
echo "references) to:"
echo "  ${VPS_USER}@${VPS_HOST}:/opt/shared/rclone/"
echo "This directory is shared across all data-source projects on this VPS."
echo "The sync cron job will fail until this is in place — the fetch and"
echo "web dashboard work fine without it."
