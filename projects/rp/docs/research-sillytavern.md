# SillyTavern: Deep Technical Survey

**Date**: 2026-03-15
**Repository**: https://github.com/SillyTavern/SillyTavern
**Branch analyzed**: `release`
**Stats**: 24,378 stars, 4,920 forks, 394 open issues, AGPL-3.0 license
**Created**: 2023-02-09 (fork of TavernAI)

---

## 1. Architecture

### Tech Stack

- **Runtime**: Node.js >= 18 (ES modules throughout, `"type": "module"`)
- **Server**: Express 4.x with extensive middleware stack
- **Frontend**: Vanilla JS single-page application. No React, no Vue, no framework. jQuery + raw DOM manipulation
- **Templating**: Handlebars (both server-side and client-side macro system)
- **Image processing**: Jimp (server-side, for character card PNG manipulation)
- **Tokenization**: `tiktoken` (OpenAI), `sillytavern-transformers` (local HuggingFace models), `@agnai/sentencepiece-js`
- **Bundling**: Webpack (for serving client modules, not a build step)
- **Vector DB**: Vectra (local vector storage for RAG)
- **Search**: Fuse.js (fuzzy search)
- **Markdown**: Showdown (Markdown to HTML)
- **State persistence**: `node-persist` (flat file), `localforage` (browser-side)
- **CSS**: Raw CSS files, no preprocessor. `st-tailwind.css` exists but is minimal

### Codebase Organization

```
server.js / src/server-main.js    -- Express app setup, middleware, startup
src/
  endpoints/                      -- REST API route handlers (one per domain)
    backends/                     -- LLM-specific proxy code
      chat-completions.js         -- OpenAI/Claude/Gemini/etc proxy
      text-completions.js         -- Text completion APIs
      kobold.js                   -- KoboldAI/KoboldCpp
    characters.js                 -- Character CRUD, PNG read/write
    worldinfo.js                  -- World Info/Lorebook server endpoints
    chats.js                      -- Chat history persistence
    extensions.js                 -- Extension management (install/update/delete)
    settings.js                   -- User settings
    secrets.js                    -- API key storage
    ... (40+ endpoint files)
  character-card-parser.js        -- PNG tEXt chunk read/write (V2 + V3)
  charx.js                        -- CHARX (ZIP-based) card format parser
  prompt-converters.js            -- Format conversion between API types
  tokenizers/                     -- Server-side tokenization
  middleware/                     -- Express middleware (auth, CORS proxy, etc)

public/
  script.js                       -- THE MONOLITH: 12,330 lines. Main app logic
  scripts/
    openai.js                     -- 6,895 lines. Chat completion prompt assembly
    world-info.js                 -- 6,193 lines. World Info/Lorebook system
    PromptManager.js              -- Prompt ordering, UI, token counting
    extensions.js                 -- Extension loader and manager
    events.js                     -- Event system (EventEmitter)
    st-context.js                 -- getContext() API for extensions
    macros.js                     -- Macro/variable substitution system
    instruct-mode.js              -- Instruct format templates
    chat-templates.js             -- Chat template auto-detection via hash
    textgen-settings.js           -- Text Generation WebUI settings
    tool-calling.js               -- Function/tool calling support
    group-chats.js                -- Multi-character group chat logic
    slash-commands/                -- Slash command parser and execution
    extensions/                   -- Built-in extensions
      memory/                     -- Chat summarization
      vectors/                    -- Vector/semantic search
      caption/                    -- Image captioning
      stable-diffusion/           -- Image generation
      tts/                        -- Text-to-speech
      translate/                  -- Translation
      quick-reply/                -- Quick reply macros
      regex/                      -- Regex message processing
    macros/                       -- New macro engine (experimental)
    templates/                    -- Handlebars template partials
```

### Server/Client Split

The server is a **dumb proxy + file store**. Almost all intelligence lives client-side:

- **Server responsibilities**: Serve static files, proxy API requests to LLM backends (adding auth headers, reformatting payloads), persist user data as flat JSON/PNG files on disk, manage user accounts, handle extension installation via git
- **Client responsibilities**: ALL prompt assembly, token counting, context management, UI rendering, world info scanning, macro substitution, extension orchestration

This is a deliberate design choice that means ST works even with backends that have no special support -- the server just forwards HTTP requests. The downside is that the client JS is enormous and complex.

### Build System

There is no real build step. The project uses:
- Webpack as a middleware (`src/middleware/webpack-serve.js`) to serve client modules on-the-fly
- ESLint for linting (`npm run lint`)
- No TypeScript compilation (uses JSDoc annotations with `@ts-check` and `jsconfig.json`)
- No minification in development
- Docker support via `Dockerfile` and `docker/docker-compose.yml`

---

## 2. Prompt Assembly Pipeline

This is the most complex part of SillyTavern. The pipeline differs between Chat Completion API (OpenAI-style) and Text Completion API (legacy/local) modes.

### Entry Point

`public/script.js` -> `Generate()` function (line ~4123, ~500 lines long). This is the master orchestrator.

### Chat Completion Pipeline (OpenAI mode)

The flow for Chat Completion APIs (`main_api === 'openai'`):

1. **`Generate()`** in `script.js`:
   - Resolves character card fields via `getCharacterCardFields()`
   - Processes regex replacements on chat messages
   - Calls `getWorldInfoPrompt()` to scan chat for WI triggers and get activated entries
   - Injects depth prompts, persona description, story string
   - Renders the story string via Handlebars context template
   - Calls `prepareOpenAIMessages()` in `openai.js`

2. **`prepareOpenAIMessages()`** in `openai.js` (line ~1435):
   - Converts raw chat messages into OpenAI message format via `setOpenAIMessages()`
   - Parses example dialogues via `setOpenAIMessageExamples()`
   - Calls `preparePromptsForChatCompletion()` to assemble all prompts
   - Calls `populateChatCompletion()` to fit everything within token budget

3. **`preparePromptsForChatCompletion()`** (line ~1260):
   - Creates system prompt entries for: `worldInfoBefore`, `worldInfoAfter`, `charDescription`, `charPersonality`, `scenario`, `impersonate`, `quietPrompt`, `groupNudge`, `bias`
   - Injects extension prompts: `summary` (memory), `authorsNote`, `vectorsMemory`, `vectorsDataBank`, `smartContext` (ChromaDB), `personaDescription`
   - Merges these with the PromptManager's user-defined prompt ordering
   - Applies character-specific system prompt and jailbreak overrides (supports `{{original}}` placeholder)
   - Returns the merged `PromptCollection`

4. **`populateChatCompletion()`** (line ~1078):
   - Creates a `ChatCompletion` object with a token budget = `maxContext - responseTokens`
   - Reserves 3 tokens for the assistant priming
   - Adds prompts in order: `worldInfoBefore`, `main` (system prompt), `worldInfoAfter`, `charDescription`, `charPersonality`, `scenario`, `personaDescription`
   - Reserves budget for control prompts (impersonate, quiet prompt)
   - Adds `nsfw`, `jailbreak`, user-relative prompts, absolute-position prompts
   - Handles in-chat injections at specific depths
   - Reserves budget for tool calling data
   - **Fills chat history in reverse chronological order** until budget exhausted via `populateChatHistory()`
   - Adds dialogue examples if budget allows (or pins them first if `pin_examples` is set)

5. **`populateChatHistory()`** (line ~836):
   - Iterates chat messages from newest to oldest
   - For each message: creates a `Message` object, counts tokens, checks if budget allows
   - Inlines media attachments (images, audio, video) if the model supports it
   - Stops adding messages when budget is exhausted (this is context overflow handling)

### Text Completion Pipeline

For non-OpenAI APIs (KoboldAI, text-generation-webui, etc.), the flow is different:

1. `Generate()` builds a flat text string rather than a message array
2. The story string (character card + world info + system prompt) is rendered via the Handlebars **context template**
3. Chat messages are appended in order, formatted with instruct sequences
4. In-chat injections are inserted at specific depths
5. The string is truncated from the beginning if it exceeds the context window

### Token Budgeting Strategy

The `ChatCompletion` class (line ~3580 in `openai.js`) manages a decreasing token budget:

```
Initial budget = maxContext - responseTokens - 3 (assistant priming)
```

Prompts are added in priority order. Each addition:
1. Checks `canAfford(message)` -- compares message tokens against remaining budget
2. If affordable, adds and decreases budget by token count
3. If not affordable, throws `TokenBudgetExceededError` (caught and skipped)

Chat history fills last, newest-first, until budget is exhausted. This means the system prompt, character card, and world info are **always prioritized** over old chat messages.

### Context Overflow Handling

- Old messages are simply dropped (not included in the prompt)
- The memory/summarization extension can preserve context by generating summaries
- The vector storage extension can retrieve semantically relevant old messages
- There is no automatic summarization -- it requires the memory extension to be enabled

---

## 3. Character Card Format

### V1 Format (Legacy TavernAI)

Simple flat JSON embedded in PNG tEXt chunk under keyword `chara`, base64-encoded:

```json
{
  "name": "string",
  "description": "string",
  "personality": "string",
  "scenario": "string",
  "first_mes": "string",
  "mes_example": "string"
}
```

### V2 Format (Current Standard)

Spec: https://github.com/malfoyslastname/character-card-spec-v2/blob/main/spec_v2.md

```typescript
type TavernCardV2 = {
  spec: 'chara_card_v2'
  spec_version: '2.0'
  data: {
    // V1 fields
    name: string
    description: string         // Character's core definition
    personality: string         // Personality summary
    scenario: string            // Current scenario/setting
    first_mes: string           // Initial greeting message
    mes_example: string         // Example dialogue ({{char}}/{{user}} format)

    // V2 additions
    creator_notes: string       // NOT used in prompts, displayed to users
    system_prompt: string       // Overrides system prompt (supports {{original}})
    post_history_instructions: string  // "Jailbreak" / post-history instruction
    alternate_greetings: string[]      // Additional first messages (swipeable)
    character_book?: CharacterBook     // Embedded lorebook
    tags: string[]              // For filtering, NOT used in prompts
    creator: string             // Card creator attribution
    character_version: string   // Version tracking
    extensions: Record<string, any>    // Arbitrary extension data
  }
}
```

The `CharacterBook` type mirrors the World Info entry format:
- `entries[]` with `keys`, `secondary_keys`, `content`, `enabled`, `insertion_order`, `constant`, `selective`, `position` ('before_char' | 'after_char'), `case_sensitive`, `priority`
- `scan_depth`, `token_budget`, `recursive_scanning`

### V3 Format (Emerging)

SillyTavern now writes **both** V2 and V3 chunks. From `src/character-card-parser.js`:

```javascript
// Write V2 chunk
chunks.splice(-1, 0, PNGtext.encode('chara', base64EncodedData));

// Try adding V3 chunk
const v3Data = JSON.parse(data);
v3Data.spec = 'chara_card_v3';
v3Data.spec_version = '3.0';
chunks.splice(-1, 0, PNGtext.encode('ccv3', base64EncodedData));
```

On read, V3 (`ccv3` keyword) takes precedence over V2 (`chara` keyword).

### CHARX Format

`src/charx.js` implements a ZIP-based format (`CharXParser` class) that bundles:
- `card.json` (the character card data)
- Avatar image
- Auxiliary assets (sprites/expressions, backgrounds)

This handles RisuAI-style exports with embedded assets and supports the `embeded://` URI scheme (note the intentional misspelling from RisuAI).

### SillyTavern Extensions to the Spec

SillyTavern stores additional data in `data.extensions`:
- `extensions.fav` -- favorite flag
- `extensions.depth_prompt` -- character-specific author's note with `depth` and `role` fields
- `extensions.talkativeness` -- for group chats
- `extensions.regex_scripts` -- character-specific regex replacements
- Custom extension data from third-party extensions

---

## 4. Memory and Context Management

### Chat Summarization (Memory Extension)

Located in `public/scripts/extensions/memory/index.js`.

The memory extension generates rolling summaries of chat history:

- **Sources**: Can use the main API, Extras API, or WebLLM (browser-local model)
- **Trigger**: Runs when a new message arrives and the chat exceeds a configurable length
- **Process**: Takes recent unsummarized messages, sends them with the existing summary to an LLM with a summarization prompt, stores the result in `chat_metadata`
- **Injection**: Summary is injected as extension prompt `1_memory` at a configurable position and depth
- **Token counting**: Uses `countSourceTokens()` to respect the source model's context limit

### Vector Storage Extension

Located in `public/scripts/extensions/vectors/`.

- Embeds chat messages and files using configurable embedding models
- Stores vectors locally via Vectra or externally
- On generation, retrieves semantically similar past messages and injects them as `3_vectors`
- Also supports a "Data Bank" (`4_vectors_data_bank`) for external document RAG

### World Info / Lorebooks

Located in `public/scripts/world-info.js` (6,193 lines -- one of the largest files).

#### Activation/Triggering System

The core scanning function is `checkWorldInfo()` (line ~4510). It implements a multi-pass recursive scanner:

1. **Budget calculation**: `budget = round(world_info_budget% * maxContext / 100)`, capped by `world_info_budget_cap`

2. **Entry sorting**: Entries are sorted by priority/order. Constant entries are processed first.

3. **Scan loop** (while `scanState`):
   - For each entry, checks:
     - Is it disabled?
     - Does it pass generation type trigger filter?
     - Does it pass character/tag filter?
     - Is it affected by timed effects (sticky, cooldown, delay)?
     - Is it delayed until a specific recursion level?
   - **Key matching**: Scans the last N messages (configurable `scan_depth`, default 2) for keyword matches
     - Supports regex keys, whole-word matching, case sensitivity
     - Selective entries require matches from both primary and secondary key lists (AND/OR logic configurable via `world_info_logic`)
   - If matched:
     - Probability check (can be configured per entry)
     - Budget check -- does the entry fit in remaining budget?
     - If yes, activate the entry
   - **Recursion**: If new entries were activated, their content is added to the scan text and another pass runs (if `world_info_recursive` is enabled)
   - Max recursion steps configurable via `world_info_max_recursion_steps`

4. **Minimum activations**: If `world_info_min_activations > 0`, scanning continues beyond normal depth until minimum entries are triggered

5. **Timed effects** (`WorldInfoTimedEffects` class, line ~480):
   - **Sticky**: Once activated, stays active for N messages
   - **Cooldown**: After deactivation, cannot reactivate for N messages
   - **Delay**: Cannot activate until N messages have passed since chat start

#### Injection Positions

Entries can be injected at multiple positions:
- `before_char` / `after_char` (relative to character definition)
- At specific depths in chat history
- As example messages
- Before/after Author's Note
- Into custom "outlets" (named injection points)

### Context Strategies (Context Templates)

Configurable via preset JSON files in `default/content/presets/context/`. Available presets include: ChatML, Alpaca, Llama 2 Chat, Llama 3 Instruct, Mistral V1-V7, Gemma 2, Command R, DeepSeek, and many more.

The context template uses Handlebars with these variables:
- `{{system}}` -- system prompt or character main prompt override
- `{{wiBefore}}` / `{{loreBefore}}` -- world info (before position)
- `{{wiAfter}}` / `{{loreAfter}}` -- world info (after position)
- `{{mesExamples}}` -- formatted example dialogues
- `{{anchorBefore}}` / `{{anchorAfter}}` -- extension prompts at before/after story positions
- `{{description}}`, `{{personality}}`, `{{scenario}}`, `{{persona}}`, `{{char}}`, `{{user}}`

---

## 5. Extension System

### Architecture

Extensions are loaded from `public/scripts/extensions/` (built-in) or downloaded via git into a user data directory. Each extension has a `manifest.json`:

```json
{
  "display_name": "Extension Name",
  "loading_order": 1,
  "requires": [],
  "optional": [],
  "js": "index.js",
  "css": "style.css",
  "author": "...",
  "version": "1.0.0"
}
```

The extension loader (`public/scripts/extensions.js`) discovers manifests, loads scripts/styles, and activates them.

### Context API

Extensions access SillyTavern internals via `getContext()` from `st-context.js`. This returns a massive object exposing:

- `chat`, `characters`, `groups`, `name1`, `name2`, `characterId`, `groupId`
- `eventSource`, `eventTypes` -- the event system
- `generate`, `sendStreamingRequest`, `stopGeneration` -- generation controls
- `tokenizers`, `getTokenCountAsync` -- tokenization
- `extensionPrompts`, `setExtensionPrompt` -- prompt injection
- `addOneMessage`, `deleteMessage`, `deleteLastMessage` -- chat manipulation
- `saveChat`, `saveMetadata`, `saveChatConditional` -- persistence
- `SlashCommandParser`, `registerSlashCommand` -- slash commands
- `MacrosParser` -- macro registration
- `ToolManager` -- function/tool calling registration
- Much more (100+ exported functions/objects)

Extensions run in the **same browser context** with full DOM access -- there is no sandboxing.

### Event System

The `eventSource` (`public/scripts/events.js`) is an EventEmitter supporting ~80+ event types:

**Generation lifecycle**: `GENERATION_STARTED`, `GENERATION_AFTER_COMMANDS`, `GENERATION_STOPPED`, `GENERATION_ENDED`, `GENERATE_BEFORE_COMBINE_PROMPTS`, `GENERATE_AFTER_COMBINE_PROMPTS`, `GENERATE_AFTER_DATA`

**Message events**: `MESSAGE_SENT`, `MESSAGE_RECEIVED`, `MESSAGE_EDITED`, `MESSAGE_DELETED`, `MESSAGE_UPDATED`, `MESSAGE_SWIPED`

**Chat events**: `CHAT_CHANGED`, `CHAT_LOADED`, `CHAT_CREATED`, `CHAT_DELETED`

**Character events**: `CHARACTER_EDITED`, `CHARACTER_DELETED`, `CHARACTER_DUPLICATED`, `CHARACTER_RENAMED`

**Settings events**: `SETTINGS_LOADED`, `SETTINGS_UPDATED`, `CHATCOMPLETION_SOURCE_CHANGED`, `CHATCOMPLETION_MODEL_CHANGED`, `OAI_PRESET_CHANGED_BEFORE/AFTER`

**World Info events**: `WORLD_INFO_ACTIVATED`, `WORLDINFO_UPDATED`, `WORLDINFO_FORCE_ACTIVATE`, `WORLDINFO_SCAN_DONE`

**Streaming**: `STREAM_TOKEN_RECEIVED`, `STREAM_REASONING_DONE`

**Connection**: `ONLINE_STATUS_CHANGED`, `CONNECTION_PROFILE_LOADED/CREATED/DELETED/UPDATED`

### Built-in Extensions

| Extension | Location | Purpose |
|-----------|----------|---------|
| Memory | `extensions/memory/` | Chat summarization |
| Vectors | `extensions/vectors/` | Semantic search / RAG |
| Caption | `extensions/caption/` | Image captioning |
| Stable Diffusion | `extensions/stable-diffusion/` | Image generation |
| TTS | `extensions/tts/` | Text-to-speech |
| Translate | `extensions/translate/` | Message translation |
| Quick Reply | `extensions/quick-reply/` | Macro buttons |
| Regex | `extensions/regex/` | Message find/replace |
| Expressions | `extensions/expressions/` | Character sprite emotions |
| Assets | `extensions/assets/` | Asset management |
| Token Counter | `extensions/token-counter/` | Token count display |
| Attachments | `extensions/attachments/` | File attachments |
| Gallery | `extensions/gallery/` | Image gallery |
| Connection Manager | `extensions/connection-manager/` | Connection profiles |

### Server Plugins

Separate from UI extensions, server plugins (`plugins/`, loaded by `src/plugin-loader.js`) can register Express routes and middleware. They run in Node.js context.

---

## 6. Prompt Templates

### Instruct Mode Templates

Defined in `public/scripts/instruct-mode.js`. Each instruct preset specifies:

- `input_sequence` / `input_suffix` -- wraps user messages
- `output_sequence` / `output_suffix` -- wraps assistant messages
- `system_sequence` / `system_suffix` -- wraps system messages
- `first_input_sequence`, `last_input_sequence`, `first_output_sequence`, `last_output_sequence` -- special sequences for first/last messages
- `story_string_prefix` / `story_string_suffix` -- wraps the entire story string
- `stop_sequence` -- stop strings
- `names_behavior` -- whether to include character names (`NONE`, `FORCE`, `ALWAYS`)
- `activation_regex` -- auto-detect which instruct template to use based on model name
- `bind_to_context` -- link instruct preset to context template

### Chat Template Auto-Detection

`public/scripts/chat-templates.js` maps SHA-256 hashes of tokenizer chat templates to instruct presets. When a model's `tokenizer_config.json` chat template hash matches, the correct instruct format is auto-selected. Covers Llama 3, Mistral V2-V7, Gemma 2, Command R, DeepSeek, GLM-4, Tulu, and more.

### Macro System

`public/scripts/macros.js` and `public/scripts/macros/macro-system.js` implement a rich variable substitution system.

**Built-in macros** (used everywhere -- prompts, cards, lorebooks, quick replies):
- `{{char}}`, `{{user}}` -- character and user names
- `{{description}}`, `{{personality}}`, `{{scenario}}`, `{{persona}}` -- card fields
- `{{mesExamples}}` -- example dialogues
- `{{lastMessage}}`, `{{lastMessageId}}` -- recent message content/index
- `{{time}}`, `{{date}}`, `{{weekday}}`, `{{isotime}}`, `{{isodate}}` -- temporal
- `{{idle_duration}}` -- time since last user message
- `{{random:A,B,C}}` -- random selection
- `{{roll:NdM}}` -- dice rolls
- `{{getvar::name}}`, `{{setvar::name::value}}` -- local variables
- `{{getglobalvar::name}}`, `{{setglobalvar::name::value}}` -- global variables
- `{{if ...}}...{{/if}}` -- conditional rendering
- `{{trim}}` -- remove surrounding newlines

**Extension macros**: Extensions can register custom macros via `MacrosParser.registerMacro()` or the new experimental macro engine.

**Scoped syntax**: Macros support scoped content blocks: `{{macroName arg}}content{{/macroName}}`

There is also a new **experimental macro engine** (`public/scripts/macros/macro-system.js`) that provides a more structured registration API with categories, descriptions, and proper argument handling.

---

## 7. Backend Support

### Main API Types

SillyTavern has two top-level API modes:

1. **Chat Completion** (`main_api === 'openai'`): OpenAI-compatible message arrays
2. **Text Completion**: Raw text prompts (KoboldAI, text-generation-webui, NovelAI)
3. **KoboldAI (Horde)**: AI Horde distributed inference

### Chat Completion Sources

From `chat_completion_sources` in `openai.js` -- **25 backends**:

| Source | Key |
|--------|-----|
| OpenAI | `openai` |
| Azure OpenAI | `azure_openai` |
| Claude (Anthropic) | `claude` |
| Google Gemini (MakerSuite) | `makersuite` |
| Vertex AI | `vertexai` |
| OpenRouter | `openrouter` |
| Mistral AI | `mistralai` |
| Cohere | `cohere` |
| Perplexity | `perplexity` |
| Groq | `groq` |
| DeepSeek | `deepseek` |
| AI21 | `ai21` |
| xAI | `xai` |
| Fireworks AI | `fireworks` |
| Moonshot | `moonshot` |
| ElectronHub | `electronhub` |
| Chutes | `chutes` |
| NanoGPT | `nanogpt` |
| AIML API | `aimlapi` |
| Pollinations | `pollinations` |
| CometAPI | `cometapi` |
| SiliconFlow | `siliconflow` |
| ZAI | `zai` |
| Custom (OpenAI-compatible) | `custom` |

### Text Completion Sources

From `textgen_types` in `textgen-settings.js` -- **15 backends**:

| Source | Key |
|--------|-----|
| text-generation-webui (oobabooga) | `ooba` |
| KoboldCpp | `koboldcpp` |
| llama.cpp | `llamacpp` |
| vLLM | `vllm` |
| Aphrodite | `aphrodite` |
| TabbyAPI | `tabby` |
| Ollama | `ollama` |
| Mancer | `mancer` |
| Together AI | `togetherai` |
| InfermaticAI | `infermaticai` |
| DreamGen | `dreamgen` |
| OpenRouter | `openrouter` |
| Featherless | `featherless` |
| HuggingFace | `huggingface` |
| Generic (OpenAI-compatible) | `generic` |

### Abstraction Layer

The server-side routing (`src/endpoints/backends/chat-completions.js`) dispatches to per-provider handler functions:
- `sendClaudeRequest()` -- Anthropic Messages API format conversion
- `sendMakerSuiteRequest()` -> `getGeminiBody()` -- Gemini-specific format (function declarations, tool configs)
- `sendAI21Request()` -- AI21 Jamba format
- Most others just forward to an OpenAI-compatible endpoint

Client-side, `openai.js` handles provider-specific quirks:
- Model list fetching and display per provider
- Provider-specific parameters (reasoning effort, verbosity)
- `createGenerationParameters()` (line ~2449) builds the request body with provider-specific fields
- Cost calculation per provider (OpenRouter, ElectronHub, Chutes)

### Tool/Function Calling

`public/scripts/tool-calling.js` provides a `ToolManager` singleton:
- Extensions register tools via `ToolManager.registerFunctionTool()` with a name, description, JSON schema parameters, and an action callback
- Tools are serialized to OpenAI function calling format
- Supports recursive tool calls up to `ToolManager.RECURSE_LIMIT`
- Stealth tools can execute without showing results in chat

---

## 8. UI Architecture

### Frontend Framework

**None**. This is vanilla JavaScript with jQuery. The UI is built from:
- A single `index.html` with inline templates
- `script.js` (12,330 lines) as the main controller
- ~80 module files in `public/scripts/`
- jQuery for DOM manipulation and events
- jQuery UI for draggable panels
- Custom popup system (`popup.js`)
- CSS animations and transitions

### State Management

State is managed through **module-level variables** exported from various files:

- `script.js` exports: `chat`, `characters`, `name1`, `name2`, `this_chid`, `online_status`, `max_context`, `chat_metadata`, etc.
- Settings are in `power_user` (from `power-user.js`), `oai_settings` (from `openai.js`), `extension_settings` (from `extensions.js`)
- No state management library. Changes propagate through direct mutation + event emission
- Settings are persisted by serializing to JSON and POSTing to the server

### UI Patterns

- **Drawers/Panels**: Collapsible sections using jQuery slideToggle
- **MovingUI**: Draggable, resizable panels (desktop mode)
- **Select2**: Enhanced dropdowns for model selection
- **Toastr**: Toast notifications
- **Sortable**: Drag-and-drop reordering (prompt manager, world info)
- **Tag system**: Character and chat tagging with filtering

### Code Quality Assessment

**The honest truth**: The codebase is a classic "organic growth" project:

- `script.js` at 12,330 lines is a God Object containing the `Generate()` function, message handling, character management, UI event handlers, and more
- `openai.js` at 6,895 lines mixes prompt assembly logic, UI rendering, model-specific code, and cost calculation
- `world-info.js` at 6,193 lines combines scanning logic, entry management, UI rendering, and slash commands
- Heavy use of jQuery-style global state mutation
- No TypeScript (JSDoc annotations only, inconsistently applied)
- Limited test coverage (there is a `tests/` directory but it's minimal)
- The CONTRIBUTING.md acknowledges "Our standards are pretty low"
- Variable naming is inconsistent (`oai_settings` vs `power_user` vs `extension_settings`)
- Some comments like `//do nothing? why does this check exist?` in the Generate function

**However**, it works reliably for millions of users and supports an extraordinary breadth of backends and features. The event system and extension API are well-designed. The prompt assembly pipeline, while complex, is logically structured.

---

## 9. Known Problems

### From GitHub Issues (394 open as of 2026-03-15)

**Top issues by engagement**:
- Accessibility (screen reader support) -- large ongoing effort in PRs #5098, #5284
- Swipe history on every AI message (#4573) -- large architectural change
- Justified gallery thumbnails (#4173) -- long-running CSS issue
- Negative depth for world info (#3344) -- feature request, under consideration
- Experimental Macro Engine causing UI lags (#5266)
- Gemini doubling output (#2960) -- API-specific bug
- Branch navigation UI (#5283) -- chat branching visualization

**Common complaint categories** (from issues and community):
1. **Complexity**: The settings are overwhelming for new users. Dozens of interconnected options for prompt assembly
2. **Mobile experience**: Mobile styling issues, safe-area-inset problems (#4729)
3. **API-specific bugs**: Different backends have different quirks that surface as bugs (Gemini doubling, Claude impersonation failures)
4. **Context management confusion**: Users don't understand why messages disappear from context or why world info doesn't trigger
5. **Performance**: Large lorebooks with recursive scanning can be slow; the experimental macro engine reportedly causes UI lag

### Development Velocity

- **Dominant contributor**: Cohee1207 with 7,087 commits (80%+ of all commits). This is essentially a one-person project with helpers
- **Secondary contributors**: Wolfsblvt (806 commits), RossAscends (371 commits)
- **Recent activity** (March 2026): Multiple PRs merged per week. Active development continues
- **Branch model**: PRs target `staging`, then merge to `release` after testing
- **Soft limit**: 200 lines per PR (per CONTRIBUTING.md)

---

## 10. Code Patterns and What to Steal

### Patterns Worth Stealing

1. **Prompt Manager with drag-and-drop ordering**: The `PromptManager` class allows users to visually reorder all prompt components, enable/disable them, set injection positions/depths. This is the killer UX feature that lets power users control exactly what goes into the prompt.

2. **Token-budget-first prompt assembly**: The `ChatCompletion` class with `reserveBudget()` / `freeBudget()` / `canAfford()` is a clean pattern. Prompts are added by priority, chat history fills the remainder. Simple and effective.

3. **World Info recursive scanning with timed effects**: The sticky/cooldown/delay system for lorebook entries is sophisticated and enables dynamic storytelling. Entries that activate other entries via recursive scanning create emergent behavior.

4. **Chat template auto-detection via hash**: Hashing the tokenizer's chat template and mapping to instruct presets is clever. Means models can be auto-configured without manual selection.

5. **Extension context API**: `getContext()` providing a single object with all application state and functions is a good pattern for extension systems. Easy to discover, easy to use.

6. **Character card PNG embedding**: Using PNG tEXt chunks to embed JSON metadata directly in the avatar image is brilliant for distribution. One file = complete character. The V2 spec's `extensions` field ensures forward compatibility.

7. **Macro system**: The `{{variable}}` substitution with conditionals, scoped content, and extension registration is powerful and user-friendly.

### Patterns to Avoid

1. **Monolithic files**: 12K-line script.js, 7K-line openai.js. These should be broken into focused modules.

2. **Client-side everything**: All prompt assembly and token counting happens in the browser. This means the logic can't be reused server-side, tested easily, or used headlessly.

3. **jQuery + global state**: Makes the codebase hard to reason about. Any code can mutate any state at any time.

4. **No TypeScript**: JSDoc annotations are inconsistently applied. A competing project should use TypeScript from day one.

5. **Flat file storage**: Everything persisted as JSON files on disk. Works for single-user, breaks for any multi-user scenario beyond basic auth.

6. **Bus factor of 1**: 80%+ commits from one person. The architecture reflects one person's mental model.

### Architecture Decisions for a Competitor

If building a competing product, the key insights from studying SillyTavern:

1. **The prompt assembly pipeline is the core product**. Everything else is UI around it. Get this right and modular.
2. **Backend abstraction must be a first-class concern**. 40+ backends means endless format translation.
3. **World Info / Lorebooks are the power feature** that distinguishes roleplay frontends from generic chat UIs.
4. **Extension system is essential** -- the community will build what you can't.
5. **Character card compatibility is table stakes** -- must support V2/V3 PNG cards and CHARX.
6. **Token counting must be accurate** -- this requires per-model tokenizers, which is complex.

---

## Sources

- [SillyTavern GitHub Repository](https://github.com/SillyTavern/SillyTavern)
- [DeepWiki - SillyTavern Architecture](https://deepwiki.com/SillyTavern/SillyTavern)
- [DeepWiki - Prompt Management and Construction](https://deepwiki.com/SillyTavern/SillyTavern/3.3-prompt-management-and-construction)
- [DeepWiki - World Info System](https://deepwiki.com/SillyTavern/SillyTavern/6.1-world-info-system)
- [DeepWiki - Extension Framework](https://deepwiki.com/SillyTavern/SillyTavern/8-extension-framework)
- [Character Card V2 Specification](https://github.com/malfoyslastname/character-card-spec-v2/blob/main/spec_v2.md)
- [SillyTavern Official Docs - Writing Extensions](https://docs.sillytavern.app/for-contributors/writing-extensions/)
- [SillyTavern Official Docs - World Info](https://docs.sillytavern.app/usage/core-concepts/worldinfo/)
- [SillyTavern Official Docs - Context Template](https://docs.sillytavern.app/usage/prompts/context-template/)
- [SillyTavern Official Docs - Macros](https://docs.sillytavern.app/usage/core-concepts/macros/)
- [World Info Encyclopedia (Community)](https://rentry.co/world-info-encyclopedia)
