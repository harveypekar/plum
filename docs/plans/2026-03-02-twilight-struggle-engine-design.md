# Twilight Struggle Core Game Engine — Design

**Date:** 2026-03-02
**Location:** `projects/ts/ts.py` (engine), `projects/ts/tests.py` (tests)

## Goal

Implement the core Twilight Struggle board game rules as a Python game engine. Primary consumers: RL agent training (Gym-like step/reset API) and future terminal-based human play (via adapter to main.py's Server/Terminal).

## Scope

**In scope (this phase):**
- Full game state representation
- Turn flow: headline phase, action rounds, end-of-turn bookkeeping
- Operations: influence placement, realignment rolls, coup attempts, space race
- DEFCON track with geographic restrictions and DEFCON 1 loss
- Military operations tracking and VP penalties
- Scoring: presence/domination/control per region, battleground/adjacency bonuses
- Victory conditions: 20 VP auto-win, Europe control, DEFCON 1, end-game scoring
- China Card mechanics
- Opponent event triggering (event fires but as stub/no-op)
- Deck management: draw, discard, reshuffle, Mid/Late War card injection
- All 110 card definitions (id, name, ops, side, war period, metadata)
- Map: all ~75 countries with stability, region, adjacency, battleground status

**Out of scope (future phases):**
- Individual card event implementations (110 unique event handlers)
- Terminal UI adapter
- RL training loop / neural network

## Architecture: Flat State Machine

### Data Layer (Constants)

```python
class Region(Enum):  # EUROPE, ASIA, MIDDLE_EAST, CENTRAL_AMERICA, SOUTH_AMERICA, AFRICA
class Subregion(Enum):  # EASTERN_EUROPE, WESTERN_EUROPE, SOUTHEAST_ASIA
class Side(Enum):  # US, USSR, NEUTRAL
class Period(Enum):  # EARLY, MID, LATE

@dataclass(frozen=True)
class Country:
    name: str
    stability: int
    battleground: bool
    region: Region
    subregion: Subregion | None
    adjacent: tuple[int, ...]  # country indices
    us_adjacent: bool   # adjacent to US superpower
    ussr_adjacent: bool # adjacent to USSR superpower

@dataclass(frozen=True)
class CardDef:
    id: int
    name: str
    ops: int
    side: Side
    war_period: Period
    removed_after_event: bool
    scoring: bool
```

Constants: `COUNTRIES: tuple[Country, ...]` and `CARDS: tuple[CardDef, ...]`

### Game State

Single `GameState` dataclass. All mutable game data in one place:

- `influence: list[list[int]]` — per-country [us, ussr] influence
- Scalar tracks: `defcon`, `vp`, `turn`, `action_round`
- `phase: Phase` enum for state machine
- `phasing_player: Side`
- `space_race: list[int]` — [us, ussr] positions (0-8)
- `mil_ops: list[int]` — [us, ussr] this turn
- `us_hand, ussr_hand: list[int]` — card IDs
- `china_card_holder, china_card_face_up, china_card_playable`
- `draw_pile, discard_pile, removed_pile: list[int]`
- `us_headline, ussr_headline: int | None`
- `game_over: bool`, `winner: Side | None`

### Engine API

```python
class TwilightStruggle:
    state: GameState

    def reset(self) -> GameState
    def legal_actions(self) -> list[Action]
    def step(self, action: Action) -> tuple[GameState, float, bool, dict]
    def clone(self) -> TwilightStruggle
```

### Action Encoding

```python
class ActionType(Enum):
    HEADLINE_SELECT
    PLAY_OPS_INFLUENCE
    PLAY_OPS_COUP
    PLAY_OPS_REALIGN
    PLAY_OPS_SPACE
    PLAY_EVENT
    PLACE_INFLUENCE      # sub-action during ops
    REALIGN_TARGET       # sub-action during ops
    EVENT_DECISION       # before/after ops choice

@dataclass
class Action:
    type: ActionType
    card_id: int | None = None
    country_id: int | None = None
```

### Key Formulas

| Mechanic | Formula |
|----------|---------|
| Country control | `inf[side] >= stability AND inf[side] - inf[other] >= stability` |
| Influence cost | 1 op (friendly/uncontrolled), 2 ops (enemy-controlled) |
| Coup success | `die + ops > stability * 2` |
| Coup result | Remove/add influence = `(die + ops) - (stability * 2)` |
| Realignment | Each rolls die + mods; high roller removes difference |
| Realignment mods | +1 each adjacent controlled, +1 more influence, +1 superpower adjacent |
| Scoring | Presence 1 VP, Domination 3 VP, Control 7 VP, +1/battleground, +1/adjacent-superpower |
| Mil ops penalty | `max(0, defcon - mil_ops)` VP to opponent |
| Space race | `ops >= box_threshold AND die in box_range` |

## Testing Strategy

TDD with pytest. Test groups mirror mechanics: control, influence, coups, realignment, scoring, DEFCON, mil ops, turn flow, China card, victory.
