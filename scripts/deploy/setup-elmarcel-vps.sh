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

log_info "Setting up bare repo for push-to-deploy"
remote "git init --bare $REMOTE_ROOT/repo.git"
remote "mkdir -p $REMOTE_ROOT/deploy/lib $REMOTE_ROOT/common"

# shellcheck disable=SC2029  # client-side expansion is intentional
scp -i "$VPS_SSH_KEY" "$SCRIPT_DIR/hooks/post-receive-elmarcel.sh" \
    "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/repo.git/hooks/post-receive"
remote "chmod +x $REMOTE_ROOT/repo.git/hooks/post-receive"

# build-and-swap.sh and logging.sh: the hook calls these directly (no SSH
# indirection needed since it already runs on the VPS), so they need to be
# resident there, not just staged transiently by a deploy run.
# shellcheck disable=SC2029
scp -i "$VPS_SSH_KEY" "$SCRIPT_DIR/lib/build-and-swap.sh" \
    "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/deploy/lib/"
# shellcheck disable=SC2029
scp -i "$VPS_SSH_KEY" "$SCRIPT_DIR/../common/logging.sh" \
    "${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/common/"

echo "Bare repo ready at ${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/repo.git"
echo "Add it as a remote from the blog repo checkout:"
echo "  git remote add hetzner ${VPS_USER}@${VPS_HOST}:${REMOTE_ROOT}/repo.git"

log_info "VPS setup complete."
echo "VPS setup complete."
echo ""
echo "MANUAL STEP REMAINING: ensure ports 80/tcp, 443/tcp and 443/udp are open"
echo "in the Hetzner Cloud firewall (console.hetzner.cloud) or host firewall."
