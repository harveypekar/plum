# RisuAI Technical Survey

**Date:** 2026-03-15
**Repo:** [kwaroran/RisuAI](https://github.com/kwaroran/RisuAI) (GPLv3)
**Version analyzed:** v2026.2.291
**Stars:** ~1,357 | **Forks:** ~305 | **Open issues:** ~128 | **Discord:** ~6,800 members

---

## 1. Architecture

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | Svelte 5 (runes: `$state`, `$derived`, `$effect`) |
| Language | TypeScript (strict) |
| Styling | Tailwind CSS 4 |
| Build tool | Vite 7 |
| Desktop shell | Tauri 2 (Rust backend) |
| Package manager | pnpm |
| Mobile | Capacitor (via `capacitor.config.ts`) + Tauri mobile |
| Testing | Vitest |

### Codebase Organization

```
src/
  ts/                      # Core business logic (TypeScript)
    storage/               # Data persistence layer
      database.svelte.ts   # Central state: Database interface (~1300 lines of fields)
      autoStorage.ts       # Platform-adaptive storage selection
      opfsStorage.ts       # Origin Private File System (web)
      nodeStorage.ts       # Node.js file-based storage
      risuSave.ts          # Save/load serialization
    process/               # Chat processing pipeline
      index.svelte.ts      # Main sendChat() orchestration (~2000 lines)
      prompt.ts            # Prompt item types and preset conversion
      request/             # API request routing
        request.ts         # Dispatcher with fallback chain
        anthropic.ts       # Claude-specific request handler
        google.ts          # Gemini/Vertex handler
        openAI/            # OpenAI-compatible handler (also OpenRouter, custom)
      memory/              # Memory/summarization systems
        supaMemory.ts      # Original summarization
        hypamemory.ts      # Embedding-based retrieval (v1)
        hypamemoryv2.ts    # Embedding-based retrieval (v2)
        hypav2.ts          # HypaMemory v2 orchestrator
        hypav3.ts          # HypaMemory v3 - latest, with categorization and similarity
      lorebook.svelte.ts   # Lorebook/world info matching engine
      mcp/                 # Model Context Protocol (MCP) client
        mcp.ts             # MCP initialization and tool aggregation
        internalmcp.ts     # Built-in MCP tools
        risuaccess/        # Self-referential MCP (RisuAI controls itself)
      templates/           # Prompt formatting templates
        chatTemplate.ts    # Jinja/ChatML template application
      scriptings.ts        # Lua scripting via wasmoon
      triggers.ts          # Event trigger system
    parser/                # Text parsing
      parser.svelte.ts     # risuChatParser - macro/variable expansion
      chatML.ts            # ChatML format parser
      chatVar.svelte.ts    # Chat variables (get/set)
    plugins/               # Plugin system
      apiV3/               # Current API (iframe-sandboxed)
      plugins.svelte.ts    # Plugin lifecycle management
    model/                 # Model registry
      modellist.ts         # LLM flags, capabilities, token limits
    characterCards.ts      # Import/export character cards
    characters.ts          # Character CRUD operations
  lib/                     # Svelte UI components
    ChatScreens/           # Chat display (Message.svelte, ChatBody.svelte, etc.)
    Setting/               # Settings panels with wrapper components
    SideBars/              # Sidebar: LoreBook/, Scripts/, character config
    UI/                    # Reusable UI: GUI/, Realm/ (hub), NewGUI/
    Mobile/                # Mobile-specific layout
    Playground/            # Dev tools: tokenizer, regex tester, Jinja preview, MCP
    Others/                # HypaV3Modal, WelcomeRisu, ProTools
  lang/                    # i18n (en, ko, cn, zh-Hant, vi, de, es)
src-tauri/                 # Tauri desktop backend (Rust)
  src/main.rs              # Minimal Tauri bootstrap
  src-python/              # Embedded Python for local models
server/
  node/server.cjs          # Self-hosted Node.js proxy server
  hono/                    # Hono framework server (Cloudflare Workers compatible)
```

### Cross-Platform Strategy

RisuAI uses a **single Svelte codebase** with platform detection at runtime (`src/ts/platform.ts`):

```typescript
export const isTauri: boolean = !!window.__TAURI_INTERNALS__
export const isNodeServer: boolean = !!globalThis.__NODE__
export const isWeb: boolean = !isTauri && !isNodeServer && location.hostname === 'risuai.xyz'
export const isMobile: boolean = /Android|iPhone|iPad|iPod|webOS/i.test(navigator.userAgent);
```

**Deployment targets** (from `tauri.conf.json`):
- **Web**: Static site hosted at risuai.xyz (Vite build)
- **Desktop**: Windows (NSIS installer), macOS (DMG/APP), Linux (DEB/RPM/AppImage) via Tauri 2
- **Mobile**: Android/iOS via Tauri mobile + Capacitor
- **Self-hosted**: Node.js server or Docker (port 6001), or Hono on Cloudflare Workers
- **PWA**: `manifest.json` present, standalone mode detection

Storage adapts per platform: Tauri uses native filesystem, web uses OPFS (Origin Private File System) or LocalForage, Node uses file-based storage.

### Build System

Vite 7 with `@sveltejs/vite-plugin-svelte`, `vite-plugin-wasm` (for wasmoon Lua, Pyodide, bergamot translator). Key scripts:
- `pnpm dev` - local dev server
- `pnpm build` - production web build with sourcemaps
- `pnpm tauri dev` / `pnpm tauri build` - desktop builds
- `pnpm hono:build` - Cloudflare Workers build

---

## 2. Character Card Handling

### Supported Formats

RisuAI supports import/export of multiple character card specifications, handled in `src/ts/characterCards.ts` (~1500 lines):

| Format | Extension | Description |
|--------|-----------|-------------|
| Character Card V2 | `.png` (with embedded JSON) | Standard PNG with JSON in tEXt chunk. Uses `@risuai/ccardlib` and `PngChunk` for reading/writing. |
| Character Card V3 | `.png` | Extended V2 with richer lorebook, assets, creator metadata. Imported via `CharacterCardV3` type from `@risuai/ccardlib`. |
| CharX | `.charx` | ZIP archive containing `card.json` + asset files (images, audio, MMD models). Processed by `CharXImporter`/`CharXWriter` in `processzip.ts`. |
| RisuAI Module | `.risum` | Binary format with RPack compression. Contains module data (lorebooks, regex scripts, triggers, assets). |
| RisuAI Preset | `.risup` | Preset export format. |
| JSON | `.json` | Raw character JSON, also used for SillyTavern preset import. |
| LOREBOOK | `.json` | CCardLib-compatible lorebook format. |

### Internal Data Model

The `character` interface in `database.svelte.ts` is the canonical representation. Key fields:

```typescript
interface character {
    type?: "character"
    name: string
    image?: string                    // Asset ID for main avatar
    firstMessage: string              // Initial greeting
    desc: string                      // Character description
    personality: string               // Personality summary
    scenario: string                  // Scenario/context
    exampleMessage: string            // Few-shot examples
    systemPrompt: string              // Character-level system prompt override
    postHistoryInstructions: string   // Post-history instructions
    alternateGreetings: string[]      // Multiple first messages
    globalLore: loreBook[]            // Character-attached lorebook
    emotionImages: [string, string][] // [emotion_name, asset_id]
    customscript: customscript[]      // Regex scripts
    triggerscript: triggerscript[]    // Event triggers
    chats: Chat[]                     // All chat sessions
    bias: [string, number][]          // Token bias pairs
    tags: string[]
    creator: string
    creatorNotes: string
    characterVersion: string
    loreSettings?: loreSettings       // Per-character lore config
    additionalAssets?: [string, string, string][]  // [name, asset_id, ext]
    ccAssets?: {type: string, name: string, uri: string, ext: string}[]
    viewScreen: 'emotion'|'none'|'imggen'
    ttsMode?: string                  // TTS provider selection
    // ... many more fields for voice, image gen, etc.
}
```

### Extensions to Standard Card Format

RisuAI extends the standard character card spec with:
1. **Emotion images** - sprite-based emotion display system
2. **Custom scripts** (regex) - per-character regex find/replace rules
3. **Trigger scripts** - event-driven scripting (Lua)
4. **Additional assets** - arbitrary file attachments (images, audio, 3D models)
5. **PNG EXIF preservation** - reads and stores metadata from PNG chunks (parameters, comments, etc.)
6. **Inlay system** - `{{inlay::name}}` / `{{inlayeddata::name}}` tags for embedding images/audio/video in messages
7. **Prebuilt asset commands** - image generation instructions embedded in character data

### Import Pipeline

The `importCharacter()` function in `characterCards.ts` handles all formats:
1. Detect format by file extension and magic bytes
2. For PNG: extract JSON from tEXt chunks via `PngChunk.readGenerator()`
3. For CharX: unzip, read `card.json`, process embedded assets
4. Run `characterFormatUpdate()` to normalize older formats
5. Apply `CCardLib` for V3 lorebook conversion
6. Save to database with `setDatabase()`

Hub integration: Characters can be imported from the RisuAI Realm hub (`sv.risuai.xyz`) or via deep link (`risuailocal://` protocol).

---

## 3. Prompt Assembly

The prompt assembly pipeline lives in `src/ts/process/index.svelte.ts` (~2000 lines). The central function is `sendChat()`.

### Pipeline Overview

```
sendChat()
  |
  +-- 1. Resolve character (single or group member)
  |
  +-- 2. Build unformatted prompt buckets:
  |     {main, jailbreak, chats, lorebook, globalNote,
  |      authorNote, lastChat, description, postEverything, personaPrompt}
  |
  +-- 3. Apply prompt template (ordered card list)
  |     OR use legacy formatingOrder
  |
  +-- 4. Process chat messages with risuChatParser()
  |     - Variable expansion ({{char}}, {{user}}, etc.)
  |     - Inlay asset resolution (images -> multimodal or captions)
  |     - Script processing (regex find/replace)
  |     - Thought tag extraction (<Thoughts>)
  |
  +-- 5. Lorebook matching and injection
  |     - Keyword/regex scanning over recent messages
  |     - Recursive scanning (lorebook content triggers other lorebooks)
  |     - Position-based injection (depth, before_desc, after_desc, etc.)
  |     - {{position::name}} injection points
  |
  +-- 6. Token counting and context window management
  |     - Count all sections against maxContext
  |     - Trim oldest messages if over budget
  |
  +-- 7. Memory system (if enabled)
  |     - SupaMemory / HypaMemory v1/v2/v3 / Hanurai
  |     - Summarization of older messages
  |     - Embedding-based relevant memory retrieval
  |
  +-- 8. Format final prompt
  |     - Apply prompt template ordering
  |     - Cache point insertion
  |     - Depth-based lorebook insertion into chat history
  |     - PostEverything section (emotion instructions, group signals)
  |
  +-- 9. Send to API
  |     - requestChatData() dispatches to provider
  |     - Fallback chain if primary fails
  |     - Streaming or blocking mode
  |
  +-- 10. Post-process response
        - Script processing on output
        - Emotion detection
        - Stable Diffusion image generation (if configured)
        - TTS speech synthesis
        - Trigger execution
```

### Prompt Template System

The prompt template is an ordered array of `PromptItem` objects. Types:

| Type | Purpose |
|------|---------|
| `plain` | Static text with role (system/user/bot) and sub-type (main/globalNote) |
| `jailbreak` | Jailbreak prompt (togglable) |
| `cot` | Chain-of-thought instructions |
| `description` | Character description (with optional `innerFormat` wrapper using `{{slot}}`) |
| `persona` | User persona prompt |
| `lorebook` | Lorebook entries (keyword-matched) |
| `chat` | Chat history with `rangeStart`/`rangeEnd` |
| `memory` | Memory system output insertion point |
| `authornote` | Author's note |
| `postEverything` | Final instructions before sending |
| `chatML` | Raw ChatML format text |
| `cache` | Cache breakpoint for API-level caching (e.g., Claude prompt caching) |

Each item can have:
- `innerFormat` - wrapper template with `{{slot}}` placeholder
- `name` - display label
- `role` - message role override

### SillyTavern Preset Import

`stChatConvert()` in `prompt.ts` converts SillyTavern chat completion presets by mapping ST identifiers (`main`, `jailbreak`, `chatHistory`, `worldInfoBefore`, `charDescription`, `personaDescription`) to RisuAI prompt items. It also handles instruct mode templates by building Jinja templates from ST's `input_sequence`/`output_sequence`/`system_sequence` format.

### Variable/Macro System

`risuChatParser()` in `parser.svelte.ts` expands macros:
- `{{char}}`, `{{user}}` - character/user names
- `{{personality}}`, `{{scenario}}`, `{{description}}` - character fields
- `{{original}}` - allows overriding while preserving defaults
- `{{slot}}` - content injection in innerFormat templates
- `{{position::name}}` - lorebook position injection
- `{{inlay::name}}` / `{{inlayeddata::name}}` - asset embedding
- `{{asset_prompt::name}}` - asset as multimodal image input
- `{{#if ...}}` / `{{/if}}` - conditional blocks
- `{{prefill_supported}}` - model capability detection
- Chat variables via `getChatVar()`/`setChatVar()`

---

## 4. Memory and Context Management

### Context Window Management

Basic approach: count tokens for all prompt sections, then trim oldest chat messages until within `maxContext`. Token counting uses model-specific tokenizers bundled in `public/token/` (Claude, Llama, GPT o200k, Gemma, DeepSeek, Mistral, etc.).

### Memory Systems (5 options)

All live in `src/ts/process/memory/`:

#### 1. SupaMemory (`supaMemory.ts`)
- Original summarization system
- Summarizes oldest messages that fall outside context window
- Stores summary as a single "supaMemory" tagged message
- Uses a configurable sub-model for summarization

#### 2. HypaMemory v1 (`hypamemory.ts`)
- Embedding-based retrieval
- Uses `HypaProcesser` class with local MiniLM or API-based embeddings
- Computes cosine similarity between current context and stored memories
- Retrieves most relevant past summaries

#### 3. HypaMemory v2 (`hypav2.ts` / `hypamemoryv2.ts`)
- Improved chunking and embedding pipeline
- `HypaProcessorV2` with better text segmentation
- Configurable chunk size (`hypaChunkSize`) and allocated tokens (`hypaAllocatedTokens`)

#### 4. HypaMemory v3 (`hypav3.ts`) -- Current flagship
- Most sophisticated system with categories, tags, and importance scoring
- **Data structure**: `HypaV3Data` with summaries, categories, metrics
- Each `Summary` tracks: text, linked chatMemos (Set), importance flag, category, tags
- **Selection strategy**: Allocates token budget across three pools:
  - Recent memories (`recentMemoryRatio`)
  - Similar memories via embedding (`similarMemoryRatio`)
  - Important/flagged memories
- **Summarization**: Configurable model, prompt, and re-summarization prompt
- **Rate limiting**: `TaskRateLimiter` for API calls during bulk summarization
- **Experimental implementation**: Parallel processing with configurable concurrency
- **UI**: Dedicated modal (`HypaV3Modal/`) for viewing, editing, bulk operations, category management
- Settings per-preset via `HypaV3Preset[]`

#### 5. Hanurai Memory (`hanuraiMemory.ts`)
- Split-based memory with configurable token allocation (`hanuraiTokens`)
- Simpler alternative to Hypa systems

### Lorebook/World Info (`lorebook.svelte.ts`)

`loadLoreBookV3Prompt()` is the main entry point:

1. **Source aggregation**: Combines character globalLore + chat localLore + module lorebooks
2. **Scanning**: Checks recent messages (configurable `scanDepth`) for keyword matches
3. **Match modes**:
   - `normal` - any key matches
   - `multiple` - multiple keys with AND/OR logic
   - `constant` - always active
   - `folder` - organizational grouping
4. **Matching options**: Full word matching, regex matching, case sensitivity
5. **Recursive scanning**: Activated lorebook content can trigger further matches
6. **Position injection**:
   - Default (in lorebook section)
   - `before_desc` / `after_desc` - relative to character description
   - `depth` N - injected N messages deep into chat history
   - `reverse_depth` - from the beginning
   - `pt_NAME` - at named `{{position::NAME}}` points
   - Custom `inject` with `append`/`prepend`/`replace` operations
7. **Token budget**: Respects per-character or global `loreBookToken` limit

---

## 5. Unique Features

### What Sets RisuAI Apart

**1. MCP (Model Context Protocol) Client** (`src/ts/process/mcp/`)
RisuAI is one of the first roleplay frontends to implement MCP. Built-in MCP tools:
- `internal:fs` - filesystem access
- `internal:risuai` - self-referential API (read/modify characters, chats, modules)
- `internal:aiaccess` - AI model access tool
- `internal:googlesearch` - web search
- `internal:graphmem` - graph-based memory
- `internal:dice` - dice rolling
- Plugin-defined MCP tools via `plugin:` prefix
- `stdio:` MCP servers (Tauri desktop only, spawns local processes)

**2. Module System** (`src/ts/process/modules.ts`)
Distributable `.risum` packages containing:
- Lorebooks, regex scripts, triggers
- Custom JavaScript (CJS)
- Assets (images, etc.)
- Background embedding text
- MCP server definitions
- Custom toggle UI definitions
Binary format with RPack compression, per-module namespace isolation.

**3. Inlay System**
Rich media embedding in chat messages:
- `{{inlay::name}}` - reference named assets
- `{{inlayeddata::name}}` - data-embedded assets
- Supports images (sent as multimodal to vision models, or captioned via transformers for text-only models), video, audio, and "signatures"
- `{{asset_prompt::name}}` - send character assets as image inputs

**4. CBS (Custom Bot Scripting)**
A custom scripting language with conditionals, loops, and string operations. Tests in `src/ts/parser/tests/cbs/`.

**5. Lua Scripting via wasmoon**
Full Lua runtime compiled to WASM (`wasmoon` package), used for trigger scripts (`runLuaEditTrigger` in `scriptings.ts`).

**6. In-Browser ML**
- `@huggingface/transformers` for local image captioning/embedding
- `@mlc-ai/web-llm` for in-browser LLM inference
- `pyodide` for Python execution in browser
- `@browsermt/bergamot-translator` for local translation

**7. Emotion/Sprite System**
Characters can have emotion images. The AI detects emotions in responses and displays corresponding sprites. Configurable via `viewScreen: 'emotion'` with custom `emotionInstructions`.

**8. Image Generation Integration**
Built-in support for Stable Diffusion (local WebUI), NovelAI image gen (v4 prompt support), DALL-E, FAL.ai, Google Imagen, ComfyUI, Stability AI, and OpenAI-compatible image APIs.

**9. Prompt Template Toggles**
`customPromptTemplateToggle` defines UI toggle/select controls that modify prompt behavior via chat variables. Power users can create switchable prompt variants.

**10. 3D Model Support**
Three.js integration (`src/ts/3d/threeload.ts`) for loading and displaying 3D models, including MMD (MikuMikuDance) support in CharX files.

**11. Realm Hub**
Built-in character sharing platform at `sv.risuai.xyz` with upload, download, and community features (`src/lib/UI/Realm/`).

### Plugin System (API v3.0)

Documented in `plugins.md` (~42KB). Key architecture:
- **Sandboxed iframes**: Each plugin runs in isolated context
- **SafeDocument/SafeElement**: Wrapped DOM access for security
- **Plugin capabilities**:
  - Custom AI providers (`risuai.registerProvider()`)
  - Message pre/post processing
  - Custom UI panels
  - Device-specific and save-specific storage
  - Hot reload for development
  - IPC communication between plugins
  - MCP tool registration
- **Metadata via comments**: `//@name`, `//@api 3.0`, `//@display-name`
- **TypeScript support**: `risuai.d.ts` type definitions included

---

## 6. UI/UX Design

### How It Differs from SillyTavern

| Aspect | RisuAI | SillyTavern |
|--------|--------|-------------|
| Framework | Svelte 5 (reactive, compiled) | jQuery + vanilla JS |
| Architecture | SPA with conditional rendering | Traditional multi-page feel |
| Mobile | First-class mobile UI (`src/lib/Mobile/`) | Responsive but desktop-first |
| Styling | Tailwind CSS 4 | Custom CSS with themes |
| State management | Svelte 5 runes (`$state`/`$derived`) | Global variables + jQuery |
| Theming | Color scheme objects, custom CSS injection | CSS themes |
| Router | No router; `App.svelte` switches views | Express-like routing |

### UI Modes

- **Classic** - Traditional chat interface
- **WaifuLike** / **WaifuCut** - Visual novel style with character sprites
- **Mobile** - Dedicated mobile components (`MobileBody`, `MobileHeader`, `MobileFooter`)
- **Lite** - Lightweight variant (`LiteMain.svelte`, `LiteUI/`)
- **Custom GUI** - User-defined HTML templates (`customGUI` field)

### Component Architecture

Settings use a registry pattern (`src/ts/setting/settingRegistry.ts`) with typed wrapper components:
- `SettingCheck`, `SettingSlider`, `SettingText`, `SettingSelect`, `SettingColor`, etc.
- Accordion-based grouping (`SettingAccordion`)
- Component rendering via `SettingRenderer.svelte`

The Playground section (`src/lib/Playground/`) provides developer tools:
- Tokenizer, Regex tester, Jinja template preview
- Parser debugger, MCP tool explorer
- Embedding playground, image generation tester
- Translation tester, subtitle editor

### Responsive Design

`DynamicGUI` store in `stores.svelte.ts` handles viewport-based layout switching. The hamburger menu can be positioned at bottom for mobile ergonomics (`hamburgerButtonBottom`).

---

## 7. Code Quality and Patterns

### Strengths

1. **Type safety**: Full TypeScript with strict typing. The `Database` interface alone has 200+ typed fields, preventing runtime errors.
2. **Svelte 5 runes**: Modern reactive state management (`$state`, `$derived`, `$effect`), eliminating many categories of bugs.
3. **Modular processing pipeline**: Clean separation between prompt assembly, request handling, and memory systems.
4. **Platform abstraction**: Storage and API layers cleanly abstract platform differences.
5. **Plugin sandboxing**: Security-conscious iframe isolation with capability-based access.
6. **Comprehensive tokenizer support**: Ships tokenizer models for 8+ model families.

### Weaknesses

1. **God object**: The `Database` interface has 200+ fields with no decomposition. The `setDatabase()` function initializes defaults for every single field with `??=` operators (~400 lines of null coalescing).
2. **Monolithic sendChat()**: The main processing function is ~2000 lines in a single file with deeply nested logic.
3. **Limited test coverage**: Only a handful of unit tests (CBS parser, chatML, imageType, inlays, HypaV3 modules). No integration tests, no E2E tests.
4. **Inconsistent naming**: Mix of camelCase and snake_case (`PresensePenalty`, `seperateParameters`), typos preserved for backwards compatibility.
5. **Large unstructured state**: Everything lives in one reactive `DBState.db` object. No proper state machines or reducers.
6. **Deep cloning**: Frequent use of `safeStructuredClone()` as a workaround for Svelte reactivity, suggesting architectural tension.

### Patterns Used

- **Store pattern**: Svelte stores for cross-component state (`stores.svelte.ts`)
- **Provider pattern**: API request routing based on model info flags
- **Template pattern**: Prompt templates as ordered card arrays
- **Strategy pattern**: Memory systems selected at runtime (supaMemory vs hypa variants)
- **Factory pattern**: Plugin instantiation via `factory.ts`
- **Observer pattern**: `observer.svelte.ts` for reactive subscriptions

### Languages/Frameworks Summary

- TypeScript: ~95% of codebase
- Svelte: UI components
- Rust: Tauri backend (minimal, mostly plugin configuration)
- Lua: Trigger scripting runtime (via wasmoon WASM)
- Python: Embedded via Pyodide (browser) and bundled Python scripts (Tauri)
- Jinja: Prompt template language (via `@huggingface/jinja`)
- CSS/Tailwind: Styling

---

## 8. Community

### Development

- **Primary developer**: kwaroran (2,928 commits, ~85% of codebase)
- **Notable contributors**: 9 others with 60+ commits each, mostly translations and UI fixes
- **Total contributors**: ~30+
- **Commit velocity**: Multiple commits per week, actively maintained as of March 2026
- **Release cadence**: Several releases per month (v2026.2.291 on March 2, 2026; 5 releases in February 2026 alone)

### Community Size

- **GitHub**: 1,357 stars, 305 forks
- **Discord**: ~6,800 members ([invite](https://discord.com/invite/JzP8tB9ZK8))
- **Issue tracker**: 128 open issues (healthy ratio for active project)

### Ecosystem

- **Realm Hub**: Built-in character sharing platform
- **Plugin ecosystem**: API v3.0 with TypeScript template, hot reload, development tools
- **Module system**: Distributable `.risum` packages for lorebooks, scripts, and assets
- **Interoperability**: Imports SillyTavern presets (chat completion, instruct, context templates, parameters)
- **Third-party tools**: [Risu2Silly](https://github.com/StenzelK/Risu2Silly) for chatlog conversion
- **Documentation**: [Official docs](https://kwaroran.github.io/docs/) at kwaroran/docs repo

### Comparison to SillyTavern

| Metric | RisuAI | SillyTavern |
|--------|--------|-------------|
| Stars | ~1,350 | ~10,000+ |
| Architecture | Modern (Svelte 5, Tauri 2) | Legacy (jQuery, Node/Express) |
| Cross-platform | Native desktop + web + mobile | Node.js server + browser |
| Target audience | Storytellers, mobile users | Power users, modders |
| Extension model | Sandboxed plugins + modules | Server-side extensions |
| Memory systems | 5 options (including embedding-based) | Extension-based |
| MCP support | Built-in client | Not built-in |
| Self-contained | Yes (web version works standalone) | Requires Node.js server |

---

## Key Takeaways for Our RP Project

1. **Prompt template as ordered card array** is a proven pattern. Each card has a type, optional innerFormat with `{{slot}}`, and role. This is more flexible than a fixed ordering.

2. **Lorebook injection at depth** is important -- inserting world info N messages deep into history rather than just at the top keeps it contextually relevant.

3. **The `{{position::name}}` injection system** allows lorebook entries to target specific named slots in prompts, which is powerful for complex prompt engineering.

4. **HypaV3 memory** is the most sophisticated approach in the ecosystem: categorized summaries + embedding similarity + importance flagging + configurable ratios between recent/similar/important memories.

5. **MCP integration** in a roleplay frontend is novel and forward-looking. It enables tool use (dice, search, file access) within the roleplay context.

6. **Module system** (.risum) as a distribution format for character enhancements (lorebooks + scripts + assets) is an underexplored pattern worth studying.

---

Sources:
- [kwaroran/RisuAI GitHub](https://github.com/kwaroran/RisuAI)
- [RisuAI Official Docs](https://kwaroran.github.io/docs/)
- [RisuAI Plugin Development Guide](https://github.com/kwaroran/RisuAI/blob/main/plugins.md)
- [RisuAI AGENTS.md](https://github.com/kwaroran/RisuAI/blob/main/AGENTS.md)
- [RisuAI vs SillyTavern Comparison (Appscribed)](https://appscribed.com/risuai-vs-sillytavern/)
- [RisuAI Discord Server](https://discord.com/invite/JzP8tB9ZK8)
- [RisuAI NamuWiki](https://en.namu.wiki/w/RisuAI)
- [Character Card Spec V2](https://github.com/malfoyslastname/character-card-spec-v2)
- [Risu2Silly Converter](https://github.com/StenzelK/Risu2Silly)
