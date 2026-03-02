"""Twilight Struggle — Europe / Early War (No Events)

Reduced-scope variant: 21 European countries, Early War cards only,
no card events (ops and scoring only). 3 turns.

Rules
=====

Victory
-------
- VP reaches +20 (US) or -20 (USSR): instant win
- Europe Control: all BGs + more total countries = instant win when scored
- DEFCON 1: phasing player loses
- After turn 3: final scoring; Europe Control = auto-win; else highest VP

Country Control
---------------
own_inf >= stability AND own_inf - opp_inf >= stability

Scoring (Europe)
----------------
- Presence (>=1 country): 3 VP
- Domination (more BGs AND more total, need >=1 BG and >=1 non-BG): 7 VP
- Control (ALL BGs AND more total): auto-win
- Bonuses: +1/BG controlled, +1/country adjacent to opponent superpower

Operations
----------
- Influence: 1 op (friendly/uncontrolled), 2 ops (enemy-controlled).
  Must be adjacent to existing friendly influence or own superpower.
- Coup: die + ops > stability * 2. BG coups degrade DEFCON.
- Realignment: both roll d6 + mods. Higher removes difference. No inf added.
  Mods: +1/adjacent controlled, +1 if more inf in target, +1 superpower adj.
- Space Race: ops >= box threshold, die <= box max to advance.

DEFCON
------
Starts 5, +1 at turn start (max 5). BG coup = -1. DEFCON 1 = phasing player
loses. At DEFCON <= 4: ALL coups and realignment blocked (everything is Europe).

Military Operations
-------------------
Required per turn = DEFCON level. Shortfall = opponent gains 1 VP / point.
Coups count (ops value). Realignment does NOT.

China Card (card 6)
-------------------
4 ops. Cannot headline. Passes face-down; flips face-up end of turn.

Turn Structure (3 turns)
------------------------
1. DEFCON +1 (if < 5)
2. Deal to hand size 8
3. Headline: both select, higher ops first, US resolves first on ties
4. 6 action rounds, USSR first each round
5. Mil ops check
6. Flip China Card face-up
7. After turn 3: final scoring

Card Play (no events)
---------------------
- All non-scoring cards: ops only (influence, coup, realign, space race)
- Scoring card: must play during turn drawn, triggers Europe scoring
- No opponent event triggers (events disabled)
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from enum import Enum, IntEnum


# -- Enums -------------------------------------------------------------------

class Side(IntEnum):
    US = 0
    USSR = 1
    NEUTRAL = 2


class Subregion(Enum):
    WESTERN_EUROPE = "western_europe"
    EASTERN_EUROPE = "eastern_europe"


class Phase(Enum):
    """Current game phase. Determines which actions are legal."""
    SETUP = "setup"                    # Initial influence placement (handled by reset)
    HEADLINE = "headline"              # Both players select a card simultaneously
    ACTION_ROUND = "action_round"      # Phasing player chooses a card and how to play it
    OPS_INFLUENCE = "ops_influence"    # Placing influence markers with operations points
    OPS_REALIGN = "ops_realign"        # Choosing realignment roll targets with ops points
    FINAL_SCORING = "final_scoring"    # End-of-game scoring after last turn
    GAME_OVER = "game_over"            # Game has ended; check winner field


class ActionType(Enum):
    """Action the phasing player can take. Two levels:
    - Card-play actions (ACTION_ROUND phase): choose which card and how to use it
    - Operations actions (OPS_* phases): spend ops points from the chosen card
    """
    # -- Card-play actions (phase: HEADLINE or ACTION_ROUND) --
    HEADLINE_SELECT = "headline_select"      # Select a card for the headline phase
    PLAY_OPS_INFLUENCE = "play_ops_influence" # Play card for influence placement ops
    PLAY_OPS_COUP = "play_ops_coup"          # Play card for a coup attempt (country_id = target)
    PLAY_OPS_REALIGN = "play_ops_realign"    # Play card for realignment rolls
    PLAY_OPS_SPACE = "play_ops_space"        # Play card for a space race attempt
    PLAY_SCORING = "play_scoring"            # Play a scoring card (must play if in hand)
    # -- Operations actions (phase: OPS_INFLUENCE or OPS_REALIGN) --
    PLACE_INFLUENCE = "place_influence"       # Place 1 influence at country_id (costs 1-2 ops)
    DONE_PLACING = "done_placing"             # Finish placing influence (forfeit remaining ops)
    REALIGN_TARGET = "realign_target"         # Realignment roll at country_id (costs 1 op)
    DONE_REALIGNING = "done_realigning"       # Finish realignment rolls (forfeit remaining ops)


# -- Countries ---------------------------------------------------------------

@dataclass(frozen=True)
class Country:
    """A country on the Twilight Struggle map.

    Attributes:
        id: Internal integer ID (index into COUNTRIES tuple).
        name: Display name as printed on the board.
        stability: Stability number. Higher = harder to coup or control.
            Control requires: own_influence >= stability AND lead >= stability.
        battleground: True if this is a Battleground country.
            Battleground countries are key for scoring and DEFCON.
            Couping a Battleground degrades DEFCON by 1.
        subregion: WESTERN_EUROPE or EASTERN_EUROPE (None for border countries).
        us_adjacent: True if this country borders the US superpower.
        ussr_adjacent: True if this country borders the USSR superpower.
        json_id: Hex ID from ts-data.json (e.g. "l00") for external tools.
    """
    id: int
    name: str
    stability: int
    battleground: bool
    subregion: Subregion | None
    us_adjacent: bool
    ussr_adjacent: bool
    json_id: str


# fmt: off
_WE, _EE = Subregion.WESTERN_EUROPE, Subregion.EASTERN_EUROPE

# All 21 European countries. Index = country ID.
# Superpower adjacency: US borders Canada. USSR borders Finland, Poland, Romania.
COUNTRIES: tuple[Country, ...] = (
    #    id  name               stab  BG     subreg  US?    USSR?  json
    Country(0,  "Canada",          4, False, _WE,    True,  False, "l00"),
    Country(1,  "UK",              5, False, _WE,    False, False, "l01"),
    Country(2,  "Benelux",         3, False, _WE,    False, False, "l04"),
    Country(3,  "France",          3, True,  _WE,    False, False, "l02"),
    Country(4,  "Spain/Portugal",  2, False, _WE,    False, False, "l03"),
    Country(5,  "Norway",          4, False, _WE,    False, False, "l0a"),
    Country(6,  "Denmark",         3, False, _WE,    False, False, "l09"),
    Country(7,  "W.Germany",       4, True,  _WE,    False, False, "l05"),
    Country(8,  "Sweden",          4, False, _WE,    False, False, "l0b"),
    Country(9,  "Italy",           2, True,  _WE,    False, False, "l06"),
    Country(10, "Greece",          2, False, _WE,    False, False, "l07"),
    Country(11, "Turkey",          2, False, _WE,    False, False, "l08"),
    Country(12, "Finland",         4, False, None,   False, True,  "l0d"),
    Country(13, "Austria",         4, False, None,   False, False, "l0c"),
    Country(14, "E.Germany",       3, True,  _EE,    False, False, "l0e"),
    Country(15, "Poland",          3, True,  _EE,    False, True,  "l0f"),
    Country(16, "Czechoslovakia",  3, False, _EE,    False, False, "l10"),
    Country(17, "Hungary",         3, False, _EE,    False, False, "l11"),
    Country(18, "Yugoslavia",      3, False, _EE,    False, False, "l12"),
    Country(19, "Romania",         3, False, _EE,    False, True,  "l13"),
    Country(20, "Bulgaria",        3, False, _EE,    False, False, "l14"),
)
# fmt: on

# Adjacencies: each pair (a, b) means countries a and b are connected.
# Connections are bidirectional. This is the map topology for Europe.
# Superpower connections are encoded on the Country (us_adjacent, ussr_adjacent).
ADJACENCIES: tuple[tuple[int, int], ...] = (
    # Western Europe
    (0, 1),    # Canada — UK
    (1, 2),    # UK — Benelux
    (1, 3),    # UK — France
    (1, 5),    # UK — Norway
    (2, 7),    # Benelux — W.Germany
    (3, 4),    # France — Spain/Portugal
    (3, 7),    # France — W.Germany
    (3, 9),    # France — Italy
    (4, 9),    # Spain/Portugal — Italy
    (5, 6),    # Norway — Denmark
    (5, 8),    # Norway — Sweden
    (6, 7),    # Denmark — W.Germany
    (6, 8),    # Denmark — Sweden
    (7, 13),   # W.Germany — Austria
    (7, 14),   # W.Germany — E.Germany
    (8, 12),   # Sweden — Finland
    (9, 10),   # Italy — Greece
    (9, 13),   # Italy — Austria
    (9, 18),   # Italy — Yugoslavia
    (10, 11),  # Greece — Turkey
    (10, 18),  # Greece — Yugoslavia
    (10, 20),  # Greece — Bulgaria
    (11, 19),  # Turkey — Romania
    # Eastern Europe
    (11, 20),  # Bulgaria — Turkey
    (13, 14),  # Austria — E.Germany
    (13, 17),  # Austria — Hungary
    (14, 15),  # E.Germany — Poland
    (14, 16),  # E.Germany — Czechoslovakia
    (15, 16),  # Poland — Czechoslovakia
    (16, 17),  # Czechoslovakia — Hungary
    (17, 18),  # Hungary — Yugoslavia
    (17, 19),  # Hungary — Romania
    (18, 19),  # Yugoslavia — Romania
    (19, 20),  # Romania — Bulgaria
)

# Derived: neighbor lookup. NEIGHBORS[country_id] = tuple of adjacent country IDs.
def _build_neighbors() -> dict[int, tuple[int, ...]]:
    adj: dict[int, set[int]] = {c.id: set() for c in COUNTRIES}
    for a, b in ADJACENCIES:
        adj[a].add(b)
        adj[b].add(a)
    return {cid: tuple(sorted(nbrs)) for cid, nbrs in adj.items()}

NEIGHBORS: dict[int, tuple[int, ...]] = _build_neighbors()

# 5 Battleground countries in Europe: France, W.Germany, Italy, E.Germany, Poland
NUM_BATTLEGROUNDS = sum(1 for c in COUNTRIES if c.battleground)


# -- Cards -------------------------------------------------------------------

@dataclass(frozen=True)
class CardDef:
    id: int
    name: str
    ops: int
    side: Side          # original side (irrelevant without events)
    scoring: bool
    removed_after_event: bool
    json_id: str        # hex ID from ts-data.json


def _build_cards() -> tuple[CardDef, ...]:
    S = Side
    cards = [
        # Europe Scoring
        CardDef(2,   "Europe Scoring",                0, S.NEUTRAL, True,  False, "c01"),
        # USSR cards
        CardDef(5,   "Five Year Plan",                3, S.USSR,    False, False, "c04"),
        CardDef(7,   "Socialist Governments",         3, S.USSR,    False, False, "c06"),
        CardDef(8,   "Fidel",                         2, S.USSR,    False, True,  "c07"),
        CardDef(9,   "Vietnam Revolts",               2, S.USSR,    False, True,  "c08"),
        CardDef(10,  "Blockade",                      1, S.USSR,    False, True,  "c09"),
        CardDef(11,  "Korean War",                    2, S.USSR,    False, True,  "c0a"),
        CardDef(12,  "Romanian Abdication",           1, S.USSR,    False, True,  "c0b"),
        CardDef(13,  "Arab-Israeli War",              2, S.USSR,    False, False, "c0c"),
        CardDef(14,  "Comecon",                       3, S.USSR,    False, True,  "c0d"),
        CardDef(15,  "Nasser",                        1, S.USSR,    False, True,  "c0e"),
        CardDef(16,  "Warsaw Pact Formed",            3, S.USSR,    False, True,  "c0f"),
        CardDef(17,  "De Gaulle Leads France",        3, S.USSR,    False, True,  "c10"),
        CardDef(28,  "Suez Crisis",                   3, S.USSR,    False, True,  "c1b"),
        CardDef(30,  "Decolonization",                2, S.USSR,    False, False, "c1d"),
        CardDef(33,  "De-Stalinization",              3, S.USSR,    False, True,  "c20"),
        # US cards
        CardDef(4,   "Duck and Cover",                3, S.US,      False, False, "c03"),
        CardDef(19,  "Truman Doctrine",               1, S.US,      False, True,  "c12"),
        CardDef(21,  "NATO",                          4, S.US,      False, True,  "c14"),
        CardDef(22,  "Independent Reds",              2, S.US,      False, True,  "c15"),
        CardDef(23,  "Marshall Plan",                 4, S.US,      False, True,  "c16"),
        CardDef(25,  "Containment",                   3, S.US,      False, True,  "c18"),
        CardDef(26,  "CIA Created",                   1, S.US,      False, True,  "c19"),
        CardDef(27,  "US/Japan Mutual Defense Pact",  4, S.US,      False, True,  "c1a"),
        CardDef(29,  "East European Unrest",          3, S.US,      False, False, "c1c"),
        CardDef(35,  "Formosan Resolution",           2, S.US,      False, True,  "c22"),
        CardDef(103, "Defectors",                     2, S.US,      False, False, "c23"),
        # Neutral cards
        CardDef(18,  "Captured Nazi Scientist",       1, S.NEUTRAL, False, True,  "c11"),
        CardDef(20,  "Olympic Games",                 2, S.NEUTRAL, False, False, "c13"),
        CardDef(24,  "Indo-Pakistani War",            2, S.NEUTRAL, False, False, "c17"),
        CardDef(31,  "Red Scare/Purge",               4, S.NEUTRAL, False, False, "c1e"),
        CardDef(32,  "UN Intervention",               1, S.NEUTRAL, False, False, "c1f"),
        CardDef(34,  "Nuclear Test Ban",              4, S.NEUTRAL, False, False, "c21"),
    ]
    return tuple(cards)


CARDS: tuple[CardDef, ...] = _build_cards()
_CARD_BY_ID: dict[int, CardDef] = {c.id: c for c in CARDS}

CHINA_CARD_ID = 6
CHINA_CARD_OPS = 4


def card_by_id(card_id: int) -> CardDef:
    return _CARD_BY_ID[card_id]


# -- Space Race Track --------------------------------------------------------

@dataclass(frozen=True)
class SpaceBox:
    name: str
    ops_required: int
    roll_max: int
    first_vp: int
    second_vp: int


SPACE_RACE_TRACK: tuple[SpaceBox, ...] = (
    SpaceBox("Start",              0, 0, 0, 0),
    SpaceBox("Satellite",          2, 3, 2, 1),
    SpaceBox("Animal in Space",    2, 4, 0, 0),
    SpaceBox("Man in Space",       2, 3, 2, 0),
    SpaceBox("Man in Earth Orbit", 2, 4, 0, 0),
    SpaceBox("Lunar Orbit",        3, 3, 3, 1),
    SpaceBox("Eagle/Bear Landed",  3, 4, 0, 0),
    SpaceBox("Space Shuttle",      3, 3, 4, 2),
    SpaceBox("Station",            4, 2, 2, 0),
)


# -- Scoring (Europe only) ---------------------------------------------------

SCORING_PRESENCE = 3
SCORING_DOMINATION = 7
SCORING_CONTROL = 1000  # auto-win sentinel


# -- GameState ---------------------------------------------------------------

@dataclass
class GameState:
    influence: list[list[int]]    # [country_id][Side.US or Side.USSR]
    defcon: int
    vp: int                       # positive = US leading
    turn: int
    action_round: int
    phase: Phase
    phasing_player: Side
    space_race: list[int]         # [us_pos, ussr_pos]
    mil_ops: list[int]            # [us, ussr]
    us_hand: list[int]
    ussr_hand: list[int]
    china_card_holder: Side
    china_card_face_up: bool
    china_card_playable: bool
    draw_pile: list[int]
    discard_pile: list[int]
    removed_pile: list[int]
    us_headline: int | None
    ussr_headline: int | None
    space_race_used: list[bool]   # [us, ussr] used this turn
    game_over: bool
    winner: Side | None
    ops_remaining: int
    active_card: int | None

    @staticmethod
    def new() -> GameState:
        return GameState(
            influence=[[0, 0] for _ in range(len(COUNTRIES))],
            defcon=5, vp=0, turn=0, action_round=0,
            phase=Phase.SETUP, phasing_player=Side.USSR,
            space_race=[0, 0], mil_ops=[0, 0],
            us_hand=[], ussr_hand=[],
            china_card_holder=Side.USSR,
            china_card_face_up=True, china_card_playable=True,
            draw_pile=[], discard_pile=[], removed_pile=[],
            us_headline=None, ussr_headline=None,
            space_race_used=[False, False],
            game_over=False, winner=None,
            ops_remaining=0, active_card=None,
        )


# -- Game Logic Functions ----------------------------------------------------
# These encode the core rules of Twilight Struggle.
# An LLM reading this code should learn how each mechanic works.


def controls_country(gs: GameState, country_id: int, side: Side) -> bool:
    """Does `side` Control a country?

    Control requires BOTH:
      1. own influence >= country's stability number
      2. own influence - opponent's influence >= stability number

    Example: France (stability 3). US has 4 influence, USSR has 1.
    US margin = 4 - 1 = 3 >= 3. US influence = 4 >= 3. US Controls France.
    """
    c = COUNTRIES[country_id]
    other = Side.USSR if side == Side.US else Side.US
    own = gs.influence[country_id][side]
    opp = gs.influence[country_id][other]
    return own >= c.stability and (own - opp) >= c.stability


def score_europe(gs: GameState) -> tuple[int, int]:
    """Score the Europe region. Returns (us_vp, ussr_vp).

    Scoring levels (each side evaluated independently):
      - Presence: Control at least 1 country → 3 VP
      - Domination: Control more Battlegrounds AND more total countries
        than opponent (must have >=1 BG and >=1 non-BG) → 7 VP
      - Control: Control ALL Battlegrounds AND more total countries → auto-win

    Bonuses (added on top of level VP):
      - +1 VP per Battleground country controlled
      - +1 VP per country controlled that is adjacent to opponent's superpower
    """
    us_controlled: list[Country] = []
    ussr_controlled: list[Country] = []
    us_bg = ussr_bg = 0

    for c in COUNTRIES:
        if controls_country(gs, c.id, Side.US):
            us_controlled.append(c)
            if c.battleground:
                us_bg += 1
        elif controls_country(gs, c.id, Side.USSR):
            ussr_controlled.append(c)
            if c.battleground:
                ussr_bg += 1

    def calc_vp(controlled: list[Country], bg: int, opp_bg: int,
                opp_count: int, side: Side) -> int:
        if not controlled:
            return 0
        vp = 0
        has_all_bg = bg == NUM_BATTLEGROUNDS and NUM_BATTLEGROUNDS > 0
        more_countries = len(controlled) > opp_count
        more_bg = bg > opp_bg
        has_bg = bg > 0
        has_non_bg = any(not c.battleground for c in controlled)

        # Determine scoring level
        if has_all_bg and more_countries:
            vp += SCORING_CONTROL       # Auto-win sentinel
        elif more_countries and more_bg and has_bg and has_non_bg:
            vp += SCORING_DOMINATION    # 7 VP
        else:
            vp += SCORING_PRESENCE      # 3 VP

        # Bonuses
        for c in controlled:
            if c.battleground:
                vp += 1                 # +1 per BG controlled
            if (side == Side.US and c.ussr_adjacent) or \
               (side == Side.USSR and c.us_adjacent):
                vp += 1                 # +1 per country adjacent to opponent superpower
        return vp

    us_vp = calc_vp(us_controlled, us_bg, ussr_bg,
                     len(ussr_controlled), Side.US)
    ussr_vp = calc_vp(ussr_controlled, ussr_bg, us_bg,
                       len(us_controlled), Side.USSR)
    return us_vp, ussr_vp


def influence_cost(gs: GameState, country_id: int, side: Side) -> int:
    """How many ops points to place 1 influence marker.

    - 1 op if the country is friendly-controlled or uncontrolled
    - 2 ops if the country is enemy-controlled (costs extra to break in)

    Note: if placing influence breaks enemy control, subsequent placements
    in that country cost 1 op (rechecked each placement).
    """
    other = Side.USSR if side == Side.US else Side.US
    return 2 if controls_country(gs, country_id, other) else 1


def can_place_influence(gs: GameState, country_id: int, side: Side) -> bool:
    """Can `side` place influence in this country?

    Influence can only be placed in a country that is:
      - Adjacent to your superpower (US: Canada, USSR: Finland/Poland/Romania), OR
      - Already has at least 1 of your influence, OR
      - Adjacent to a country that has at least 1 of your influence
    """
    c = COUNTRIES[country_id]
    if side == Side.US and c.us_adjacent:
        return True
    if side == Side.USSR and c.ussr_adjacent:
        return True
    if gs.influence[country_id][side] > 0:
        return True
    return any(gs.influence[adj][side] > 0 for adj in NEIGHBORS[country_id])


def resolve_coup(gs: GameState, country_id: int, side: Side,
                 ops: int, die_roll: int):
    """Resolve a Coup attempt. Mutates gs.

    Coup formula:
      roll = die_roll + ops
      threshold = stability * 2
      If roll > threshold: success. diff = roll - threshold.
        Remove min(diff, opponent_influence) from opponent.
        Add remainder to your influence.

    Side effects:
      - Military Operations credit = ops value of card played
      - Couping a Battleground country degrades DEFCON by 1
      - If DEFCON reaches 1, the phasing player (attacker) LOSES immediately
    """
    c = COUNTRIES[country_id]
    other = Side.USSR if side == Side.US else Side.US
    # Coups always give military operations credit equal to the card's ops value
    gs.mil_ops[side] += ops

    # Battleground coup degrades DEFCON
    if c.battleground:
        gs.defcon -= 1
        if gs.defcon <= 1:
            gs.defcon = 1
            gs.game_over = True
            gs.winner = other  # Phasing player caused DEFCON 1 → they lose
            return

    # Resolve the coup roll
    diff = (die_roll + ops) - (c.stability * 2)
    if diff > 0:
        removed = min(diff, gs.influence[country_id][other])
        gs.influence[country_id][other] -= removed
        gs.influence[country_id][side] += diff - removed


def realignment_modifiers(gs: GameState, country_id: int) -> tuple[int, int]:
    """Calculate Realignment die roll modifiers for both sides.

    Each side gets:
      +1 for each adjacent country they Control
      +1 if they have more influence in the target country
      +1 if their superpower is adjacent to the target
    Returns (us_modifier, ussr_modifier).
    """
    c = COUNTRIES[country_id]
    us_mod = ussr_mod = 0
    for adj_id in NEIGHBORS[country_id]:
        if controls_country(gs, adj_id, Side.US):
            us_mod += 1
        if controls_country(gs, adj_id, Side.USSR):
            ussr_mod += 1
    if gs.influence[country_id][Side.US] > gs.influence[country_id][Side.USSR]:
        us_mod += 1
    elif gs.influence[country_id][Side.USSR] > gs.influence[country_id][Side.US]:
        ussr_mod += 1
    if c.us_adjacent:
        us_mod += 1
    if c.ussr_adjacent:
        ussr_mod += 1
    return us_mod, ussr_mod


def resolve_realignment(gs: GameState, country_id: int,
                        us_roll: int, ussr_roll: int):
    """Resolve a Realignment roll. Mutates gs.

    Both sides roll d6 + modifiers. The higher total removes
    (difference) influence from the other side. Tie = no effect.
    Realignment only removes influence — never adds.
    Realignment does NOT give Military Operations credit.
    """
    us_mod, ussr_mod = realignment_modifiers(gs, country_id)
    us_total = us_roll + us_mod
    ussr_total = ussr_roll + ussr_mod
    if us_total > ussr_total:
        diff = us_total - ussr_total
        gs.influence[country_id][Side.USSR] = max(
            0, gs.influence[country_id][Side.USSR] - diff)
    elif ussr_total > us_total:
        diff = ussr_total - us_total
        gs.influence[country_id][Side.US] = max(
            0, gs.influence[country_id][Side.US] - diff)


def defcon_restricts(defcon: int) -> bool:
    """Are Coups and Realignment restricted at this DEFCON level?

    In the full game, DEFCON restricts Battleground coups/realignment
    in specific regions. In this Europe-only variant, at DEFCON <= 4
    ALL coups and realignment are blocked because everything is in Europe.
    Only DEFCON 5 allows free coups/realignment.
    """
    return defcon <= 4


def milops_penalty(defcon: int, milops: int) -> int:
    """VP penalty for insufficient Military Operations.

    Each player must conduct military operations >= the current DEFCON level
    each turn. Shortfall = opponent gains 1 VP per point short.
    Only Coups give Military Operations credit (ops value of the card played).
    Realignment does NOT count toward Military Operations.
    """
    return max(0, defcon - milops)


def can_attempt_space_race(gs: GameState, side: Side, ops: int) -> bool:
    """Can this side attempt the Space Race with a card of the given ops value?

    Requirements:
      - Not already at the end of the track (box 8)
      - Card ops >= the next box's ops threshold
      - Only 1 attempt per turn per player (checked separately)
    """
    pos = gs.space_race[side]
    if pos >= 8:
        return False
    return ops >= SPACE_RACE_TRACK[pos + 1].ops_required


def resolve_space_race(gs: GameState, side: Side, die_roll: int) -> int:
    """Attempt to advance on the Space Race track. Returns VP gained (0 if fail).

    Roll die: if die_roll <= next box's roll_max, advance one box.
    First player to reach a box gets first_vp; second player gets second_vp.
    The Space Race is the safe way to discard a card — in the full game,
    opponent card events do NOT trigger when used for Space Race.
    """
    pos = gs.space_race[side]
    target = SPACE_RACE_TRACK[pos + 1]
    if die_roll <= target.roll_max:
        gs.space_race[side] = pos + 1
        other = Side.USSR if side == Side.US else Side.US
        if gs.space_race[other] >= pos + 1:
            return target.second_vp  # Second to reach this box
        return target.first_vp       # First to reach this box
    return 0


def headline_order(ussr_card_id: int, us_card_id: int) -> tuple[Side, Side]:
    """Determine headline resolution order.
    Higher ops card resolves first. US resolves first on ties.
    Scoring cards headlined at ops value 0.
    """
    ussr_ops = 0 if _CARD_BY_ID[ussr_card_id].scoring else _CARD_BY_ID[ussr_card_id].ops
    us_ops = 0 if _CARD_BY_ID[us_card_id].scoring else _CARD_BY_ID[us_card_id].ops
    if ussr_ops > us_ops:
        return Side.USSR, Side.US
    return Side.US, Side.USSR


def check_victory(gs: GameState):
    """Check the VP track for an instant victory.

    VP >= +20: US wins immediately.
    VP <= -20: USSR wins immediately.
    This check runs after every VP-changing action.
    """
    if gs.vp >= 20:
        gs.game_over = True
        gs.winner = Side.US
    elif gs.vp <= -20:
        gs.game_over = True
        gs.winner = Side.USSR


def check_europe_control(gs: GameState) -> Side | None:
    """Check if either side Controls the Europe region (auto-win when scored).

    Europe Control = Control ALL Battleground countries AND more total countries
    than your opponent. This is an instant win when Europe is scored.
    """
    for side in (Side.US, Side.USSR):
        other = Side.USSR if side == Side.US else Side.US
        controlled = [c for c in COUNTRIES if controls_country(gs, c.id, side)]
        bg = sum(1 for c in controlled if c.battleground)
        opp_count = sum(1 for c in COUNTRIES if controls_country(gs, c.id, other))
        if bg == NUM_BATTLEGROUNDS and len(controlled) > opp_count:
            return side
    return None


def final_scoring(gs: GameState):
    """End-of-game scoring after the last turn (turn 3).

    1. Check for Europe Control (auto-win)
    2. Score Europe normally (Presence/Domination VP)
    3. China Card holder gets +1 VP (US positive, USSR negative)
    4. Whoever leads on VP track wins. VP 0 = draw (None).
    """
    winner = check_europe_control(gs)
    if winner:
        gs.game_over = True
        gs.winner = winner
        return
    us_vp, ussr_vp = score_europe(gs)
    gs.vp += us_vp - ussr_vp
    # China Card holder gets 1 VP at end of game
    if gs.china_card_holder == Side.US:
        gs.vp += 1
    elif gs.china_card_holder == Side.USSR:
        gs.vp -= 1
    check_victory(gs)
    if not gs.game_over:
        gs.game_over = True
        gs.winner = Side.US if gs.vp > 0 else (Side.USSR if gs.vp < 0 else None)


def pass_china_card(gs: GameState, from_side: Side):
    """Pass the China Card to the opponent after playing it.

    The China Card passes face-down (not playable until flipped at end of turn).
    """
    other = Side.USSR if from_side == Side.US else Side.US
    gs.china_card_holder = other
    gs.china_card_face_up = False
    gs.china_card_playable = False


def flip_china_card(gs: GameState):
    """Flip the China Card face-up at end of turn, making it playable."""
    if not gs.china_card_face_up:
        gs.china_card_face_up = True
        gs.china_card_playable = True


# -- Action ------------------------------------------------------------------

@dataclass
class Action:
    """A single action the phasing player can take.

    Attributes:
        type: What kind of action (see ActionType enum).
        card_id: Which card is being played (for card-play actions).
        country_id: Which country is targeted (for PLACE_INFLUENCE,
            PLAY_OPS_COUP, REALIGN_TARGET).
    """
    type: ActionType
    card_id: int | None = None
    country_id: int | None = None


# -- Game Engine -------------------------------------------------------------

HAND_SIZE = 8       # Cards dealt to each player per turn (Early War)
ACTION_ROUNDS = 6   # Action rounds per turn (Early War)
NUM_TURNS = 3       # Total turns in this variant (Early War only)


class TwilightStruggle:

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.state = GameState.new()

    def reset(self, seed: int | None = None) -> GameState:
        if seed is not None:
            self.rng = random.Random(seed)
        gs = GameState.new()
        self.state = gs

        # Build draw pile (all Early War cards except China Card)
        gs.draw_pile = [c.id for c in CARDS if c.id != CHINA_CARD_ID]
        self.rng.shuffle(gs.draw_pile)
        _deal_cards(gs, HAND_SIZE, self.rng)

        # Starting influence — these are fixed by the rules.
        # USSR starts with influence in Eastern Europe.
        # US starts with influence in Western Europe.
        cn = {c.name: c for c in COUNTRIES}
        for name, inf in [("E.Germany", 3), ("Finland", 1),
                          ("Poland", 4), ("Czechoslovakia", 1), ("Yugoslavia", 1)]:
            gs.influence[cn[name].id][Side.USSR] = inf
        for name, inf in [("Canada", 2), ("UK", 5),
                          ("W.Germany", 4), ("Italy", 2), ("France", 1)]:
            gs.influence[cn[name].id][Side.US] = inf

        gs.turn = 1
        gs.phase = Phase.HEADLINE
        gs.phasing_player = Side.USSR
        return gs

    def clone(self) -> TwilightStruggle:
        new = TwilightStruggle.__new__(TwilightStruggle)
        new.rng = random.Random()
        new.rng.setstate(self.rng.getstate())
        new.state = copy.deepcopy(self.state)
        return new

    def legal_actions(self) -> list[Action]:
        gs = self.state
        if gs.game_over:
            return []

        if gs.phase == Phase.HEADLINE:
            return self._headline_actions()
        if gs.phase == Phase.ACTION_ROUND:
            return self._action_round_actions()
        if gs.phase == Phase.OPS_INFLUENCE:
            return self._influence_actions()
        if gs.phase == Phase.OPS_REALIGN:
            return self._realign_actions()
        return []

    def step(self, action: Action) -> tuple[GameState, float, bool, dict]:
        gs = self.state

        if gs.phase == Phase.HEADLINE:
            self._step_headline(action)
        elif gs.phase == Phase.ACTION_ROUND:
            self._step_action_round(action)
        elif gs.phase == Phase.OPS_INFLUENCE:
            self._step_influence(action)
        elif gs.phase == Phase.OPS_REALIGN:
            self._step_realign(action)

        if not gs.game_over:
            check_victory(gs)

        reward = gs.vp / 20.0 if gs.game_over else 0.0
        return gs, reward, gs.game_over, {}

    # -- Legal action generators ---------------------------------------------

    def _headline_actions(self) -> list[Action]:
        gs = self.state
        hand = gs.ussr_hand if gs.phasing_player == Side.USSR else gs.us_hand
        actions = [Action(ActionType.HEADLINE_SELECT, card_id=cid)
                   for cid in hand if cid != CHINA_CARD_ID]
        if not actions:
            # Skip this player's headline
            if gs.phasing_player == Side.USSR:
                gs.ussr_headline = None
                gs.phasing_player = Side.US
                return self.legal_actions()
            else:
                gs.us_headline = None
                if gs.ussr_headline is None:
                    gs.phase = Phase.ACTION_ROUND
                    gs.action_round = 1
                    gs.phasing_player = Side.USSR
                    return self.legal_actions()
                self._resolve_headlines()
                return [] if gs.game_over else self.legal_actions()
        return actions

    def _action_round_actions(self) -> list[Action]:
        gs = self.state
        hand = gs.ussr_hand if gs.phasing_player == Side.USSR else gs.us_hand
        side = gs.phasing_player
        actions: list[Action] = []
        restricted = defcon_restricts(gs.defcon)

        for cid in hand:
            card = card_by_id(cid)
            if card.scoring:
                actions.append(Action(ActionType.PLAY_SCORING, card_id=cid))
                continue
            actions.append(Action(ActionType.PLAY_OPS_INFLUENCE, card_id=cid))
            if not restricted:
                actions.append(Action(ActionType.PLAY_OPS_REALIGN, card_id=cid))
                other = Side.USSR if side == Side.US else Side.US
                for c in COUNTRIES:
                    if gs.influence[c.id][other] > 0:
                        actions.append(Action(ActionType.PLAY_OPS_COUP,
                                              card_id=cid, country_id=c.id))
            if (can_attempt_space_race(gs, side, card.ops)
                    and not gs.space_race_used[side]):
                actions.append(Action(ActionType.PLAY_OPS_SPACE, card_id=cid))

        # China Card
        if (gs.china_card_holder == side and gs.china_card_face_up
                and gs.china_card_playable):
            has_scoring = any(card_by_id(c).scoring for c in hand)
            if not has_scoring:
                actions.append(Action(ActionType.PLAY_OPS_INFLUENCE,
                                      card_id=CHINA_CARD_ID))
                if not restricted:
                    actions.append(Action(ActionType.PLAY_OPS_REALIGN,
                                          card_id=CHINA_CARD_ID))
                    other = Side.USSR if side == Side.US else Side.US
                    for c in COUNTRIES:
                        if gs.influence[c.id][other] > 0:
                            actions.append(Action(ActionType.PLAY_OPS_COUP,
                                                  card_id=CHINA_CARD_ID,
                                                  country_id=c.id))
                if (can_attempt_space_race(gs, side, CHINA_CARD_OPS)
                        and not gs.space_race_used[side]):
                    actions.append(Action(ActionType.PLAY_OPS_SPACE,
                                          card_id=CHINA_CARD_ID))

        if not actions:
            self._advance_action_round()
            return [] if gs.game_over else self.legal_actions()
        return actions

    def _influence_actions(self) -> list[Action]:
        gs = self.state
        side = gs.phasing_player
        actions = []
        for c in COUNTRIES:
            if can_place_influence(gs, c.id, side):
                cost = influence_cost(gs, c.id, side)
                if cost <= gs.ops_remaining:
                    actions.append(Action(ActionType.PLACE_INFLUENCE,
                                          country_id=c.id))
        if gs.ops_remaining == 0 or not actions:
            return [Action(ActionType.DONE_PLACING)]
        actions.append(Action(ActionType.DONE_PLACING))
        return actions

    def _realign_actions(self) -> list[Action]:
        gs = self.state
        side = gs.phasing_player
        other = Side.USSR if side == Side.US else Side.US
        actions = []
        if gs.ops_remaining > 0:
            for c in COUNTRIES:
                if gs.influence[c.id][other] > 0:
                    actions.append(Action(ActionType.REALIGN_TARGET,
                                          country_id=c.id))
        if not actions:
            return [Action(ActionType.DONE_REALIGNING)]
        actions.append(Action(ActionType.DONE_REALIGNING))
        return actions

    # -- Step handlers -------------------------------------------------------

    def _step_headline(self, action: Action):
        gs = self.state
        if gs.phasing_player == Side.USSR:
            gs.ussr_headline = action.card_id
            gs.ussr_hand.remove(action.card_id)
            gs.phasing_player = Side.US
        else:
            gs.us_headline = action.card_id
            gs.us_hand.remove(action.card_id)
            self._resolve_headlines()

    def _resolve_headlines(self):
        gs = self.state
        if gs.ussr_headline is None and gs.us_headline is None:
            gs.phase = Phase.ACTION_ROUND
            gs.action_round = 1
            gs.phasing_player = Side.USSR
            return

        cards = []
        if gs.ussr_headline is not None:
            cards.append((Side.USSR, gs.ussr_headline))
        if gs.us_headline is not None:
            cards.append((Side.US, gs.us_headline))

        if len(cards) == 2:
            first, second = headline_order(gs.ussr_headline, gs.us_headline)
            ordered = [first, second]
        else:
            ordered = [cards[0][0]]

        for side in ordered:
            cid = gs.ussr_headline if side == Side.USSR else gs.us_headline
            card = card_by_id(cid)
            if card.scoring:
                self._resolve_scoring(cid)
            if card.removed_after_event:
                gs.removed_pile.append(cid)
            else:
                gs.discard_pile.append(cid)
            if gs.game_over:
                return

        gs.ussr_headline = None
        gs.us_headline = None
        gs.phase = Phase.ACTION_ROUND
        gs.action_round = 1
        gs.phasing_player = Side.USSR

    def _resolve_scoring(self, card_id: int):
        gs = self.state
        if card_id == 2:  # Europe Scoring
            winner = check_europe_control(gs)
            if winner:
                gs.game_over = True
                gs.winner = winner
                return
            us_vp, ussr_vp = score_europe(gs)
            gs.vp += us_vp - ussr_vp

    def _step_action_round(self, action: Action):
        gs = self.state
        side = gs.phasing_player
        hand = gs.ussr_hand if side == Side.USSR else gs.us_hand

        if action.card_id != CHINA_CARD_ID and action.card_id in hand:
            hand.remove(action.card_id)

        ops = CHINA_CARD_OPS if action.card_id == CHINA_CARD_ID else card_by_id(action.card_id).ops

        if action.card_id == CHINA_CARD_ID:
            pass_china_card(gs, side)

        if action.type == ActionType.PLAY_SCORING:
            self._resolve_scoring(action.card_id)
            gs.discard_pile.append(action.card_id)
            self._advance_action_round()

        elif action.type == ActionType.PLAY_OPS_INFLUENCE:
            gs.active_card = action.card_id
            gs.ops_remaining = ops
            gs.phase = Phase.OPS_INFLUENCE

        elif action.type == ActionType.PLAY_OPS_COUP:
            die = self.rng.randint(1, 6)
            resolve_coup(gs, action.country_id, side, ops, die)
            self._advance_action_round()

        elif action.type == ActionType.PLAY_OPS_REALIGN:
            gs.active_card = action.card_id
            gs.ops_remaining = ops
            gs.phase = Phase.OPS_REALIGN

        elif action.type == ActionType.PLAY_OPS_SPACE:
            die = self.rng.randint(1, 6)
            vp = resolve_space_race(gs, side, die)
            if vp > 0:
                gs.vp += vp if side == Side.US else -vp
            gs.space_race_used[side] = True
            if action.card_id != CHINA_CARD_ID:
                gs.discard_pile.append(action.card_id)
            self._advance_action_round()

    def _step_influence(self, action: Action):
        gs = self.state
        if action.type == ActionType.DONE_PLACING:
            gs.ops_remaining = 0
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()
            return
        side = gs.phasing_player
        cost = influence_cost(gs, action.country_id, side)
        gs.influence[action.country_id][side] += 1
        gs.ops_remaining -= cost
        if gs.ops_remaining <= 0:
            gs.ops_remaining = 0
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()

    def _step_realign(self, action: Action):
        gs = self.state
        if action.type == ActionType.DONE_REALIGNING:
            gs.ops_remaining = 0
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()
            return
        resolve_realignment(gs, action.country_id,
                            self.rng.randint(1, 6), self.rng.randint(1, 6))
        gs.ops_remaining -= 1
        if gs.ops_remaining <= 0:
            gs.ops_remaining = 0
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()

    # -- Turn flow -----------------------------------------------------------

    def _advance_action_round(self):
        gs = self.state
        if gs.game_over:
            return
        gs.active_card = None
        if gs.phasing_player == Side.USSR:
            gs.phasing_player = Side.US
        else:
            gs.phasing_player = Side.USSR
            gs.action_round += 1
        if gs.action_round > ACTION_ROUNDS:
            self._end_turn()

    def _end_turn(self):
        gs = self.state
        # Mil ops penalty
        us_pen = milops_penalty(gs.defcon, gs.mil_ops[Side.US])
        ussr_pen = milops_penalty(gs.defcon, gs.mil_ops[Side.USSR])
        gs.vp -= us_pen    # US shortfall helps USSR
        gs.vp += ussr_pen  # USSR shortfall helps US
        check_victory(gs)
        if gs.game_over:
            return

        flip_china_card(gs)

        if gs.turn >= NUM_TURNS:
            final_scoring(gs)
            return

        # Advance turn
        gs.turn += 1
        gs.draw_pile.extend(gs.discard_pile)
        gs.discard_pile.clear()
        gs.mil_ops = [0, 0]
        gs.space_race_used = [False, False]
        gs.action_round = 0

        if gs.defcon < 5:
            gs.defcon += 1

        _deal_cards(gs, HAND_SIZE, self.rng)
        gs.phase = Phase.HEADLINE
        gs.phasing_player = Side.USSR


def _deal_cards(gs: GameState, hand_size: int, rng: random.Random):
    rng.shuffle(gs.draw_pile)
    while len(gs.ussr_hand) < hand_size and gs.draw_pile:
        gs.ussr_hand.append(gs.draw_pile.pop())
    while len(gs.us_hand) < hand_size and gs.draw_pile:
        gs.us_hand.append(gs.draw_pile.pop())
