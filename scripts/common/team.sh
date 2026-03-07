#!/bin/bash
# Launch a tmux-based Claude agent team
# Usage: team.sh [task1 "description"] [task2 "description"] ...
#   or:  team.sh                     (interactive — opens empty panes)
#
# Examples:
#   team.sh "Fix auth bug" "Add unit tests for coach"
#   team.sh                 # 2 empty panes, you type the prompts
#
# Tmux cheatsheet (printed on launch):
#   Ctrl-b %       Split pane vertically
#   Ctrl-b "       Split pane horizontally
#   Ctrl-b arrow   Navigate between panes
#   Ctrl-b z       Zoom/unzoom current pane
#   Ctrl-b [       Scroll mode (q to exit)
#   Ctrl-b d       Detach (agents keep running!)
#   tmux attach -t plum-team   Reattach
#   tmux kill-session -t plum-team   Kill all agents

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SESSION="plum-team"
WORKTREE_BASE="/tmp/plum-team"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_cheatsheet() {
    echo ""
    echo -e "${BOLD}${CYAN}=== Tmux Agent Team Cheatsheet ===${NC}"
    echo ""
    echo -e "  ${GREEN}Ctrl-b %${NC}       Split pane vertically"
    echo -e "  ${GREEN}Ctrl-b \"${NC}       Split pane horizontally"
    echo -e "  ${GREEN}Ctrl-b arrow${NC}   Navigate between panes"
    echo -e "  ${GREEN}Ctrl-b z${NC}       Zoom/unzoom current pane"
    echo -e "  ${GREEN}Ctrl-b [${NC}       Scroll mode (q to exit)"
    echo -e "  ${GREEN}Ctrl-b d${NC}       Detach (agents keep running!)"
    echo ""
    echo -e "  ${GREEN}tmux attach -t ${SESSION}${NC}        Reattach"
    echo -e "  ${GREEN}tmux kill-session -t ${SESSION}${NC}  Kill all agents"
    echo ""
    echo -e "${BOLD}${CYAN}=== Worktrees ===${NC}"
    echo ""
}

cleanup_worktrees() {
    echo -e "${CYAN}Cleaning up team worktrees...${NC}"
    for wt in "$WORKTREE_BASE"-*; do
        [ -d "$wt" ] || continue
        branch=$(basename "$wt")
        echo "  Removing worktree: $wt"
        git -C "$REPO_ROOT" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
        git -C "$REPO_ROOT" branch -D "$branch" 2>/dev/null || true
    done
    echo -e "${GREEN}Done.${NC}"
}

# Handle --cleanup flag
if [ "${1:-}" = "--cleanup" ]; then
    cleanup_worktrees
    exit 0
fi

# Check dependencies
if ! command -v tmux &>/dev/null; then
    echo -e "${RED}tmux not found. Install with: sudo apt install tmux${NC}"
    exit 1
fi

if ! command -v claude &>/dev/null; then
    echo -e "${RED}claude CLI not found.${NC}"
    exit 1
fi

# Kill existing session if any
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo -e "${RED}Session '$SESSION' already exists.${NC}"
    echo "  tmux attach -t $SESSION   (to reattach)"
    echo "  tmux kill-session -t $SESSION   (to kill it first)"
    exit 1
fi

# Collect tasks
tasks=("$@")
num_agents=${#tasks[@]}

# Default: 2 interactive agents if no tasks given
if [ "$num_agents" -eq 0 ]; then
    num_agents=2
fi

# Create worktrees and build pane commands
declare -a worktree_dirs
for i in $(seq 1 "$num_agents"); do
    branch="plum-team-agent${i}"
    wt_dir="${WORKTREE_BASE}-agent${i}"

    # Clean up stale worktree if it exists
    if [ -d "$wt_dir" ]; then
        git -C "$REPO_ROOT" worktree remove --force "$wt_dir" 2>/dev/null || rm -rf "$wt_dir"
        git -C "$REPO_ROOT" branch -D "$branch" 2>/dev/null || true
    fi

    git -C "$REPO_ROOT" worktree add "$wt_dir" -b "$branch" 2>/dev/null
    worktree_dirs+=("$wt_dir")
done

# Print cheatsheet before entering tmux
print_cheatsheet
for i in $(seq 1 "$num_agents"); do
    idx=$((i - 1))
    echo -e "  Agent $i: ${GREEN}${worktree_dirs[$idx]}${NC} (branch: plum-team-agent${i})"
done
echo ""

# Build tmux session
# First pane: agent 1
first_dir="${worktree_dirs[0]}"
if [ ${#tasks[@]} -gt 0 ]; then
    tmux new-session -d -s "$SESSION" -c "$first_dir" "claude -p '${tasks[0]}'; echo '--- Agent 1 done. Press enter to close ---'; read"
else
    tmux new-session -d -s "$SESSION" -c "$first_dir" "claude"
fi

# Additional panes
for i in $(seq 2 "$num_agents"); do
    idx=$((i - 1))
    dir="${worktree_dirs[$idx]}"
    if [ ${#tasks[@]} -ge "$i" ]; then
        tmux split-window -h -t "$SESSION" -c "$dir" "claude -p '${tasks[$idx]}'; echo '--- Agent $i done. Press enter to close ---'; read"
    else
        tmux split-window -h -t "$SESSION" -c "$dir" "claude"
    fi
    # Rebalance panes after each split
    tmux select-layout -t "$SESSION" tiled 2>/dev/null || true
done

echo -e "${BOLD}Attaching to session. ${CYAN}Ctrl-b d${NC} to detach.${BOLD}${NC}"
echo -e "Run ${GREEN}$0 --cleanup${NC} when done to remove worktrees."
echo ""

# Attach
tmux attach -t "$SESSION"
