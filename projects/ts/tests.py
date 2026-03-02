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


class TestSpaceRace:
    def test_track_length(self):
        from ts import SPACE_RACE_TRACK
        assert len(SPACE_RACE_TRACK) == 9

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
        assert europe.control == 1000

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


class TestScoring:
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
        # US controls all CA battlegrounds + more countries total
        for name in ["Mexico", "Cuba", "Panama", "Guatemala", "Honduras"]:
            c = country_by_name(name)
            gs.influence[c.id][Side.US] = c.stability
        us_vp, ussr_vp = score_region(gs, Region.CENTRAL_AMERICA)
        # US has Control: 5 VP + 3 BG bonus = 8
        # (Cuba is US-adjacent, not USSR-adjacent, so no adjacency bonus for US)
        assert us_vp == 8
        assert ussr_vp == 0

    def test_adjacency_bonus(self):
        from ts import GameState, Side, Region, score_region, country_by_name
        gs = GameState.new()
        nk = country_by_name("N.Korea")
        gs.influence[nk.id][Side.US] = 3  # stability 3
        us_vp, _ = score_region(gs, Region.ASIA)
        # Presence(3) + 1(BG) + 1(adj to USSR) = 5
        assert us_vp == 5


class TestInfluencePlacement:
    def test_cost_uncontrolled(self):
        from ts import GameState, Side, influence_cost, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        assert influence_cost(gs, iran.id, Side.US) == 1

    def test_cost_enemy_controlled(self):
        from ts import GameState, Side, influence_cost, country_by_name
        gs = GameState.new()
        turkey = country_by_name("Turkey")
        gs.influence[turkey.id][Side.USSR] = 2
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
        pakistan = country_by_name("Pakistan")
        assert can_place_influence(gs, pakistan.id, Side.US) is True

    def test_cannot_place_nonadjacent(self):
        from ts import GameState, Side, can_place_influence, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.US] = 1
        brazil = country_by_name("Brazil")
        assert can_place_influence(gs, brazil.id, Side.US) is False

    def test_can_place_adjacent_to_superpower(self):
        from ts import GameState, Side, can_place_influence, country_by_name
        gs = GameState.new()
        canada = country_by_name("Canada")
        assert can_place_influence(gs, canada.id, Side.US) is True

    def test_place_influence(self):
        from ts import GameState, Side, place_influence, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.US] = 1
        place_influence(gs, iran.id, Side.US)
        assert gs.influence[iran.id][Side.US] == 2


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
        assert gs.defcon == 4

    def test_coup_no_defcon_for_non_bg(self):
        from ts import GameState, Side, resolve_coup, country_by_name
        gs = GameState.new()
        gs.defcon = 5
        lebanon = country_by_name("Lebanon")
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
        assert gs.winner == Side.USSR  # phasing player loses


class TestRealignment:
    def test_realignment_modifiers(self):
        from ts import GameState, Side, realignment_modifiers, country_by_name
        gs = GameState.new()
        nk = country_by_name("N.Korea")
        gs.influence[nk.id][Side.USSR] = 3
        us_mod, ussr_mod = realignment_modifiers(gs, nk.id)
        # USSR: +1 adjacent superpower, +1 more influence
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
        # USSR mod +2: 2+2=4 = US 4. Tie, no change.
        assert gs.influence[nk.id][Side.USSR] == 3

    def test_realignment_no_add(self):
        from ts import GameState, Side, resolve_realignment, country_by_name
        gs = GameState.new()
        iran = country_by_name("Iran")
        gs.influence[iran.id][Side.USSR] = 1
        resolve_realignment(gs, iran.id, Side.US, us_roll=6, ussr_roll=1)
        assert gs.influence[iran.id][Side.US] == 0

    def test_adjacent_controlled_modifier(self):
        from ts import GameState, Side, realignment_modifiers, country_by_name
        gs = GameState.new()
        turkey = country_by_name("Turkey")
        jordan = country_by_name("Jordan")
        syria = country_by_name("Syria")
        gs.influence[turkey.id][Side.US] = 2
        gs.influence[jordan.id][Side.US] = 2
        gs.influence[syria.id][Side.USSR] = 1
        us_mod, ussr_mod = realignment_modifiers(gs, syria.id)
        assert us_mod == 2  # Turkey + Jordan controlled adj


class TestDefcon:
    def test_defcon_restrictions(self):
        from ts import defcon_restricts_region, Region
        assert defcon_restricts_region(5, Region.EUROPE) is False
        assert defcon_restricts_region(4, Region.EUROPE) is True
        assert defcon_restricts_region(4, Region.ASIA) is False
        assert defcon_restricts_region(3, Region.EUROPE) is True
        assert defcon_restricts_region(3, Region.ASIA) is True
        assert defcon_restricts_region(3, Region.MIDDLE_EAST) is False
        assert defcon_restricts_region(2, Region.EUROPE) is True
        assert defcon_restricts_region(2, Region.ASIA) is True
        assert defcon_restricts_region(2, Region.MIDDLE_EAST) is True
        assert defcon_restricts_region(2, Region.CENTRAL_AMERICA) is False


class TestMilOps:
    def test_penalty_none(self):
        from ts import milops_penalty
        assert milops_penalty(defcon=4, milops=4) == 0

    def test_penalty_deficit(self):
        from ts import milops_penalty
        assert milops_penalty(defcon=4, milops=2) == 2

    def test_penalty_excess(self):
        from ts import milops_penalty
        assert milops_penalty(defcon=3, milops=5) == 0
