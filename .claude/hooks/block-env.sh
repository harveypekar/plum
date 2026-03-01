#!/bin/bash
# PreToolUse hook: block edits to .env files
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

if [[ "$file_path" == */.env || "$file_path" == */.env.* ]]; then
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: .env files contain secrets and must never be edited by Claude. Edit .env manually."
  }
}
EOF
  exit 0
fi
