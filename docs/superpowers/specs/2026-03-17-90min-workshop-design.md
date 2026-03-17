# 90-Minute Programming & Games Workshop

**Date:** 2026-03-17
**Location:** `projects/teach/90min_programming_games/`
**Audience:** 16-year-olds, little or no coding experience
**Goals (priority order):** "I made a game!" → "I understand how code works!" → "I can keep going on my own!"

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
- Each card: retro-bordered box with title, tiny live p5 canvas preview, `[COPY]` button
- Clicking a card expands it to show full source code
- Categories as section headers (e.g., `> MOVEMENT`, `> PHYSICS`)
- Regular snippets: `[COPY]` appends code to the editor
- Game templates: `[COPY]` shows confirm prompt `> TEMPLATE WILL REPLACE YOUR CODE. CONTINUE? [Y] [N]`, pushes current code to undo stack first, then replaces

### Center Panel: Editor + Console

**Editor (top):**
- CodeMirror 6 with terminal-themed skin (green on black, blinking cursor)
- Starts with minimal starter template (see below)
- Auto-runs on edit with 1-second debounce

**Buttons (middle row):**
- `[▶ RUN]` — manual re-run (resets sketch state)
- `[↺ RESET]` — restores starter template (with confirm prompt)
- `[◄ UNDO]` / `[► REDO]` — global snapshot undo/redo

**Console (bottom):**
- Terminal-style output log
- `console.log()` output in green, errors in amber/red
- Prefixed with `>` like a terminal prompt
- Error format: `> ERROR [ln 12, col 5]: x is not defined` — where `ln 12, col 5` is a clickable link that jumps editor cursor to that position and briefly highlights the line
- Scrollable, with `[CLEAR]` button

### Right Panel: Game Canvas

- p5.js sketch output, 400×400
- CRT scanline overlay
- Framed like an old monitor bezel

## Starter Template

```javascript
// JOUW GAME / YOUR GAME
let x = 200;
let y = 200;

function setup() {
  createCanvas(400, 400);
}

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
- Ctrl+Z / Ctrl+Y mapped to this snapshot history (separate from CodeMirror's internal undo)
- Game template replacement pushes current code to stack before replacing

## Auto-Generated UI Controls (`_ui` suffix)

Any top-level `let` or `const` variable whose name ends in `_ui` gets an auto-generated control in a tweaks panel (between editor and canvas, or collapsible).

| Declaration | Detected type | Control |
|---|---|---|
| `let speed_ui = 5;` | Number | Slider |
| `let color_ui = '#00ff41';` | Color hex string | Color picker |
| `let color_ui = [0, 255, 65];` | RGB array | Color picker |
| `let gravity_ui = true;` | Boolean | Toggle switch |
| `let name_ui = "PLAYER 1";` | String | Text input |
| `let sprite_ui = "img:";` | Image (prefix `img:`) | Image file picker |
| `let sound_ui = "snd:";` | Audio (prefix `snd:`) | Audio file picker |

**Behavior:**
- Parsed on each run via regex scan of top-level declarations
- Changing a control immediately updates the variable in the running sketch (live, no re-run)
- Slider range configurable via comment: `let speed_ui = 5; // min:0 max:20 step:0.5`
- Default slider range: 0 to 2× initial value
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

## Gallery Snippets (~25 total)

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
21. GPU shader (WebGL — color-cycling or distortion effect)

### `> INPUT`
22. Webcam feed as background or player avatar (`createCapture`)

### `> GAME TEMPLATES` (replace editor contents)
23. Flappy Bird (pipe gaps, gravity, tap to flap)
24. Mario-style platformer (platforms, run, jump)
25. Micromachines (top-down car, rotation steering, track)
26. Space Invaders (grid of enemies, shoot upward, march down)

### `> GAME LOGIC`
27. Score counter
28. Lives / health bar
29. Game over screen
30. Timer countdown

Each snippet is self-contained: works when pasted into the starter template. Variables named clearly. Dutch-first concept comments. Uses `_ui` suffix where appropriate so participants immediately get sliders/pickers.

## Technical Stack

- **Single HTML file** — everything inlined or CDN-loaded
- **p5.js** — CDN
- **CodeMirror 6** — CDN (bundled ESM)
- **CSS** — inlined (CRT theme, scanlines, glow effects)
- **Gallery data** — embedded JSON structure (title NL/EN, description NL/EN, code)
- **Gallery previews** — each runs its own p5 instance (instance mode) to avoid conflicts
- **Error capture** — user code wrapped in try/catch, `console.log`/`console.error` overridden to pipe to in-page console. Syntax errors caught via parse check before execution.
- **No server required** — works from `file://`, USB stick, GitHub Pages, any static host
