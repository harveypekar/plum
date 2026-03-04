"""Template-driven terminal renderer for Twilight Struggle.

Reads ts_gui_template.txt at module load, parses $(XX) placeholders to build
a country cell map, then substitutes game state data and applies 24-bit ANSI
colors at render time. Non-European countries display as 0/0.
"""

import re
from datetime import datetime
from pathlib import Path
from ts_game import Side, controls_country, card_by_id

# -- ANSI codes ---------------------------------------------------------------

ESC = "\033"
CLEAR = f"{ESC}[2J{ESC}[H"
RESET = f"{ESC}[0m"
BOLD = f"{ESC}[1m"


def _fg(r, g, b):
    return f"{ESC}[38;2;{r};{g};{b}m"


def _bg(r, g, b):
    return f"{ESC}[48;2;{r};{g};{b}m"


# -- Color palette (24-bit RGB) -----------------------------------------------

US_CLR    = _fg(100, 149, 237)   # cornflower blue
USSR_CLR  = _fg(220, 50, 50)     # red
EUR_CLR   = _fg(200, 200, 200)   # light gray (Europe)
ME_CLR    = _fg(230, 200, 60)    # yellow (Mid East)
ASIA_CLR  = _fg(80, 200, 80)     # green (Asia)
AFR_CLR   = _fg(220, 150, 50)    # orange (Africa)
CAM_CLR   = _fg(80, 200, 200)    # cyan (C.America)
SAM_CLR   = _fg(220, 120, 180)   # pink (S.America)
GOLD      = _fg(255, 215, 0)     # BG star
DIM_CLR   = _fg(80, 80, 80)      # box drawing, stability
HDR_CLR   = _fg(200, 200, 200)   # status bar text
MOVE_CLR  = _fg(180, 180, 100)   # last move
THINK_US   = _fg(0, 0, 0) + _bg(50, 70, 130)    # black on mid-blue
THINK_USSR = _fg(0, 0, 0) + _bg(130, 40, 40)     # black on mid-red
PERF_CLR   = _fg(100, 100, 100)                   # metrics (dim gray)

# -- Data mappings -------------------------------------------------------------

# ISO code -> engine country ID (21 European countries only)
ISO_TO_ENGINE = {
    "CA": 0, "GB": 1, "BX": 2, "FR": 3, "SP": 4,
    "NO": 5, "DK": 6, "DE": 7, "SE": 8, "IT": 9,
    "GR": 10, "TR": 11, "FI": 12, "AT": 13, "DD": 14,
    "PL": 15, "CS": 16, "HU": 17, "YU": 18, "RO": 19, "BG": 20,
}

# Region sets (for uncontrolled country name colors)
EUROPE    = set(ISO_TO_ENGINE)
MID_EAST  = {"LB", "SY", "IL", "IQ", "IR", "JO", "SA", "GS", "EG", "LY"}
ASIA      = {"AF", "PK", "IN", "KP", "KR", "JP", "TW", "TH", "LA", "VN",
             "MY", "ID", "PH", "MM", "AU"}
AFRICA    = {"MA", "DZ", "TN", "WA", "XS", "SD", "CI", "NG", "CM", "ET",
             "KE", "SO", "ZR", "AO", "ZW", "BW", "ZA", "XF"}
C_AMERICA = {"MX", "GT", "SV", "HN", "CR", "PA", "CU", "HT", "DO", "JM", "NI"}
S_AMERICA = {"CO", "VE", "BR", "EC", "PE", "BO", "CL", "AR", "PY", "UY"}


def _region_color(code):
    if code in EUROPE:    return EUR_CLR
    if code in MID_EAST:  return ME_CLR
    if code in ASIA:      return ASIA_CLR
    if code in AFRICA:    return AFR_CLR
    if code in C_AMERICA: return CAM_CLR
    if code in S_AMERICA: return SAM_CLR
    return EUR_CLR


# -- Template parsing (at module load) ----------------------------------------

_TEMPLATE_DIR = Path(__file__).parent
with open(_TEMPLATE_DIR / "ts_gui_template.txt") as _f:
    TEMPLATE_LINES = _f.read().splitlines()

# Parse all $(XX) placeholders (exactly 2 uppercase letters).
# CELLS[code] = [(line_idx, col_of_dollar_sign), ...]
CELLS: dict[str, list[tuple[int, int]]] = {}
for _li, _line in enumerate(TEMPLATE_LINES):
    for _m in re.finditer(r'\$\(([A-Z]{2})\)', _line):
        CELLS.setdefault(_m.group(1), []).append((_li, _m.start()))

# Per-line cell info for map lines (idx 1-17).
# Each country cell is 10 chars: NA[* ]S $(XX) — the $(XX) is at offset +5.
# LINE_CELLS[line_idx] = [(cell_start_col, code), ...] sorted by column.
LINE_CELLS: dict[int, list[tuple[int, str]]] = {}
for _code, _positions in CELLS.items():
    for _li, _col in _positions:
        if 1 <= _li <= 17:
            LINE_CELLS.setdefault(_li, []).append((_col - 5, _code))
for _li in LINE_CELLS:
    LINE_CELLS[_li].sort()

BOX_CHARS = set("─│┌┐└┘├┤┬┴┼═")


# -- Colorize helpers ----------------------------------------------------------


def _colorize_cell(code, cell_text, ctrl):
    """Color a 10-char country cell: 'NA S II/JJ' or 'NA*S II/JJ'."""
    name = cell_text[0:2]
    star = cell_text[2]
    stab = cell_text[3]
    inf = cell_text[5:10]  # "II/JJ" e.g. " 0/ 4"

    if ctrl == "US":
        nc = US_CLR
    elif ctrl == "USSR":
        nc = USSR_CLR
    else:
        nc = _region_color(code)

    parts = [f"{nc}{name}"]
    parts.append(f"{GOLD}*" if star == "*" else " ")
    parts.append(f"{DIM_CLR}{stab} ")
    parts.append(f"{US_CLR}{inf[0:2]}{DIM_CLR}/{USSR_CLR}{inf[3:5]}")
    return "".join(parts)


def _colorize_non_cell(text):
    """Color non-cell text on a map line (box drawing, labels)."""
    out = []
    i = 0
    while i < len(text):
        if text[i:i + 6] == "═USSR═":
            out.append(f"{DIM_CLR}═{USSR_CLR}USSR{DIM_CLR}═")
            i += 6
        elif text[i:i + 5] == "═USA═":
            out.append(f"{DIM_CLR}═{US_CLR}USA{DIM_CLR}═")
            i += 5
        elif text[i] in BOX_CHARS:
            j = i + 1
            while j < len(text) and text[j] in BOX_CHARS:
                j += 1
            out.append(f"{DIM_CLR}{text[i:j]}")
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _colorize_map_line(line_idx, line, control):
    """Color a map line with cell-aware coloring."""
    cells = LINE_CELLS.get(line_idx, [])
    out = []
    pos = 0
    for cell_start, code in cells:
        if pos < cell_start:
            out.append(_colorize_non_cell(line[pos:cell_start]))
        cell_end = cell_start + 10
        out.append(_colorize_cell(code, line[cell_start:cell_end], control.get(code, "")))
        pos = cell_end
    if pos < len(line):
        out.append(_colorize_non_cell(line[pos:]))
    out.append(RESET)
    return "".join(out)


# -- Main render function -----------------------------------------------------


def render(gs, last_move: str = "", model: str = "q8") -> str:
    """Render the full game screen. Returns a raw ANSI string."""
    lines = list(TEMPLATE_LINES)
    side = gs.phasing_player
    side_name = "US" if side == Side.US else "USSR"

    # -- 1. Status bar (line 0) — must replace $(AR) here before country sub --
    china = ("US" if gs.china_card_holder == Side.US else "USSR") + \
            ("*" if gs.china_card_face_up else "")
    now = datetime.now().strftime("%H:%M")
    lines[0] = (lines[0]
        .replace("$(SIDE)", side_name)
        .replace("$(T)", str(gs.turn))
        .replace("$(AR)", str(gs.action_round))
        .replace("$(DEF)", str(gs.defcon))
        .replace("$(VP)", f"{gs.vp:+d}")
        .replace("$(MIL)", f"{gs.mil_ops[Side.US]}/{gs.mil_ops[Side.USSR]}")
        .replace("$(SPC)", f"{gs.space_race[Side.US]}/{gs.space_race[Side.USSR]}")
        .replace("$(CHN)", china)
        .replace("$(TIME)", now)
        .replace("$(MDL)", model))

    # -- 2. Country influence (map lines 1-17) --
    influence = {}  # code -> "II/JJ" (5 chars)
    control = {}    # code -> "US" | "USSR"
    for code, positions in CELLS.items():
        if not any(1 <= li <= 17 for li, _ in positions):
            continue
        eid = ISO_TO_ENGINE.get(code)
        if eid is not None:
            us = gs.influence[eid][Side.US]
            ussr = gs.influence[eid][Side.USSR]
            if controls_country(gs, eid, Side.US):
                control[code] = "US"
            elif controls_country(gs, eid, Side.USSR):
                control[code] = "USSR"
        else:
            us, ussr = 0, 0
        influence[code] = f"{us:2d}/{ussr:2d}"

    for code, val in influence.items():
        for line_idx, col in CELLS.get(code, []):
            if 1 <= line_idx <= 17:
                ln = lines[line_idx]
                lines[line_idx] = ln[:col] + val + ln[col + 5:]

    # -- 3. Bottom area (lines 19+) --
    hand = gs.us_hand if side == Side.US else gs.ussr_hand
    card_names = [card_by_id(cid).name for cid in hand]
    hand_str = ", ".join(card_names)

    for i in range(19, len(lines)):
        lines[i] = (lines[i]
            .replace("$(SIDE)", side_name)
            .replace("$(HAND)", hand_str)
            .replace("$(MOVE)", last_move)
            .replace("$(THINK)", "")
            .replace("$(INPUT)", ""))

    # -- 4. Colorize --
    colored = []
    for idx, line in enumerate(lines):
        if idx == 0:
            colored.append(f"{BOLD}{HDR_CLR}{line}{RESET}")
        elif 1 <= idx <= 17:
            colored.append(_colorize_map_line(idx, line, control))
        elif idx == 18:
            colored.append(f"{DIM_CLR}{line}{RESET}")
        elif idx == 19:
            sc = US_CLR if side_name == "US" else USSR_CLR
            colon = line.find(":")
            if colon >= 0:
                colored.append(f"{BOLD}{sc}{line[:colon + 1]}{RESET}{HDR_CLR}{line[colon + 1:]}{RESET}")
            else:
                colored.append(f"{HDR_CLR}{line}{RESET}")
        elif idx == 20:
            colored.append(f"{MOVE_CLR}{line}{RESET}")
        elif idx == 22:
            sc = US_CLR if side_name == "US" else USSR_CLR
            colored.append(f"{BOLD}{sc}{line}{RESET}")
        else:
            colored.append(line)

    return CLEAR + "\n".join(colored)
