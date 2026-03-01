---
name: plum-todo-push
description: Use when the user invokes /plum-todo-push to create a new GitHub Issue
---

# Todo Push

Create a new GitHub Issue for a task.

## Instructions

1. The user's arguments after `/plum-todo-push` are the task text to add
2. Determine appropriate labels from the standard set:
   - **Category** (pick one): `deploy`, `backup`, `monitor`, `research`, `security`, `common`
   - **Priority** (pick one): `P0-critical`, `P1-high`, `P2-normal`, `P3-low`
3. Create the issue via Bash:
   ```bash
   gh issue create --title "<task text>" --label "<category>" --label "<priority>"
   ```
4. Confirm to the user: show the issue number, title, labels, and URL
