#!/bin/bash
# Logging utility for all Plum scripts
# Usage: source scripts/common/logging.sh

# Configuration
LOGS_DIR="${LOGS_DIR:-$HOME/.logs/plum}"
SCRIPT_NAME="${1:-unknown}"
LOG_FILE="$LOGS_DIR/$SCRIPT_NAME/$(date +%Y-%m-%d).log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Log levels
LOG_INFO="INFO"
LOG_WARN="WARN"
LOG_ERROR="ERROR"

# Function: log message
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Convenience functions
log_info() { log "$LOG_INFO" "$@"; }
log_warn() { log "$LOG_WARN" "$@"; }
log_error() { log "$LOG_ERROR" "$@"; }

# Function: log and exit on error
log_die() {
    log "$LOG_ERROR" "$@"
    exit 1
}

export LOG_FILE LOGS_DIR SCRIPT_NAME
