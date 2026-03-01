#!/bin/bash
# PostToolUse hook: run shellcheck on .sh files after edit
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

# Only lint shell scripts
if [[ ! "$file_path" =~ \.sh$ ]]; then
  exit 0
fi

# Check file exists (might have been deleted)
if [[ ! -f "$file_path" ]]; then
  exit 0
fi

errors=$(shellcheck "$file_path" 2>&1) || true

if [[ -n "$errors" ]]; then
  # Escape for JSON
  escaped=$(echo "$errors" | head -30 | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "ShellCheck warnings in $file_path:\n${escaped}"
  }
}
EOF
else
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "ShellCheck passed for $file_path"
  }
}
EOF
fi
exit 0
