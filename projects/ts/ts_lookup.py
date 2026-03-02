"""Lookup helpers for ts_game data.

Convenience functions for finding countries and cards by name or JSON ID.
Separated from ts_game.py to keep the game engine focused on rules and data.
"""

from ts_game import COUNTRIES, CARDS, Country, CardDef

_COUNTRY_BY_NAME: dict[str, Country] = {c.name: c for c in COUNTRIES}
_COUNTRY_BY_JSON: dict[str, Country] = {c.json_id: c for c in COUNTRIES}
_CARD_BY_NAME: dict[str, CardDef] = {c.name: c for c in CARDS}


def country_by_name(name: str) -> Country:
    """Look up a Country by its display name (e.g. 'W.Germany')."""
    return _COUNTRY_BY_NAME[name]


def country_by_json_id(jid: str) -> Country:
    """Look up a Country by its ts-data.json hex ID (e.g. 'l05')."""
    return _COUNTRY_BY_JSON[jid]


def card_by_name(name: str) -> CardDef:
    """Look up a CardDef by its name (e.g. 'NATO')."""
    return _CARD_BY_NAME[name]
