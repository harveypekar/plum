#!/bin/bash
# Test script: verify logging works

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/logging.sh" "test-logging"

log_info "Testing logging infrastructure"
log_info "Log file: $LOG_FILE"
log_warn "This is a warning"
log_error "This is an error (but not fatal)"
log_info "Test complete"

echo ""
echo "✅ Log file created at: $LOG_FILE"
cat "$LOG_FILE"
