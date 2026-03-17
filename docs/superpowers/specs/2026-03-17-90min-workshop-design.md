# 90-Minute Programming & Games Workshop

**Date:** 2026-03-17
**Location:** `projects/teach/90min_programming_games/`
**Audience:** 16-year-olds, little or no coding experience
**Goals (priority order):** "I made a game!" → "I understand how code works!" → "I can keep going on my own!"
**Requirements:** Desktop browser (Chrome/Edge/Firefox 2024+), reliable internet

## Overview

A single self-contained HTML page that serves as the entire workshop environment. Participants open a URL (or local file), browse a gallery of working code snippets, copy them into their editor, combine and modify them, and build their own game. No installation, no accounts, no guided progression — just a gallery to raid and a canvas to build on.

## Visual Theme

80's terminal / CRT aesthetic:

- Black background, phosphor green (`#00ff41`) primary, amber (`#ffb000`) accents
- Monospace font throughout (VT323 for headers, IBM Plex Mono or similar for code)
- CRT scanline overlay on the game canvas
- Subtle glow effects via CSS (text-shadow, box-shadow)
- Retro box-drawing character borders (`╔══╗`)
- All UI elements (buttons, sliders, toggles) styled to match the theme

## Page Layout

Three-panel layout, all visible simultaneously, no tabs or navigation:

### Left Panel: Gallery

- Scrollable grid of snippet cards
- Each card: retro-bordered box with title, tiny live p5 canvas preview (lazy-loaded on scroll, ~80×80, paused when off-screen), `[COPY]` button
- Clicking a card expands it to show full source code
- Categories as section headers (e.g., `> MOVEMENT`, `> PHYSICS`)
- Regular snippets: `[COPY]` inserts code into the correct sections of the editor (see Snippet Composability)
- Game templates: `[COPY]` shows confirm prompt `> TEMPLATE WILL REPLACE YOUR CODE. CONTINUE? [Y] [N]`, pushes current code to undo stack first, then replaces

### Center Panel: Editor + Console

**Editor (top):**
- CodeMirror 5 with terminal-themed skin (green on black, blinking cursor)
- Starts with minimal starter template (see below)
- Auto-runs on edit with 1-second debounce

**Buttons (middle row):**
- `[▶ RUN]` — manual re-run (resets sketch state)
- `[↺ RESET]` — restores starter template (with confirm prompt)
- `[◄ UNDO]` / `[► REDO]` — global snapshot undo/redo (see Global Undo/Redo)
- `[⬇ DOWNLOAD]` — exports current code as a standalone HTML file with p5.js CDN link

**Console (bottom):**
- Terminal-style output log
- `console.log()` output in green, errors in amber/red
- Prefixed with `>` like a terminal prompt
- Error format: `> ERROR [ln 12, col 5]: x is not defined` — where `ln 12, col 5` is a clickable link that jumps editor cursor to that position and briefly highlights the line
- Scrollable, with `[CLEAR]` button

### Right Panel: Game Canvas + Tweaks

**Canvas (top):**
- p5.js sketch output, 400×400
- CRT scanline overlay
- Framed like an old monitor bezel

**Tweaks panel (below canvas, collapsible):**
- Auto-generated UI controls for `_ui` variables (see Auto-Generated UI Controls)

## Snippet Composability

Snippets are designed to be combined without conflicts. Each snippet has two sections and uses a name prefix on all its variables and functions.

### Starter template structure

```javascript
// JOUW GAME / YOUR GAME

// === LOGIC ===
let x = 200;
let y = 200;

// === SETUP ===
function setup() {
  createCanvas(400, 400);
}

// === DRAW ===
function draw() {
  background(0);
  fill(0, 255, 65);
  circle(x, y, 30);
}
```

### Snippet structure

Each snippet contains two clearly marked sections:

- **Logic section** — variable declarations, helper functions. All identifiers prefixed with the snippet name (e.g., `gravity_velocityY`, `gravity_apply()`).
- **Draw section** — code to run inside `draw()`. Uses the same prefixed identifiers.

Example — "gravity" snippet:

```javascript
// --- LOGIC: gravity ---
// Zwaartekracht: snelheid (velocity) en versnelling (acceleration)
let gravity_velocityY = 0;
let gravity_acceleration_ui = 0.5; // min:0 max:2 step:0.1
let gravity_ground = 380;

function gravity_apply() {
  gravity_velocityY += gravity_acceleration_ui;
  y += gravity_velocityY;
  if (y >= gravity_ground) {
    y = gravity_ground;
    gravity_velocityY = 0;
  }
}

// --- DRAW: gravity ---
gravity_apply();
```

### Insertion behavior

When `[COPY]` is clicked on a regular snippet:

1. **Logic section** → inserted before the `// === SETUP ===` marker
2. **Draw section** → inserted before the closing `}` of `draw()`

**Failsafe:** If the marker comments are missing (participant deleted them):
- Logic section → inserted at the top of the file
- Draw section → inserted before the last `}` in the file (assumed to be `draw()`'s closing brace)

### Namespace convention

All snippet variables and functions are prefixed with `snippetname_` to avoid collisions. E.g.:
- `gravity_velocityY`, `gravity_apply()`
- `bounce_speed`, `bounce_check()`
- `score_points`, `score_display()`

## Starter Template

```javascript
// JOUW GAME / YOUR GAME

// === LOGIC ===
let x = 200;
let y = 200;

// === SETUP ===
function setup() {
  createCanvas(400, 400);
}

// === DRAW ===
function draw() {
  background(0);
  fill(0, 255, 65);
  circle(x, y, 30);
}
```

A green dot on black. Does nothing — participants bring it to life with gallery snippets.

## Global Undo/Redo

- Saves a full-code snapshot to the history stack every time the code auto-runs (after debounced edit or paste)
- Pasting a large template is one undo step (not 200 character-level undos)
- CodeMirror keeps Ctrl+Z / Ctrl+Y for character-level undo (normal editing)
- `[◄ UNDO]` / `[► REDO]` buttons operate on the snapshot stack (full-code level)
- Game template replacement pushes current code to stack before replacing

## Persistence

- **Auto-save:** editor contents saved to `localStorage` on every debounced edit. Restored on page load.
- **Download:** `[⬇ DOWNLOAD]` exports current code as a standalone `.html` file with p5.js CDN link, so participants take their game home.

## Infinite Loop Protection

User code is instrumented before execution: a counter is injected into `while` and `for` loops. If any loop exceeds 100,000 iterations, it throws an error displayed in the console:

```
> ERROR: Oneindige lus gestopt / Infinite loop stopped
```

This prevents a frozen browser tab.

**Note on code execution:** User code is evaluated dynamically (this is the core purpose of the tool — an in-browser code editor). All code runs client-side only, in the participant's own browser, with no server communication. This is the same execution model used by p5.js Web Editor, CodePen, and JSFiddle.

## Auto-Generated UI Controls (`_ui` suffix)

Any top-level `let` or `const` variable whose name ends in `_ui` gets an auto-generated control in the tweaks panel (below the game canvas, collapsible).

| Declaration | Detected type | Control |
|---|---|---|
| `let speed_ui = 5;` | Number | Slider |
| `let color_ui = '#00ff41';` | Color hex string | Color picker |
| `let color_ui = [0, 255, 65];` | RGB array | Color picker |
| `let gravity_ui = true;` | Boolean | Toggle switch |
| `let name_ui = "PLAYER 1";` | String | Text input |
| `let sprite_ui = "img:";` | Image (prefix `img:`) | Image file picker (loaded via `URL.createObjectURL()`) |
| `let sound_ui = "snd:";` | Audio (prefix `snd:`) | Audio file picker (loaded via `URL.createObjectURL()`) |

**Behavior:**
- Parsed on each run via regex scan of top-level declarations (lines starting with `let`/`const` at zero indentation)
- Changing a control immediately updates the variable in the running sketch (live, no re-run)
- When code auto-runs, current `_ui` control values are preserved and re-injected after the sketch restarts
- Slider range configurable via comment: `let speed_ui = 5; // min:0 max:20 step:0.5`
- Default slider range: 0 to 2× initial value (minimum range [0, 10] if initial value is 0; absolute value used if negative)
- Labels derived from comment: `let speed_ui = 5; // Snelheid (speed)` → label shows "Snelheid (speed)"
- Controls styled in CRT theme

## Bilingual (Dutch / English)

- Language toggle in top bar: `[NL]` / `[EN]`
- All UI text switches: button labels, category headers, snippet titles/descriptions, confirm prompts, error prefixes
- Code stays in English (variable names, p5.js API)
- Comments introduce concepts in Dutch first, English technical term in parentheses:

```javascript
// Zwaartekracht toepassen door snelheid (velocity) te verhogen
y += velocityY;
velocityY += 0.5;
```

- `_ui` variable labels use the Dutch comment when available

## Gallery Snippets (~32 total)

### `> MOVEMENT`
1. Arrow key movement (4-direction)
2. WASD movement
3. Mouse follow (smooth lerp)
4. Mouse click to move

### `> PHYSICS`
5. Gravity + ground
6. Jumping (with ground check)
7. Bouncing off walls
8. Friction / deceleration

### `> OBJECTS`
9. Spawn objects on timer
10. Spawn on click
11. Random position spawning
12. Object pool (array of things that move)

### `> COLLISION`
13. Circle vs circle
14. Point vs rectangle
15. Collect / destroy on hit

### `> VISUALS`
16. Sprite animation (spritesheet)
17. Particle trail
18. Aftertrails (fading ghost copies behind moving object)
19. Screen shake
20. Flashing / blinking
21. GPU shader — post-processing filter effect (color-cycling or distortion, applied via p5 `filter(SHADER)` in 2D mode so it doesn't break other snippets)
22. GPU particle effect — thousands of particles rendered via WebGL shader (sparks, fire, snow — shows what GPU parallelism can do vs. CPU)
23. GPU rectangle flood — hundreds of rotating/scaling rectangles rendered via WebGL instancing (visually impressive, demonstrates GPU batch rendering)

### `> INPUT`
24. Webcam feed as background or player avatar (`createCapture`, with graceful fallback if permission denied)

### `> GAME TEMPLATES` (replace editor contents)
25. Flappy Bird (pipe gaps, gravity, tap to flap)
26. Mario-style platformer (platforms, run, jump)
27. Micromachines (top-down car, rotation steering, track)
28. Space Invaders (grid of enemies, shoot upward, march down)

### `> GAME LOGIC`
29. Score counter
30. Lives / health bar
31. Game over screen
32. Timer countdown

Each snippet follows the composability convention: two sections (logic + draw), all identifiers prefixed with the snippet name, Dutch-first concept comments, `_ui` suffix on tweakable variables.

## Technical Stack

- **Single HTML file** — everything inlined or CDN-loaded
- **p5.js** — CDN
- **CodeMirror 5** — CDN (single file, no build step needed)
- **CSS** — inlined (CRT theme, scanlines, glow effects)
- **Gallery data** — embedded JSON structure (title NL/EN, description NL/EN, logic code, draw code)
- **Gallery previews** — each runs its own p5 instance (instance mode), lazy-loaded on scroll into view, paused when off-screen, ~80×80 canvas
- **Error capture** — user code evaluated dynamically (client-side only, same model as p5.js Web Editor/CodePen), `console.log`/`console.error` overridden to pipe to in-page console. Syntax errors caught via parse check before execution.
- **Infinite loop protection** — loop counter injection before execution
- **Persistence** — `localStorage` auto-save, standalone HTML download export
- **No server required** — works from `file://`, USB stick, GitHub Pages, any static host
