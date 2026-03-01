#!/bin/bash
# PreToolUse hook: block dangerous git commands inside worktrees
input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# Only care about Bash tool calls with a command
if [[ -z "$command" ]]; then
  exit 0
fi

# Check if we're inside a worktree
cwd=$(pwd)
if [[ "$cwd" != */.claude/worktrees/* ]]; then
  exit 0
fi

# Block dangerous commands
if echo "$command" | grep -qE '(git\s+push|git\s+merge|git\s+checkout\s+(main|master)|gh\s+pr\s+create)'; then
  reason=$(echo "$command" | grep -oE '(git\s+push|git\s+merge|git\s+checkout\s+(main|master)|gh\s+pr\s+create)' | head -1)
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: '${reason}' is not allowed inside a worktree. Commit your work on this branch — the user will review and merge manually."
  }
}
EOF
  exit 0
fi
