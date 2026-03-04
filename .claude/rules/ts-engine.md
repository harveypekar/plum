---
paths:
  - "projects/ts/**"
---

# Twilight Struggle Engine

Board game engine for Twilight Struggle. Mixed C++ core and Python UI/AI layer.

## Structure

- `src/tsc/` — C++ game engine (CMake build)
- `*.py` — Python UI, game logic wrappers, AI player
- `tests/` + `tests.py` — Test suite
- `corpus/` — Game data/card definitions
- `playdek.json` — Card data from Playdek edition

## Commands

```bash
# Build C++ engine
cmake -B build && cmake --build build

# Run game
python main.py

# Run tests
python tests.py
```

## AI Player

Uses Ollama locally (`ollama serve` required). The prompt template (`prompt.md`) instructs the AI to output `/play` commands. See `manual.md` for the terminal server architecture (async TCP + styled text).

## Key Files

- `ts_game.py` — Core game state and rules
- `ts_ui.py` — Terminal UI
- `ts_lookup.py` — Card/country lookups
- `main.py` — Entry point
- `sqlite.db` — Game state persistence
