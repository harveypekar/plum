#!/bin/bash
# Load environment variables safely
# Usage: source scripts/common/load-env.sh

# Find .env in same directory as this script or parent directories
find_env_file() {
    local current_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

    while [ "$current_dir" != "/" ]; do
        if [ -f "$current_dir/.env" ]; then
            echo "$current_dir/.env"
            return 0
        fi
        current_dir="$(dirname "$current_dir")"
    done

    return 1
}

# Load .env file
ENV_FILE=$(find_env_file)

if [ -z "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found. Please create it from .env.example"
    exit 1
fi

# Source .env with set -a to preserve variable quoting
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "❌ Error: Cannot read .env file"
    exit 1
fi
