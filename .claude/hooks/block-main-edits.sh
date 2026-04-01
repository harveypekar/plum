#!/usr/bin/env bash
# Block Edit/Write in the main worktree — all work must happen in feature worktrees.
# Allows editing CLAUDE.md and .claude/ config files (meta work is fine on main).

set -euo pipefail

INPUT="$(cat)"
FILE_PATH="$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')"

# No file path means nothing to check
[[ -z "$FILE_PATH" ]] && exit 0

# Allow .claude/ config and CLAUDE.md edits on main
case "$FILE_PATH" in
    */.claude/*|*/CLAUDE.md) exit 0 ;;
esac

# Resolve the repo root for the file being edited
REPO_ROOT="$(cd "$(dirname "$FILE_PATH")" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)" || true
[[ -z "$REPO_ROOT" ]] && exit 0

MAIN_WORKTREE="/mnt/d/prg/plum"

# If editing inside the main worktree, block it
if [[ "$REPO_ROOT" == "$MAIN_WORKTREE" ]]; then
    echo "BLOCKED: Do not edit files in the main worktree ($MAIN_WORKTREE)."
    echo "Create a feature worktree first: git worktree add -b <branch> ../plum-<branch> main"
    exit 2
fi
