#!/bin/bash
# PreToolUse hook: block git commit and git push on master/main branch
# Forces Claude to work in worktrees with feature branches and PRs.
input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

if [[ -z "$command" ]]; then
  exit 0
fi

# Only check git commit and git push commands
if ! echo "$command" | grep -qE 'git\s+(commit|push)'; then
  exit 0
fi

# Check current branch
current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [[ "$current_branch" == "master" || "$current_branch" == "main" ]]; then
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: git commit/push on $current_branch is not allowed. Use a worktree with a feature branch and create a PR."
  }
}
EOF
  exit 0
fi
