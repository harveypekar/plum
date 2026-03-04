---
paths:
  - "projects/coach/**"
---

# Coach — Running Analysis Tool

Single Python script (`analyze.py`, ~1960 lines). Generates self-contained HTML training reports with AI coaching commentary.

## Commands

```bash
python analyze.py              # Full report with AI coaching
python analyze.py --no-ai      # Report without AI (faster)
python fetch_garmin.py          # Incremental Garmin data fetch
python fetch_garmin.py --full   # Force re-fetch all Garmin data
```

## Architecture

Pipeline: data loading → filtering (runs >2km, >10min) → metrics computation → AI coaching → HTML generation.

- Zero dependencies for analyze.py (stdlib only, Python 3.10+)
- fetch_garmin.py requires `garminconnect` (pip install)
- All charts are inline SVG, all styling inline CSS, no JS frameworks
- AI commentary shells out to `claude --model sonnet`; strips `CLAUDECODE` env var to avoid recursion
- `metrics.json` saved as intermediate artifact for debugging

## Data Layout

- Input: `../sourceData/intervals/activities.json` + `../sourceData/intervals/streams/{id}.json`
- Garmin: `data/garmin/` (activities, daily wellness, weekly aggregates, profile, devices, gear)
- Garmin tokens cached in `data/garmin/.tokens/` — never store credentials on disk

## Key Constants

`RACE_DATE`, `RACE_NAME`, `COACH_PERSONAS`, `TIME_SECTIONS`, `GLOSSARY` — all at top of analyze.py.

## Domain Context

See `research.md` for sport-science rationale (cardiac drift, CTL/ATL/TSB model).
