---
name: plum-todo-pop
description: Use when the user invokes /plum-todo-pop to pop the first task from TODO.txt and execute it
---

# Todo Pop

Pop a task from TODO.txt and execute it.

## Current TODO.txt contents

!`cat TODO.txt`

## Instructions

Each line has the format `<id> <task text>` (e.g., `kxmvqf Fix the login bug`).

**If an argument was provided** (e.g., `/plum-todo-pop tcmtfr`):
1. Find the line whose ID matches the argument
2. If no match, list all available IDs and ask the user to pick one

**If no argument was provided:**
1. Use the first line of TODO.txt

**Then:**
1. Remove that line from TODO.txt using the Edit tool (keep all remaining lines intact)
2. Tell the user the task ID and task text
3. Execute the task fully
