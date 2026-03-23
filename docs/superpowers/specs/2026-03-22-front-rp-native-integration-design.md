# Front: Native RP Integration

Replace the iframe-based rp tab with native UI controls using the front project's dockable panel system and an amber terminal theme.

## Layout

Default panel layout for the rp tab:

```
north:  ['services']                              — existing status bar
west:   ['rp-browser']                            — tabbed list (Chats | Cards | Scenarios)
center: rp-center                                 — tabbed detail views
south:  ['logs-rp', 'rp-scene-state', 'rp-under-hood']  — logs + rp debug panels
east:   (empty)                                   — available for user docking
```

The center area replaces the iframe with a native content zone. Center remains a special non-panel zone in the dock system (not draggable) — its content is rendered by the rp tab manager instead of an iframe. All other panels are dockable (drag to reposition, resize, collapse).

New panels (`rp-browser`, `rp-scene-state`, `rp-under-hood`) are registered in the `PANELS` object with `render()` functions, following the same pattern as existing panels like `services` and `logs-*`.

### Per-Tab Dock Layouts

Each top-level tab (master, rp) has its own default layout and its own `localStorage` key for persisted state. Switching tabs calls `dock.render()` with the appropriate layout. Panel instances are re-rendered on tab switch (not preserved in background).

## Theme

Amber terminal aesthetic (`#ffbf00` primary accent, `#000` background, monospace font). The master tab retains green. Only the rp tab uses amber for borders, headers, text accents, and status indicators. Panel chrome (headers, resize handles) uses amber instead of green when the rp tab is active.

## West Panel: rp-browser

A dockable panel with three internal tabs:

- **Chats**: Conversation list (name, timestamp). "+ New" button opens the new chat modal.
- **Cards**: Compact card list (small avatar + name). "+ New Card" and "Generate" buttons. Drop zone for SillyTavern PNG import at top.
- **Scenarios**: Scenario list (name + truncated description). "+ New Scenario" button.

Clicking any item emits an event that opens the corresponding detail view in the center.

## Center: Tabbed Detail Views

A tab bar at the top showing open items (like browser tabs). Each open conversation, card editor, or scenario editor gets a closeable tab. When no tabs are open, a placeholder is shown.

### Chat Detail

**Header**: AI character name (text only), model + scenario name, action buttons (Continue, Regenerate, Restart, Auto).

**Message area**: Scrollable. Scenario banner at top if applicable. Message bubbles (user left, assistant right, no inline avatars). Dialogue highlighting (quoted text colored differently for user vs assistant, amber palette). Hover actions (edit, delete, copy). Streaming with amber blinking cursor. Message sequence numbers.

**Avatar strip**: Non-scrolling column adjacent to the right of the scrollable message area. User avatar pinned at top, AI avatar pinned at bottom. Does not scroll with messages.

**Input area**: Textarea + Send button. Stop button appears during streaming.

**Auto-mode**: AI plays both sides. Toggle via Auto button in header.

**Streaming**: `fetch` + `ReadableStream`, chunks appended to active message bubble in real-time. Streaming endpoints:
- Send message: `POST /rp/conversations/{id}/message`
- Regenerate: `POST /rp/conversations/{id}/regenerate`
- Continue: `POST /rp/conversations/{id}/continue`
- Auto-reply: `POST /rp/conversations/{id}/auto-reply`

All four return streaming responses in the same format.

### Card Editor Detail

Tab title shows card name. Avatar preview at top (clickable to change). Form fields: Name, Description, Personality, First Message, Example Messages, Scenario, Tags. "Extract as Scenario" button on scenario field. Export button (SillyTavern PNG download). Delete with confirmation. Save/Cancel actions.

### Card Generation

Triggered by "Generate" button in browser panel. Step 1: description textarea + model selector + Generate button + progress bar. Step 2: per-field review with editable blocks, each with "Regenerate" button and optional instructions input. "Create Card" commits to database.

### Scenario Editor Detail

Tab title shows scenario name. Form fields: Name, Description (supports `${user}` and `${char}` variables), First Message, Model Override (optional dropdown), Context Strategy (dropdown), Enable Thinking (checkbox with model support hint), Repeat Penalty, Temperature, Min-P, Top-K, Repeat Last N (numeric inputs). Delete with confirmation. Save/Cancel actions.

## South Panels

### rp-scene-state (dockable)

Textarea for scene state (location, clothing, physical state, props, mood). Save button and Auto-generate button. Updates via `/rp/conversations/{id}/scene-state` endpoint.

### rp-under-hood (dockable)

Sub-tabs: System Prompt, User Prompt, Raw Response. Monospace pre-formatted debug content. Updates after each message exchange.

## New Chat Modal

Overlay modal triggered by "+ New" in browser's Chats tab:

- Your Character (dropdown populated from cards)
- AI Character (dropdown populated from cards)
- Scenario (optional dropdown)
- Model (dropdown from `GET /health` → `available_models[]`). Each model object has `name`, `alias`, `parameter_size`, `quantization_level`, `supports_think`. Tags (roleplay/uncensored/instruct) are derived client-side by pattern-matching model names (e.g., "lumimaid" → roleplay+uncensored).
- Start Chat / Cancel

Creating a conversation auto-opens the new chat tab in center.

## State Management

A shared `rpState` object:

```javascript
rpState = {
    cards: [],
    scenarios: [],
    conversations: [],
    models: [],
    openTabs: [],    // {type: 'chat'|'card'|'scenario', id: number}
    activeTab: null,
}
```

Simple event bus for cross-panel communication:

- `conv-opened` / `card-opened` / `scenario-opened` — browser click opens detail in center
- `cards-changed` / `scenarios-changed` / `convs-changed` — after CRUD, browser refreshes list
- `conv-message` — new message received, update scene state / under-the-hood panels
- `tab-closed` — center tab closed, update state

## Code Organization

Single `app.js` file (~2,000 lines) with section headers:

```
// ===== Constants & Config =====
// ===== DOM Helper =====
// ===== Dock System =====
// ===== Master Tab =====
// ===== RP: State & Event Bus =====
// ===== RP: Browser Panel =====
// ===== RP: Center (Tab Manager) =====
// ===== RP: Chat =====
// ===== RP: Cards =====
// ===== RP: Scenarios =====
// ===== RP: New Chat Modal =====
// ===== RP: Scene State Panel =====
// ===== RP: Under the Hood Panel =====
// ===== Init =====
```

Single `styles.css` with amber theme variables scoped to the rp tab.

## API Endpoints (No Backend Changes)

All existing `/rp/*` endpoints are consumed directly. See `projects/rp/routes.py` for the full endpoint reference. Key groups:

- **Cards**: CRUD (`GET/POST/PUT/DELETE /rp/cards/*`), import (`POST /rp/cards/import`), generation (`POST /rp/cards/generate`, `/rp/cards/generate-field`), avatar (`GET/PUT /rp/cards/{id}/avatar`), export (`GET /rp/cards/{id}/export`), extract scenario (`POST /rp/cards/{id}/extract-scenario`)
- **Scenarios**: CRUD (`GET/POST/PUT/DELETE /rp/scenarios/*`)
- **Conversations**: CRUD (`GET/POST/DELETE /rp/conversations/*`), detail (`GET /rp/conversations/{id}`), restart (`POST /rp/conversations/{id}/restart`), scene state (`PUT /rp/conversations/{id}/scene-state`, `POST /rp/conversations/{id}/refresh-scene-state`)
- **Messages**: Send (`POST /rp/conversations/{id}/message` — streaming), regenerate (`POST /rp/conversations/{id}/regenerate` — streaming), continue (`POST /rp/conversations/{id}/continue` — streaming), auto-reply (`POST /rp/conversations/{id}/auto-reply` — streaming), edit/delete (`PUT/DELETE /rp/messages/{id}`), save partial (`POST /rp/conversations/{id}/save-partial`)
- **Models**: `GET /health` → `available_models[]` with `name`, `alias`, `parameter_size`, `quantization_level`, `supports_think`

## Error Handling

- **API failures**: Show inline amber error text in the relevant panel (e.g., below the form, in the message area). No toast system — keep it simple.
- **Streaming interruption**: Keep the partial message text in the bubble, append "[streaming interrupted]" indicator. User can Regenerate to retry.
- **Stale references**: If an open editor's entity (card/scenario/conversation) is deleted externally, show "This item no longer exists" in the center tab. Close the tab on next user interaction.
- **Network errors during polling**: Silently skip (same as current front behavior for service status polling).
