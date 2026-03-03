

struct ts_country
{
    int id;
    char *name;
    bool battleground;
    bool stability;
};

struct ts_adjacency
{
    // ordered from lowest to highest id
    int id_a;
    int id_b;
};

enum ts_card_id
{
    TS_ASIA_SCORING = 1,
    TS_EUROPE_SCORING = 2,
    TS_MIDDLE_EAST_SCORING = 3,
    TS_DUCK_AND_COVER = 4,
    TS_FIVE_YEAR_PLAN = 5,
    TS_THE_CHINA_CARD = 6,
    TS_SOCIALIST_GOVERNMENTS = 7,
    TS_FIDEL = 8,
    TS_VIETNAM_REVOLTS = 9,
    TS_BLOCKADE = 10,
    TS_KOREAN_WAR = 11,
    TS_ROMANIAN_ABDICATION = 12,
    TS_ARAB_ISRAELI_WAR = 13,
    TS_COMECON = 14,
    TS_NASSER = 15,
    TS_WARSAW_PACT_FORMED = 16,
    TS_DE_GAULLE_LEADS_FRANCE = 17,
    TS_CAPTURED_NAZI_SCIENTIST = 18,
    TS_TRUMAN_DOCTRINE = 19,
    TS_OLYMPIC_GAMES = 20,
    TS_NATO = 21,
    TS_INDEPENDENT_REDS = 22,
    TS_MARSHALL_PLAN = 23,
    TS_INDO_PAKISTANI_WAR = 24,
    TS_CONTAINMENT = 25,
    TS_CIA_CREATED = 26,
    TS_US_JAPAN_MUTUAL_DEFENSE_PACT = 27,
    TS_SUEZ_CRISIS = 28,
    TS_EAST_EUROPEAN_UNREST = 29,
    TS_DECOLONIZATION = 30,
    TS_RED_SCARE_PURGE = 31,
    TS_UN_INTERVENTION = 32,
    TS_DE_STALINIZATION = 33,
    TS_NUCLEAR_TEST_BAN = 34,
    TS_FORMOSAN_RESOLUTION = 35,
    TS_DEFECTORS = 103,
    TS_BRUSH_WAR = 36,
    TS_CENTRAL_AMERICA_SCORING = 37,
    TS_SOUTHEAST_ASIA_SCORING = 38,
    TS_ARMS_RACE = 39,
    TS_CUBAN_MISSILE_CRISIS = 40,
    TS_NUCLEAR_SUBS = 41,
    TS_QUAGMIRE = 42,
    TS_SALT_NEGOTIATIONS = 43,
    TS_BEAR_TRAP = 44,
    TS_SUMMIT = 45,
    TS_HOW_I_LEARNED_TO_STOP_WORRYING = 46,
    TS_JUNTA = 47,
    TS_KITCHEN_DEBATES = 48,
    TS_MISSILE_ENVY = 49,
    TS_WE_WILL_BURY_YOU = 50,
    TS_BREZHNEV_DOCTRINE = 51,
    TS_PORTUGUESE_EMPIRE_CRUMBLES = 52,
    TS_SOUTH_AFRICAN_UNREST = 53,
    TS_ALLENDE = 54,
    TS_WILLY_BRANDT = 55,
    TS_MUSLIM_REVOLUTION = 56,
    TS_ABM_TREATY = 57,
    TS_CULTURAL_REVOLUTION = 58,
    TS_FLOWER_POWER = 59,
    TS_U2_INCIDENT = 60,
    TS_OPEC = 61,
    TS_LONE_GUNMAN = 62,
    TS_COLONIAL_REAR_GUARDS = 63,
    TS_PANAMA_CANAL_RETURNED = 64,
    TS_CAMP_DAVID_ACCORDS = 65,
    TS_PUPPET_GOVERNMENTS = 66,
    TS_GRAIN_SALES_TO_SOVIETS = 67,
    TS_JOHN_PAUL_II_ELECTED_POPE = 68,
    TS_LATIN_AMERICAN_DEATH_SQUADS = 69,
    TS_OAS_FOUNDED = 70,
    TS_NIXON_PLAYS_THE_CHINA_CARD = 71,
    TS_SADAT_EXPELS_SOVIETS = 72,
    TS_SHUTTLE_DIPLOMACY = 73,
    TS_THE_VOICE_OF_AMERICA = 74,
    TS_LIBERATION_THEOLOGY = 75,
    TS_USSURI_RIVER_SKIRMISH = 76,
    TS_ASK_NOT_WHAT_YOUR_COUNTRY = 77,
    TS_ALLIANCE_FOR_PROGRESS = 78,
    TS_AFRICA_SCORING = 79,
    TS_ONE_SMALL_STEP = 80,
    TS_SOUTH_AMERICA_SCORING = 81,
    TS_IRANIAN_HOSTAGE_CRISIS = 82,
    TS_THE_IRON_LADY = 83,
    TS_REAGAN_BOMBS_LIBYA = 84,
    TS_STAR_WARS = 85,
    TS_NORTH_SEA_OIL = 86,
    TS_THE_REFORMER = 87,
    TS_MARINE_BARRACKS_BOMBING = 88,
    TS_SOVIETS_SHOOT_DOWN_KAL_007 = 89,
    TS_GLASNOST = 90,
    TS_ORTEGA_ELECTED_IN_NICARAGUA = 91,
    TS_TERRORISM = 92,
    TS_IRAN_CONTRA_SCANDAL = 93,
    TS_CHERNOBYL = 94,
    TS_LATIN_AMERICAN_DEBT_CRISIS = 95,
    TS_TEAR_DOWN_THIS_WALL = 96,
    TS_AN_EVIL_EMPIRE = 97,
    TS_ALDRICH_AMES_REMIX = 98,
    TS_PERSHING_II_DEPLOYED = 99,
    TS_WARGAMES = 100,
    TS_SOLIDARITY = 101,
    TS_IRAN_IRAQ_WAR = 102,
    TS_THE_CAMBRIDGE_FIVE = 104,
    TS_SPECIAL_RELATIONSHIP = 105,
    TS_NORAD = 106,
    TS_CHE = 107,
    TS_OUR_MAN_IN_TEHRAN = 108,
    TS_YURI_AND_SAMANTHA = 109,
    TS_AWACS_SALE_TO_SAUDIS = 110,
}

enum ts_player
{
    TS_PLAYER_NONE = 2,
    TS_US = 0,
    TS_USSR = 1
}

enum ts_war
{
    TS_EARLY,
    TS_MID,
    TS_LATE
}

struct ts_card
{
    ts_card_id id;
    char *name;
    char *description;
    int ops;
    ts_player side;
    ts_war war;
}

struct ts_card cards[] = {
    // Early War (1-35, 103-106)
    {TS_ASIA_SCORING, "Asia Scoring", "Scoring card for Asia region", 0, TS_PLAYER_NONE, TS_EARLY},
    {TS_EUROPE_SCORING, "Europe Scoring", "Scoring card for Europe region", 0, TS_PLAYER_NONE, TS_EARLY},
    {TS_MIDDLE_EAST_SCORING, "Middle East Scoring", "Scoring card for Middle East region", 0, TS_PLAYER_NONE, TS_EARLY},
    {TS_DUCK_AND_COVER, "Duck and Cover", "US event", 3, TS_US, TS_EARLY},
    {TS_FIVE_YEAR_PLAN, "Five Year Plan", "USSR event", 3, TS_USSR, TS_EARLY},
    {TS_THE_CHINA_CARD, "The China Card", "Either side event", 4, TS_PLAYER_NONE, TS_EARLY},
    {TS_SOCIALIST_GOVERNMENTS, "Socialist Governments", "USSR event", 3, TS_USSR, TS_EARLY},
    {TS_FIDEL, "Fidel", "USSR event", 2, TS_USSR, TS_EARLY},
    {TS_VIETNAM_REVOLTS, "Vietnam Revolts", "USSR event", 2, TS_USSR, TS_EARLY},
    {TS_BLOCKADE, "Blockade", "USSR event", 1, TS_USSR, TS_EARLY},
    {TS_KOREAN_WAR, "Korean War", "USSR event", 2, TS_USSR, TS_EARLY},
    {TS_ROMANIAN_ABDICATION, "Romanian Abdication", "USSR event", 1, TS_USSR, TS_EARLY},
    {TS_ARAB_ISRAELI_WAR, "Arab-Israeli War", "USSR event", 2, TS_USSR, TS_EARLY},
    {TS_COMECON, "Comecon", "USSR event", 3, TS_USSR, TS_EARLY},
    {TS_NASSER, "Nasser", "USSR event", 1, TS_USSR, TS_EARLY},
    {TS_WARSAW_PACT_FORMED, "Warsaw Pact Formed", "USSR event", 3, TS_USSR, TS_EARLY},
    {TS_DE_GAULLE_LEADS_FRANCE, "De Gaulle Leads France", "USSR event", 3, TS_USSR, TS_EARLY},
    {TS_CAPTURED_NAZI_SCIENTIST, "Captured Nazi Scientist", "USSR event", 1, TS_USSR, TS_EARLY},
    {TS_TRUMAN_DOCTRINE, "Truman Doctrine", "US event", 1, TS_US, TS_EARLY},
    {TS_OLYMPIC_GAMES, "Olympic Games", "Either side event", 2, TS_PLAYER_NONE, TS_EARLY},
    {TS_NATO, "NATO", "US event", 4, TS_US, TS_EARLY},
    {TS_INDEPENDENT_REDS, "Independent Reds", "US event", 2, TS_US, TS_EARLY},
    {TS_MARSHALL_PLAN, "Marshall Plan", "US event", 4, TS_US, TS_EARLY},
    {TS_INDO_PAKISTANI_WAR, "Indo-Pakistani War", "Either side event", 2, TS_PLAYER_NONE, TS_EARLY},
    {TS_CONTAINMENT, "Containment", "US event", 3, TS_US, TS_EARLY},
    {TS_CIA_CREATED, "CIA Created", "US event", 1, TS_US, TS_EARLY},
    {TS_US_JAPAN_MUTUAL_DEFENSE_PACT, "US/Japan Mutual Defense Pact", "US event", 4, TS_US, TS_EARLY},
    {TS_SUEZ_CRISIS, "Suez Crisis", "US event", 3, TS_US, TS_EARLY},
    {TS_EAST_EUROPEAN_UNREST, "East European Unrest", "US event", 3, TS_US, TS_EARLY},
    {TS_DECOLONIZATION, "Decolonization", "USSR event", 2, TS_USSR, TS_EARLY},
    {TS_RED_SCARE_PURGE, "Red Scare/Purge", "US event", 4, TS_US, TS_EARLY},
    {TS_UN_INTERVENTION, "UN Intervention", "Either side event", 1, TS_PLAYER_NONE, TS_EARLY},
    {TS_DE_STALINIZATION, "De-Stalinization", "USSR event", 3, TS_USSR, TS_EARLY},
    {TS_NUCLEAR_TEST_BAN, "Nuclear Test Ban", "Either side event", 4, TS_PLAYER_NONE, TS_EARLY},
    {TS_FORMOSAN_RESOLUTION, "Formosan Resolution", "US event", 2, TS_US, TS_EARLY},
    {TS_DEFECTORS, "Defectors", "US event", 2, TS_US, TS_EARLY},

    // Mid War (36-81, 107-108)
    {TS_BRUSH_WAR, "Brush War", "Either side event", 3, TS_PLAYER_NONE, TS_MID},
    {TS_CENTRAL_AMERICA_SCORING, "Central America Scoring", "Scoring card", 0, TS_PLAYER_NONE, TS_MID},
    {TS_SOUTHEAST_ASIA_SCORING, "Southeast Asia Scoring", "Scoring card", 0, TS_PLAYER_NONE, TS_MID},
    {TS_ARMS_RACE, "Arms Race", "Either side event", 3, TS_PLAYER_NONE, TS_MID},
    {TS_CUBAN_MISSILE_CRISIS, "Cuban Missile Crisis", "US event", 3, TS_US, TS_MID},
    {TS_NUCLEAR_SUBS, "Nuclear Subs", "US event", 2, TS_US, TS_MID},
    {TS_QUAGMIRE, "Quagmire", "US event", 3, TS_US, TS_MID},
    {TS_SALT_NEGOTIATIONS, "SALT Negotiations", "USSR event", 3, TS_USSR, TS_MID},
    {TS_BEAR_TRAP, "Bear Trap", "US event", 3, TS_US, TS_MID},
    {TS_SUMMIT, "Summit", "Either side event", 1, TS_PLAYER_NONE, TS_MID},
    {TS_HOW_I_LEARNED_TO_STOP_WORRYING, "How I Learned to Stop Worrying", "USSR event", 2, TS_USSR, TS_MID},
    {TS_JUNTA, "Junta", "Either side event", 2, TS_PLAYER_NONE, TS_MID},
    {TS_KITCHEN_DEBATES, "Kitchen Debates", "US event", 1, TS_US, TS_MID},
    {TS_MISSILE_ENVY, "Missile Envy", "Either side event", 2, TS_PLAYER_NONE, TS_MID},
    {TS_WE_WILL_BURY_YOU, "We Will Bury You", "USSR event", 4, TS_USSR, TS_MID},
    {TS_BREZHNEV_DOCTRINE, "Brezhnev Doctrine", "USSR event", 3, TS_USSR, TS_MID},
    {TS_PORTUGUESE_EMPIRE_CRUMBLES, "Portuguese Empire Crumbles", "USSR event", 2, TS_USSR, TS_MID},
    {TS_SOUTH_AFRICAN_UNREST, "South African Unrest", "USSR event", 2, TS_USSR, TS_MID},
    {TS_ALLENDE, "Allende", "USSR event", 1, TS_USSR, TS_MID},
    {TS_WILLY_BRANDT, "Willy Brandt", "USSR event", 2, TS_USSR, TS_MID},
    {TS_MUSLIM_REVOLUTION, "Muslim Revolution", "USSR event", 4, TS_USSR, TS_MID},
    {TS_ABM_TREATY, "ABM Treaty", "Either side event", 4, TS_PLAYER_NONE, TS_MID},
    {TS_CULTURAL_REVOLUTION, "Cultural Revolution", "USSR event", 3, TS_USSR, TS_MID},
    {TS_FLOWER_POWER, "Flower Power", "USSR event", 4, TS_USSR, TS_MID},
    {TS_U2_INCIDENT, "U2 Incident", "USSR event", 3, TS_USSR, TS_MID},
    {TS_OPEC, "OPEC", "USSR event", 3, TS_USSR, TS_MID},
    {TS_LONE_GUNMAN, "Lone Gunman", "USSR event", 1, TS_USSR, TS_MID},
    {TS_COLONIAL_REAR_GUARDS, "Colonial Rear Guards", "US event", 2, TS_US, TS_MID},
    {TS_PANAMA_CANAL_RETURNED, "Panama Canal Returned", "US event", 1, TS_US, TS_MID},
    {TS_CAMP_DAVID_ACCORDS, "Camp David Accords", "US event", 2, TS_US, TS_MID},
    {TS_PUPPET_GOVERNMENTS, "Puppet Governments", "US event", 2, TS_US, TS_MID},
    {TS_GRAIN_SALES_TO_SOVIETS, "Grain Sales to Soviets", "US event", 2, TS_US, TS_MID},
    {TS_JOHN_PAUL_II_ELECTED_POPE, "John Paul II Elected Pope", "US event", 2, TS_US, TS_MID},
    {TS_LATIN_AMERICAN_DEATH_SQUADS, "Latin American Death Squads", "Either side event", 2, TS_PLAYER_NONE, TS_MID},
    {TS_OAS_FOUNDED, "OAS Founded", "US event", 1, TS_US, TS_MID},
    {TS_NIXON_PLAYS_THE_CHINA_CARD, "Nixon Plays the China Card", "US event", 2, TS_US, TS_MID},
    {TS_SADAT_EXPELS_SOVIETS, "Sadat Expels Soviets", "US event", 1, TS_US, TS_MID},
    {TS_SHUTTLE_DIPLOMACY, "Shuttle Diplomacy", "US event", 3, TS_US, TS_MID},
    {TS_THE_VOICE_OF_AMERICA, "The Voice of America", "US event", 2, TS_US, TS_MID},
    {TS_LIBERATION_THEOLOGY, "Liberation Theology", "USSR event", 2, TS_USSR, TS_MID},
    {TS_USSURI_RIVER_SKIRMISH, "Ussuri River Skirmish", "US event", 3, TS_US, TS_MID},
    {TS_ASK_NOT_WHAT_YOUR_COUNTRY, "Ask Not What Your Country...", "US event", 3, TS_US, TS_MID},
    {TS_ALLIANCE_FOR_PROGRESS, "Alliance for Progress", "US event", 3, TS_US, TS_MID},
    {TS_AFRICA_SCORING, "Africa Scoring", "Scoring card", 0, TS_PLAYER_NONE, TS_MID},
    {TS_ONE_SMALL_STEP, "One Small Step...", "Either side event", 2, TS_PLAYER_NONE, TS_MID},
    {TS_SOUTH_AMERICA_SCORING, "South America Scoring", "Scoring card", 0, TS_PLAYER_NONE, TS_MID},

    // Late War (82-102, 109-110)
    {TS_IRANIAN_HOSTAGE_CRISIS, "Iranian Hostage Crisis", "USSR event", 3, TS_USSR, TS_LATE},
    {TS_THE_IRON_LADY, "The Iron Lady", "USSR event", 3, TS_USSR, TS_LATE},
    {TS_REAGAN_BOMBS_LIBYA, "Reagan Bombs Libya", "US event", 2, TS_US, TS_LATE},
    {TS_STAR_WARS, "Star Wars", "US event", 2, TS_US, TS_LATE},
    {TS_NORTH_SEA_OIL, "North Sea Oil", "US event", 3, TS_US, TS_LATE},
    {TS_THE_REFORMER, "The Reformer", "USSR event", 3, TS_USSR, TS_LATE},
    {TS_MARINE_BARRACKS_BOMBING, "Marine Barracks Bombing", "USSR event", 2, TS_USSR, TS_LATE},
    {TS_SOVIETS_SHOOT_DOWN_KAL_007, "Soviets Shoot Down KAL-007", "US event", 4, TS_US, TS_LATE},
    {TS_GLASNOST, "Glasnost", "USSR event", 4, TS_USSR, TS_LATE},
    {TS_ORTEGA_ELECTED_IN_NICARAGUA, "Ortega Elected in Nicaragua", "USSR event", 2, TS_USSR, TS_LATE},
    {TS_TERRORISM, "Terrorism", "Either side event", 2, TS_PLAYER_NONE, TS_LATE},
    {TS_IRAN_CONTRA_SCANDAL, "Iran-Contra Scandal", "US event", 2, TS_US, TS_LATE},
    {TS_CHERNOBYL, "Chernobyl", "US event", 3, TS_US, TS_LATE},
    {TS_LATIN_AMERICAN_DEBT_CRISIS, "Latin American Debt Crisis", "US event", 2, TS_US, TS_LATE},
    {TS_TEAR_DOWN_THIS_WALL, "Tear Down this Wall", "US event", 3, TS_US, TS_LATE},
    {TS_AN_EVIL_EMPIRE, "An Evil Empire", "US event", 3, TS_US, TS_LATE},
    {TS_ALDRICH_AMES_REMIX, "Aldrich Ames Remix", "USSR event", 3, TS_USSR, TS_LATE},
    {TS_PERSHING_II_DEPLOYED, "Pershing II Deployed", "USSR event", 3, TS_USSR, TS_LATE},
    {TS_WARGAMES, "Wargames", "Either side event", 4, TS_PLAYER_NONE, TS_LATE},
    {TS_SOLIDARITY, "Solidarity", "US event", 2, TS_US, TS_LATE},
    {TS_IRAN_IRAQ_WAR, "Iran-Iraq War", "Either side event", 2, TS_PLAYER_NONE, TS_LATE},

    // Optional cards
    {TS_THE_CAMBRIDGE_FIVE, "The Cambridge Five", "USSR event", 2, TS_USSR, TS_EARLY},
    {TS_SPECIAL_RELATIONSHIP, "Special Relationship", "US event", 2, TS_US, TS_EARLY},
    {TS_NORAD, "NORAD", "US event", 3, TS_US, TS_EARLY},
    {TS_CHE, "Che", "USSR event", 3, TS_USSR, TS_MID},
    {TS_OUR_MAN_IN_TEHRAN, "Our Man in Tehran", "US event", 2, TS_US, TS_MID},
    {TS_YURI_AND_SAMANTHA, "Yuri and Samantha", "USSR event", 2, TS_USSR, TS_LATE},
    {TS_AWACS_SALE_TO_SAUDIS, "AWACS Sale to Saudis", "US event", 3, TS_US, TS_LATE},
};

int ts_card_amount = sizeof(cards) / sizeof(cards[0]);

enum ts_mode
{
    HEADLINE_PICK,
    HEADLINE_ACT,
    REALIGNMENT,
    DISCARD,
    PLAY_CARD
};

struct ts_state
{
    int turn;
    int ar;
    int defcon;
    int vp;
    int mil;
    char phasing;

    int *countries;
    int **influences;

    ts_card *drawDeck;
    ts_card *discardDeck;
    ts_card *removedDeck
};

struct ts_move
{
    ts_card card;
    int target_country;
    int target_influence;
};

void ts_is_legal_move(ts_state &state, ts_mode mode)
{
}

void ts_init_game(ts_state &state)
{
}

void ts_gameover(ts_state &state)
{
}

void ts_run()
{
}
