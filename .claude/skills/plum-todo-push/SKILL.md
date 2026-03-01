---
name: plum-todo-push
description: Use when the user invokes /plum-todo-push to append a new task to the end of TODO.txt
---

# Todo Push

Append a new task to the end of TODO.txt.

## Instructions

1. The user's arguments after `/todo-push` are the task text to add
2. Generate a random 6-letter lowercase ID: run `cat /dev/urandom | tr -dc 'a-z' | head -c 6` via Bash
3. Read TODO.txt to get the current contents
4. Append the line as `<id> <task text>` (e.g., `kxmvqf Fix the login bug`)
5. Confirm to the user what was added (including the ID) and show the updated TODO.txt
