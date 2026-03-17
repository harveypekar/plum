# 90-Minute Workshop Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-page workshop tool where 16-year-olds combine code snippets to create games, with an 80's CRT terminal aesthetic.

**Architecture:** Single HTML file with inlined CSS and JS. CDN loads for p5.js and CodeMirror 5. Three-panel layout: gallery (left), editor+console (center), canvas+tweaks (right). Snippet data embedded as JS objects.

**Tech Stack:** HTML5, CSS3, p5.js (CDN), CodeMirror 5 (CDN), vanilla JS

**Spec:** `docs/superpowers/specs/2026-03-17-90min-workshop-design.md`

---

## Chunk 1: Core Shell

### Task 1: HTML skeleton + CRT theme

**Files:**
- Create: `projects/teach/90min_programming_games/index.html`

Build the full HTML structure with all three panels, CRT styling, and retro UI. No functionality yet — just the visual shell.

- [ ] **Step 1: Create HTML file with structure**

Three-panel flexbox layout:
- Left: `#gallery` — scrollable, category headers
- Center: `#editor-panel` — editor container, button row (RUN, RESET, UNDO, REDO, DOWNLOAD), console container
- Right: `#canvas-panel` — canvas container with CRT bezel, collapsible tweaks panel
- Top bar: title + language toggle `[NL]` / `[EN]`

CSS inlined in `<style>`:
- Black background, `#00ff41` green, `#ffb000` amber
- Google Fonts: VT323 for headers, monospace for code
- CRT scanline overlay (repeating-linear-gradient on canvas)
- Glow effects (text-shadow, box-shadow)
- Box-drawing character borders via CSS `border-image` or pseudo-elements
- Retro-styled buttons (bordered, monospace, hover glow)
- Responsive: panels should work on 1366×768 minimum

- [ ] **Step 2: Verify in browser**

Open `index.html` in browser. Confirm:
- Three panels visible
- CRT aesthetic looks right
- Buttons present (non-functional)
- Scanline effect on canvas area

- [ ] **Step 3: Commit**

```bash
git add projects/teach/90min_programming_games/index.html
git commit -m "feat(workshop): add HTML skeleton with CRT terminal theme"
```

### Task 2: CodeMirror 5 editor

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

Wire up CodeMirror 5 from CDN with the terminal theme and starter template.

- [ ] **Step 1: Add CodeMirror CDN links and initialize**

Add to `<head>`:
- CodeMirror 5 CSS + JS from cdnjs
- JavaScript mode
- Custom theme overrides (green on black, `#00ff41` cursor)

Add to `<script>`:
- Initialize CodeMirror on `#editor` div
- Load starter template:

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

- [ ] **Step 2: Verify in browser**

Confirm editor loads with green-on-black theme, starter code visible, syntax highlighting works.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add CodeMirror 5 editor with terminal theme"
```

### Task 3: p5.js canvas + sketch execution

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

Wire up p5.js and the sketch execution engine.

- [ ] **Step 1: Add p5.js CDN and execution engine**

Add p5.js CDN to `<head>`.

Execution engine in `<script>`:
- `runSketch(code)` function:
  1. Remove existing p5 instance if any
  2. Instrument loops (inject counter into `while`/`for` bodies, throw after 100k iterations)
  3. Create new p5 instance in instance mode, attached to `#canvas-container`
  4. Override `console.log` and `console.error` to pipe to the console panel
  5. Catch syntax errors via try/catch around evaluation, display in console
- Auto-run: debounce CodeMirror `change` event by 1 second, call `runSketch()`
- `[▶ RUN]` button: call `runSketch()` immediately
- `[↺ RESET]` button: confirm prompt, restore starter template, run

- [ ] **Step 2: Verify in browser**

Confirm: green circle appears on black canvas. Edit a number in the editor — circle updates after 1 second. Click RUN — immediate update.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add p5.js sketch execution with auto-run"
```

### Task 4: Console panel

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

- [ ] **Step 1: Implement console output**

Console panel in `#console`:
- `logToConsole(msg, type)` function — appends `<div>` with `> ` prefix
  - type `'log'`: green text
  - type `'error'`: amber/red text
  - type `'error'` with line/col: make `ln N, col M` a clickable `<a>` that calls `editor.setCursor(line-1, col-1)` and adds a brief CSS highlight on that line
- Override `console.log` / `console.error` in sketch execution scope
- Parse error stack traces to extract line/column numbers (offset by any wrapper lines)
- `[CLEAR]` button: empty the console div
- Auto-scroll to bottom on new messages

- [ ] **Step 2: Verify in browser**

Add `console.log("hello")` to draw — see green output. Add a syntax error — see amber error with clickable line number.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add console panel with clickable error locations"
```

---

## Chunk 2: Features

### Task 5: Snippet insertion engine

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

- [ ] **Step 1: Implement insertSnippet()**

```javascript
function insertSnippet(logicCode, drawCode) {
  let code = editor.getValue();

  // Find markers
  const setupMarker = '// === SETUP ===';
  const setupIdx = code.indexOf(setupMarker);

  // Insert logic section
  if (setupIdx !== -1) {
    code = code.slice(0, setupIdx) + logicCode + '\n\n' + code.slice(setupIdx);
  } else {
    code = logicCode + '\n\n' + code; // failsafe: top of file
  }

  // Find last } for draw code insertion
  // Re-find after logic insertion shifted indices
  const lastBrace = code.lastIndexOf('}');
  if (lastBrace !== -1) {
    code = code.slice(0, lastBrace) + '  ' + drawCode + '\n' + code.slice(lastBrace);
  }

  editor.setValue(code);
}
```

Also implement `replaceWithTemplate(code)`:
- Push current code to undo stack
- Set editor value to template code

- [ ] **Step 2: Test with a hardcoded snippet**

Temporarily add a test button that calls `insertSnippet()` with gravity snippet code. Verify it inserts in the right places.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add snippet insertion engine with marker failsafe"
```

### Task 6: Global undo/redo

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

- [ ] **Step 1: Implement snapshot undo stack**

```javascript
const undoStack = [];
const redoStack = [];
let lastSnapshot = '';

function pushSnapshot() {
  const current = editor.getValue();
  if (current !== lastSnapshot) {
    undoStack.push(lastSnapshot);
    redoStack.length = 0;
    lastSnapshot = current;
  }
}

function undo() {
  if (undoStack.length === 0) return;
  redoStack.push(editor.getValue());
  const prev = undoStack.pop();
  lastSnapshot = prev;
  editor.setValue(prev);
}

function redo() {
  if (redoStack.length === 0) return;
  undoStack.push(editor.getValue());
  const next = redoStack.pop();
  lastSnapshot = next;
  editor.setValue(next);
}
```

- Call `pushSnapshot()` before each auto-run
- Wire `[◄ UNDO]` and `[► REDO]` buttons

- [ ] **Step 2: Verify**

Make edits, click UNDO — previous code restored. Click REDO — re-applied. Paste a template — one undo step.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add global snapshot undo/redo"
```

### Task 7: Persistence (localStorage + download)

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

- [ ] **Step 1: Implement auto-save and download**

Auto-save:
- On each debounced edit, `localStorage.setItem('workshop_code', editor.getValue())`
- On page load, check `localStorage.getItem('workshop_code')` — if present, use it instead of starter template

Download:
- `[⬇ DOWNLOAD]` generates a standalone HTML string with p5.js CDN link and the user's code
- Triggers download via `Blob` + `URL.createObjectURL` + click on temporary `<a>`

- [ ] **Step 2: Verify**

Edit code, refresh page — code persists. Click DOWNLOAD — get a .html file that runs the game standalone.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add localStorage persistence and HTML download"
```

### Task 8: `_ui` variable detection + tweaks panel

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

- [ ] **Step 1: Implement _ui parser and control generation**

Parser:
- Regex scan each line for `^(let|const)\s+(\w+_ui)\s*=\s*(.+);`
- Extract variable name, initial value, and any comment (for label and range config)
- Detect type from value: number, hex string, array, boolean, string, `img:` prefix, `snd:` prefix

Control generation in `#tweaks-panel`:
- Number → `<input type="range">` with CRT styling
- Color hex → `<input type="color">`
- RGB array → `<input type="color">` (convert to/from hex)
- Boolean → retro toggle switch
- String → `<input type="text">`
- Image/audio → `<input type="file">` with appropriate accept attribute

Live update:
- Each control's `input` event updates a global `_uiValues` map
- Before sketch eval, inject `_uiValues` overrides for any `_ui` variables
- On auto-run, read current `_uiValues` and preserve them

- [ ] **Step 2: Verify**

Add `let speed_ui = 5; // Snelheid (speed) min:0 max:20` to the editor. Confirm slider appears with label "Snelheid (speed)", adjusting it changes behavior live.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add _ui variable detection and tweaks panel"
```

### Task 9: Bilingual support

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

- [ ] **Step 1: Implement i18n system**

Create a `STRINGS` object:
```javascript
const STRINGS = {
  nl: {
    run: '▶ START',
    reset: '↺ RESET',
    undo: '◄ TERUG',
    redo: '► OPNIEUW',
    download: '⬇ DOWNLOAD',
    clear: 'WISSEN',
    confirmReset: 'TEMPLATE VERVANGT JE CODE. DOORGAAN?',
    confirmTemplate: 'TEMPLATE VERVANGT JE CODE. DOORGAAN?',
    infiniteLoop: 'Oneindige lus gestopt',
    // category headers
    movement: 'BEWEGING',
    physics: 'NATUURKUNDE',
    objects: 'OBJECTEN',
    collision: 'BOTSING',
    visuals: 'VISUEEL',
    input: 'INVOER',
    templates: 'GAME TEMPLATES',
    gameLogic: 'SPELLOGICA',
  },
  en: {
    run: '▶ RUN',
    reset: '↺ RESET',
    undo: '◄ UNDO',
    redo: '► REDO',
    download: '⬇ DOWNLOAD',
    clear: 'CLEAR',
    confirmReset: 'THIS WILL REPLACE YOUR CODE. CONTINUE?',
    confirmTemplate: 'TEMPLATE WILL REPLACE YOUR CODE. CONTINUE?',
    infiniteLoop: 'Infinite loop stopped',
    movement: 'MOVEMENT',
    physics: 'PHYSICS',
    objects: 'OBJECTS',
    collision: 'COLLISION',
    visuals: 'VISUALS',
    input: 'INPUT',
    templates: 'GAME TEMPLATES',
    gameLogic: 'GAME LOGIC',
  }
};
```

- `setLang(lang)` function: updates all UI text, stores preference in localStorage
- `[NL]` / `[EN]` toggle in top bar
- Snippet titles/descriptions stored as `{nl: '...', en: '...'}`
- Default to NL

- [ ] **Step 2: Verify**

Toggle between NL/EN. Confirm all buttons, headers, and snippet descriptions switch language.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add bilingual NL/EN support"
```

### Task 10: Gallery UI

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

- [ ] **Step 1: Implement gallery rendering**

Snippet data structure:
```javascript
const SNIPPETS = [
  {
    id: 'arrows',
    category: 'movement',
    title: { nl: 'Pijltjestoetsen bewegen', en: 'Arrow key movement' },
    desc: { nl: 'Beweeg in 4 richtingen met pijltjestoetsen', en: 'Move in 4 directions with arrow keys' },
    template: false, // true for game templates
    logic: `...`,
    draw: `...`,
    preview: function(p) { ... } // p5 instance-mode sketch for thumbnail
  },
  // ... all 32 snippets
];
```

Gallery rendering:
- Group snippets by category
- Render category headers with `> CATEGORY` styling
- Each card: title, description, tiny canvas (80×80), `[COPY]` button
- Click card → expand/collapse to show source code
- `[COPY]` on regular snippet → call `insertSnippet(logic, draw)`
- `[COPY]` on template → confirm prompt → call `replaceWithTemplate()`
- Lazy-load previews via IntersectionObserver: create p5 instance when card scrolls into view, remove when out

- [ ] **Step 2: Verify**

Confirm gallery renders with categories, cards expand, previews animate, COPY inserts correctly.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(workshop): add gallery UI with lazy-loaded previews"
```

---

## Chunk 3: Snippets — Movement, Physics, Objects, Collision

### Task 11: Movement snippets (1-4)

**Files:**
- Modify: `projects/teach/90min_programming_games/index.html`

Write the 4 movement snippets with logic/draw sections, prefixed variables, Dutch-first comments, and `_ui` variables where appropriate.

- [ ] **Step 1: Arrow key movement**

```javascript
// --- LOGIC: arrows ---
// Beweeg met pijltjestoetsen (arrow keys)
let arrows_speed_ui = 3; // Snelheid (speed) min:1 max:10

function arrows_move() {
  if (keyIsDown(LEFT_ARROW)) x -= arrows_speed_ui;
  if (keyIsDown(RIGHT_ARROW)) x += arrows_speed_ui;
  if (keyIsDown(UP_ARROW)) y -= arrows_speed_ui;
  if (keyIsDown(DOWN_ARROW)) y += arrows_speed_ui;
}

// --- DRAW: arrows ---
arrows_move();
```

- [ ] **Step 2: WASD movement**

Similar to arrows but uses key codes for W/A/S/D.

- [ ] **Step 3: Mouse follow (smooth lerp)**

```javascript
// --- LOGIC: mousefollow ---
// Volg de muis met vloeiende beweging (lerp = lineaire interpolatie)
let mousefollow_smoothing_ui = 0.05; // Vloeiendheid (smoothing) min:0.01 max:0.3 step:0.01

function mousefollow_update() {
  x = lerp(x, mouseX, mousefollow_smoothing_ui);
  y = lerp(y, mouseY, mousefollow_smoothing_ui);
}

// --- DRAW: mousefollow ---
mousefollow_update();
```

- [ ] **Step 4: Mouse click to move**

Click sets a target, object moves toward it each frame.

- [ ] **Step 5: Add preview functions for each**

Small p5 instance-mode sketches showing the behavior.

- [ ] **Step 6: Verify all 4 in browser**

Copy each snippet — confirm it works with the starter template.

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(workshop): add movement snippets (arrows, WASD, mouse follow, click-to-move)"
```

### Task 12: Physics snippets (5-8)

- [ ] **Step 1: Gravity + ground**

Applies gravity acceleration to velocityY, clamps at ground level.

- [ ] **Step 2: Jumping (with ground check)**

Space bar to jump, only when on ground. Uses gravity snippet's ground concept.

- [ ] **Step 3: Bouncing off walls**

Object bounces off all 4 canvas edges, reversing velocity on contact.

- [ ] **Step 4: Friction / deceleration**

Multiplies velocity by a friction factor each frame, with `_ui` slider.

- [ ] **Step 5: Add previews, verify, commit**

```bash
git commit -m "feat(workshop): add physics snippets (gravity, jump, bounce, friction)"
```

### Task 13: Objects snippets (9-12)

- [ ] **Step 1: Spawn objects on timer**

Creates a new object every N frames, stores in array, draws all.

- [ ] **Step 2: Spawn on click**

mousePressed creates object at click position.

- [ ] **Step 3: Random position spawning**

Objects appear at random positions periodically.

- [ ] **Step 4: Object pool (array of things that move)**

Array of objects with position and velocity, all updated in draw.

- [ ] **Step 5: Add previews, verify, commit**

```bash
git commit -m "feat(workshop): add object snippets (timer spawn, click spawn, random spawn, pool)"
```

### Task 14: Collision snippets (13-15)

- [ ] **Step 1: Circle vs circle**

Distance check between two circles, highlight on collision.

- [ ] **Step 2: Point vs rectangle**

Check if point (e.g. mouse or object) is inside a rectangle.

- [ ] **Step 3: Collect / destroy on hit**

Object array filtered on collision — collected objects disappear, score increments.

- [ ] **Step 4: Add previews, verify, commit**

```bash
git commit -m "feat(workshop): add collision snippets (circle-circle, point-rect, collect)"
```

---

## Chunk 4: Snippets — Visuals, Input, Game Logic

### Task 15: Visual snippets (16-23)

- [ ] **Step 1: Sprite animation (spritesheet)**

Cycles through frames of a spritesheet (can use a simple generated spritesheet or placeholder).

- [ ] **Step 2: Particle trail**

Spawns small particles at object position that fade out over time.

- [ ] **Step 3: Aftertrails (fading ghost copies)**

Stores last N positions, draws circles with decreasing alpha.

- [ ] **Step 4: Screen shake**

Applies random translate offset on collision/event, decays over frames.

- [ ] **Step 5: Flashing / blinking**

Object toggles visibility using frame count modulo.

- [ ] **Step 6: GPU shader — post-processing filter**

p5.js `createFilterShader()` with a simple GLSL fragment shader (e.g. color cycling or CRT distortion). Applied via `filter(shader)` after all drawing.

- [ ] **Step 7: GPU particle effect**

WebGL shader that renders thousands of particles. Uses a secondary WEBGL canvas overlaid on the main one, so the main 2D canvas is unaffected.

- [ ] **Step 8: GPU rectangle flood**

Similar approach — secondary WEBGL canvas with hundreds of rotating/scaling rectangles rendered via shader/instancing.

- [ ] **Step 9: Add previews, verify, commit**

```bash
git commit -m "feat(workshop): add visual snippets (sprite, particles, aftertrails, shake, flash, GPU effects)"
```

### Task 16: Input snippet (24)

- [ ] **Step 1: Webcam feed**

```javascript
// --- LOGIC: webcam ---
// Webcam beeld als achtergrond (webcam feed as background)
let webcam_capture;

function webcam_setup() {
  webcam_capture = createCapture(VIDEO);
  webcam_capture.size(400, 400);
  webcam_capture.hide();
}

// --- DRAW: webcam ---
if (webcam_capture) {
  image(webcam_capture, 0, 0, 400, 400);
}
```

Note: This snippet also needs setup code. Add a third section type `setup` that inserts inside `setup()`, or call `webcam_setup()` from draw with a guard (`if (!webcam_capture) webcam_setup()`).

- [ ] **Step 2: Add preview, verify, commit**

```bash
git commit -m "feat(workshop): add webcam input snippet"
```

### Task 17: Game logic snippets (29-32)

- [ ] **Step 1: Score counter**

Displays score in top-left, with `_ui` for text size and color.

- [ ] **Step 2: Lives / health bar**

Draws hearts or a bar, decrements on collision.

- [ ] **Step 3: Game over screen**

When lives reach 0, shows "GAME OVER" text with restart prompt.

- [ ] **Step 4: Timer countdown**

Counts down from N seconds, triggers game over when done.

- [ ] **Step 5: Add previews, verify, commit**

```bash
git commit -m "feat(workshop): add game logic snippets (score, lives, game over, timer)"
```

---

## Chunk 5: Game Templates

### Task 18: Flappy Bird template (25)

- [ ] **Step 1: Write complete Flappy Bird game**

Full standalone game: bird with gravity, tap/space to flap, scrolling pipe gaps, collision detection, score counter. Uses `_ui` variables for gravity, flap strength, pipe gap size, pipe speed. Dutch-first comments on every concept.

- [ ] **Step 2: Add to SNIPPETS as template, verify, commit**

```bash
git commit -m "feat(workshop): add Flappy Bird game template"
```

### Task 19: Mario-style platformer template (26)

- [ ] **Step 1: Write complete platformer**

Player with run + jump, several platforms, gravity, left/right scrolling or static screen. `_ui` for jump height, run speed, gravity. Dutch-first comments.

- [ ] **Step 2: Add to SNIPPETS as template, verify, commit**

```bash
git commit -m "feat(workshop): add Mario platformer game template"
```

### Task 20: Micromachines template (27)

- [ ] **Step 1: Write complete top-down racer**

Car with rotation steering (left/right rotate, up accelerates), friction, simple track drawn with shapes. `_ui` for car speed, turn rate, friction.

- [ ] **Step 2: Add to SNIPPETS as template, verify, commit**

```bash
git commit -m "feat(workshop): add Micromachines racer game template"
```

### Task 21: Space Invaders template (28)

- [ ] **Step 1: Write complete Space Invaders**

Grid of enemies marching side-to-side and down, player at bottom moves left/right and shoots upward, collision removes enemies, score tracking. `_ui` for enemy speed, bullet speed, player speed.

- [ ] **Step 2: Add to SNIPPETS as template, verify, commit**

```bash
git commit -m "feat(workshop): add Space Invaders game template"
```

---

## Chunk 6: Polish

### Task 22: Final integration and testing

- [ ] **Step 1: Test full workflow end-to-end**

1. Open page — starter template loads, green dot visible
2. Copy 3+ snippets — they compose correctly
3. Undo/redo works across snippet insertions
4. `_ui` sliders appear and work live
5. Toggle NL/EN — all text switches
6. Load a game template — replaces code, undo works
7. Add `console.log()` — appears in console
8. Introduce an error — clickable line number works
9. Write a `while(true)` — loop protection kicks in
10. Refresh page — code persists from localStorage
11. Click DOWNLOAD — standalone HTML file works

- [ ] **Step 2: Fix any issues found**

- [ ] **Step 3: Final commit**

```bash
git commit -m "feat(workshop): polish and integration fixes"
```
