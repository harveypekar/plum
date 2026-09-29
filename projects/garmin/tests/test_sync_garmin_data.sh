#!/bin/bash
# Test that sync_garmin_data.sh aborts before touching the network when the
# configured rclone remote does not resolve to a crypt backend.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PROJECT_DIR/../.." && pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/test/test-helpers.sh"

print_header "sync_garmin_data.sh: abort on non-crypt remote"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

mkdir -p "$WORKDIR/bin" "$WORKDIR/data/garmin"
echo '{}' > "$WORKDIR/data/garmin/status.json"

# Fake rclone: reports the remote as type "sftp" (not crypt) and fails
# loudly if the script tries to use it for anything beyond the config check
# — proves the script aborts before any sync step runs.
cat > "$WORKDIR/bin/rclone" <<'EOF'
#!/bin/bash
if [ "$1" = "config" ] && [ "$2" = "show" ]; then
    echo "type = sftp"
    exit 0
fi
echo "rclone should not be invoked beyond the config check" >&2
exit 1
EOF
chmod +x "$WORKDIR/bin/rclone"

set +e
PATH="$WORKDIR/bin:$PATH" GARMIN_DATA_DIR="$WORKDIR/data/garmin" RCLONE_REMOTE="hetzner-crypt" \
    bash "$PROJECT_DIR/sync_garmin_data.sh" > "$WORKDIR/out.log" 2>&1
EXIT_CODE=$?
set -e

assert_eq "exits non-zero on non-crypt remote" "1" "$EXIT_CODE"
assert_contains "abort message names the wrong remote type" "$(cat "$WORKDIR/out.log")" "not type 'crypt'"

if [ "$TEST_FAILURES" -gt 0 ]; then
    echo "FAILED: $TEST_FAILURES assertion(s)"
    exit 1
fi
echo "All assertions passed."
