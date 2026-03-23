#!/bin/bash
# PreToolUse hook: ensure Claude commits under its own identity, not the user's.
# Denies any `git commit` that doesn't include --author with Claude's email.
input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

if [[ -z "$command" ]]; then
  exit 0
fi

# Only check git commit commands (account for flags like -C between git and commit)
if ! echo "$command" | grep -qE 'git\s+(-\S+\s+\S+\s+)*commit'; then
  exit 0
fi

# Allow if --author is already set to Claude's identity
if echo "$command" | grep -qE -- '--author=.*noreply@anthropic\.com'; then
  exit 0
fi

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: git commit must include --author=\"Claude <noreply@anthropic.com>\". Re-run with the --author flag."
  }
}
EOF
exit 0
