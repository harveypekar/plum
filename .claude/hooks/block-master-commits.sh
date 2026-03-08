#!/bin/bash
# PreToolUse hook: block git commit and git push on master/main branch
# Forces Claude to work in worktrees with feature branches and PRs.
# Allows pushing feature branches even when the hook runs from main's workdir.
input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

if [[ -z "$command" ]]; then
  exit 0
fi

# Only check git commit and git push commands
if ! echo "$command" | grep -qE 'git\s+(commit|push)'; then
  exit 0
fi

# For git push: allow if the command explicitly names a non-main branch
if echo "$command" | grep -qE 'git\s+push'; then
  # If pushing an explicit branch that isn't main/master, allow it
  if echo "$command" | grep -qE 'git\s+push\s+' && \
     ! echo "$command" | grep -qE 'git\s+push.*\s+(main|master)\b'; then
    exit 0
  fi
fi

# Determine the working directory for branch detection
work_dir=$(pwd)
if echo "$command" | grep -qE '^\s*cd\s+'; then
  cd_target=$(echo "$command" | grep -oP '^\s*cd\s+\K\S+' | head -1)
  if [[ -d "$cd_target" ]]; then
    work_dir="$cd_target"
  fi
fi

current_branch=$(git -C "$work_dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
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
