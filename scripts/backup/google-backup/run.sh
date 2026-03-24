#!/bin/bash
# Bash wrapper for google-backup: sources Plum env/logging, activates venv, runs Python.
# Usage: bash scripts/backup/google-backup/run.sh [auth|--all|--gmail|...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUM_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source Plum utilities
export SCRIPT_NAME="google-backup"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/logging.sh"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/load-env.sh"

log_info "google-backup starting with args: $*"

# Activate venv (create if missing)
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    pip install -q -r "$SCRIPT_DIR/requirements.txt"
else
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
fi

# Pass LOG_FILE to Python (set by logging.sh)
export LOG_FILE

# Set PYTHONPATH so python -m google_backup finds the package
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

# Run the Python package, forwarding all args
python -m google_backup "$@"
EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ]; then
    log_info "google-backup completed successfully"
else
    log_error "google-backup exited with code $EXIT_CODE"
fi

exit "$EXIT_CODE"
