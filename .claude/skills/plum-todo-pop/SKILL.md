---
name: plum-todo-pop
description: Use when the user invokes /plum-todo-pop to pick a GitHub Issue and execute it
---

# Todo Pop

Pick a GitHub Issue and execute it as a task.

## Current open issues

!`gh issue list --state open --limit 20 --json number,title,labels --template '{{range .}}#{{.number}} {{.title}} [{{range .labels}}{{.name}} {{end}}]{{"\n"}}{{end}}'`

## Instructions

**If an argument was provided** (e.g., `/plum-todo-pop 42`):
1. Fetch the issue: `gh issue view <number> --json number,title,body`
2. If the issue doesn't exist or is closed, list open issues and ask the user to pick one

**If no argument was provided:**
1. Use the oldest open issue (first in the list above)

**Then:**
1. Tell the user the issue number, title, and body
2. Execute the task fully
3. When the task is complete, close the issue with a comment summarizing what was done:
   ```bash
   gh issue close <number> --comment "Completed: <brief summary of what was done>"
   ```
