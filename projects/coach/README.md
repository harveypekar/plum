# Running Coach Analysis

```
python coach/analyze.py
python coach/analyze.py --no-ai
```

Reads sourceData/intervals/ data, computes metrics, calls Claude for 4 coaching
perspectives (ultrarunning coach, marathon coach, backyard ultra champion, physio),
generates coach/report.html and opens it in your browser.

Options: `--no-ai` skips Claude commentary (faster, no Claude CLI needed).

Requires: Python 3.10+, claude CLI (for AI commentary -- report works without it too).
No pip packages needed.
