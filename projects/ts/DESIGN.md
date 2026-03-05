# Twilight Struggle Engine — Design

## Goal

Implementation of Twilights Struggle that has a LLM (ollama) AI player, a train RL player, a random player, and allows a human player. C++ game engine for state and rules, Python terminal server for UI and running games.

## Architecture

```
┌──────────────┐     ┌────────────────┐     ┌──────────┐
│  C++ Engine  │◄───►│  Python Server │◄───►│ Terminal │
│  (rules,     │     │  (TCP, styled  │     │ (player) │
│   state)     │     │   text, AI)    │     │          │
└──────────────┘     └───────┬────────┘     └──────────┘
                             │
                     ┌───────▼────────┐
                     │  Ollama (LLM)  │
                     │  AI opponent   │
                     └────────────────┘
```

### C++ Engine (`src/tsc/`)

Pure-function state machine. Game state is a flat struct (`ts_state`) advanced by `ts_advance_game()`, which takes an immutable state and returns a new one. No heap allocation — all arrays are fixed-size.

**Key types:**

- `ts_state` — full game snapshot: turn, DEFCON, VP, influence map, draw/discard/removed piles, player hands, space/military tracks, china card, current step
- `ts_country` — static country data (id, name, battleground, stability)
- `ts_card` — static card data (id, name, ops, side, war period)
- `ts_move` — a player action (card + target country + influence)
- `ts_current_step` — enum driving the state machine (init → place influence → headline → action rounds)

**State machine flow:**

1. `TS_STEP_INIT` — deal Early War cards, place fixed USSR influence (Syria, Iraq, North Korea, East Germany, Finland)
2. `TS_STEP_USSR_PLACE_SIX_INFLUENCE_EASTERN_EUROPE` — USSR chooses 6 influence in Eastern Europe
3. `TS_STEP_INIT_US` — place fixed US influence (Canada, Iran, Israel, Japan, Australia, Philippines, South Korea, Panama, South Africa, UK)
4. `TS_STEP_US_PLACE_SEVEN_INFLUENCE_WESTERN_EUROPE` — US chooses 7 influence in Western Europe
5. `TS_STEP_INIT_FINISH` — initialize space/military tracks, set turn 1, DEFCON 5, VP 0
6. `TS_STEP_BEGIN_TURN` — deal cards (hand size 8 for turns 1-3, 9 for 4-10), shuffle in Mid War (turn 4) and Late War (turn 8), improve DEFCON
7. `TS_STEP_HEADLINE_A/B` — both players select headline cards
8. `TS_STEP_RESOLVE_FIRST/SECOND_HEADLINE` — resolve in ops-value order

**Files:**

| File | Purpose | Requirement |
|------|---------|-------------|
| `types.h` | All types, data tables (countries, cards), game logic | Contains all game logic and data as as-simple-as-possible c++, intended to be turned into a reference, in code and in English |
| `util.h` | RNG (Mersenne Twister), dice rolls, memory utilities | Implementation details that are not interesting for understanding the rule |
| `main.cpp` | Unit tests via utest.h | |
| `utest.h` | Single-header test framework | |

**Data tables:** 84 countries with stability/battleground, 110 cards across Early/Mid/Late War periods. Country IDs are sparse (matching board positions), card IDs are sequential within each war period.

### Python Server

Async TCP server with ANSI-styled text output and Ollama streaming. See `manual.md` for full protocol spec.

**Components:**

- `Server` — async TCP, accepts terminal connections, dispatches messages
- `Terminal` — connects to server, sends input, renders styled text
- `OllamaClient` — streams LLM responses token-by-token
- `StyledText` — chainable ANSI text builder with JSON serialization

**Protocol:** newline-delimited JSON over TCP. Supports complete messages and streaming (start/chunk/end frames).

**AI prompt** (`prompt.md`): instructs the LLM to analyze game state and respond with `/play` commands (influence, coup, space race, scoring).

### Tests

Two test suites:

- `src/tsc/main.cpp` — utest.h-based C++ tests for engine state
- `tests/test_ts.cpp` — standalone C++ tests for static data (country count, battleground count, card count, France properties)

## Build

CMake + Ninja, C++17:

```bash
cmake -B build && cmake --build build
./build/ts
```

## Design Decisions

- **Immutable state transitions**: `ts_advance_game` copies the input state and returns a modified copy. This enables undo, replay, and safe AI exploration of game trees.
- **Flat struct, no heap**: `ts_state` uses fixed-size arrays sized to maximum possible values (`TS_MAX_PILE_SIZE`, `TS_MAX_HAND_SIZE`). Entire state is `memcpy`-able.
- **Sparse country IDs**: enum values match board layout numbering rather than being contiguous. The `countries[]` array provides the mapping.
- **Step-based state machine**: player choice points (placing influence, selecting headlines) are separate steps that pause the state machine, allowing external code to inject decisions.

## Current Status

- Country and card data tables complete (84 countries, 110 cards)
- Game setup sequence implemented through initial influence placement
- Turn structure scaffolded (card dealing, Mid/Late War deck integration, DEFCON improvement)
- Headline phase started (selection and resolution by ops value)
- Action rounds not yet implemented
- Python terminal server scaffolded but empty (`server.py`)
- AI prompt template defined

## Known Issues

- `types.h:624` — double card draw: `drawDeckSize -= 2` is redundant after `--drawDeckSize` on lines 621-622, removing 4 cards per iteration instead of 2
- `ts_advance_game` and `ts_gameover` have missing return paths (compiler warnings)
- `TS_STEP_RESOLVE_SECOND_HEADLINE` not handled in switch
