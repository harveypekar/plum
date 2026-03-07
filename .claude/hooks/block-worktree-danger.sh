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

# Block dangerous commands (but allow pushing feature branches and creating PRs)
if echo "$command" | grep -qE 'git\s+push.*\s+(main|master)\b|git\s+merge|git\s+checkout\s+(main|master)'; then
  reason=$(echo "$command" | grep -oE 'git\s+push.*\s+(main|master)|git\s+merge|git\s+checkout\s+(main|master)' | head -1)
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: '${reason}' is not allowed inside a worktree."
  }
}
EOF
  exit 0
fi
