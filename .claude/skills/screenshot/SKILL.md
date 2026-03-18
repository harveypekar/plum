---
name: screenshot
description: Use when the user invokes /screenshot to view the most recent screenshot from the scratch folder
---

# Screenshot

Find and display the newest screenshot from `C:\drive\scratch`.

## Instructions

1. List PNG files matching the screenshot naming pattern (date + timestamp + window title) and pick the newest one:
   ```bash
   ls -t /mnt/c/drive/scratch/*.png 2>/dev/null | head -1
   ```
2. If no PNG files are found, tell the user and stop.
3. Use the **Read** tool to display the image file at the path returned.
4. Tell the user the filename (just the basename, not the full path) and show the image.
