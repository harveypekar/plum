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
        assert len(COUNTRIES) == 84

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
        assert len(bg) == 29

    def test_mexico_stability(self):
        mexico = country_by_name("Mexico")
        assert mexico.stability == 2
        assert mexico.battleground is True
        assert mexico.region == Region.CENTRAL_AMERICA


class TestCards:
    def test_total_cards(self):
        from ts import CARDS
        assert len(CARDS) == 110

    def test_china_card(self):
        from ts import card_by_id, Side, Period
        china = card_by_id(6)
        assert china.name == "The China Card"
        assert china.ops == 4
        assert china.scoring is False

    def test_scoring_cards(self):
        from ts import CARDS
        scoring = [c for c in CARDS if c.scoring]
        assert len(scoring) == 7

    def test_early_war_count(self):
        from ts import CARDS, Period
        early = [c for c in CARDS if c.war_period == Period.EARLY]
        assert len(early) == 36

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
        assert len(optional) == 7

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
