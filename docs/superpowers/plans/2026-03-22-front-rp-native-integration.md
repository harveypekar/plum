# Front: Native RP Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the iframe-based rp tab with native UI controls using the front project's dockable panel system and an amber terminal theme, achieving full feature parity with the existing rp SPA.

**Architecture:** Extend the existing dock system with per-tab layouts (master=green, rp=amber). The rp tab uses a west browser panel for navigation, a center zone for tabbed detail views (chat/card/scenario), and south panels for logs, scene state, and debug info. A lightweight event bus on `rpState` coordinates cross-panel communication.

**Tech Stack:** Vanilla JS (no build tools), CSS custom properties for theming, fetch + ReadableStream for streaming chat.

**Spec:** `docs/superpowers/specs/2026-03-22-front-rp-native-integration-design.md`

**Source of truth for feature parity:** `projects/rp/static/app.js` (~1635 lines)

**Important: `el()` helper API difference.** The front's `el(tag, attrs, children)` uses `class` for className, and does not support `onClick`, `textContent`, or `style` as object in attrs. When porting code from the rp app.js (which uses `className`, `textContent`, `onClick`), convert: `className` → `class`, attach event listeners separately via `addEventListener`, set `textContent` via the children parameter or after creation.

---

## File Structure

All changes are in two files:

| File | Action | Responsibility |
|------|--------|----------------|
| `projects/front/app.js` | Modify | All JS — dock system changes, rp state/event bus, all rp panels, init wiring |
| `projects/front/styles.css` | Modify | Amber theme variables, rp-specific styles |

No new files. No backend changes. `index.html` stays as-is (already has master/rp tabs and dock-layout div).

---

## Task 1: Per-Tab Dock Layouts & Amber Theme

**Files:**
- Modify: `projects/front/styles.css`
- Modify: `projects/front/app.js`

**What:** Add CSS custom properties for theming (green/amber), per-tab layout support in the dock system, and the RP default layout definition.

- [ ] **Step 1: Add CSS custom properties and amber theme**

In `styles.css`, add CSS custom properties at the top and an amber theme class. The `:root` gets `--accent: #0f0; --accent-bg: #001a00; --accent-dark: #002200; --accent-dim: #003300;`. A `.theme-amber` class overrides these with `--accent: #ffbf00; --accent-bg: #1a1200; --accent-dark: #221900; --accent-dim: #332600;`. Convert all hardcoded green references (`#0f0`, `#001a00`, `#002200`, `#003300`) to use `var(--accent)` etc.

- [ ] **Step 2: Add RP-specific styles**

Add styles for: `.rp-browser-tabs` (internal tab bar in browser panel), `.rp-browser-list` (scrollable list), `.rp-browser-item` (list items), `.rp-center-tabs` (center tab bar), `.rp-center-tab` (individual tabs with close button), `.rp-chat-container` (flex layout for chat + avatar strip), `.rp-chat-messages` (scrollable message area), `.rp-avatar-strip` (fixed column right of chat), `.rp-msg` (message bubble), `.rp-msg.user` / `.rp-msg.assistant` (alignment), `.rp-input-area` (textarea + buttons), `.rp-form` (card/scenario editor forms), `.rp-modal` (new chat modal overlay), `.dialogue-quote-user` / `.dialogue-quote-assistant` (dialogue highlighting in amber palette), `.streaming-cursor` (blinking amber cursor), `.rp-error` (inline error text).

- [ ] **Step 3: Add per-tab layout constants and RP panel stubs to app.js**

Add constants:

```javascript
const DOCK_STORAGE_KEY_MASTER = 'plum-dock-state-master';
const DOCK_STORAGE_KEY_RP = 'plum-dock-state-rp';

const DEFAULT_LAYOUT_MASTER = {
    north: ['services'],
    south: ['logs-rp'],
    west: ['logs-aiserver'],
    east: ['logs-ollama'],
};

const DEFAULT_LAYOUT_RP = {
    north: ['services'],
    south: ['logs-rp', 'rp-scene-state', 'rp-under-hood'],
    west: ['rp-browser'],
    east: [],
};
```

Register three new panel stubs in `PANELS`:

```javascript
'rp-browser': {
    id: 'rp-browser',
    title: 'RP Browser',
    render() { return el('div', { id: 'rp-browser-root' }, 'Loading...'); },
},
'rp-scene-state': {
    id: 'rp-scene-state',
    title: 'Scene State',
    render() { return el('div', { id: 'rp-scene-state-root' }, 'Loading...'); },
},
'rp-under-hood': {
    id: 'rp-under-hood',
    title: 'Under the Hood',
    render() { return el('div', { id: 'rp-under-hood-root' }, 'Loading...'); },
},
```

- [ ] **Step 4: Modify dock to support per-tab layouts**

Remove the old `DOCK_STORAGE_KEY` constant and `DEFAULT_LAYOUT` — they are replaced by the per-tab constants above. Update `dock.loadState()` to accept a storage key parameter. Update `dock.saveState()` similarly. Add a `dock.switchLayout(tabName)` method that picks the right storage key and default layout based on tab name. Modify `app.switchTab()` to:
1. Apply theme class: `document.body.classList.toggle('theme-amber', tabName === 'rp')`.
2. Call `dock.switchLayout(tabName)` which loads the appropriate layout from localStorage (or default) and re-renders.

Update dock center rendering: the `#dock-layout` div lives inside the `#rp` tab-content, so the dock is only visible when the rp tab is active. Replace the iframe in `dock.render()`'s center creation with `rpCenter.render()`. The master tab uses its own `#master` div (service-grid) and never touches the dock.

- [ ] **Step 5: Verify manually**

Open the front page, switch between master and rp tabs. Master should be green with iframe. RP should be amber with stub panels and an empty center area.

- [ ] **Step 6: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): per-tab dock layouts with amber theme for rp tab"
```

---

## Task 2: RP State, Event Bus & API Helper

**Files:**
- Modify: `projects/front/app.js`

**What:** Add the shared `rpState` object with event bus, an `rpApi` helper for fetch calls, and the `rpModels` helper functions (tags, labels, supports_think).

- [ ] **Step 1: Add rpState and event bus**

```javascript
// ===== RP: State & Event Bus =====

const rpState = {
    cards: [],
    scenarios: [],
    conversations: [],
    models: [],
    openTabs: [],    // {type: 'chat'|'card'|'scenario', id: number}
    activeTab: null,
    _listeners: {},

    on(event, fn) {
        (this._listeners[event] ||= []).push(fn);
    },
    off(event, fn) {
        const arr = this._listeners[event];
        if (arr) this._listeners[event] = arr.filter(f => f !== fn);
    },
    emit(event, data) {
        (this._listeners[event] || []).forEach(fn => fn(data));
    },
};
```

- [ ] **Step 2: Add rpApi helper**

```javascript
async function rpApi(method, path, body) {
    const opts = { method };
    if (body !== undefined) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
    }
    if (res.status === 204) return null;
    return res.json();
}
```

- [ ] **Step 3: Add model helpers**

Port `modelTags`, `modelGetTags`, `modelLabel`, `modelSupportsThink`, `populateModelSelect` from existing rp `app.js` (lines 104-176). Prefix with `rp` namespace: `rpModelTags`, `rpModelGetTags`, `rpModelLabel`, etc.

- [ ] **Step 4: Add data loading functions**

```javascript
async function rpLoadCards() {
    try { rpState.cards = await rpApi('GET', '/rp/cards'); } catch {}
    rpState.emit('cards-changed');
}
async function rpLoadScenarios() {
    try { rpState.scenarios = await rpApi('GET', '/rp/scenarios'); } catch {}
    rpState.emit('scenarios-changed');
}
async function rpLoadConversations() {
    try { rpState.conversations = await rpApi('GET', '/rp/conversations'); } catch {}
    rpState.emit('convs-changed');
}
async function rpLoadModels() {
    try {
        const data = await rpApi('GET', '/health');
        rpState.models = data.available_models || [];
    } catch {}
}
```

- [ ] **Step 5: Commit**

```
git add projects/front/app.js
git commit -m "feat(front): rp state, event bus, API helper, and model utilities"
```

---

## Task 3: RP Browser Panel (West)

**Files:**
- Modify: `projects/front/app.js`
- Modify: `projects/front/styles.css`

**What:** Implement the `rp-browser` panel with three internal tabs (Chats, Cards, Scenarios) and list rendering.

- [ ] **Step 1: Implement rpBrowser render function**

Replace the stub `render()` in `PANELS['rp-browser']` with a full implementation:
- Three tab buttons (Chats | Cards | Scenarios)
- Each tab has a list container and action buttons
- **Chats tab**: list of conversations showing AI card name (resolved by matching `conv.ai_card_id` against `rpState.cards`) and relative timestamp (using `rpTimeAgo()`). Each item has a delete button (confirm, then DELETE `/rp/conversations/{id}`, then `rpLoadConversations()`). "+ New" button opens the new chat modal.
- **Cards tab**: list of cards (small avatar 32x32 + name). Each item has delete button (confirm, DELETE `/rp/cards/{id}`, then `rpLoadCards()`). "+ New Card" and "Generate" buttons. Drop zone for SillyTavern PNG import at top.
- **Scenarios tab**: list of scenarios (name + truncated description). Each item has delete button (confirm, DELETE `/rp/scenarios/{id}`, then `rpLoadScenarios()`). "+ New Scenario" button.
- Clicking any list item calls `rpState.emit('conv-opened', id)`, `rpState.emit('card-opened', id)`, or `rpState.emit('scenario-opened', id)`

- [ ] **Step 2: Wire up event listeners for list refresh**

```javascript
rpState.on('cards-changed', () => { /* re-render cards list */ });
rpState.on('scenarios-changed', () => { /* re-render scenarios list */ });
rpState.on('convs-changed', () => { /* re-render conversations list */ });
```

The browser panel keeps internal references to its list containers and refreshes them when events fire.

- [ ] **Step 3: Add styles for browser panel**

Add CSS for `.rp-browser-tabs`, `.rp-browser-tab`, `.rp-browser-tab.active`, `.rp-browser-list`, `.rp-browser-item`, `.rp-browser-item:hover`, `.rp-browser-actions` (action buttons row), `.rp-card-avatar-small`, `.rp-drop-zone`, `.rp-drop-zone.dragover`.

- [ ] **Step 4: Implement SillyTavern PNG import**

Add drag-and-drop and file picker on the Cards tab drop zone. On drop/select, POST FormData to `/rp/cards/import`, then call `rpLoadCards()`.

- [ ] **Step 5: Verify manually**

Switch to rp tab. Browser panel should show in west slot. Switch between Chats/Cards/Scenarios tabs. Lists should populate from API.

- [ ] **Step 6: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): rp browser panel with chats, cards, scenarios tabs"
```

---

## Task 4: RP Center Tab Manager

**Files:**
- Modify: `projects/front/app.js`

**What:** Implement the center zone as a tabbed detail view manager (like browser tabs — open, close, switch).

- [ ] **Step 1: Implement rpCenter object**

```javascript
// ===== RP: Center (Tab Manager) =====

const rpCenter = {
    container: null,
    tabBar: null,
    contentArea: null,

    render() {
        const root = el('div', { class: 'rp-center' });
        this.container = root;
        this.tabBar = el('div', { class: 'rp-center-tabs' });
        this.contentArea = el('div', { class: 'rp-center-content' });
        root.appendChild(this.tabBar);
        root.appendChild(this.contentArea);
        this.renderTabs();
        this.renderContent();
        return root;
    },

    renderTabs() {
        this.tabBar.textContent = '';
        rpState.openTabs.forEach(t => {
            const label = t.type === 'chat' ? 'Chat #' + t.id
                : t.type === 'card' ? 'Card #' + t.id
                : 'Scenario #' + t.id;
            const tab = el('div', {
                class: 'rp-center-tab' + (rpState.activeTab === t ? ' active' : ''),
            });
            tab.appendChild(el('span', {}, label));
            const closeBtn = el('span', { class: 'rp-center-tab-close' }, 'x');
            closeBtn.addEventListener('click', (e) => { e.stopPropagation(); this.closeTab(t.type, t.id); });
            tab.appendChild(closeBtn);
            tab.addEventListener('click', () => {
                rpState.activeTab = t;
                this.renderTabs();
                this.renderContent();
            });
            this.tabBar.appendChild(tab);
        });
    },

    renderContent() {
        this.contentArea.textContent = '';
        const tab = rpState.activeTab;
        if (!tab) {
            this.contentArea.appendChild(el('div', { class: 'rp-placeholder' }, 'Select an item from the browser'));
            return;
        }
        if (tab.type === 'chat') rpChat.render(this.contentArea, tab.id);
        else if (tab.type === 'card') rpCards.renderEditor(this.contentArea, tab.id);
        else if (tab.type === 'scenario') rpScenarios.renderEditor(this.contentArea, tab.id);
    },

    openTab(type, id) {
        const existing = rpState.openTabs.find(t => t.type === type && t.id === id);
        if (!existing) rpState.openTabs.push({ type, id });
        rpState.activeTab = rpState.openTabs.find(t => t.type === type && t.id === id);
        this.renderTabs();
        this.renderContent();
    },

    closeTab(type, id) {
        rpState.openTabs = rpState.openTabs.filter(t => !(t.type === type && t.id === id));
        if (rpState.activeTab && rpState.activeTab.type === type && rpState.activeTab.id === id) {
            rpState.activeTab = rpState.openTabs.length > 0 ? rpState.openTabs[rpState.openTabs.length - 1] : null;
        }
        rpState.emit('tab-closed', { type, id });
        this.renderTabs();
        this.renderContent();
    },
};
```

- [ ] **Step 2: Wire events to center**

```javascript
rpState.on('conv-opened', id => rpCenter.openTab('chat', id));
rpState.on('card-opened', id => rpCenter.openTab('card', id));
rpState.on('scenario-opened', id => rpCenter.openTab('scenario', id));
```

- [ ] **Step 3: Update dock center rendering**

In `dock.render()`, when `app.currentTab === 'rp'`, instead of creating an iframe, call `rpCenter.render()` and append the result to the center div.

- [ ] **Step 4: Add center tab bar styles**

CSS for `.rp-center`, `.rp-center-tabs` (flex row), `.rp-center-tab` (tab with close X), `.rp-center-tab.active`, `.rp-center-content` (flex: 1, overflow hidden), `.rp-placeholder`.

- [ ] **Step 5: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): rp center tab manager with open/close/switch"
```

---

## Task 5: RP Chat View

**Files:**
- Modify: `projects/front/app.js`
- Modify: `projects/front/styles.css`

**What:** Implement the full chat detail view with streaming, message actions, auto-mode, and avatar strip.

- [ ] **Step 1: Define rpChat object and implement render()**

Define `rpChat` as an object with state for the current conversation:

```javascript
// ===== RP: Chat =====

const rpChat = {
    convId: null,
    convDetail: null,
    isStreaming: false,
    abortController: null,
    autoMode: false,

    async render(container, convId) { /* ... */ },
};
```

The chat view has four zones:
1. **Header**: AI card name, model + scenario info, action buttons (Continue, Regenerate, Restart, Auto)
2. **Chat container**: flex row with scrollable message area (left) and avatar strip (right)
3. **Input area**: textarea + Send button (Stop button during streaming)

Load conversation detail via `GET /rp/conversations/{id}`. Render existing messages with `rpRenderDialogue()` for quote coloring. Show scenario banner if applicable.

- [ ] **Step 2: Implement rpStreamResponse()**

Port the streaming function from existing rp app.js (lines 543-688). Adapt for the new DOM structure:
- No inline avatars in message bubbles
- Update `rp-under-hood` panel with debug data via `rpState.emit('conv-message', data)`
- Handle `auto_role` to switch message alignment
- Handle thinking sections (collapsible)
- On abort, save partial via `/rp/conversations/{id}/save-partial`
- On done, re-render bubble with `rpRenderDialogue()`

```javascript
async function rpStreamResponse(url, body, container, forceRole, convId) {
    // AbortController for stop button
    rpChat.abortController = new AbortController();
    const opts = { method: 'POST', signal: rpChat.abortController.signal };
    if (body !== undefined) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
    }

    let streamRole = forceRole || 'assistant';
    const wrapper = el('div', { class: 'rp-msg ' + streamRole });
    const bubble = el('div', { class: 'rp-msg-bubble streaming-cursor' });
    // ... (thinking section, error handling, chunk parsing)
    // Same JSON-line protocol as existing app
}
```

- [ ] **Step 3: Implement message actions**

- **Send**: POST `/rp/conversations/{id}/message` with `{ content }`, stream response
- **Continue**: POST `/rp/conversations/{id}/continue`, stream response
- **Regenerate**: POST `/rp/conversations/{id}/regenerate`, remove last assistant message from DOM, stream response
- **Restart**: confirm action, POST `/rp/conversations/{id}/restart`, show timer, reload conversation
- **Auto**: toggle auto-mode, call `rpAutoReplyLoop()` which repeatedly POSTs `/rp/conversations/{id}/auto-reply` with 500ms pause between turns
- **Stop**: abort the AbortController, stop auto-mode

- [ ] **Step 4: Implement message hover actions**

On hover over a message bubble, show edit/delete/copy buttons:
- **Edit**: replace bubble with textarea, save via `PUT /rp/messages/{id}` with `{ content }`
- **Delete**: confirm, `DELETE /rp/messages/{id}`, remove from DOM
- **Copy**: copy text to clipboard

- [ ] **Step 5: Implement rpRenderDialogue()**

Port `renderDialogue()` from existing app — regex to find quoted text `"..."` and wrap in `<span class="dialogue-quote-user">` or `dialogue-quote-assistant` based on role. Use curly quotes.

- [ ] **Step 6: Implement avatar strip**

A non-scrolling column to the right of the message area:
- User avatar pinned at top (using card avatar URL or placeholder)
- AI avatar pinned at bottom
- Uses `display: flex; flex-direction: column; justify-content: space-between`

- [ ] **Step 7: Add chat styles**

CSS for `.rp-chat-header`, `.rp-chat-actions` (button row), `.rp-chat-body` (flex row), `.rp-chat-messages` (scrollable, flex: 1), `.rp-avatar-strip` (width 80px, flex-shrink 0), `.rp-msg` (message row), `.rp-msg.user` (align left), `.rp-msg.assistant` (align right), `.rp-msg-bubble` (max-width 80%, padding, border), `.rp-msg-hover-actions` (hidden by default, visible on hover), `.rp-msg-sequence` (small sequence number), `.rp-input-area`, `.streaming-cursor::after` (blinking amber block), `.rp-chat-banner` (scenario banner), `.rp-msg-thinking` (collapsible thinking block).

- [ ] **Step 8: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): rp chat view with streaming, actions, and avatar strip"
```

---

## Task 6: RP Card Editor & AI Card Generation

**Files:**
- Modify: `projects/front/app.js`
- Modify: `projects/front/styles.css`

**What:** Implement the card editor detail view and the AI card generation workflow.

- [ ] **Step 1: Implement rpCards.renderEditor()**

When a card tab is opened in center, render:
- Avatar preview (clickable to change via file picker, `PUT /rp/cards/{id}/avatar`)
- Form fields: Name, Description, Personality, First Message, Example Messages, Scenario, Tags
- "Extract as Scenario" button (POST `/rp/cards/{id}/extract-scenario`)
- "Export" button (open `/rp/cards/{id}/export` in new tab)
- Delete with confirm action (DELETE `/rp/cards/{id}`)
- Save (PUT `/rp/cards/{id}`) / Cancel

For new cards (id=null), POST to `/rp/cards`.

Card data structure: `{ name, card_data: { data: { name, description, personality, first_mes, mes_example, scenario, tags } } }`.

- [ ] **Step 2: Implement rpCards.renderGenerator()**

Triggered by "Generate" button in browser panel. Opens as a special tab in center.

**Step 1 UI**: Description textarea + model selector + "Generate" button + progress indicator.
On generate: POST `/rp/cards/generate` with `{ description, model }`. Response contains `{ card: { name, description, personality, first_mes, mes_example, scenario, tags } }`.

**Step 2 UI**: Per-field review using field definitions array:

```javascript
const rpCardGenFieldDefs = [
    { key: 'name', label: 'Name', rows: 1 },
    { key: 'description', label: 'Description', rows: 4 },
    { key: 'personality', label: 'Personality', rows: 3 },
    { key: 'first_mes', label: 'First Message', rows: 3 },
    { key: 'mes_example', label: 'Example Messages', rows: 3 },
    { key: 'scenario', label: 'Scenario', rows: 2 },
    { key: 'tags', label: 'Tags', rows: 1 },
];
```

For each field, show label + editable textarea + "Regenerate" button. Regenerate opens an instructions input + "Go" button. **Important:** Before calling generate-field, sync all current textarea values back into the card object (iterate `rpCardGenFieldDefs`, read each textarea, update card object — tags field needs `split(',').map(t => t.trim())`). Then call POST `/rp/cards/generate-field` with `{ card, field, instructions, model }`. Response `{ value }` updates that field's textarea.

"Create Card" button: POST `/rp/cards` with the assembled card data, then close generator tab.

- [ ] **Step 3: Add card editor/generator styles**

CSS for `.rp-card-editor`, `.rp-card-avatar-preview`, `.rp-form-field`, `.rp-form-field label`, `.rp-form-field textarea`, `.rp-form-field input`, `.rp-form-actions`, `.rp-card-gen-step`, `.rp-card-gen-field`, `.rp-card-gen-field-header`, `.rp-card-gen-field-instructions`.

- [ ] **Step 4: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): rp card editor and AI card generation"
```

---

## Task 7: RP Scenario Editor

**Files:**
- Modify: `projects/front/app.js`
- Modify: `projects/front/styles.css`

**What:** Implement the scenario editor detail view.

- [ ] **Step 1: Implement rpScenarios.renderEditor()**

When a scenario tab is opened in center, render a form with:
- Name (text input)
- Description (textarea, hint: supports `${user}` and `${char}` variables)
- First Message (textarea)
- Model Override (dropdown from rpState.models, with "Use conversation default" option)
- Context Strategy (dropdown with options: `sliding_window`, `full_context` — check existing rp HTML for authoritative list)
- Enable Thinking (checkbox with model support hint — calls `rpModelSupportsThink()`)
- Repeat Penalty, Temperature, Min-P, Top-K, Repeat Last N (numeric inputs)
- Delete with confirm (DELETE `/rp/scenarios/{id}`)
- Save / Cancel

Save builds settings object: `{ context_strategy, think, model, repeat_penalty, temperature, min_p, top_k, repeat_last_n }` (only include non-empty numeric values). PUT `/rp/scenarios/{id}` or POST `/rp/scenarios` for new.

- [ ] **Step 2: Add scenario editor styles**

Reuse `.rp-form-field` styles from card editor. Add `.rp-form-row` for inline fields (think checkbox + hint, numeric inputs in a grid).

- [ ] **Step 3: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): rp scenario editor"
```

---

## Task 8: New Chat Modal

**Files:**
- Modify: `projects/front/app.js`
- Modify: `projects/front/styles.css`

**What:** Implement the overlay modal for creating new conversations.

- [ ] **Step 1: Implement rpNewChatModal**

```javascript
const rpNewChatModal = {
    async open() {
        await Promise.all([rpLoadModels(), rpLoadCards(), rpLoadScenarios()]);
        // Build modal DOM with:
        // - Your Character dropdown (from rpState.cards)
        // - AI Character dropdown (from rpState.cards)
        // - Scenario dropdown (optional, from rpState.scenarios, with "None" option)
        // - Model dropdown (from rpState.models, using rpModelLabel)
        // - Pre-select from most recent conversation if available
        // - Start Chat / Cancel buttons
    },

    async create(userCardId, aiCardId, scenarioId, model) {
        // Show timer in center: "Generating opening scene... Ns"
        // POST /rp/conversations with { user_card_id, ai_card_id, scenario_id, model }
        // On success: rpLoadConversations(), open new chat tab
        // On error: show inline error
    },

    close() {
        // Remove modal overlay
    },
};
```

- [ ] **Step 2: Wire "New" button in browser panel**

The "+ New" button in the Chats tab of the browser panel calls `rpNewChatModal.open()`.

- [ ] **Step 3: Add modal styles**

CSS for `.rp-modal` (fixed overlay, z-index 1000), `.rp-modal-content` (centered box), `.rp-modal-field`, `.rp-modal-actions`, `.rp-modal select`, `.rp-timer` (centered timer text).

- [ ] **Step 4: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): new chat modal with character, scenario, model selection"
```

---

## Task 9: Scene State & Under the Hood Panels

**Files:**
- Modify: `projects/front/app.js`
- Modify: `projects/front/styles.css`

**What:** Implement the two south-docked debug panels.

- [ ] **Step 1: Implement rp-scene-state panel**

Replace the stub render function with:
- Textarea for scene state text
- "Save" button: PUT `/rp/conversations/{id}/scene-state` with `{ scene_state }`
- "Auto-generate" button: POST `/rp/conversations/{id}/refresh-scene-state`, then reload conversation detail to get updated state
- Updates when active chat changes (listen for `conv-opened` and `conv-message` events)
- Shows "No active conversation" when no chat is open

- [ ] **Step 2: Implement rp-under-hood panel**

Replace the stub render function with:
- Three sub-tabs: System Prompt, User Prompt, Raw Response
- Each tab shows a monospace `<pre>` block
- Updates via `conv-message` event (streaming chunks with `debug_prompt` data)
- System Prompt populated from `chunk.debug_prompt`
- User Prompt populated from `chunk.debug_user_prompt`
- Raw Response populated from the `done` chunk (JSON.stringify with indent)

- [ ] **Step 3: Add styles**

CSS for `.rp-scene-state-area`, `.rp-under-hood-tabs`, `.rp-under-hood-tab`, `.rp-under-hood-pane`, `.rp-under-hood-pre` (monospace, overflow auto, amber text).

- [ ] **Step 4: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): scene state and under-the-hood debug panels"
```

---

## Task 10: Init Wiring & Final Integration

**Files:**
- Modify: `projects/front/app.js`

**What:** Wire everything together in the init flow, remove the iframe for the rp tab, and ensure all panels communicate correctly.

- [ ] **Step 1: Update app.init() and app.switchTab()**

When switching to the rp tab for the first time:
1. Apply amber theme
2. Load initial data: `rpLoadCards()`, `rpLoadScenarios()`, `rpLoadConversations()`, `rpLoadModels()`
3. Render dock with RP layout

Add a `rpInitialized` flag to avoid reloading data on every tab switch — just re-render the dock.

- [ ] **Step 2: Add confirmAction utility**

Port the `confirmAction()` helper from existing rp app.js (lines 45-65) — reusable for delete confirmations across cards, scenarios, and conversations.

- [ ] **Step 3: Add timeAgo utility**

Port the `timeAgo()` function (rp app.js line 178) as `rpTimeAgo()` for displaying relative timestamps in the conversation list.

- [ ] **Step 4: Add autoResizeInput utility**

Port `autoResizeInput()` (rp app.js lines 707-711) for the chat input textarea — sets height to `Math.min(scrollHeight, 150)` on input.

- [ ] **Step 5: End-to-end manual test**

Full workflow test:
1. Open front page, switch to rp tab — amber theme, browser panel in west, logs in south
2. Create a new card via "+ New Card" — fill fields, save
3. Create a scenario via "+ New Scenario" — fill fields, save
4. Start a new chat — select cards, scenario, model — conversation created
5. Send a message — streaming works, avatar strip shows, dialogue coloring works
6. Use Continue, Regenerate, Auto buttons
7. Edit and delete a message
8. Check scene state panel — save and auto-generate
9. Check under-the-hood panel — system prompt, user prompt, raw response
10. Import a SillyTavern PNG card
11. Generate a card with AI — step 1 generate, step 2 review/regenerate fields, create
12. Switch back to master tab — green theme, iframe layout restored
13. Resize, collapse, drag panels — verify dock state persists per-tab

- [ ] **Step 6: Commit**

```
git add projects/front/app.js projects/front/styles.css
git commit -m "feat(front): wire rp init, utilities, final integration"
```
