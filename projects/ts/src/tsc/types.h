#include <cstring>
#include <random>
#include "util.h"


#define TS_MAX_HAND_SIZE 12


enum ts_country_id
{

    // Western Europe
    TS_CANADA = 3,
    TS_UK = 4,
    TS_NORWAY = 5,
    TS_SWEDEN = 6,
    TS_DENMARK = 8,
    TS_BENELUX = 9,
    TS_FRANCE = 10,
    TS_SPAIN_PORTUGAL = 11,
    TS_ITALY = 12,
    TS_GREECE = 13,
    TS_WEST_GERMANY = 15,
    TS_TURKEY = 23,

    // Europe (border countries, no subregion)
    TS_FINLAND = 7,
    TS_AUSTRIA = 14,

    // Eastern Europe
    TS_EAST_GERMANY = 16,
    TS_POLAND = 17,
    TS_CZECHOSLOVAKIA = 18,
    TS_HUNGARY = 19,
    TS_YUGOSLAVIA = 20,
    TS_ROMANIA = 21,
    TS_BULGARIA = 22,

    // Middle East
    TS_LIBYA = 24,
    TS_EGYPT = 25,
    TS_ISRAEL = 26,
    TS_LEBANON = 27,
    TS_SYRIA = 28,
    TS_IRAQ = 29,
    TS_IRAN = 30,
    TS_JORDAN = 31,
    TS_GULF_STATES = 32,
    TS_SAUDI_ARABIA = 33,

    // Asia
    TS_AFGHANISTAN = 34,
    TS_PAKISTAN = 35,
    TS_INDIA = 36,
    TS_AUSTRALIA = 42,
    TS_JAPAN = 45,
    TS_TAIWAN = 46,
    TS_SOUTH_KOREA = 47,
    TS_NORTH_KOREA = 48,
    TS_CHINESE_CIVIL_WAR = 87,

    // Southeast Asia
    TS_BURMA = 37,
    TS_LAOS_CAMBODIA = 38,
    TS_THAILAND = 39,
    TS_VIETNAM = 40,
    TS_MALAYSIA = 41,
    TS_INDONESIA = 43,
    TS_PHILIPPINES = 44,

    // Africa
    TS_ALGERIA = 49,
    TS_MOROCCO = 50,
    TS_TUNISIA = 51,
    TS_WEST_AFRICAN_STATES = 52,
    TS_IVORY_COAST = 53,
    TS_SAHARAN_STATES = 54,
    TS_NIGERIA = 55,
    TS_CAMEROON = 56,
    TS_ZAIRE = 57,
    TS_ANGOLA = 58,
    TS_SOUTH_AFRICA = 59,
    TS_BOTSWANA = 60,
    TS_ZIMBABWE = 61,
    TS_SE_AFRICAN_STATES = 62,
    TS_KENYA = 63,
    TS_SOMALIA = 64,
    TS_ETHIOPIA = 65,
    TS_SUDAN = 66,

    // Central America
    TS_MEXICO = 67,
    TS_GUATEMALA = 68,
    TS_EL_SALVADOR = 69,
    TS_HONDURAS = 70,
    TS_COSTA_RICA = 71,
    TS_PANAMA = 72,
    TS_NICARAGUA = 73,
    TS_CUBA = 74,
    TS_HAITI = 75,
    TS_DOMINICAN_REPUBLIC = 76,

    // South America
    TS_COLOMBIA = 77,
    TS_ECUADOR = 78,
    TS_PERU = 79,
    TS_CHILE = 80,
    TS_ARGENTINA = 81,
    TS_URUGUAY = 82,
    TS_PARAGUAY = 83,
    TS_BOLIVIA = 84,
    TS_BRAZIL = 85,
    TS_VENEZUELA = 86,
};

struct ts_country
{
    int id;
    const char *name;
    bool battleground;
    int stability;
};

struct ts_country countries[] = {

    // Western Europe
    {TS_CANADA, "Canada", false, 4},
    {TS_UK, "UK", false, 5},
    {TS_NORWAY, "Norway", false, 4},
    {TS_SWEDEN, "Sweden", false, 4},
    {TS_DENMARK, "Denmark", false, 3},
    {TS_BENELUX, "Benelux", false, 3},
    {TS_FRANCE, "France", true, 3},
    {TS_SPAIN_PORTUGAL, "Spain/Portugal", false, 2},
    {TS_ITALY, "Italy", true, 2},
    {TS_GREECE, "Greece", false, 2},
    {TS_WEST_GERMANY, "West Germany", true, 4},
    {TS_TURKEY, "Turkey", false, 2},

    // Europe (border countries)
    {TS_FINLAND, "Finland", false, 4},
    {TS_AUSTRIA, "Austria", false, 4},

    // Eastern Europe
    {TS_EAST_GERMANY, "East Germany", true, 3},
    {TS_POLAND, "Poland", true, 3},
    {TS_CZECHOSLOVAKIA, "Czechoslovakia", false, 3},
    {TS_HUNGARY, "Hungary", false, 3},
    {TS_YUGOSLAVIA, "Yugoslavia", false, 3},
    {TS_ROMANIA, "Romania", false, 3},
    {TS_BULGARIA, "Bulgaria", false, 3},

    // Middle East
    {TS_LIBYA, "Libya", true, 2},
    {TS_EGYPT, "Egypt", true, 2},
    {TS_ISRAEL, "Israel", true, 4},
    {TS_LEBANON, "Lebanon", false, 1},
    {TS_SYRIA, "Syria", false, 2},
    {TS_IRAQ, "Iraq", true, 3},
    {TS_IRAN, "Iran", true, 2},
    {TS_JORDAN, "Jordan", false, 2},
    {TS_GULF_STATES, "Gulf States", false, 3},
    {TS_SAUDI_ARABIA, "Saudi Arabia", true, 3},

    // Asia
    {TS_AFGHANISTAN, "Afghanistan", false, 2},
    {TS_PAKISTAN, "Pakistan", true, 2},
    {TS_INDIA, "India", true, 3},
    {TS_AUSTRALIA, "Australia", false, 4},
    {TS_JAPAN, "Japan", true, 4},
    {TS_TAIWAN, "Taiwan", false, 3},
    {TS_SOUTH_KOREA, "South Korea", true, 3},
    {TS_NORTH_KOREA, "North Korea", true, 3},
    {TS_CHINESE_CIVIL_WAR, "Chinese Civil War", false, 3},

    // Southeast Asia
    {TS_BURMA, "Burma", false, 2},
    {TS_LAOS_CAMBODIA, "Laos/Cambodia", false, 1},
    {TS_THAILAND, "Thailand", true, 2},
    {TS_VIETNAM, "Vietnam", false, 1},
    {TS_MALAYSIA, "Malaysia", false, 2},
    {TS_INDONESIA, "Indonesia", false, 1},
    {TS_PHILIPPINES, "Philippines", false, 2},

    // Africa
    {TS_ALGERIA, "Algeria", true, 2},
    {TS_MOROCCO, "Morocco", false, 3},
    {TS_TUNISIA, "Tunisia", false, 2},
    {TS_WEST_AFRICAN_STATES, "West African States", false, 2},
    {TS_IVORY_COAST, "Ivory Coast", false, 2},
    {TS_SAHARAN_STATES, "Saharan States", false, 1},
    {TS_NIGERIA, "Nigeria", true, 1},
    {TS_CAMEROON, "Cameroon", false, 1},
    {TS_ZAIRE, "Zaire", true, 1},
    {TS_ANGOLA, "Angola", true, 1},
    {TS_SOUTH_AFRICA, "South Africa", true, 3},
    {TS_BOTSWANA, "Botswana", false, 2},
    {TS_ZIMBABWE, "Zimbabwe", false, 1},
    {TS_SE_AFRICAN_STATES, "SE African States", false, 1},
    {TS_KENYA, "Kenya", false, 2},
    {TS_SOMALIA, "Somalia", false, 2},
    {TS_ETHIOPIA, "Ethiopia", false, 1},
    {TS_SUDAN, "Sudan", false, 1},

    // Central America
    {TS_MEXICO, "Mexico", true, 2},
    {TS_GUATEMALA, "Guatemala", false, 1},
    {TS_EL_SALVADOR, "El Salvador", false, 1},
    {TS_HONDURAS, "Honduras", false, 2},
    {TS_COSTA_RICA, "Costa Rica", false, 3},
    {TS_PANAMA, "Panama", true, 2},
    {TS_NICARAGUA, "Nicaragua", false, 1},
    {TS_CUBA, "Cuba", true, 3},
    {TS_HAITI, "Haiti", false, 1},
    {TS_DOMINICAN_REPUBLIC, "Dominican Republic", false, 1},

    // South America
    {TS_COLOMBIA, "Colombia", false, 1},
    {TS_ECUADOR, "Ecuador", false, 2},
    {TS_PERU, "Peru", false, 2},
    {TS_CHILE, "Chile", true, 3},
    {TS_ARGENTINA, "Argentina", true, 2},
    {TS_URUGUAY, "Uruguay", false, 2},
    {TS_PARAGUAY, "Paraguay", false, 2},
    {TS_BOLIVIA, "Bolivia", false, 2},
    {TS_BRAZIL, "Brazil", true, 2},
    {TS_VENEZUELA, "Venezuela", true, 2},
};

const int ts_country_amount = sizeof(countries) / sizeof(countries[0]);

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
};

enum ts_player
{
    TS_PLAYER_NONE = 2,
    TS_US = 0,
    TS_USSR = 1
};

enum ts_war
{
    TS_EARLY,
    TS_MID,
    TS_LATE
};

struct ts_card
{
    ts_card_id id;
    const char *name;
    const char *description;
    int ops;
    ts_player side;
    ts_war war;
};

struct ts_card ts_cards[] = {
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

const int ts_card_amount = sizeof(ts_cards) / sizeof(ts_cards[0]);

#define TS_MAX_PILE_SIZE ts_card_amount

enum ts_china_card_state
{
    TS_CHINA_CARD_STATE_USSR_FACEUP,
    TS_CHINA_CARD_STATE_USSR_FACE_DOWN,
    TS_CHINA_CARD_STATE_US_FACEUP,
    TS_CHINA_CARD_STATE_US_FACE_DOWN,
};

enum ts_current_step
{
    TS_STEP_INIT = 0,
    TS_STEP_USSR_PLACE_SIX_INFLUENCE_EASTERN_EUROPE,
    TS_STEP_INIT_US,
    TS_STEP_US_PLACE_SEVEN_INFLUENCE_WESTERN_EUROPE,
    TS_STEP_INIT_FINISH,
    TS_STEP_BEGIN_TURN,
    TS_STEP_HEADLINE_A,
    TS_STEP_HEADLINE_B,
    TS_STEP_RESOLVE_FIRST_HEADLINE,
    TS_STEP_RESOLVE_SECOND_HEADLINE,
};



struct ts_state
{
    ts_util_random _random;
    ts_current_step _current_step;

    int turn;
    int ar;
    int defcon;
    int vp;
    int mil;
    ts_player phasing;
    ts_china_card_state china_card_state;

    ts_card_id headlineCards[2];

    int countryInfluences[2][ts_country_amount]; 

    ts_card_id drawPile[TS_MAX_PILE_SIZE];
    int drawDeckSize;
    ts_card_id discardPile[TS_MAX_PILE_SIZE];
    int discardDeckSize;
    ts_card_id removedDeck[TS_MAX_PILE_SIZE];
    int removedDeckSize;

    ts_card_id playerHands[2][TS_MAX_HAND_SIZE];
    int playerHandSizes[2];

    int spaceTrack[2];
    int militaryTrack[2];
};

struct ts_move
{
    ts_card card;
    int target_country;
    int target_influence;
};

void ts_shuffle(ts_card_id *deck, int size)
{
    for (int i = 0; i < size; i++)
    {
        int j = rand() % size;
        ts_card_id temp = deck[i];
        deck[i] = deck[j];
        deck[j] = temp;
    }
}

inline void ts_copy_state(ts_state const &src, ts_state &dst)
{
    memcpy(&dst, &src, sizeof(ts_state));
}

inline void ts_shuffle_discard_into_draw_pile(ts_state &state)
{
    for (int i = 0; i < state.discardDeckSize; i++)
    {
        state.drawPile[state.drawDeckSize++] = state.discardPile[i];
    }
    state.discardDeckSize = 0;
    ts_shuffle(state.drawPile, state.drawDeckSize);
}

inline ts_state ts_advance_game(ts_state const &state)
{
    ts_state newState;
    ts_copy_state(state, newState);

    switch(state._current_step)
    {
        case TS_STEP_INIT:
        {
            // 3.0 GAME SETUP
            // 3.1
            //      Shuffle the Early War cards and deal each player 8 cards.
            newState.drawDeckSize = 0;
            for (int i = 0; i < ts_card_amount; i++)
            {
                ts_card &card = ts_cards[i];
                if (card.war == TS_EARLY)
                {
                    newState.drawPile[newState.drawDeckSize++] = card.id;
                }
            }

            for (int i = 0; i < 8; i++)
            {
                newState.playerHands[TS_US][newState.playerHandSizes[TS_US]++] = newState.drawPile[--newState.drawDeckSize];
                newState.playerHands[TS_USSR][newState.playerHandSizes[TS_USSR]++] = newState.drawPile[--newState.drawDeckSize];

                newState.drawDeckSize-=2;
            }

            //      In addition, place ‘The China Card’ face up in front of the USSR player.
            newState.china_card_state = TS_CHINA_CARD_STATE_USSR_FACEUP;
            //      The players are allowed to examine their cards prior to deploying their initial Influence markers.
            // 3.2 The USSR player sets up first.The USSR places a total of 15 Influence markers in the following locations :
            //      1 in Syria,
            newState.countryInfluences[TS_USSR][TS_SYRIA] = 1;
            //      1 in Iraq
            newState.countryInfluences[TS_USSR][TS_IRAQ] = 1;
            //      3 in North Korea
            newState.countryInfluences[TS_USSR][TS_NORTH_KOREA] = 3;
            //      3 in East Germany
            newState.countryInfluences[TS_USSR][TS_EAST_GERMANY] = 3; 
            // 1 in Finland
            newState.countryInfluences[TS_USSR] [TS_FINLAND]= 1;
            //  and 6 anywhere in Eastern Europe.
            newState._current_step = TS_STEP_USSR_PLACE_SIX_INFLUENCE_EASTERN_EUROPE;            
            return newState;
        }
    
        case TS_STEP_USSR_PLACE_SIX_INFLUENCE_EASTERN_EUROPE:
        {
            // 6 anywhere in Eastern Europe.    
            return newState;
        }
        case TS_STEP_INIT_US:
        {
            // 3.3 The US player sets up second, placing a total of 25 Influence markers in the following locations : 
            // 2 in Canada, 
            newState.countryInfluences[TS_US][TS_CANADA]= 2;
            // 1 in Iran, 
            newState.countryInfluences[TS_US][TS_IRAN] = 1;
            // 1 in Israel
            newState.countryInfluences[TS_US][TS_ISRAEL] = 1;
            // 1 in Japan
            newState.countryInfluences[TS_US][TS_JAPAN] = 1;
            // 4 in Australia
            newState.countryInfluences[TS_US][TS_AUSTRALIA] = 4;
            // 1 in the Philippines
            newState.countryInfluences[TS_US][TS_PHILIPPINES] = 1;
            // 1 in South Korea
            newState.countryInfluences[TS_US][TS_SOUTH_KOREA] = 1;
            // 1 in Panama,
            newState.countryInfluences[TS_US][TS_PANAMA] = 1;
            // 1 in South Africa
            newState.countryInfluences[TS_US][TS_SOUTH_AFRICA] = 1;
            // 5 in the United Kingdom
            newState.countryInfluences[TS_US][TS_UK] = 5;

            // and 7 anywhere in Western Europe.
            newState._current_step = TS_STEP_US_PLACE_SEVEN_INFLUENCE_WESTERN_EUROPE;
            return newState;
        }
        case TS_STEP_US_PLACE_SEVEN_INFLUENCE_WESTERN_EUROPE:
        {
            return newState;
        }
        case TS_STEP_INIT_FINISH:
        {
            // 3.4 
            // Place the US and USSR Space Race markers to the left of the Space Race track.
            newState.spaceTrack[TS_US] = 0;
            newState.spaceTrack[TS_USSR] = 0;
            // Each player places his Military OP marker on the zero space of their respective Military Operations Track
            newState.militaryTrack[TS_US] = 0;
            newState.militaryTrack[TS_USSR] = 0;
            // Place the Turn marker on the first space of the Turn Record Track.
            newState.turn = 1;
            // Place the Defcon marker on the 5 space of the DEFCON Track.
            newState.defcon = 5;
            // Finally, place the VP marker on the Victory Points Track on the zero space.
            newState.vp = 0;

            return newState;
        }
        case TS_STEP_BEGIN_TURN:
        {
            // 4.1 Twilight Struggle has ten turns. Each turn represents 
            // between three and five years, and will involve six or seven
            // normal card plays by each player. At the beginning of the game,
            // each player receives eight cards from the Early War deck. At the
            // beginning of turn 4, the Mid War deck is shuffled into the draw pile 
            // and the players’ hand size increases to nine. 
            // At the beginning of turn 8, the Late War deck is shuffled into the draw pile.

            // B. Deal Cards: Each player receives enough cards to bring their
            // total hand size to 8 on turns 1-3. On turns 4-10, players should
            // receive enough cards to bring their total hand size to 9. ‘The
            // China Card’ is never included in this total.
            if (newState.turn == 4)
            {
                for (int i = 0; i < ts_card_amount; i++)
                {
                    ts_card &card = ts_cards[i];
                    if (card.war == TS_MID)
                    {
                        newState.drawPile[newState.drawDeckSize++] = card.id;
                    }
                }
                newState._current_step = TS_STEP_BEGIN_TURN;
                ts_shuffle(newState.drawPile, newState.drawDeckSize);
            }
            else if (newState.turn == 8)
            {
                for (int i = 0; i < ts_card_amount; i++)
                {
                    ts_card &card = ts_cards[i];
                    if (card.war == TS_LATE)
                    {
                        newState.drawPile[newState.drawDeckSize++] = card.id;
                    }
                }
                newState._current_step = TS_STEP_BEGIN_TURN;
                ts_shuffle(newState.drawPile, newState.drawDeckSize);
            }
        

            int handsize = (newState.turn >= 4) ? 9 : 8;

            // 4.3.1 Deal all cards remaining in the draw deck before reshuf-
            // fling, except in turns 4 and 8 (see 4.4.)
            while (newState.playerHandSizes[TS_US] < handsize)
            {
                /* When there are no cards remaining in the draw deck, reshuffle
                all discards to form a new draw deck. Note that cards played as
                Events with an asterisk (*) are removed from the game when they
                are played, and are not shuffled into the new draw deck.*/
                
                if (newState.drawDeckSize == 0)
                    ts_shuffle_discard_into_draw_pile(newState);

                newState.playerHands[TS_US][newState.playerHandSizes[TS_US]++] = 
                    newState.drawPile[--newState.drawDeckSize];
            }
            while (newState.playerHandSizes[TS_USSR] < handsize)
            {
                if (newState.drawDeckSize == 0)
                    ts_shuffle_discard_into_draw_pile(newState);

                newState.playerHands[TS_USSR][newState.playerHandSizes[TS_USSR]++] = 
                    newState.drawPile[--newState.drawDeckSize];
            }

            // A. Improve DEFCON Status: If the DEFCON level is lower
            // than 5, add one to the DEFCON status (towards Peace).
            if (newState.defcon < 5)
            {
                newState.defcon++;
            }

            newState._current_step = TS_STEP_BEGIN_TURN;
            return newState;
        }
        case TS_STEP_HEADLINE_A:
        {
            // The indirection of A and B, instead of specific players is
            // because of the space race. Any player can gain the right to 
            // see the other's player headline, so they should come 
            // last
            newState._current_step = TS_STEP_HEADLINE_B;
            return newState;
        }
        case TS_STEP_HEADLINE_B:
        {
            return newState;
        }
        case TS_STEP_RESOLVE_FIRST_HEADLINE:
        {   
            newState.phasing = 
               ts_cards[state.headlineCards[TS_US]].ops < 
                    ts_cards[state.headlineCards[TS_USSR]].ops ? 
                    TS_USSR : TS_US;
            
            return newState;
        }
    }
}

bool ts_gameover(ts_state &state)
{
}

void ts_game()
{
    ts_state state;
    ts_advance_game(state);
}
