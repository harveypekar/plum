# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Running coach analysis tool. A single Python script (`analyze.py`) reads Intervals.icu export data, computes training metrics, calls Claude CLI for multi-persona coaching commentary, and generates a self-contained HTML report.

## Commands

```bash
# Generate full report (with AI coaching commentary)
python analyze.py

# Generate report without AI commentary (faster, no Claude CLI needed)
python analyze.py --no-ai

# Generate report without RAG context (model's base knowledge only)
python analyze.py --no-rag
```

Requires Python 3.10+. AI commentary requires the `claude` CLI. RAG requires `sentence-transformers` and `pymupdf`.

## Architecture

`analyze.py` (~1960 lines) is the entire application. The pipeline is:

1. **Data loading** — reads `../sourceData/intervals/activities.json` and per-activity stream files from `../sourceData/intervals/streams/`
2. **Filtering** — keeps runs >2km and >10min
3. **Metrics computation** (`build_metrics()`) — produces a metrics dict covering: last run analysis, weekly/monthly volume, CTL/ATL/TSB fitness model, pace trends, HR analysis, cadence/stride, and a training plan projection to race day
4. **AI coaching** (`get_panel_discussions()`) — shells out to `claude --model sonnet` for 4 time-horizon sections (last run, last week, last month, race prep), each discussed by 4 personas (ultrarunning coach, marathon coach, backyard ultra champion, sports physio)
5. **HTML generation** (`build_report()`) — assembles inline SVG charts (`SvgChart` class), metric tables, and AI panel discussions into a dark-themed self-contained HTML file

Key design choices:
- Zero dependencies: all charts are inline SVG, all styling is inline CSS, no JS frameworks
- The `CLAUDECODE` env var is stripped before calling `claude` CLI to avoid recursion
- Prior panel discussions are fed as context to subsequent sections for conversational continuity
- RAG retrieves relevant research chunks from pgvector and injects them into coaching prompts
- `metrics.json` is saved as an intermediate artifact for debugging/reuse

## Data Layout

Input data lives one directory up at `../sourceData/intervals/`:
- `activities.json` — full activity list from Intervals.icu
- `streams/{activity_id}.json` — per-activity time series (HR, pace, cadence, altitude, etc.)

## Key Constants

- `RACE_DATE` and `RACE_NAME` at the top of `analyze.py` control the training plan target
- `COACH_PERSONAS` dict defines the 4 AI coaching perspectives and their display colors
- `TIME_SECTIONS` list defines the 4 discussion time horizons and which metrics each receives
- `GLOSSARY` dict provides tooltip definitions for running-specific terms in AI output

## Garmin Data Fetcher

```bash
# Fetch all data (incremental — skips already-fetched data)
python fetch_garmin.py

# Force re-fetch everything
python fetch_garmin.py --full
```

Requires: `pip install garminconnect`. Prompts for Garmin email/password on first run, caches OAuth tokens in `data/garmin/.tokens/` for subsequent runs. Never stores credentials on disk.

Fetches everything the Garmin Connect API offers: activities (with 10 sub-endpoints each), 26 daily wellness endpoints, weekly aggregates, profile, devices, gear, badges, challenges, goals, workouts, blood pressure, weight, and progress summaries. All responses saved as raw JSON to `data/garmin/`.

Key directories under `data/garmin/`:
- `activities/list.json` + `activities/{id}/` — activity summaries, details, splits, HR zones, weather, gear
- `daily/{date}/` — 26 files per date (HR, sleep, stress, HRV, SpO2, body battery, training readiness, etc.)
- `weekly/` — steps, stress, intensity minutes (52 weeks)
- `profile/`, `devices/`, `gear/`, `badges/`, `challenges/`, `goals/`, `workouts/`

## RAG Knowledge Base

`rag.py` + `db.py` provide a RAG pipeline that grounds AI coaching in the project's research corpus. Uses pgvector for similarity search and `all-MiniLM-L6-v2` for local embeddings (no API keys).

```bash
# Ingest all research files (incremental — skips unchanged files)
python rag.py --ingest

# Query the knowledge base
python rag.py "cardiac drift threshold"

# Show ingestion stats
python rag.py --stats
```

**How it integrates:** `analyze.py`'s `get_panel_discussions()` calls `rag.query()` before each Claude CLI invocation. The query is built from the section's focus text + notable metric signals (e.g., high HR drift triggers "cardiac drift" retrieval). Retrieved research chunks are injected as `RELEVANT COACHING KNOWLEDGE` in the prompt. Chunks are deduplicated across sections via `exclude_chunk_ids`.

**Data flow:** `research/summary/*.md` + `research/source/*.md` + `research/source/*.pdf` → chunked → embedded (384-dim) → stored in `research_chunks` table → cosine similarity search at query time.

**Dependencies:** `sentence-transformers` (pulls in PyTorch), `pymupdf`, `psycopg2`. Requires the Postgres container with pgvector (`projects/db/docker-compose.yml`).

## Domain Context

See `research.md` for the sport-science rationale behind cardiac drift thresholds, CTL/ATL/TSB model, and other analysis decisions.
