#!/bin/bash
# shellcheck disable=SC2016
# Tests for enforce-claude-author.sh hook
HOOK="$(dirname "$0")/../enforce-claude-author.sh"
pass=0
fail=0

assert_blocked() {
  local desc="$1" input="$2"
  output=$(echo "$input" | bash "$HOOK" 2>&1)
  if echo "$output" | grep -q '"permissionDecision": "deny"'; then
    echo "PASS: $desc"
    ((pass++))
  else
    echo "FAIL: $desc — expected BLOCKED, got: $output"
    ((fail++))
  fi
}

assert_allowed() {
  local desc="$1" input="$2"
  output=$(echo "$input" | bash "$HOOK" 2>&1)
  if [[ -z "$output" ]] || ! echo "$output" | grep -q '"permissionDecision": "deny"'; then
    echo "PASS: $desc"
    ((pass++))
  else
    echo "FAIL: $desc — expected ALLOWED, got: $output"
    ((fail++))
  fi
}

# --- BLOCKED cases ---

assert_blocked "bare git commit" \
  '{"tool_input":{"command":"git commit -m \"feat: add feature\""}}'

assert_blocked "git commit with Co-Authored-By but no --author" \
  '{"tool_input":{"command":"git commit -m \"$(cat <<'\''EOF'\''\nfeat: stuff\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>\nEOF\n)\""}}'

assert_blocked "git commit --amend without author" \
  '{"tool_input":{"command":"git commit --amend -m \"fix: typo\""}}'

assert_blocked "cd into worktree then git commit" \
  '{"tool_input":{"command":"cd /tmp/worktree && git commit -m \"feat: thing\""}}'

assert_blocked "git -C path commit without author" \
  '{"tool_input":{"command":"git -C /tmp/worktree commit -m \"feat: thing\""}}'

assert_blocked "wrong author email" \
  '{"tool_input":{"command":"git commit --author=\"Someone <someone@example.com>\" -m \"feat: x\""}}'

# --- ALLOWED cases ---

assert_allowed "commit with correct --author" \
  '{"tool_input":{"command":"git commit --author=\"Claude <noreply@anthropic.com>\" -m \"feat: add feature\""}}'

assert_allowed "commit with author in worktree" \
  '{"tool_input":{"command":"cd /tmp/wt && git commit --author=\"Claude <noreply@anthropic.com>\" -m \"fix: stuff\""}}'

assert_allowed "git -C with correct author" \
  '{"tool_input":{"command":"git -C /tmp/wt commit --author=\"Claude <noreply@anthropic.com>\" -m \"feat: x\""}}'

assert_allowed "non-commit git command" \
  '{"tool_input":{"command":"git status"}}'

assert_allowed "git push (not a commit)" \
  '{"tool_input":{"command":"git push origin feat/branch"}}'

assert_allowed "git log (not a commit)" \
  '{"tool_input":{"command":"git log --oneline -10"}}'

assert_allowed "empty command" \
  '{"tool_input":{}}'

assert_allowed "non-git bash command" \
  '{"tool_input":{"command":"ls -la"}}'

echo ""
echo "Results: $pass passed, $fail failed"
[[ "$fail" -eq 0 ]]
