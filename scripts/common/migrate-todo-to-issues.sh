#!/bin/bash
# One-time migration: convert TODO.txt items to GitHub Issues
# Usage: bash scripts/common/migrate-todo-to-issues.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TODO_FILE="$PROJECT_ROOT/TODO.txt"

if [[ ! -f "$TODO_FILE" ]]; then
  echo "ERROR: TODO.txt not found at $TODO_FILE"
  exit 1
fi

if [[ ! -s "$TODO_FILE" ]]; then
  echo "ERROR: TODO.txt is empty, nothing to migrate"
  exit 1
fi

echo "=== Migrating TODO.txt to GitHub Issues ==="
echo ""

while IFS= read -r line; do
  [[ -z "$line" ]] && continue

  old_id="${line%% *}"
  task_text="${line#* }"

  echo "Creating issue for: $old_id — $task_text"

  issue_url=$(gh issue create --title "$task_text" --label migrated --body "Migrated from TODO.txt (old ID: $old_id)")
  issue_num=$(echo "$issue_url" | grep -oE '[0-9]+$')

  printf "  -> Issue #%s\n" "$issue_num"
done < "$TODO_FILE"

echo ""
echo "=== Migration Complete ==="
echo "Run: git rm TODO.txt && git commit -m 'chore: migrate TODO.txt to GitHub Issues'"
