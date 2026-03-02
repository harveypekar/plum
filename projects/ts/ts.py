"""Twilight Struggle core game engine."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from enum import Enum, IntEnum


# -- Enums -------------------------------------------------------------------

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
    OPTIONAL = "optional"


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


# -- Static Data -------------------------------------------------------------

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
        ("Finland", 4, False, R.EUROPE, None),                     # 32
        ("Austria", 4, False, R.EUROPE, None),                     # 33
        # Eastern Europe (34-40)
        ("E.Germany", 3, True, R.EUROPE, S.EASTERN_EUROPE),        # 34
        ("Poland", 3, True, R.EUROPE, S.EASTERN_EUROPE),           # 35
        ("Czechoslovakia", 3, False, R.EUROPE, S.EASTERN_EUROPE),  # 36
        ("Hungary", 3, False, R.EUROPE, S.EASTERN_EUROPE),         # 37
        ("Yugoslavia", 3, False, R.EUROPE, S.EASTERN_EUROPE),      # 38
        ("Romania", 3, False, R.EUROPE, S.EASTERN_EUROPE),         # 39
        ("Bulgaria", 3, False, R.EUROPE, S.EASTERN_EUROPE),        # 40
        # Middle East (41-50)
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
        # Asia (51-65)
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
        # Africa (66-83)
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

    def link(a: int, b: int) -> None:
        adj[a].append(b)
        adj[b].append(a)

    # Central America
    link(0, 1)    # Mexico-Guatemala
    link(1, 2)    # Guatemala-El Salvador
    link(1, 3)    # Guatemala-Honduras
    link(2, 3)    # El Salvador-Honduras
    link(3, 6)    # Honduras-Nicaragua
    link(3, 4)    # Honduras-Costa Rica
    link(4, 6)    # Costa Rica-Nicaragua
    link(5, 6)    # Cuba-Nicaragua
    link(5, 7)    # Cuba-Haiti
    link(7, 8)    # Haiti-Dominican Rep
    link(4, 9)    # Costa Rica-Panama
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
    link(41, 48)  # Lebanon-Jordan
    link(42, 43)  # Syria-Israel
    link(42, 44)  # Syria-Iraq
    link(42, 48)  # Syria-Jordan
    link(43, 47)  # Israel-Egypt
    link(43, 48)  # Israel-Jordan
    link(44, 45)  # Iraq-Iran
    link(44, 48)  # Iraq-Jordan
    link(44, 49)  # Iraq-Gulf States
    link(44, 50)  # Iraq-Saudi Arabia
    link(46, 47)  # Libya-Egypt
    link(46, 66)  # Libya-Tunisia (Africa link)
    link(47, 71)  # Egypt-Sudan (Africa link)
    link(48, 50)  # Jordan-Saudi Arabia
    link(49, 50)  # Gulf States-Saudi Arabia
    # Asia
    link(45, 51)  # Iran-Afghanistan
    link(45, 52)  # Iran-Pakistan
    link(51, 52)  # Afghanistan-Pakistan
    link(52, 53)  # Pakistan-India
    link(53, 54)  # India-Burma
    link(54, 55)  # Burma-Laos/Cambodia
    link(54, 56)  # Burma-Thailand
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
    link(24, 68)  # Spain/Portugal-Morocco (cross-region)
    link(67, 66)  # Algeria-Tunisia
    link(67, 68)  # Algeria-Morocco
    link(67, 70)  # Algeria-Saharan States
    link(68, 69)  # Morocco-W.African States
    link(69, 72)  # W.African States-Ivory Coast
    link(69, 70)  # W.African States-Saharan States
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
