#!/bin/bash
# Pull and decrypt WhatsApp backup from Android device via adb
# Usage: bash projects/backup/whatsapp-pull.sh
#
# Prerequisites:
#   - adb installed and phone connected with USB debugging enabled
#   - pip install wa-crypt-tools
#
# The script will:
#   1. Pull the encrypted backup from the phone
#   2. Prompt you for the backup password
#   3. Decrypt the database
#   4. Show a summary of the decrypted data

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUM_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

export SCRIPT_NAME="whatsapp-pull"
# shellcheck disable=SC1091
source "$PLUM_ROOT/scripts/common/logging.sh"

BACKUP_DIR="$HOME/bak/whatsapp"
PHONE_DB_PATH="/sdcard/Android/media/com.whatsapp/WhatsApp/Databases"
ENCRYPTED_FILE="$BACKUP_DIR/msgstore.db.crypt15"
DECRYPTED_FILE="$BACKUP_DIR/msgstore.db"

# Verify adb is available
if ! command -v adb &>/dev/null; then
    log_die "adb not found. Install Android SDK platform-tools."
fi

# Verify wa-crypt-tools is available
if ! command -v wacreator &>/dev/null; then
    log_die "wa-crypt-tools not found. Install with: pip install wa-crypt-tools"
fi

# Check phone is connected
if ! adb devices | grep -q "device$"; then
    log_die "No Android device found. Connect phone and enable USB debugging."
fi

mkdir -p "$BACKUP_DIR"

# Pull encrypted backup
log_info "Pulling encrypted backup from phone..."
if ! adb pull "$PHONE_DB_PATH/msgstore.db.crypt15" "$ENCRYPTED_FILE"; then
    log_die "Failed to pull backup. Is WhatsApp installed?"
fi
log_info "Backup saved to $ENCRYPTED_FILE"

# Prompt for password and attempt decryption
echo ""
echo "Enter your WhatsApp backup password (Ctrl+C to cancel):"
read -r -s PASSWORD

log_info "Attempting decryption..."
if wacreator decrypt --password "$PASSWORD" "$ENCRYPTED_FILE" "$DECRYPTED_FILE" 2>&1; then
    log_info "Decryption successful: $DECRYPTED_FILE"

    # Show summary
    if command -v sqlite3 &>/dev/null; then
        MSG_COUNT=$(sqlite3 "$DECRYPTED_FILE" "SELECT count(*) FROM messages;" 2>/dev/null || echo "unknown")
        CHAT_COUNT=$(sqlite3 "$DECRYPTED_FILE" "SELECT count(DISTINCT key_remote_jid) FROM messages;" 2>/dev/null || echo "unknown")
        echo ""
        echo "=== WhatsApp Backup Summary ==="
        echo "Messages: $MSG_COUNT"
        echo "Chats:    $CHAT_COUNT"
        echo "Database: $DECRYPTED_FILE"
        echo "==============================="
    fi
else
    log_error "Decryption failed. Wrong password?"
    rm -f "$DECRYPTED_FILE"
    exit 1
fi
