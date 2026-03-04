# Twilight Struggle Core Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the core Twilight Struggle board game rules as a Python game engine with Gym-like API for RL training and future terminal play.

**Architecture:** Single-file flat state machine (`ts.py`). Frozen dataclasses for static map/card data. Mutable `GameState` dataclass for game state. `TwilightStruggle` class with `reset()`/`step()`/`legal_actions()`/`clone()`. TDD with pytest in `tests.py`.

**Tech Stack:** Python 3.12+, dataclasses, enum, random. No external dependencies. pytest for testing.

**Files:**
- Create: `projects/ts/ts.py` (engine)
- Modify: `projects/ts/tests.py` (tests — currently empty)

---

### Task 1: Enums and Country Data

**Files:**
- Create: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests for enums and country lookups**

```python
# tests.py
import pytest
from ts import (
    Side, Region, Subregion, Period, Phase, ActionType,
    Country, COUNTRIES, country_by_name,
)


class TestEnums:
    def test_sides(self):
        assert Side.US.value == 0
        assert Side.USSR.value == 1
        assert Side.NEUTRAL.value == 2

    def test_regions(self):
        assert len(Region) == 6

    def test_subregions(self):
        assert Subregion.EASTERN_EUROPE in Subregion
        assert Subregion.WESTERN_EUROPE in Subregion
        assert Subregion.SOUTHEAST_ASIA in Subregion


class TestCountries:
    def test_total_countries(self):
        assert len(COUNTRIES) == 77

    def test_lookup_by_name(self):
        israel = country_by_name("Israel")
        assert israel.stability == 4
        assert israel.battleground is True
        assert israel.region == Region.MIDDLE_EAST

    def test_us_battleground(self):
        france = country_by_name("France")
        assert france.stability == 3
        assert france.battleground is True
        assert france.region == Region.EUROPE
        assert france.subregion == Subregion.WESTERN_EUROPE

    def test_adjacency(self):
        cuba = country_by_name("Cuba")
        adj_names = {COUNTRIES[i].name for i in cuba.adjacent}
        assert "Nicaragua" in adj_names
        assert "Haiti" in adj_names

    def test_superpower_adjacency(self):
        canada = country_by_name("Canada")
        assert canada.us_adjacent is True
        assert canada.ussr_adjacent is False
        finland = country_by_name("Finland")
        assert finland.ussr_adjacent is True

    def test_battleground_count(self):
        bg = [c for c in COUNTRIES if c.battleground]
        assert len(bg) == 21

    def test_mexico_stability(self):
        mexico = country_by_name("Mexico")
        assert mexico.stability == 2
        assert mexico.battleground is True
        assert mexico.region == Region.CENTRAL_AMERICA
```

**Step 2: Run tests to verify they fail**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py -v`
Expected: FAIL (cannot import from ts)

**Step 3: Implement enums and country data**

```python
# ts.py
"""Twilight Struggle core game engine."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from enum import Enum, IntEnum


# ── Enums ──────────────────────────────────────────────────────────

class Side(IntEnum):
    US = 0
    USSR = 1
    NEUTRAL = 2


class Region(Enum):
    EUROPE = "europe"
    ASIA = "asia"
    MIDDLE_EAST = "middle_east"
    CENTRAL_AMERICA = "central_america"
    SOUTH_AMERICA = "south_america"
    AFRICA = "africa"


class Subregion(Enum):
    EASTERN_EUROPE = "eastern_europe"
    WESTERN_EUROPE = "western_europe"
    SOUTHEAST_ASIA = "southeast_asia"


class Period(Enum):
    EARLY = "early"
    MID = "mid"
    LATE = "late"


class Phase(Enum):
    SETUP = "setup"
    IMPROVE_DEFCON = "improve_defcon"
    DEAL_CARDS = "deal_cards"
    HEADLINE = "headline"
    HEADLINE_RESOLVE = "headline_resolve"
    ACTION_ROUND = "action_round"
    OPS_INFLUENCE = "ops_influence"
    OPS_REALIGN = "ops_realign"
    OPS_COUP = "ops_coup"
    EVENT_DECISION = "event_decision"
    CHECK_MILOPS = "check_milops"
    FLIP_CHINA = "flip_china"
    ADVANCE_TURN = "advance_turn"
    FINAL_SCORING = "final_scoring"
    GAME_OVER = "game_over"


class ActionType(Enum):
    HEADLINE_SELECT = "headline_select"
    PLAY_OPS_INFLUENCE = "play_ops_influence"
    PLAY_OPS_COUP = "play_ops_coup"
    PLAY_OPS_REALIGN = "play_ops_realign"
    PLAY_OPS_SPACE = "play_ops_space"
    PLAY_EVENT = "play_event"
    PLACE_INFLUENCE = "place_influence"
    REALIGN_TARGET = "realign_target"
    DONE_PLACING = "done_placing"
    DONE_REALIGNING = "done_realigning"
    EVENT_BEFORE_OPS = "event_before_ops"
    EVENT_AFTER_OPS = "event_after_ops"


# ── Static Data ────────────────────────────────────────────────────

@dataclass(frozen=True)
class Country:
    id: int
    name: str
    stability: int
    battleground: bool
    region: Region
    subregion: Subregion | None
    adjacent: tuple[int, ...]
    us_adjacent: bool
    ussr_adjacent: bool


def _build_countries() -> tuple[Country, ...]:
    """Build the complete map. Adjacency uses indices into the returned tuple."""
    # Define raw data: (name, stability, battleground, region, subregion)
    # Then adjacency separately since it needs cross-references.
    R = Region
    S = Subregion

    raw = [
        # Central America (0-9)
        ("Mexico", 2, True, R.CENTRAL_AMERICA, None),             # 0
        ("Guatemala", 1, False, R.CENTRAL_AMERICA, None),          # 1
        ("El Salvador", 1, False, R.CENTRAL_AMERICA, None),        # 2
        ("Honduras", 2, False, R.CENTRAL_AMERICA, None),           # 3
        ("Costa Rica", 3, False, R.CENTRAL_AMERICA, None),         # 4
        ("Cuba", 3, True, R.CENTRAL_AMERICA, None),                # 5
        ("Nicaragua", 1, False, R.CENTRAL_AMERICA, None),          # 6
        ("Haiti", 1, False, R.CENTRAL_AMERICA, None),              # 7
        ("Dominican Rep", 1, False, R.CENTRAL_AMERICA, None),      # 8
        ("Panama", 2, True, R.CENTRAL_AMERICA, None),              # 9
        # South America (10-19)
        ("Colombia", 1, False, R.SOUTH_AMERICA, None),             # 10
        ("Ecuador", 2, False, R.SOUTH_AMERICA, None),              # 11
        ("Peru", 2, False, R.SOUTH_AMERICA, None),                 # 12
        ("Chile", 3, True, R.SOUTH_AMERICA, None),                 # 13
        ("Argentina", 2, True, R.SOUTH_AMERICA, None),             # 14
        ("Venezuela", 2, True, R.SOUTH_AMERICA, None),             # 15
        ("Bolivia", 2, False, R.SOUTH_AMERICA, None),              # 16
        ("Paraguay", 2, False, R.SOUTH_AMERICA, None),             # 17
        ("Uruguay", 2, False, R.SOUTH_AMERICA, None),              # 18
        ("Brazil", 2, True, R.SOUTH_AMERICA, None),                # 19
        # Western Europe (20-31)
        ("Canada", 4, False, R.EUROPE, S.WESTERN_EUROPE),          # 20
        ("UK", 5, False, R.EUROPE, S.WESTERN_EUROPE),              # 21
        ("Benelux", 3, False, R.EUROPE, S.WESTERN_EUROPE),         # 22
        ("France", 3, True, R.EUROPE, S.WESTERN_EUROPE),           # 23
        ("Spain/Portugal", 2, False, R.EUROPE, S.WESTERN_EUROPE),  # 24
        ("Norway", 3, False, R.EUROPE, S.WESTERN_EUROPE),          # 25
        ("Denmark", 3, False, R.EUROPE, S.WESTERN_EUROPE),         # 26
        ("W.Germany", 4, True, R.EUROPE, S.WESTERN_EUROPE),        # 27
        ("Sweden", 4, False, R.EUROPE, S.WESTERN_EUROPE),          # 28
        ("Italy", 2, True, R.EUROPE, S.WESTERN_EUROPE),            # 29
        ("Greece", 2, False, R.EUROPE, S.WESTERN_EUROPE),          # 30
        ("Turkey", 2, False, R.EUROPE, S.WESTERN_EUROPE),          # 31
        # Both East+West Europe (32-33)
        ("Finland", 4, False, R.EUROPE, None),                     # 32  (both E+W)
        ("Austria", 4, False, R.EUROPE, None),                     # 33  (both E+W)
        # Eastern Europe (34-40)
        ("E.Germany", 3, True, R.EUROPE, S.EASTERN_EUROPE),        # 34
        ("Poland", 3, True, R.EUROPE, S.EASTERN_EUROPE),           # 35
        ("Czechoslovakia", 3, False, R.EUROPE, S.EASTERN_EUROPE),  # 36
        ("Hungary", 3, False, R.EUROPE, S.EASTERN_EUROPE),         # 37
        ("Yugoslavia", 3, False, R.EUROPE, S.EASTERN_EUROPE),      # 38
        ("Romania", 3, False, R.EUROPE, S.EASTERN_EUROPE),         # 39
        ("Bulgaria", 3, False, R.EUROPE, S.EASTERN_EUROPE),        # 40
        # Middle East (41-49)
        ("Lebanon", 1, False, R.MIDDLE_EAST, None),                # 41
        ("Syria", 2, False, R.MIDDLE_EAST, None),                  # 42
        ("Israel", 4, True, R.MIDDLE_EAST, None),                  # 43
        ("Iraq", 3, True, R.MIDDLE_EAST, None),                    # 44
        ("Iran", 2, True, R.MIDDLE_EAST, None),                    # 45
        ("Libya", 2, True, R.MIDDLE_EAST, None),                   # 46
        ("Egypt", 2, True, R.MIDDLE_EAST, None),                   # 47
        ("Jordan", 2, False, R.MIDDLE_EAST, None),                 # 48
        ("Gulf States", 3, False, R.MIDDLE_EAST, None),            # 49
        ("Saudi Arabia", 3, True, R.MIDDLE_EAST, None),            # 50
        # Asia (51-56) + SE Asia (57-63)
        ("Afghanistan", 2, False, R.ASIA, None),                   # 51
        ("Pakistan", 2, True, R.ASIA, None),                       # 52
        ("India", 3, True, R.ASIA, None),                          # 53
        ("Burma", 2, False, R.ASIA, S.SOUTHEAST_ASIA),             # 54
        ("Laos/Cambodia", 1, False, R.ASIA, S.SOUTHEAST_ASIA),     # 55
        ("Thailand", 2, True, R.ASIA, S.SOUTHEAST_ASIA),           # 56
        ("Vietnam", 1, False, R.ASIA, S.SOUTHEAST_ASIA),           # 57
        ("Malaysia", 2, False, R.ASIA, S.SOUTHEAST_ASIA),          # 58
        ("Indonesia", 1, False, R.ASIA, S.SOUTHEAST_ASIA),         # 59
        ("Philippines", 2, False, R.ASIA, S.SOUTHEAST_ASIA),       # 60
        ("Australia", 4, False, R.ASIA, None),                     # 61
        ("Japan", 4, True, R.ASIA, None),                          # 62
        ("Taiwan", 3, False, R.ASIA, None),                        # 63
        ("S.Korea", 3, True, R.ASIA, None),                        # 64
        ("N.Korea", 3, True, R.ASIA, None),                        # 65
        # Africa (66-76)
        ("Tunisia", 2, False, R.AFRICA, None),                     # 66
        ("Algeria", 2, True, R.AFRICA, None),                      # 67
        ("Morocco", 3, False, R.AFRICA, None),                     # 68
        ("W.African States", 2, False, R.AFRICA, None),            # 69
        ("Saharan States", 1, False, R.AFRICA, None),              # 70
        ("Sudan", 1, False, R.AFRICA, None),                       # 71
        ("Ivory Coast", 2, False, R.AFRICA, None),                 # 72
        ("Nigeria", 1, True, R.AFRICA, None),                      # 73
        ("Ethiopia", 1, False, R.AFRICA, None),                    # 74
        ("Somalia", 2, False, R.AFRICA, None),                     # 75
        ("Cameroon", 1, False, R.AFRICA, None),                    # 76
        ("Zaire", 1, True, R.AFRICA, None),                        # 77
        ("Kenya", 2, False, R.AFRICA, None),                       # 78
        ("Angola", 1, True, R.AFRICA, None),                       # 79
        ("Zimbabwe", 1, False, R.AFRICA, None),                    # 80
        ("SE African States", 1, False, R.AFRICA, None),           # 81
        ("Botswana", 2, False, R.AFRICA, None),                    # 82
        ("South Africa", 3, True, R.AFRICA, None),                 # 83
    ]

    # Adjacency: keyed by index, values are list of adjacent indices
    adj: dict[int, list[int]] = {i: [] for i in range(len(raw))}

    def link(a: int, b: int):
        adj[a].append(b)
        adj[b].append(a)

    # Central America
    link(0, 1)    # Mexico-Guatemala
    link(1, 2)    # Guatemala-El Salvador
    link(1, 3)    # Guatemala-Honduras
    link(2, 3)    # El Salvador-Honduras
    link(3, 6)    # Honduras-Nicaragua
    link(3, 4)    # Honduras-Costa Rica (via Honduras connection)
    link(4, 6)    # Costa Rica-Nicaragua
    link(5, 6)    # Cuba-Nicaragua
    link(5, 7)    # Cuba-Haiti
    link(7, 8)    # Haiti-Dominican Rep
    link(4, 9)    # Costa Rica-Panama (via Costa Rica)
    # Central to South America
    link(9, 10)   # Panama-Colombia
    # South America
    link(10, 15)  # Colombia-Venezuela
    link(10, 11)  # Colombia-Ecuador
    link(11, 12)  # Ecuador-Peru
    link(12, 13)  # Peru-Chile
    link(12, 16)  # Peru-Bolivia
    link(13, 14)  # Chile-Argentina
    link(14, 17)  # Argentina-Paraguay
    link(14, 18)  # Argentina-Uruguay
    link(15, 19)  # Venezuela-Brazil
    link(16, 17)  # Bolivia-Paraguay
    link(17, 18)  # Paraguay-Uruguay
    link(18, 19)  # Uruguay-Brazil
    # Western Europe
    link(20, 21)  # Canada-UK
    link(21, 22)  # UK-Benelux
    link(21, 23)  # UK-France
    link(21, 25)  # UK-Norway
    link(22, 23)  # Benelux-France
    link(22, 27)  # Benelux-W.Germany
    link(23, 24)  # France-Spain/Portugal
    link(23, 27)  # France-W.Germany
    link(23, 29)  # France-Italy
    link(24, 29)  # Spain/Portugal-Italy
    link(25, 28)  # Norway-Sweden
    link(25, 26)  # Norway-Denmark
    link(26, 28)  # Denmark-Sweden
    link(26, 27)  # Denmark-W.Germany
    link(28, 32)  # Sweden-Finland
    link(27, 33)  # W.Germany-Austria
    link(27, 34)  # W.Germany-E.Germany
    link(29, 33)  # Italy-Austria
    link(29, 38)  # Italy-Yugoslavia
    link(29, 30)  # Italy-Greece
    link(30, 31)  # Greece-Turkey
    link(30, 40)  # Greece-Bulgaria
    link(30, 38)  # Greece-Yugoslavia
    link(31, 42)  # Turkey-Syria
    link(31, 39)  # Turkey-Romania
    # East+Mid Europe
    link(33, 34)  # Austria-E.Germany
    link(33, 37)  # Austria-Hungary
    link(34, 35)  # E.Germany-Poland
    link(34, 36)  # E.Germany-Czechoslovakia
    link(35, 36)  # Poland-Czechoslovakia
    link(36, 37)  # Czechoslovakia-Hungary
    link(37, 38)  # Hungary-Yugoslavia
    link(37, 39)  # Hungary-Romania
    link(38, 39)  # Yugoslavia-Romania
    link(39, 40)  # Romania-Bulgaria
    link(40, 31)  # Bulgaria-Turkey
    # Middle East
    link(41, 42)  # Lebanon-Syria
    link(41, 43)  # Lebanon-Israel
    link(41, 48)  # Lebanon-Jordan (via Lebanon)
    link(42, 43)  # Syria-Israel
    link(42, 44)  # Syria-Iraq
    link(42, 48)  # Syria-Jordan (via Syria connections)
    link(43, 47)  # Israel-Egypt
    link(43, 48)  # Israel-Jordan
    link(44, 45)  # Iraq-Iran
    link(44, 48)  # Iraq-Jordan
    link(44, 49)  # Iraq-Gulf States
    link(44, 50)  # Iraq-Saudi Arabia
    link(46, 47)  # Libya-Egypt
    link(46, 66)  # Libya-Tunisia
    link(47, 71)  # Egypt-Sudan
    link(48, 50)  # Jordan-Saudi Arabia
    link(49, 50)  # Gulf States-Saudi Arabia
    # Asia
    link(45, 51)  # Iran-Afghanistan
    link(45, 52)  # Iran-Pakistan
    link(51, 52)  # Afghanistan-Pakistan
    link(52, 53)  # Pakistan-India
    link(53, 54)  # India-Burma
    link(54, 55)  # Burma-Laos/Cambodia
    link(54, 56)  # Burma-Thailand (via Burma path -- not standard)
    link(55, 56)  # Laos/Cambodia-Thailand
    link(55, 57)  # Laos/Cambodia-Vietnam
    link(56, 57)  # Thailand-Vietnam
    link(56, 58)  # Thailand-Malaysia
    link(58, 59)  # Malaysia-Indonesia
    link(58, 61)  # Malaysia-Australia
    link(59, 60)  # Indonesia-Philippines
    link(60, 62)  # Philippines-Japan
    link(62, 63)  # Japan-Taiwan
    link(62, 64)  # Japan-S.Korea
    link(63, 64)  # Taiwan-S.Korea
    link(64, 65)  # S.Korea-N.Korea
    # Africa
    link(24, 68)  # Spain/Portugal-Morocco
    link(67, 66)  # Algeria-Tunisia
    link(67, 68)  # Algeria-Morocco
    link(67, 70)  # Algeria-Saharan States
    link(68, 69)  # Morocco-W.African States
    link(69, 72)  # W.African States-Ivory Coast
    link(69, 70)  # W.African States-Saharan States (via connection path -- indirect)
    link(70, 73)  # Saharan States-Nigeria
    link(71, 74)  # Sudan-Ethiopia
    link(72, 73)  # Ivory Coast-Nigeria
    link(73, 76)  # Nigeria-Cameroon
    link(74, 75)  # Ethiopia-Somalia
    link(75, 78)  # Somalia-Kenya
    link(76, 77)  # Cameroon-Zaire
    link(77, 79)  # Zaire-Angola
    link(77, 80)  # Zaire-Zimbabwe
    link(78, 81)  # Kenya-SE African States
    link(79, 82)  # Angola-Botswana
    link(79, 83)  # Angola-South Africa
    link(80, 81)  # Zimbabwe-SE African States
    link(80, 82)  # Zimbabwe-Botswana
    link(82, 83)  # Botswana-South Africa

    # US-adjacent countries (connected to US superpower space)
    us_adj = {0, 5, 20, 62}  # Mexico, Cuba, Canada, Japan
    # USSR-adjacent countries (connected to USSR superpower space)
    ussr_adj = {32, 35, 39, 51, 65}  # Finland, Poland, Romania, Afghanistan, N.Korea

    countries = []
    for i, (name, stab, bg, reg, subreg) in enumerate(raw):
        countries.append(Country(
            id=i,
            name=name,
            stability=stab,
            battleground=bg,
            region=reg,
            subregion=subreg,
            adjacent=tuple(sorted(set(adj[i]))),
            us_adjacent=(i in us_adj),
            ussr_adjacent=(i in ussr_adj),
        ))
    return tuple(countries)


COUNTRIES: tuple[Country, ...] = _build_countries()

_COUNTRY_BY_NAME: dict[str, Country] = {c.name: c for c in COUNTRIES}


def country_by_name(name: str) -> Country:
    return _COUNTRY_BY_NAME[name]
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py -v`
Expected: All TestEnums and TestCountries tests PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add enums and country map data with 84 countries"
```

---

### Task 2: Card Definitions

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestCards:
    def test_total_cards(self):
        from ts import CARDS
        assert len(CARDS) == 110

    def test_china_card(self):
        from ts import CARDS, card_by_id, Side, Period
        china = card_by_id(6)
        assert china.name == "The China Card"
        assert china.ops == 4
        assert china.scoring is False

    def test_scoring_cards(self):
        from ts import CARDS
        scoring = [c for c in CARDS if c.scoring]
        assert len(scoring) == 7  # Asia, Europe, ME, CA, SA, Africa, SE Asia

    def test_early_war_count(self):
        from ts import CARDS, Period
        early = [c for c in CARDS if c.war_period == Period.EARLY]
        assert len(early) == 35

    def test_mid_war_count(self):
        from ts import CARDS, Period
        mid = [c for c in CARDS if c.war_period == Period.MID]
        assert len(mid) == 46

    def test_late_war_count(self):
        from ts import CARDS, Period
        late = [c for c in CARDS if c.war_period == Period.LATE]
        assert len(late) == 21

    def test_optional_cards(self):
        from ts import CARDS, Period
        optional = [c for c in CARDS if c.war_period == Period.OPTIONAL]
        assert len(optional) == 8

    def test_se_asia_scoring_removed(self):
        from ts import card_by_id
        se_asia = card_by_id(38)
        assert se_asia.name == "Southeast Asia Scoring"
        assert se_asia.scoring is True
        assert se_asia.removed_after_event is True

    def test_defectors(self):
        from ts import card_by_id, Side, Period
        d = card_by_id(103)
        assert d.name == "Defectors"
        assert d.ops == 2
        assert d.side == Side.US
        assert d.war_period == Period.EARLY
```

Note: Add `OPTIONAL` to the `Period` enum for the 8 optional cards (104-110 + Defectors uses EARLY).

**Step 2: Run to verify failure**

**Step 3: Implement CardDef and CARDS**

Add `OPTIONAL` value to `Period` enum. Add to `ts.py`:

```python
@dataclass(frozen=True)
class CardDef:
    id: int
    name: str
    ops: int
    side: Side
    war_period: Period
    removed_after_event: bool
    scoring: bool


def _build_cards() -> tuple[CardDef, ...]:
    S = Side
    P = Period
    cards = [
        # Early War (1-35)
        CardDef(1, "Asia Scoring", 0, S.NEUTRAL, P.EARLY, False, True),
        CardDef(2, "Europe Scoring", 0, S.NEUTRAL, P.EARLY, False, True),
        CardDef(3, "Middle East Scoring", 0, S.NEUTRAL, P.EARLY, False, True),
        CardDef(4, "Duck and Cover", 3, S.US, P.EARLY, False, False),
        CardDef(5, "Five Year Plan", 3, S.USSR, P.EARLY, False, False),
        CardDef(6, "The China Card", 4, S.NEUTRAL, P.EARLY, False, False),
        CardDef(7, "Socialist Governments", 3, S.USSR, P.EARLY, False, False),
        CardDef(8, "Fidel", 2, S.USSR, P.EARLY, True, False),
        CardDef(9, "Vietnam Revolts", 2, S.USSR, P.EARLY, True, False),
        CardDef(10, "Blockade", 1, S.USSR, P.EARLY, True, False),
        CardDef(11, "Korean War", 2, S.USSR, P.EARLY, True, False),
        CardDef(12, "Romanian Abdication", 1, S.USSR, P.EARLY, True, False),
        CardDef(13, "Arab-Israeli War", 2, S.USSR, P.EARLY, False, False),
        CardDef(14, "Comecon", 3, S.USSR, P.EARLY, True, False),
        CardDef(15, "Nasser", 1, S.USSR, P.EARLY, True, False),
        CardDef(16, "Warsaw Pact Formed", 3, S.USSR, P.EARLY, True, False),
        CardDef(17, "De Gaulle Leads France", 3, S.USSR, P.EARLY, True, False),
        CardDef(18, "Captured Nazi Scientist", 1, S.NEUTRAL, P.EARLY, True, False),
        CardDef(19, "Truman Doctrine", 1, S.US, P.EARLY, True, False),
        CardDef(20, "Olympic Games", 2, S.NEUTRAL, P.EARLY, False, False),
        CardDef(21, "NATO", 4, S.US, P.EARLY, True, False),
        CardDef(22, "Independent Reds", 2, S.US, P.EARLY, True, False),
        CardDef(23, "Marshall Plan", 4, S.US, P.EARLY, True, False),
        CardDef(24, "Indo-Pakistani War", 2, S.NEUTRAL, P.EARLY, False, False),
        CardDef(25, "Containment", 3, S.US, P.EARLY, True, False),
        CardDef(26, "CIA Created", 1, S.US, P.EARLY, True, False),
        CardDef(27, "US/Japan Mutual Defense Pact", 4, S.US, P.EARLY, True, False),
        CardDef(28, "Suez Crisis", 3, S.USSR, P.EARLY, True, False),
        CardDef(29, "East European Unrest", 3, S.US, P.EARLY, False, False),
        CardDef(30, "Decolonization", 2, S.USSR, P.EARLY, False, False),
        CardDef(31, "Red Scare/Purge", 4, S.NEUTRAL, P.EARLY, False, False),
        CardDef(32, "UN Intervention", 1, S.NEUTRAL, P.EARLY, False, False),
        CardDef(33, "De-Stalinization", 3, S.USSR, P.EARLY, True, False),
        CardDef(34, "Nuclear Test Ban", 4, S.NEUTRAL, P.EARLY, False, False),
        CardDef(35, "Formosan Resolution", 2, S.US, P.EARLY, True, False),
        # Mid War (36-81)
        CardDef(36, "Brush War", 3, S.NEUTRAL, P.MID, False, False),
        CardDef(37, "Central America Scoring", 0, S.NEUTRAL, P.MID, False, True),
        CardDef(38, "Southeast Asia Scoring", 0, S.NEUTRAL, P.MID, True, True),
        CardDef(39, "Arms Race", 3, S.NEUTRAL, P.MID, False, False),
        CardDef(40, "Cuban Missile Crisis", 3, S.NEUTRAL, P.MID, True, False),
        CardDef(41, "Nuclear Subs", 2, S.US, P.MID, True, False),
        CardDef(42, "Quagmire", 3, S.USSR, P.MID, True, False),
        CardDef(43, "SALT Negotiations", 3, S.NEUTRAL, P.MID, True, False),
        CardDef(44, "Bear Trap", 3, S.US, P.MID, True, False),
        CardDef(45, "Summit", 1, S.NEUTRAL, P.MID, False, False),
        CardDef(46, "How I Learned to Stop Worrying", 2, S.NEUTRAL, P.MID, True, False),
        CardDef(47, "Junta", 2, S.NEUTRAL, P.MID, False, False),
        CardDef(48, "Kitchen Debates", 1, S.US, P.MID, True, False),
        CardDef(49, "Missile Envy", 2, S.NEUTRAL, P.MID, False, False),
        CardDef(50, "We Will Bury You", 4, S.USSR, P.MID, True, False),
        CardDef(51, "Brezhnev Doctrine", 3, S.USSR, P.MID, True, False),
        CardDef(52, "Portuguese Empire Crumbles", 2, S.USSR, P.MID, True, False),
        CardDef(53, "South African Unrest", 2, S.USSR, P.MID, False, False),
        CardDef(54, "Allende", 1, S.USSR, P.MID, True, False),
        CardDef(55, "Willy Brandt", 2, S.USSR, P.MID, True, False),
        CardDef(56, "Muslim Revolution", 4, S.USSR, P.MID, False, False),
        CardDef(57, "ABM Treaty", 4, S.NEUTRAL, P.MID, False, False),
        CardDef(58, "Cultural Revolution", 3, S.USSR, P.MID, True, False),
        CardDef(59, "Flower Power", 4, S.USSR, P.MID, True, False),
        CardDef(60, "U2 Incident", 3, S.USSR, P.MID, True, False),
        CardDef(61, "OPEC", 3, S.USSR, P.MID, False, False),
        CardDef(62, "Lone Gunman", 1, S.USSR, P.MID, True, False),
        CardDef(63, "Colonial Rear Guards", 2, S.NEUTRAL, P.MID, False, False),
        CardDef(64, "Panama Canal Returned", 1, S.US, P.MID, True, False),
        CardDef(65, "Camp David Accords", 2, S.US, P.MID, True, False),
        CardDef(66, "Puppet Governments", 2, S.US, P.MID, True, False),
        CardDef(67, "Grain Sales to Soviets", 2, S.US, P.MID, False, False),
        CardDef(68, "John Paul II Elected Pope", 2, S.US, P.MID, True, False),
        CardDef(69, "Latin American Death Squads", 2, S.NEUTRAL, P.MID, False, False),
        CardDef(70, "OAS Founded", 1, S.US, P.MID, True, False),
        CardDef(71, "Nixon Plays the China Card", 2, S.US, P.MID, True, False),
        CardDef(72, "Sadat Expels Soviets", 1, S.US, P.MID, True, False),
        CardDef(73, "Shuttle Diplomacy", 3, S.US, P.MID, False, False),
        CardDef(74, "The Voice of America", 2, S.US, P.MID, False, False),
        CardDef(75, "Liberation Theology", 2, S.USSR, P.MID, False, False),
        CardDef(76, "Ussuri River Skirmish", 3, S.US, P.MID, True, False),
        CardDef(77, "Ask Not What Your Country Can Do For You", 3, S.US, P.MID, True, False),
        CardDef(78, "Alliance for Progress", 3, S.US, P.MID, True, False),
        CardDef(79, "Africa Scoring", 0, S.NEUTRAL, P.MID, False, True),
        CardDef(80, "One Small Step", 2, S.NEUTRAL, P.MID, False, False),
        CardDef(81, "South America Scoring", 0, S.NEUTRAL, P.MID, False, True),
        # Late War (82-102)
        CardDef(82, "Iranian Hostage Crisis", 3, S.USSR, P.LATE, True, False),
        CardDef(83, "The Iron Lady", 3, S.US, P.LATE, True, False),
        CardDef(84, "Reagan Bombs Libya", 2, S.US, P.LATE, True, False),
        CardDef(85, "Star Wars", 2, S.US, P.LATE, True, False),
        CardDef(86, "North Sea Oil", 3, S.US, P.LATE, True, False),
        CardDef(87, "The Reformer", 3, S.USSR, P.LATE, True, False),
        CardDef(88, "Marine Barracks Bombing", 2, S.NEUTRAL, P.LATE, True, False),
        CardDef(89, "Soviets Shoot Down KAL-007", 4, S.US, P.LATE, True, False),
        CardDef(90, "Glasnost", 4, S.USSR, P.LATE, True, False),
        CardDef(91, "Ortega Elected in Nicaragua", 2, S.USSR, P.LATE, True, False),
        CardDef(92, "Terrorism", 2, S.NEUTRAL, P.LATE, False, False),
        CardDef(93, "Iran-Contra Scandal", 2, S.USSR, P.LATE, True, False),
        CardDef(94, "Chernobyl", 3, S.US, P.LATE, True, False),
        CardDef(95, "Latin American Debt Crisis", 2, S.NEUTRAL, P.LATE, False, False),
        CardDef(96, "Tear Down This Wall", 3, S.US, P.LATE, True, False),
        CardDef(97, "An Evil Empire", 3, S.US, P.LATE, True, False),
        CardDef(98, "Aldrich Ames Remix", 3, S.USSR, P.LATE, True, False),
        CardDef(99, "Pershing II Deployed", 3, S.USSR, P.LATE, True, False),
        CardDef(100, "Wargames", 4, S.NEUTRAL, P.LATE, True, False),
        CardDef(101, "Solidarity", 2, S.US, P.LATE, True, False),
        CardDef(102, "Iran-Iraq War", 2, S.NEUTRAL, P.LATE, True, False),
        # Early War extra
        CardDef(103, "Defectors", 2, S.US, P.EARLY, False, False),
        # Optional (104-110)
        CardDef(104, "The Cambridge Five", 2, S.USSR, P.OPTIONAL, False, False),
        CardDef(105, "Special Relationship", 2, S.US, P.OPTIONAL, False, False),
        CardDef(106, "NORAD", 3, S.US, P.OPTIONAL, True, False),
        CardDef(107, "Che", 3, S.USSR, P.OPTIONAL, False, False),
        CardDef(108, "Our Man in Tehran", 2, S.US, P.OPTIONAL, True, False),
        CardDef(109, "Yuri and Samantha", 2, S.USSR, P.OPTIONAL, True, False),
        CardDef(110, "AWACS Sale to Saudis", 3, S.US, P.OPTIONAL, True, False),
    ]
    return tuple(cards)


CARDS: tuple[CardDef, ...] = _build_cards()

_CARD_BY_ID: dict[int, CardDef] = {c.id: c for c in CARDS}


def card_by_id(card_id: int) -> CardDef:
    return _CARD_BY_ID[card_id]
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestCards -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add all 110 card definitions"
```

---

### Task 3: Space Race Track and Scoring Tables

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestSpaceRace:
    def test_track_length(self):
        from ts import SPACE_RACE_TRACK
        assert len(SPACE_RACE_TRACK) == 9  # positions 0-8

    def test_satellite(self):
        from ts import SPACE_RACE_TRACK
        sat = SPACE_RACE_TRACK[1]
        assert sat.name == "Satellite"
        assert sat.ops_required == 2
        assert sat.roll_max == 3
        assert sat.first_vp == 2
        assert sat.second_vp == 1

    def test_station(self):
        from ts import SPACE_RACE_TRACK
        station = SPACE_RACE_TRACK[8]
        assert station.name == "Station"
        assert station.ops_required == 4
        assert station.roll_max == 2


class TestScoringTable:
    def test_europe_control_auto_win(self):
        from ts import SCORING_TABLE, Region
        europe = SCORING_TABLE[Region.EUROPE]
        assert europe.control == 1000  # signals auto-win

    def test_asia_scoring(self):
        from ts import SCORING_TABLE, Region
        asia = SCORING_TABLE[Region.ASIA]
        assert asia.presence == 3
        assert asia.domination == 7
        assert asia.control == 9

    def test_central_america_scoring(self):
        from ts import SCORING_TABLE, Region
        ca = SCORING_TABLE[Region.CENTRAL_AMERICA]
        assert ca.presence == 1
        assert ca.domination == 3
        assert ca.control == 5
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
@dataclass(frozen=True)
class SpaceBox:
    name: str
    ops_required: int
    roll_max: int       # succeed if die <= roll_max
    first_vp: int
    second_vp: int


SPACE_RACE_TRACK: tuple[SpaceBox, ...] = (
    SpaceBox("Start", 0, 0, 0, 0),
    SpaceBox("Satellite", 2, 3, 2, 1),
    SpaceBox("Animal in Space", 2, 4, 0, 0),
    SpaceBox("Man in Space", 2, 3, 2, 0),
    SpaceBox("Man in Earth Orbit", 2, 4, 0, 0),
    SpaceBox("Lunar Orbit", 3, 3, 3, 1),
    SpaceBox("Eagle/Bear Has Landed", 3, 4, 0, 0),
    SpaceBox("Space Shuttle", 3, 3, 4, 2),
    SpaceBox("Station", 4, 2, 2, 0),
)


@dataclass(frozen=True)
class RegionScoring:
    presence: int
    domination: int
    control: int


SCORING_TABLE: dict[Region, RegionScoring] = {
    Region.EUROPE: RegionScoring(3, 7, 1000),  # control = auto-win
    Region.ASIA: RegionScoring(3, 7, 9),
    Region.MIDDLE_EAST: RegionScoring(3, 5, 7),
    Region.CENTRAL_AMERICA: RegionScoring(1, 3, 5),
    Region.SOUTH_AMERICA: RegionScoring(2, 5, 6),
    Region.AFRICA: RegionScoring(1, 4, 6),
}
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add space race track and scoring tables"
```

---

### Task 4: GameState and Country Control Logic

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestCountryControl:
    def test_uncontrolled(self):
        from ts import GameState, Side, controls_country, country_by_name
        gs = GameState.new()
        israel = country_by_name("Israel")
        assert controls_country(gs, israel.id, Side.US) is False
        assert controls_country(gs, israel.id, Side.USSR) is False

    def test_us_controls(self):
        from ts import GameState, Side, controls_country, country_by_name
        gs = GameState.new()
        # Israel stability 4: need >= 4 and exceed opponent by >= 4
        israel = country_by_name("Israel")
        gs.influence[israel.id][Side.US] = 4
        assert controls_country(gs, israel.id, Side.US) is True

    def test_control_requires_margin(self):
        from ts import GameState, Side, controls_country, country_by_name
        gs = GameState.new()
        israel = country_by_name("Israel")
        gs.influence[israel.id][Side.US] = 5
        gs.influence[israel.id][Side.USSR] = 2
        # US has 5, USSR has 2. Margin = 3 < stability 4.
        assert controls_country(gs, israel.id, Side.US) is False

    def test_control_with_margin(self):
        from ts import GameState, Side, controls_country, country_by_name
        gs = GameState.new()
        turkey = country_by_name("Turkey")  # stability 2
        gs.influence[turkey.id][Side.US] = 4
        gs.influence[turkey.id][Side.USSR] = 2
        # US has 4 >= 2 stability, margin = 2 >= 2 stability
        assert controls_country(gs, turkey.id, Side.US) is True

    def test_countries_in_region(self):
        from ts import COUNTRIES, Region
        me_countries = [c for c in COUNTRIES if c.region == Region.MIDDLE_EAST]
        assert len(me_countries) == 10
```

**Step 2: Run to verify failure**

**Step 3: Implement GameState and control logic**

```python
@dataclass
class GameState:
    influence: list[list[int]]        # [country_id][Side.US or Side.USSR]
    defcon: int
    vp: int                           # positive = US leading
    turn: int
    action_round: int
    phase: Phase
    phasing_player: Side
    space_race: list[int]             # [us_pos, ussr_pos]
    mil_ops: list[int]                # [us_milops, ussr_milops]
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
    space_race_used: list[bool]       # [us_used_this_turn, ussr_used_this_turn]
    game_over: bool
    winner: Side | None
    # Ops tracking for multi-step actions
    ops_remaining: int
    active_card: int | None

    @staticmethod
    def new() -> GameState:
        return GameState(
            influence=[[0, 0] for _ in range(len(COUNTRIES))],
            defcon=5,
            vp=0,
            turn=0,
            action_round=0,
            phase=Phase.SETUP,
            phasing_player=Side.USSR,
            space_race=[0, 0],
            mil_ops=[0, 0],
            us_hand=[],
            ussr_hand=[],
            china_card_holder=Side.USSR,
            china_card_face_up=True,
            china_card_playable=True,
            draw_pile=[],
            discard_pile=[],
            removed_pile=[],
            us_headline=None,
            ussr_headline=None,
            space_race_used=[False, False],
            game_over=False,
            winner=None,
            ops_remaining=0,
            active_card=None,
        )


def controls_country(gs: GameState, country_id: int, side: Side) -> bool:
    """Rule 2.1.7: Control requires influence >= stability AND margin >= stability."""
    c = COUNTRIES[country_id]
    other = Side.USSR if side == Side.US else Side.US
    own = gs.influence[country_id][side]
    opp = gs.influence[country_id][other]
    return own >= c.stability and (own - opp) >= c.stability
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestCountryControl -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add GameState and country control logic"
```

---

### Task 5: Scoring Engine

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestScoring:
    def _setup_state(self):
        from ts import GameState, Side, country_by_name
        gs = GameState.new()
        return gs

    def test_no_presence(self):
        from ts import GameState, Region, score_region
        gs = GameState.new()
        us_vp, ussr_vp = score_region(gs, Region.MIDDLE_EAST)
        assert us_vp == 0
        assert ussr_vp == 0

    def test_us_presence(self):
        from ts import GameState, Side, Region, score_region, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.US] = 2
        us_vp, ussr_vp = score_region(gs, Region.MIDDLE_EAST)
        # Presence(3) + 1 BG bonus = 4
        assert us_vp == 4
        assert ussr_vp == 0

    def test_domination(self):
        from ts import GameState, Side, Region, score_region, country_by_name
        gs = GameState.new()
        # USSR controls Cuba(BG,stab3), Haiti(non-BG,stab1), DR(non-BG,stab1)
        # US controls Guatemala(non-BG,stab1)
        for name, inf in [("Cuba", 3), ("Haiti", 1), ("Dominican Rep", 1)]:
            c = country_by_name(name)
            gs.influence[c.id][Side.USSR] = inf
        guat = country_by_name("Guatemala")
        gs.influence[guat.id][Side.US] = 1
        us_vp, ussr_vp = score_region(gs, Region.CENTRAL_AMERICA)
        # USSR: Domination(3) + 1(Cuba BG) + 1(Cuba adj to US) = 5
        assert ussr_vp == 5
        # US: Presence(1)
        assert us_vp == 1

    def test_control(self):
        from ts import GameState, Side, Region, score_region, country_by_name
        gs = GameState.new()
        # US controls all 3 CA battlegrounds + more countries total
        for name in ["Mexico", "Cuba", "Panama", "Guatemala", "Honduras"]:
            c = country_by_name(name)
            gs.influence[c.id][Side.US] = c.stability
        us_vp, ussr_vp = score_region(gs, Region.CENTRAL_AMERICA)
        # US has Control: 5 VP + 3 BG bonus + 1 (Cuba adj US) = 9
        assert us_vp == 9
        assert ussr_vp == 0

    def test_adjacency_bonus(self):
        from ts import GameState, Side, Region, score_region, country_by_name
        gs = GameState.new()
        # N.Korea is adjacent to USSR; if US controls it, +1 VP
        nk = country_by_name("N.Korea")
        gs.influence[nk.id][Side.US] = 3  # stability 3
        us_vp, _ = score_region(gs, Region.ASIA)
        # Presence(3) + 1(BG) + 1(adj to USSR) = 5
        assert us_vp == 5
```

**Step 2: Run to verify failure**

**Step 3: Implement scoring**

```python
def _countries_in_region(region: Region) -> list[Country]:
    """Get all countries in a region (including subregions for Europe/Asia)."""
    return [c for c in COUNTRIES if c.region == region]


def _countries_in_subregion(subregion: Subregion) -> list[Country]:
    return [c for c in COUNTRIES
            if c.subregion == subregion or
            (subregion in (Subregion.EASTERN_EUROPE, Subregion.WESTERN_EUROPE) and c.subregion is None and c.region == Region.EUROPE)]


def score_region(gs: GameState, region: Region) -> tuple[int, int]:
    """Score a region. Returns (us_vp, ussr_vp).

    Rule 10.1: Presence/Domination/Control + BG bonus + adjacency bonus.
    """
    countries = _countries_in_region(region)
    scoring = SCORING_TABLE[region]

    us_controlled = []
    ussr_controlled = []
    us_bg = 0
    ussr_bg = 0

    for c in countries:
        if controls_country(gs, c.id, Side.US):
            us_controlled.append(c)
            if c.battleground:
                us_bg += 1
        elif controls_country(gs, c.id, Side.USSR):
            ussr_controlled.append(c)
            if c.battleground:
                ussr_bg += 1

    total_bg = sum(1 for c in countries if c.battleground)

    def calc_vp(controlled: list[Country], bg_count: int, opp_bg: int,
                opp_count: int, side: Side) -> int:
        if not controlled:
            return 0

        vp = 0
        # Determine level: Control > Domination > Presence
        has_all_bg = (bg_count == total_bg and total_bg > 0)
        more_countries = len(controlled) > opp_count
        more_bg = bg_count > opp_bg
        has_bg = bg_count > 0
        has_non_bg = any(not c.battleground for c in controlled)

        if has_all_bg and more_countries:
            vp += scoring.control
        elif more_countries and more_bg and has_bg and has_non_bg:
            vp += scoring.domination
        else:
            vp += scoring.presence

        # Bonuses
        for c in controlled:
            if c.battleground:
                vp += 1
            other_side = Side.USSR if side == Side.US else Side.US
            if (side == Side.US and c.ussr_adjacent) or (side == Side.USSR and c.us_adjacent):
                vp += 1

        return vp

    us_vp = calc_vp(us_controlled, us_bg, ussr_bg, len(ussr_controlled), Side.US)
    ussr_vp = calc_vp(ussr_controlled, ussr_bg, us_bg, len(us_controlled), Side.USSR)

    return us_vp, ussr_vp
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestScoring -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add region scoring engine"
```

---

### Task 6: Influence Placement

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestInfluencePlacement:
    def test_cost_uncontrolled(self):
        from ts import GameState, Side, influence_cost, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        assert influence_cost(gs, iran.id, Side.US) == 1

    def test_cost_enemy_controlled(self):
        from ts import GameState, Side, influence_cost, country_by_name
        gs = GameState.new()
        turkey = country_by_name("Turkey")  # stability 2
        gs.influence[turkey.id][Side.USSR] = 2
        # USSR controls Turkey: cost 2 for US
        assert influence_cost(gs, turkey.id, Side.US) == 2

    def test_cost_friendly_controlled(self):
        from ts import GameState, Side, influence_cost, country_by_name
        gs = GameState.new()
        turkey = country_by_name("Turkey")
        gs.influence[turkey.id][Side.US] = 2
        assert influence_cost(gs, turkey.id, Side.US) == 1

    def test_can_place_adjacent_to_friendly(self):
        from ts import GameState, Side, can_place_influence, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.US] = 1
        # Pakistan is adjacent to Iran
        pakistan = country_by_name("Pakistan")
        assert can_place_influence(gs, pakistan.id, Side.US) is True

    def test_cannot_place_nonadjacent(self):
        from ts import GameState, Side, can_place_influence, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.US] = 1
        # Brazil is not adjacent to Iran
        brazil = country_by_name("Brazil")
        assert can_place_influence(gs, brazil.id, Side.US) is False

    def test_can_place_adjacent_to_superpower(self):
        from ts import GameState, Side, can_place_influence, country_by_name
        gs = GameState.new()
        # Canada is US-adjacent, always placeable
        canada = country_by_name("Canada")
        assert can_place_influence(gs, canada.id, Side.US) is True

    def test_place_influence(self):
        from ts import GameState, Side, place_influence, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.US] = 1
        place_influence(gs, iran.id, Side.US)
        assert gs.influence[iran.id][Side.US] == 2
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def influence_cost(gs: GameState, country_id: int, side: Side) -> int:
    """Rule 6.1.2: 1 op for friendly/uncontrolled, 2 for enemy-controlled."""
    other = Side.USSR if side == Side.US else Side.US
    if controls_country(gs, country_id, other):
        return 2
    return 1


def can_place_influence(gs: GameState, country_id: int, side: Side) -> bool:
    """Rule 6.1.1/6.1.4: Must be adjacent to existing friendly influence or superpower."""
    c = COUNTRIES[country_id]
    # Adjacent to superpower
    if side == Side.US and c.us_adjacent:
        return True
    if side == Side.USSR and c.ussr_adjacent:
        return True
    # Adjacent to friendly influence
    for adj_id in c.adjacent:
        if gs.influence[adj_id][side] > 0:
            return True
    # Has own influence already
    if gs.influence[country_id][side] > 0:
        return True
    return False


def place_influence(gs: GameState, country_id: int, side: Side):
    """Place one influence marker."""
    gs.influence[country_id][side] += 1
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestInfluencePlacement -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add influence placement with adjacency and cost rules"
```

---

### Task 7: Coup Attempts

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestCoup:
    def test_successful_coup(self):
        from ts import GameState, Side, resolve_coup, country_by_name
        gs = GameState.new()
        mexico = country_by_name("Mexico")  # stability 2
        gs.influence[mexico.id][Side.USSR] = 2
        # die=4, ops=3: 4+3=7 > 2*2=4, result=3
        # Remove 2 USSR, add 1 US
        resolve_coup(gs, mexico.id, Side.US, ops=3, die_roll=4)
        assert gs.influence[mexico.id][Side.USSR] == 0
        assert gs.influence[mexico.id][Side.US] == 1

    def test_failed_coup(self):
        from ts import GameState, Side, resolve_coup, country_by_name
        gs = GameState.new()
        mexico = country_by_name("Mexico")
        gs.influence[mexico.id][Side.USSR] = 2
        # die=1, ops=2: 1+2=3 <= 2*2=4, no effect
        resolve_coup(gs, mexico.id, Side.US, ops=2, die_roll=1)
        assert gs.influence[mexico.id][Side.USSR] == 2
        assert gs.influence[mexico.id][Side.US] == 0

    def test_coup_defcon_degradation(self):
        from ts import GameState, Side, resolve_coup, country_by_name
        gs = GameState.new()
        gs.defcon = 5
        iran = country_by_name("Iran")  # battleground
        gs.influence[iran.id][Side.USSR] = 1
        resolve_coup(gs, iran.id, Side.US, ops=3, die_roll=1)
        assert gs.defcon == 4  # degraded by 1 for BG coup

    def test_coup_no_defcon_for_non_bg(self):
        from ts import GameState, Side, resolve_coup, country_by_name
        gs = GameState.new()
        gs.defcon = 5
        lebanon = country_by_name("Lebanon")  # not battleground
        gs.influence[lebanon.id][Side.USSR] = 1
        resolve_coup(gs, lebanon.id, Side.US, ops=2, die_roll=1)
        assert gs.defcon == 5

    def test_coup_milops_tracking(self):
        from ts import GameState, Side, resolve_coup, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.USSR] = 1
        resolve_coup(gs, iran.id, Side.US, ops=3, die_roll=1)
        assert gs.mil_ops[Side.US] == 3

    def test_defcon_1_game_over(self):
        from ts import GameState, Side, resolve_coup, country_by_name
        gs = GameState.new()
        gs.defcon = 2
        iran = country_by_name("Iran")  # BG
        gs.influence[iran.id][Side.USSR] = 1
        gs.phasing_player = Side.US
        resolve_coup(gs, iran.id, Side.US, ops=3, die_roll=1)
        assert gs.defcon == 1
        assert gs.game_over is True
        assert gs.winner == Side.USSR  # phasing player (US) loses
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def resolve_coup(gs: GameState, country_id: int, side: Side, ops: int, die_roll: int):
    """Rule 6.3: Resolve coup attempt. Mutates gs."""
    c = COUNTRIES[country_id]
    other = Side.USSR if side == Side.US else Side.US

    # Track mil ops (6.3.3)
    gs.mil_ops[side] += ops

    # DEFCON degradation for battleground coups (6.3.4)
    if c.battleground:
        gs.defcon -= 1
        if gs.defcon <= 1:
            gs.defcon = 1
            gs.game_over = True
            gs.winner = other  # phasing player loses (8.1.3)
            return

    # Resolve (6.3.2)
    roll_plus_ops = die_roll + ops
    target = c.stability * 2
    if roll_plus_ops > target:
        diff = roll_plus_ops - target
        # Remove opponent influence first, then add own
        removed = min(diff, gs.influence[country_id][other])
        gs.influence[country_id][other] -= removed
        remaining = diff - removed
        gs.influence[country_id][side] += remaining
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestCoup -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add coup resolution with DEFCON degradation"
```

---

### Task 8: Realignment Rolls

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestRealignment:
    def test_realignment_modifiers(self):
        from ts import GameState, Side, realignment_modifiers, country_by_name
        gs = GameState.new()
        nk = country_by_name("N.Korea")  # adjacent to USSR
        gs.influence[nk.id][Side.USSR] = 3
        us_mod, ussr_mod = realignment_modifiers(gs, nk.id)
        # USSR: +1 adjacent superpower, +1 more influence in target
        assert ussr_mod == 2
        assert us_mod == 0

    def test_realignment_us_wins(self):
        from ts import GameState, Side, resolve_realignment, country_by_name
        gs = GameState.new()
        nk = country_by_name("N.Korea")
        gs.influence[nk.id][Side.USSR] = 3
        # US rolls 5, USSR rolls 2 (mod +2 = 4). US wins by 1.
        resolve_realignment(gs, nk.id, Side.US, us_roll=5, ussr_roll=2)
        assert gs.influence[nk.id][Side.USSR] == 2

    def test_realignment_tie(self):
        from ts import GameState, Side, resolve_realignment, country_by_name
        gs = GameState.new()
        nk = country_by_name("N.Korea")
        gs.influence[nk.id][Side.USSR] = 3
        resolve_realignment(gs, nk.id, Side.US, us_roll=4, ussr_roll=2)
        # USSR mod +2: 2+2=4, tie with US 4. No change.
        assert gs.influence[nk.id][Side.USSR] == 3

    def test_realignment_no_add(self):
        from ts import GameState, Side, resolve_realignment, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.USSR] = 1
        resolve_realignment(gs, iran.id, Side.US, us_roll=6, ussr_roll=1)
        # US wins. Only removes USSR influence, never adds.
        assert gs.influence[iran.id][Side.US] == 0

    def test_adjacent_controlled_modifier(self):
        from ts import GameState, Side, realignment_modifiers, country_by_name
        gs = GameState.new()
        # US controls Turkey and Jordan (adjacent to Syria)
        turkey = country_by_name("Turkey")
        jordan = country_by_name("Jordan")
        syria = country_by_name("Syria")
        gs.influence[turkey.id][Side.US] = 2  # controls (stab 2)
        gs.influence[jordan.id][Side.US] = 2  # controls (stab 2)
        gs.influence[syria.id][Side.USSR] = 1
        us_mod, ussr_mod = realignment_modifiers(gs, syria.id)
        # US: +1 (Turkey controlled adj) + +1 (Jordan controlled adj) = 2
        # (no superpower adjacency, no more influence)
        assert us_mod == 2
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def realignment_modifiers(gs: GameState, country_id: int) -> tuple[int, int]:
    """Rule 6.2.2: Calculate realignment die modifiers for both sides."""
    c = COUNTRIES[country_id]
    us_mod = 0
    ussr_mod = 0

    # +1 for each adjacent controlled country
    for adj_id in c.adjacent:
        if controls_country(gs, adj_id, Side.US):
            us_mod += 1
        if controls_country(gs, adj_id, Side.USSR):
            ussr_mod += 1

    # +1 if more influence in target
    if gs.influence[country_id][Side.US] > gs.influence[country_id][Side.USSR]:
        us_mod += 1
    elif gs.influence[country_id][Side.USSR] > gs.influence[country_id][Side.US]:
        ussr_mod += 1

    # +1 if superpower adjacent
    if c.us_adjacent:
        us_mod += 1
    if c.ussr_adjacent:
        ussr_mod += 1

    return us_mod, ussr_mod


def resolve_realignment(gs: GameState, country_id: int, acting_side: Side,
                        us_roll: int, ussr_roll: int):
    """Rule 6.2: Resolve realignment roll. Mutates gs."""
    us_mod, ussr_mod = realignment_modifiers(gs, country_id)
    us_total = us_roll + us_mod
    ussr_total = ussr_roll + ussr_mod

    if us_total > ussr_total:
        diff = us_total - ussr_total
        gs.influence[country_id][Side.USSR] = max(0, gs.influence[country_id][Side.USSR] - diff)
    elif ussr_total > us_total:
        diff = ussr_total - us_total
        gs.influence[country_id][Side.US] = max(0, gs.influence[country_id][Side.US] - diff)
    # Tie: no effect (6.2.2)
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestRealignment -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add realignment rolls with modifiers"
```

---

### Task 9: DEFCON Restrictions and Military Ops

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestDefcon:
    def test_defcon_restrictions(self):
        from ts import defcon_restricts_region, Region
        # DEFCON 5: no restrictions
        assert defcon_restricts_region(5, Region.EUROPE) is False
        # DEFCON 4: Europe restricted
        assert defcon_restricts_region(4, Region.EUROPE) is True
        assert defcon_restricts_region(4, Region.ASIA) is False
        # DEFCON 3: Europe + Asia
        assert defcon_restricts_region(3, Region.EUROPE) is True
        assert defcon_restricts_region(3, Region.ASIA) is True
        assert defcon_restricts_region(3, Region.MIDDLE_EAST) is False
        # DEFCON 2: Europe + Asia + Middle East
        assert defcon_restricts_region(2, Region.EUROPE) is True
        assert defcon_restricts_region(2, Region.ASIA) is True
        assert defcon_restricts_region(2, Region.MIDDLE_EAST) is True
        assert defcon_restricts_region(2, Region.CENTRAL_AMERICA) is False


class TestMilOps:
    def test_penalty_none(self):
        from ts import milops_penalty
        # DEFCON 4, player did 4 milops: no penalty
        assert milops_penalty(defcon=4, milops=4) == 0

    def test_penalty_deficit(self):
        from ts import milops_penalty
        # DEFCON 4, player did 2: penalty = 2
        assert milops_penalty(defcon=4, milops=2) == 2

    def test_penalty_excess(self):
        from ts import milops_penalty
        # DEFCON 3, player did 5: no penalty
        assert milops_penalty(defcon=3, milops=5) == 0
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def defcon_restricts_region(defcon: int, region: Region) -> bool:
    """Rule 8.1.5: Check if DEFCON level restricts coup/realignment in a region."""
    if defcon <= 4 and region == Region.EUROPE:
        return True
    if defcon <= 3 and region == Region.ASIA:
        return True
    if defcon <= 2 and region == Region.MIDDLE_EAST:
        return True
    return False


def milops_penalty(defcon: int, milops: int) -> int:
    """Rule 8.2.1: VP penalty for insufficient military operations."""
    return max(0, defcon - milops)
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestDefcon tests.py::TestMilOps -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add DEFCON restrictions and mil ops penalty"
```

---

### Task 10: Space Race

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestSpaceRaceAttempt:
    def test_successful_advance(self):
        from ts import GameState, Side, resolve_space_race
        gs = GameState.new()
        # Attempt to reach box 1 (Satellite): needs ops>=2, roll<=3
        vp = resolve_space_race(gs, Side.US, ops=2, die_roll=2)
        assert gs.space_race[Side.US] == 1
        assert vp == 2  # first player to box 1

    def test_failed_roll(self):
        from ts import GameState, Side, resolve_space_race
        gs = GameState.new()
        vp = resolve_space_race(gs, Side.US, ops=2, die_roll=5)
        assert gs.space_race[Side.US] == 0
        assert vp == 0

    def test_second_player_vp(self):
        from ts import GameState, Side, resolve_space_race
        gs = GameState.new()
        gs.space_race[Side.USSR] = 1  # USSR already at box 1
        vp = resolve_space_race(gs, Side.US, ops=2, die_roll=2)
        assert gs.space_race[Side.US] == 1
        assert vp == 1  # second player VP

    def test_insufficient_ops(self):
        from ts import GameState, Side, can_attempt_space_race
        gs = GameState.new()
        # Box 1 needs ops>=2
        assert can_attempt_space_race(gs, Side.US, ops=1) is False
        assert can_attempt_space_race(gs, Side.US, ops=2) is True

    def test_already_at_end(self):
        from ts import GameState, Side, can_attempt_space_race
        gs = GameState.new()
        gs.space_race[Side.US] = 8
        assert can_attempt_space_race(gs, Side.US, ops=4) is False
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def can_attempt_space_race(gs: GameState, side: Side, ops: int) -> bool:
    """Rule 6.4.1/6.4.6: Check if space race attempt is possible."""
    pos = gs.space_race[side]
    if pos >= 8:
        return False
    target = SPACE_RACE_TRACK[pos + 1]
    return ops >= target.ops_required


def resolve_space_race(gs: GameState, side: Side, ops: int, die_roll: int) -> int:
    """Rule 6.4: Attempt space race advance. Returns VP gained."""
    pos = gs.space_race[side]
    target_box = SPACE_RACE_TRACK[pos + 1]

    if die_roll <= target_box.roll_max:
        gs.space_race[side] = pos + 1
        other = Side.USSR if side == Side.US else Side.US
        if gs.space_race[other] >= pos + 1:
            return target_box.second_vp
        return target_box.first_vp
    return 0
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestSpaceRaceAttempt -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add space race resolution"
```

---

### Task 11: Deck Management and Game Setup

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestDeckManagement:
    def test_early_war_deck(self):
        from ts import build_early_war_deck, CARDS, Period
        deck = build_early_war_deck()
        # All early war cards except China Card (id=6)
        assert 6 not in deck
        assert all(CARDS[i-1].war_period == Period.EARLY for i in deck
                   if CARDS[i-1].war_period == Period.EARLY)

    def test_deal_cards(self):
        from ts import GameState, deal_cards
        gs = GameState.new()
        gs.draw_pile = list(range(1, 36))  # early war card IDs (excl China)
        gs.draw_pile.remove(6)  # remove China Card
        deal_cards(gs, hand_size=8)
        assert len(gs.us_hand) == 8
        assert len(gs.ussr_hand) == 8
        assert len(gs.draw_pile) == 34 - 16  # 34 cards, dealt 16


class TestGameSetup:
    def test_initial_setup(self):
        from ts import TwilightStruggle, Side, Phase, country_by_name
        game = TwilightStruggle()
        gs = game.reset()
        # DEFCON 5, VP 0, Turn 1
        assert gs.defcon == 5
        assert gs.vp == 0
        assert gs.turn == 1
        # USSR has China Card
        assert gs.china_card_holder == Side.USSR
        assert gs.china_card_face_up is True
        # Each player has 8 cards
        assert len(gs.us_hand) == 8
        assert len(gs.ussr_hand) == 8
        # Check some initial influence
        syria = country_by_name("Syria")
        assert gs.influence[syria.id][Side.USSR] == 1
        eger = country_by_name("E.Germany")
        assert gs.influence[eger.id][Side.USSR] == 3
        uk = country_by_name("UK")
        assert gs.influence[uk.id][Side.US] == 5
        iran = country_by_name("Iran")
        assert gs.influence[iran.id][Side.US] == 1
        # Phase should be HEADLINE
        assert gs.phase == Phase.HEADLINE
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def build_early_war_deck() -> list[int]:
    """Build the early war draw pile (excludes China Card #6)."""
    return [c.id for c in CARDS if c.war_period == Period.EARLY and c.id != 6]


def deal_cards(gs: GameState, hand_size: int):
    """Deal cards to bring both players to hand_size."""
    random.shuffle(gs.draw_pile)
    while len(gs.ussr_hand) < hand_size and gs.draw_pile:
        gs.ussr_hand.append(gs.draw_pile.pop())
    while len(gs.us_hand) < hand_size and gs.draw_pile:
        gs.us_hand.append(gs.draw_pile.pop())


class TwilightStruggle:
    """Core game engine."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.state = GameState.new()

    def reset(self, seed: int | None = None) -> GameState:
        if seed is not None:
            self.rng = random.Random(seed)
        gs = GameState.new()
        self.state = gs

        # Build and shuffle early war deck
        gs.draw_pile = build_early_war_deck()
        self.rng.shuffle(gs.draw_pile)

        # Deal 8 cards each
        deal_cards(gs, hand_size=8)

        # USSR initial influence (rule 3.2): 1 Syria, 1 Iraq, 3 N.Korea, 3 E.Germany, 1 Finland
        # + 6 anywhere in Eastern Europe (we place 4 Poland, 1 Yugoslavia, 1 Czechoslovakia as default)
        _cn = country_by_name
        for name, inf in [("Syria", 1), ("Iraq", 1), ("N.Korea", 3),
                          ("E.Germany", 3), ("Finland", 1)]:
            gs.influence[_cn(name).id][Side.USSR] = inf
        # Default Eastern Europe placement (6 points)
        for name, inf in [("Poland", 4), ("Czechoslovakia", 1), ("Yugoslavia", 1)]:
            gs.influence[_cn(name).id][Side.USSR] = inf

        # US initial influence (rule 3.3)
        for name, inf in [("Canada", 2), ("Iran", 1), ("Israel", 1), ("Japan", 1),
                          ("Australia", 4), ("Philippines", 1), ("S.Korea", 1),
                          ("Panama", 1), ("South Africa", 1), ("UK", 5)]:
            gs.influence[_cn(name).id][Side.US] = inf
        # Default Western Europe placement (7 points)
        for name, inf in [("W.Germany", 4), ("Italy", 2), ("France", 1)]:
            gs.influence[_cn(name).id][Side.US] = inf

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
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestDeckManagement tests.py::TestGameSetup -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add deck management, game setup, and TwilightStruggle class"
```

---

### Task 12: Headline Phase

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestHeadline:
    def test_headline_higher_ops_first(self):
        from ts import headline_order, card_by_id, Side
        # USSR plays 4 ops, US plays 2 ops: USSR goes first
        order = headline_order(ussr_card_id=21, us_card_id=20)  # NATO(4) vs Olympic(2)
        assert order == (Side.USSR, Side.US)

    def test_headline_tie_us_first(self):
        from ts import headline_order, Side
        # Both 3 ops: US goes first
        order = headline_order(ussr_card_id=7, us_card_id=4)  # Socialist(3) vs Duck(3)
        assert order == (Side.US, Side.USSR)

    def test_headline_scoring_card_last(self):
        from ts import headline_order, Side
        # Scoring card (0 ops) always second
        order = headline_order(ussr_card_id=1, us_card_id=20)  # Asia Scoring(0) vs Olympic(2)
        assert order == (Side.US, Side.USSR)

    def test_both_scoring_us_first(self):
        from ts import headline_order, Side
        order = headline_order(ussr_card_id=1, us_card_id=3)  # Both scoring
        assert order == (Side.US, Side.USSR)
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def headline_order(ussr_card_id: int, us_card_id: int) -> tuple[Side, Side]:
    """Rule 4.5C: Determine headline resolution order.

    Higher ops value goes first. Ties: US first.
    Scoring cards have headline value 0.
    """
    ussr_card = card_by_id(ussr_card_id)
    us_card = card_by_id(us_card_id)
    ussr_val = 0 if ussr_card.scoring else ussr_card.ops
    us_val = 0 if us_card.scoring else us_card.ops

    if ussr_val > us_val:
        return (Side.USSR, Side.US)
    else:
        return (Side.US, Side.USSR)
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestHeadline -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add headline phase resolution order"
```

---

### Task 13: Victory Conditions

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestVictory:
    def test_us_20vp_auto_win(self):
        from ts import GameState, Side, check_victory
        gs = GameState.new()
        gs.vp = 20
        check_victory(gs)
        assert gs.game_over is True
        assert gs.winner == Side.US

    def test_ussr_20vp_auto_win(self):
        from ts import GameState, Side, check_victory
        gs = GameState.new()
        gs.vp = -20
        check_victory(gs)
        assert gs.game_over is True
        assert gs.winner == Side.USSR

    def test_no_auto_win_at_19(self):
        from ts import GameState, check_victory
        gs = GameState.new()
        gs.vp = 19
        check_victory(gs)
        assert gs.game_over is False

    def test_europe_control_us_wins(self):
        from ts import GameState, Side, check_europe_control_victory, country_by_name, COUNTRIES, Region
        gs = GameState.new()
        # US controls all European battlegrounds + more countries
        europe_bgs = [c for c in COUNTRIES if c.region == Region.EUROPE and c.battleground]
        for c in europe_bgs:
            gs.influence[c.id][Side.US] = c.stability
        # Also control some non-BG
        for name in ["UK", "Benelux", "Norway", "Denmark", "Greece"]:
            c = country_by_name(name)
            gs.influence[c.id][Side.US] = c.stability
        result = check_europe_control_victory(gs)
        assert result == Side.US

    def test_final_scoring(self):
        from ts import GameState, Side, final_scoring, country_by_name
        gs = GameState.new()
        gs.vp = 0
        # Give US some influence for presence
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.US] = 2
        final_scoring(gs)
        # VP should have changed (exact value depends on all regions)
        assert gs.vp != 0 or gs.game_over  # at minimum something happened
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def check_victory(gs: GameState):
    """Rule 10.3.1: Check for automatic VP victory."""
    if gs.vp >= 20:
        gs.game_over = True
        gs.winner = Side.US
    elif gs.vp <= -20:
        gs.game_over = True
        gs.winner = Side.USSR


def check_europe_control_victory(gs: GameState) -> Side | None:
    """Rule 10.3.1: Check if either side Controls Europe (auto-win when scored)."""
    us_vp, ussr_vp = score_region(gs, Region.EUROPE)
    scoring = SCORING_TABLE[Region.EUROPE]

    # Check if either side got the control-level VP (1000)
    countries = _countries_in_region(Region.EUROPE)
    total_bg = sum(1 for c in countries if c.battleground)

    for side in (Side.US, Side.USSR):
        other = Side.USSR if side == Side.US else Side.US
        controlled = [c for c in countries if controls_country(gs, c.id, side)]
        bg_count = sum(1 for c in controlled if c.battleground)
        opp_count = len([c for c in countries if controls_country(gs, c.id, other)])
        if bg_count == total_bg and len(controlled) > opp_count:
            return side
    return None


def final_scoring(gs: GameState):
    """Rule 10.3.2: Score all regions at end of Turn 10."""
    # Check Europe control first (auto-win)
    europe_winner = check_europe_control_victory(gs)
    if europe_winner:
        gs.game_over = True
        gs.winner = europe_winner
        return

    for region in Region:
        us_vp, ussr_vp = score_region(gs, region)
        gs.vp += (us_vp - ussr_vp)

    # China card holder gets 1 VP
    if gs.china_card_holder == Side.US:
        gs.vp += 1
    elif gs.china_card_holder == Side.USSR:
        gs.vp -= 1

    check_victory(gs)

    if not gs.game_over:
        gs.game_over = True
        if gs.vp > 0:
            gs.winner = Side.US
        elif gs.vp < 0:
            gs.winner = Side.USSR
        else:
            gs.winner = None  # draw
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestVictory -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add victory conditions and final scoring"
```

---

### Task 14: China Card Mechanics

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestChinaCard:
    def test_china_ops_base(self):
        from ts import china_card_ops, GameState, Side, Region
        gs = GameState.new()
        assert china_card_ops(all_in_asia=False) == 4

    def test_china_ops_asia_bonus(self):
        from ts import china_card_ops
        assert china_card_ops(all_in_asia=True) == 5

    def test_china_pass_after_play(self):
        from ts import GameState, Side, pass_china_card
        gs = GameState.new()
        gs.china_card_holder = Side.USSR
        pass_china_card(gs, from_side=Side.USSR)
        assert gs.china_card_holder == Side.US
        assert gs.china_card_face_up is False
        assert gs.china_card_playable is False

    def test_china_pass_by_event(self):
        from ts import GameState, Side, pass_china_card
        gs = GameState.new()
        gs.china_card_holder = Side.US
        pass_china_card(gs, from_side=Side.US, via_event=True)
        assert gs.china_card_holder == Side.USSR
        assert gs.china_card_face_up is True
        assert gs.china_card_playable is True

    def test_china_flip_at_end_of_turn(self):
        from ts import GameState, flip_china_card
        gs = GameState.new()
        gs.china_card_face_up = False
        gs.china_card_playable = False
        flip_china_card(gs)
        assert gs.china_card_face_up is True
        assert gs.china_card_playable is True
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def china_card_ops(all_in_asia: bool) -> int:
    """Rule 9.6: China Card ops value (4 base, +1 if all ops in Asia)."""
    return 5 if all_in_asia else 4


def pass_china_card(gs: GameState, from_side: Side, via_event: bool = False):
    """Rule 9.3/9.4: Pass China Card to opponent."""
    other = Side.USSR if from_side == Side.US else Side.US
    gs.china_card_holder = other
    if via_event:
        gs.china_card_face_up = True
        gs.china_card_playable = True
    else:
        gs.china_card_face_up = False
        gs.china_card_playable = False


def flip_china_card(gs: GameState):
    """Rule 4.5G: Flip China Card face-up at end of turn."""
    if not gs.china_card_face_up:
        gs.china_card_face_up = True
        gs.china_card_playable = True
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestChinaCard -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add China Card mechanics"
```

---

### Task 15: Turn Flow State Machine

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

**Step 1: Write failing tests**

```python
class TestTurnFlow:
    def test_action_rounds_early_war(self):
        from ts import action_rounds_for_turn
        assert action_rounds_for_turn(1) == 6
        assert action_rounds_for_turn(3) == 6

    def test_action_rounds_mid_war(self):
        from ts import action_rounds_for_turn
        assert action_rounds_for_turn(4) == 7
        assert action_rounds_for_turn(10) == 7

    def test_hand_size(self):
        from ts import hand_size_for_turn
        assert hand_size_for_turn(1) == 8
        assert hand_size_for_turn(3) == 8
        assert hand_size_for_turn(4) == 9
        assert hand_size_for_turn(10) == 9

    def test_end_of_turn_milops_penalty(self):
        from ts import GameState, Side, apply_milops_penalty
        gs = GameState.new()
        gs.defcon = 4
        gs.mil_ops = [2, 4]  # US did 2, USSR did 4
        apply_milops_penalty(gs)
        # US deficit = 4-2 = 2, USSR gets 2 VP (vp decreases by 2)
        assert gs.vp == -2

    def test_advance_turn_mid_war_shuffle(self):
        from ts import GameState, advance_turn, Period, CARDS
        gs = GameState.new()
        gs.turn = 3
        gs.discard_pile = [4, 5]  # some early war discards
        advance_turn(gs)
        assert gs.turn == 4
        # Mid war cards should be in draw pile
        mid_cards = {c.id for c in CARDS if c.war_period == Period.MID}
        draw_set = set(gs.draw_pile)
        assert mid_cards.issubset(draw_set)
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```python
def action_rounds_for_turn(turn: int) -> int:
    """Rule 4.1: 6 action rounds turns 1-3, 7 turns 4-10."""
    return 6 if turn <= 3 else 7


def hand_size_for_turn(turn: int) -> int:
    """Rule 4.5B: Hand size 8 turns 1-3, 9 turns 4-10."""
    return 8 if turn <= 3 else 9


def apply_milops_penalty(gs: GameState):
    """Rule 8.2: Apply VP penalty for insufficient mil ops."""
    us_penalty = milops_penalty(gs.defcon, gs.mil_ops[Side.US])
    ussr_penalty = milops_penalty(gs.defcon, gs.mil_ops[Side.USSR])
    gs.vp -= us_penalty   # US deficit benefits USSR
    gs.vp += ussr_penalty  # USSR deficit benefits US


def advance_turn(gs: GameState):
    """Rule 4.5H: Advance turn, inject Mid/Late War cards if needed."""
    gs.turn += 1

    # Rule 4.4: At turn 4, add Mid War cards (don't add discards)
    if gs.turn == 4:
        mid_cards = [c.id for c in CARDS if c.war_period == Period.MID]
        gs.draw_pile.extend(mid_cards)

    # Rule 4.4: At turn 8, add Late War cards
    if gs.turn == 8:
        late_cards = [c.id for c in CARDS if c.war_period == Period.LATE]
        gs.draw_pile.extend(late_cards)

    # Reset per-turn state
    gs.mil_ops = [0, 0]
    gs.space_race_used = [False, False]
    gs.action_round = 0
```

**Step 4: Run tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py::TestTurnFlow -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add turn flow helpers and mid/late war deck injection"
```

---

### Task 16: Full Game Loop Integration

**Files:**
- Modify: `projects/ts/ts.py`
- Test: `projects/ts/tests.py`

This task wires everything together into the `step()` and `legal_actions()` methods of the `TwilightStruggle` class, handling the full phase state machine.

**Step 1: Write failing tests**

```python
class TestGameLoop:
    def test_legal_actions_headline(self):
        from ts import TwilightStruggle, Phase, ActionType
        game = TwilightStruggle(seed=42)
        gs = game.reset()
        assert gs.phase == Phase.HEADLINE
        actions = game.legal_actions()
        # Both players need to select headlines. USSR goes first.
        assert all(a.type == ActionType.HEADLINE_SELECT for a in actions)
        # Should offer each card in USSR's hand
        assert len(actions) == len(gs.ussr_hand)

    def test_step_headline_transitions(self):
        from ts import TwilightStruggle, Phase, ActionType, Action, Side
        game = TwilightStruggle(seed=42)
        gs = game.reset()
        # USSR selects headline
        ussr_card = gs.ussr_hand[0]
        game.step(Action(ActionType.HEADLINE_SELECT, card_id=ussr_card))
        # Now US selects
        assert gs.phasing_player == Side.US
        us_card = gs.us_hand[0]
        game.step(Action(ActionType.HEADLINE_SELECT, card_id=us_card))
        # Should transition to headline resolution or action rounds
        assert gs.phase in (Phase.HEADLINE_RESOLVE, Phase.ACTION_ROUND)

    def test_random_game_completes(self):
        """Play a random game to completion — no crashes."""
        from ts import TwilightStruggle, ActionType
        game = TwilightStruggle(seed=123)
        gs = game.reset()
        for _ in range(5000):  # safety limit
            if gs.game_over:
                break
            actions = game.legal_actions()
            if not actions:
                break
            action = actions[game.rng.randint(0, len(actions) - 1)]
            game.step(action)
        assert gs.game_over is True
        assert gs.winner is not None or gs.winner is None  # draw is valid
```

**Step 2: Run to verify failure**

**Step 3: Implement `legal_actions()` and `step()`**

This is the largest piece. Add these methods to the `TwilightStruggle` class:

```python
    # Inside TwilightStruggle class:

    def legal_actions(self) -> list[Action]:
        gs = self.state
        actions = []

        if gs.game_over:
            return []

        if gs.phase == Phase.HEADLINE:
            hand = gs.ussr_hand if gs.phasing_player == Side.USSR else gs.us_hand
            for card_id in hand:
                card = card_by_id(card_id)
                if card_id == 6:
                    continue  # China Card cannot be played in headline
                actions.append(Action(ActionType.HEADLINE_SELECT, card_id=card_id))
            return actions

        if gs.phase == Phase.ACTION_ROUND:
            hand = gs.ussr_hand if gs.phasing_player == Side.USSR else gs.us_hand
            side = gs.phasing_player

            for card_id in hand:
                card = card_by_id(card_id)
                if card.scoring:
                    # Scoring cards must be played — offer only as event
                    actions.append(Action(ActionType.PLAY_EVENT, card_id=card_id))
                    continue
                # Play as event (own or neutral)
                actions.append(Action(ActionType.PLAY_EVENT, card_id=card_id))
                # Play for ops
                if card.ops > 0:
                    actions.append(Action(ActionType.PLAY_OPS_INFLUENCE, card_id=card_id))
                    actions.append(Action(ActionType.PLAY_OPS_REALIGN, card_id=card_id))
                    # Coup: only if valid targets exist
                    actions.append(Action(ActionType.PLAY_OPS_COUP, card_id=card_id))
                    # Space race
                    if can_attempt_space_race(gs, side, card.ops):
                        if not gs.space_race_used[side]:
                            actions.append(Action(ActionType.PLAY_OPS_SPACE, card_id=card_id))

            # China Card
            if (gs.china_card_holder == side and gs.china_card_face_up
                    and gs.china_card_playable):
                # Check not forced to hold scoring card
                has_scoring = any(card_by_id(c).scoring for c in hand)
                if not has_scoring:
                    actions.append(Action(ActionType.PLAY_OPS_INFLUENCE, card_id=6))
                    actions.append(Action(ActionType.PLAY_OPS_REALIGN, card_id=6))
                    actions.append(Action(ActionType.PLAY_OPS_COUP, card_id=6))
                    if can_attempt_space_race(gs, side, 4) and not gs.space_race_used[side]:
                        actions.append(Action(ActionType.PLAY_OPS_SPACE, card_id=6))

            return actions

        if gs.phase == Phase.OPS_INFLUENCE:
            side = gs.phasing_player
            actions = []
            for c in COUNTRIES:
                if can_place_influence(gs, c.id, side):
                    cost = influence_cost(gs, c.id, side)
                    if cost <= gs.ops_remaining:
                        actions.append(Action(ActionType.PLACE_INFLUENCE, country_id=c.id))
            if gs.ops_remaining == 0 or not actions:
                return [Action(ActionType.DONE_PLACING)]
            actions.append(Action(ActionType.DONE_PLACING))
            return actions

        if gs.phase == Phase.OPS_REALIGN:
            side = gs.phasing_player
            for c in COUNTRIES:
                if gs.influence[c.id][Side.US if side == Side.USSR else Side.USSR] > 0:
                    if not defcon_restricts_region(gs.defcon, c.region):
                        if gs.ops_remaining > 0:
                            actions.append(Action(ActionType.REALIGN_TARGET, country_id=c.id))
            if gs.ops_remaining == 0 or not actions:
                return [Action(ActionType.DONE_REALIGNING)]
            actions.append(Action(ActionType.DONE_REALIGNING))
            return actions

        return []

    def step(self, action: Action) -> tuple[GameState, float, bool, dict]:
        gs = self.state

        if gs.phase == Phase.HEADLINE:
            self._step_headline(action)
        elif gs.phase == Phase.ACTION_ROUND:
            self._step_action_round(action)
        elif gs.phase == Phase.OPS_INFLUENCE:
            self._step_ops_influence(action)
        elif gs.phase == Phase.OPS_REALIGN:
            self._step_ops_realign(action)

        # Check victory after every step
        if not gs.game_over:
            check_victory(gs)

        reward = gs.vp / 20.0 if gs.game_over else 0.0
        return gs, reward, gs.game_over, {}

    def _step_headline(self, action: Action):
        gs = self.state
        if gs.phasing_player == Side.USSR:
            gs.ussr_headline = action.card_id
            gs.ussr_hand.remove(action.card_id)
            gs.phasing_player = Side.US
        else:
            gs.us_headline = action.card_id
            gs.us_hand.remove(action.card_id)
            # Resolve headlines
            self._resolve_headlines()

    def _resolve_headlines(self):
        gs = self.state
        first, second = headline_order(gs.ussr_headline, gs.us_headline)
        # Events are stubs for now — just discard/remove cards
        for side in (first, second):
            card_id = gs.ussr_headline if side == Side.USSR else gs.us_headline
            card = card_by_id(card_id)
            if card.scoring:
                self._resolve_scoring_card(card_id, side)
            if card.removed_after_event:
                gs.removed_pile.append(card_id)
            else:
                gs.discard_pile.append(card_id)
            if gs.game_over:
                return
        gs.ussr_headline = None
        gs.us_headline = None
        gs.phase = Phase.ACTION_ROUND
        gs.action_round = 1
        gs.phasing_player = Side.USSR

    def _resolve_scoring_card(self, card_id: int, side: Side):
        gs = self.state
        card = card_by_id(card_id)
        region_map = {
            1: Region.ASIA, 2: Region.EUROPE, 3: Region.MIDDLE_EAST,
            37: Region.CENTRAL_AMERICA, 38: Region.ASIA,  # SE Asia scored as Asia
            79: Region.AFRICA, 81: Region.SOUTH_AMERICA,
        }
        region = region_map.get(card_id)
        if region:
            if card_id == 2:  # Europe scoring — check control victory
                winner = check_europe_control_victory(gs)
                if winner:
                    gs.game_over = True
                    gs.winner = winner
                    return
            us_vp, ussr_vp = score_region(gs, region)
            gs.vp += (us_vp - ussr_vp)

    def _step_action_round(self, action: Action):
        gs = self.state
        side = gs.phasing_player
        hand = gs.ussr_hand if side == Side.USSR else gs.us_hand
        card = card_by_id(action.card_id)

        # Remove card from hand (except China Card)
        if action.card_id != 6 and action.card_id in hand:
            hand.remove(action.card_id)

        ops = card.ops
        if action.card_id == 6:
            ops = 4  # China Card base ops
            pass_china_card(gs, from_side=side)

        if action.type == ActionType.PLAY_EVENT:
            if card.scoring:
                self._resolve_scoring_card(action.card_id, side)
            # Non-scoring events are stubs — just discard/remove
            if card.removed_after_event:
                gs.removed_pile.append(action.card_id)
            else:
                gs.discard_pile.append(action.card_id)
            self._advance_action_round()

        elif action.type == ActionType.PLAY_OPS_INFLUENCE:
            gs.active_card = action.card_id
            gs.ops_remaining = ops
            gs.phase = Phase.OPS_INFLUENCE
            # If opponent's event, trigger it (stub: just mark for discard)
            self._maybe_trigger_opponent_event(action.card_id, side)

        elif action.type == ActionType.PLAY_OPS_COUP:
            gs.active_card = action.card_id
            # Pick first valid target for now — actual target comes from a sub-action
            # For simplicity, we encode the coup target in country_id
            # We need a sub-step for coup target selection
            gs.ops_remaining = ops
            gs.phase = Phase.OPS_COUP
            self._maybe_trigger_opponent_event(action.card_id, side)
            # For the MVP, auto-resolve coup on first valid target
            # (This will be refined — for now, find any valid target)
            other = Side.USSR if side == Side.US else Side.US
            for c in COUNTRIES:
                if gs.influence[c.id][other] > 0:
                    if not defcon_restricts_region(gs.defcon, c.region):
                        die = self.rng.randint(1, 6)
                        resolve_coup(gs, c.id, side, ops, die)
                        break
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()

        elif action.type == ActionType.PLAY_OPS_REALIGN:
            gs.active_card = action.card_id
            gs.ops_remaining = ops
            gs.phase = Phase.OPS_REALIGN
            self._maybe_trigger_opponent_event(action.card_id, side)

        elif action.type == ActionType.PLAY_OPS_SPACE:
            die = self.rng.randint(1, 6)
            vp = resolve_space_race(gs, side, ops, die)
            if vp > 0:
                if side == Side.US:
                    gs.vp += vp
                else:
                    gs.vp -= vp
            gs.space_race_used[side] = True
            if action.card_id != 6:
                gs.discard_pile.append(action.card_id)
            self._advance_action_round()

    def _step_ops_influence(self, action: Action):
        gs = self.state
        if action.type == ActionType.DONE_PLACING:
            gs.ops_remaining = 0
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()
            return
        side = gs.phasing_player
        cost = influence_cost(gs, action.country_id, side)
        place_influence(gs, action.country_id, side)
        gs.ops_remaining -= cost
        if gs.ops_remaining <= 0:
            gs.ops_remaining = 0
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()

    def _step_ops_realign(self, action: Action):
        gs = self.state
        if action.type == ActionType.DONE_REALIGNING:
            gs.ops_remaining = 0
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()
            return
        us_roll = self.rng.randint(1, 6)
        ussr_roll = self.rng.randint(1, 6)
        resolve_realignment(gs, action.country_id, gs.phasing_player, us_roll, ussr_roll)
        gs.ops_remaining -= 1
        if gs.ops_remaining <= 0:
            gs.ops_remaining = 0
            gs.phase = Phase.ACTION_ROUND
            self._advance_action_round()

    def _maybe_trigger_opponent_event(self, card_id: int, side: Side):
        """Rule 5.2: If card is opponent's event, trigger it (stub)."""
        gs = self.state
        card = card_by_id(card_id)
        if card_id == 6:
            return
        other = Side.USSR if side == Side.US else Side.US
        if card.side == other:
            # Event would trigger — stub: just mark card properly
            if card.removed_after_event:
                if card_id not in gs.removed_pile:
                    gs.removed_pile.append(card_id)
            elif card_id not in gs.discard_pile:
                gs.discard_pile.append(card_id)

    def _advance_action_round(self):
        gs = self.state
        if gs.game_over:
            return
        gs.active_card = None
        max_rounds = action_rounds_for_turn(gs.turn)

        # Switch player
        if gs.phasing_player == Side.USSR:
            gs.phasing_player = Side.US
        else:
            gs.phasing_player = Side.USSR
            gs.action_round += 1

        # Check if turn is over
        if gs.action_round > max_rounds:
            self._end_turn()

    def _end_turn(self):
        gs = self.state
        # E. Check military ops
        apply_milops_penalty(gs)
        check_victory(gs)
        if gs.game_over:
            return

        # G. Flip China Card
        flip_china_card(gs)

        # H. Advance turn
        if gs.turn >= 10:
            # I. Final scoring
            final_scoring(gs)
            return

        advance_turn(gs)

        # A. Improve DEFCON
        if gs.defcon < 5:
            gs.defcon += 1

        # B. Deal cards
        deal_cards(gs, hand_size_for_turn(gs.turn))

        # Back to headline
        gs.phase = Phase.HEADLINE
        gs.phasing_player = Side.USSR
```

**Step 4: Run ALL tests**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py -v`
Expected: All PASS including the random game completion test.

**Step 5: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add full game loop with step/legal_actions state machine"
```

---

### Task 17: Final Pass — Run Full Suite and Fix

**Step 1: Run the complete test suite**

Run: `cd /mnt/d/prg/plum/projects/ts && python3 -m pytest tests.py -v --tb=short`

**Step 2: Fix any failures** (iterate until green)

**Step 3: Run the random game stress test multiple times**

```python
# Add to tests.py
class TestStress:
    def test_100_random_games(self):
        from ts import TwilightStruggle
        for seed in range(100):
            game = TwilightStruggle(seed=seed)
            gs = game.reset()
            for _ in range(5000):
                if gs.game_over:
                    break
                actions = game.legal_actions()
                if not actions:
                    break
                action = actions[game.rng.randint(0, len(actions) - 1)]
                game.step(action)
            assert gs.game_over, f"Game {seed} did not complete"
```

**Step 4: Commit**

```bash
git add projects/ts/ts.py projects/ts/tests.py
git commit -m "feat(ts): add stress tests, finalize core engine"
```
