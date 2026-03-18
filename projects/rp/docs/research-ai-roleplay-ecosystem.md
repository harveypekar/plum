# AI Roleplay Tools & Ecosystem: Technical Survey

*Date: 2026-03-15*

---

## 1. DreamGen

**GitHub org:** [DreamGenX](https://github.com/DreamGenX)

### Open-Source Components

DreamGen's open-source footprint is modest. Their GitHub account (DreamGenX) has:

- **DreamGenTrain** (14 stars) — Simple DPO/preference-tuning scripts built on [Unsloth](https://github.com/unslothai/unsloth). Contains `dpo.py` and `merge.py`. Practical tips on learning rates, beta, and DPO vs IPO. References WandB runs from the Bagel model series. [Source](https://github.com/DreamGenX/DreamGenTrain)

- **scenario-spec** (1 star) — A TypeScript/Zod schema defining DreamGen's "Scenario" format for structured storytelling. This is the most architecturally interesting piece. [Source](https://github.com/DreamGenX/scenario-spec)

- Forks of AutoAWQ, axolotl, TensorRT-LLM, torchtune, unsloth-zoo, SillyTavern, FramePack — internal development forks, no novel code.

Their main product (dreamgen.com) is closed-source.

### Scenario Spec: Structured Storytelling Approach

The scenario-spec is a Zod-validated TypeScript schema that goes well beyond character cards. Key concepts:

**Format types:** `"story"` or `"role_play"` — determines valid placeholders and interaction types.

**Entities** with typed kinds:
```typescript
entityKindSchema = z.enum(['character', 'character_user', 'location', 'item'])
```
Each entity has:
- `id` (UUID), `label` (for placeholder references like `{{label}}`), `kind`
- `display` data (name, markdown description, images)
- `definition` data (name for prompts, description)

**Scenario definition** includes:
- `description` — the scenario/world description
- `pastEvents` — summary of events before session start
- `style` — writing style instructions
- `start` — array of initial interactions
- `examples` — example interactions with descriptions

**Interactions** are typed messages:
- `instruction` — system-level directives
- `text` — narrative text blocks
- `message` — character messages with `role` (bot/user), optional `characterId` (UUID)

Each interaction has a `prompt` object with `priority` (for context window management, max 0, default -1) and `excluded` flag.

**Placeholder validation** is built in — the schema checks that all `{{label}}` references in descriptions resolve to actual entity labels.

**Key insight:** DreamGen treats RP as a structured document problem, not just a chat prompt. Entities are first-class objects with UUIDs, not just text blobs. This enables multi-character scenarios where each character has distinct identity and can be referenced by ID. [Source](https://github.com/DreamGenX/scenario-spec/tree/main/package/src)

---

## 2. Maid (Mobile Artificial Intelligence Distribution)

**GitHub:** [Mobile-Artificial-Intelligence/maid](https://github.com/Mobile-Artificial-Intelligence/maid) — 2,400 stars

### Architecture

- **Framework:** React Native (Expo) with TypeScript
- **Platform:** Android (Google Play + GitHub releases)
- **Local inference:** Uses [`llama.rn`](https://github.com/mybigday/llama.rn) — a React Native binding for llama.cpp
- **Remote providers:** Anthropic, DeepSeek, Mistral, Novita, Ollama, OpenAI — each has its own context provider (`context/language-model/`)

### How It Runs Models on Mobile

The `llama.tsx` context provider shows the approach:
1. User picks a GGUF file (via `expo-document-picker` or downloads from curated HuggingFace list)
2. Validates GGUF magic bytes (`0x47 0x47 0x55 0x46`)
3. Calls `initLlama()` from `llama.rn` which loads the model via llama.cpp's C++ engine compiled for ARM
4. Messages are converted to OpenAI-compatible format (`RNLlamaOAICompatibleMessage`) with multimodal support (images)
5. Inference runs on-device — no server needed

### Character Card Support

Maid does **not** appear to support SillyTavern character cards directly. It has:
- Custom system prompts and "assistant persona" settings
- Conversation export/import as JSON
- No evidence of PNG metadata parsing or V2/V3 card import in the codebase

### Notable Design

- Supabase backend for optional account sync
- Companion TTS app ([Maise](https://github.com/Mobile-Artificial-Intelligence/maise))
- Material You theming
- MIT licensed, no telemetry

[Source](https://github.com/Mobile-Artificial-Intelligence/maid)

---

## 3. Jan

**GitHub:** [janhq/jan](https://github.com/janhq/jan) — 41,081 stars

### Architecture

- **Desktop framework:** Tauri (Rust backend + web frontend)
- **Frontend:** React/TypeScript (Vite), lives in `web-app/`
- **Backend:** Rust (`src-tauri/`) with a plugin system
- **Model runtime:** Bundled llama.cpp extension (`extensions/llamacpp-extension/`) and MLX support (`mlx-server/` for Apple Silicon, `extensions/mlx-extension/`)

### Extension System

Jan's architecture is plugin-based. Key extensions in `extensions/`:
- `assistant-extension` — AI assistant management
- `conversational-extension` — chat/conversation handling
- `download-extension` — model download management
- `llamacpp-extension` — llama.cpp inference engine
- `mlx-extension` — Apple MLX inference
- `rag-extension` — retrieval-augmented generation
- `vector-db-extension` — vector database for RAG

### Chat Handling

Conversations are managed through the `conversational-extension`. Jan uses a file-based data model — threads and messages are stored as JSON files in a local `~/jan/` directory. Each thread has metadata and a message history file.

### RP-Specific Features

Jan has **no RP-specific features**. It is designed as a general-purpose ChatGPT replacement focused on:
- Model discovery and download from HuggingFace
- OpenAI-compatible API server mode
- Clean, productivity-oriented UX

No character card support, no persona system, no lorebook/world info. To use Jan for RP, users would manually craft system prompts.

[Source](https://github.com/janhq/jan)

---

## 4. Open WebUI

**GitHub:** [open-webui/open-webui](https://github.com/open-webui/open-webui) — 127,306 stars

### Architecture

- **Backend:** Python (FastAPI), in `backend/open_webui/`
- **Frontend:** Svelte/SvelteKit
- **Database:** SQLite or PostgreSQL via SQLAlchemy + Alembic migrations
- **Primary integration:** Ollama, OpenAI API, and any OpenAI-compatible endpoint

### Backend Structure (routers)

Extensive API surface: `chats.py`, `models.py`, `memories.py`, `knowledge.py`, `retrieval.py`, `tools.py`, `functions.py`, `pipelines.py`, `skills.py`, `images.py`, `audio.py`, `terminals.py`, `channels.py`, `notes.py`, `evaluations.py`, etc.

Notable for RP: `memories.py` (persistent memory), `knowledge.py` (knowledge bases/RAG), `functions.py`/`tools.py` (extensible function calling), `pipelines.py` (custom processing pipelines).

### RP Usage

Open WebUI has **no built-in RP features**, but its extensibility makes it usable:

- **Model presets:** Users create custom model profiles with RP system prompts
- **Pipelines:** The pipeline system allows custom pre/post-processing of messages, which can inject character definitions
- **Knowledge bases:** Can be used as a lorebook equivalent via RAG
- **Memories:** Persistent memory feature can track character/session state
- **Functions/Tools:** Extension points for custom logic

There are no known RP-specific forks or extensions in the public ecosystem. The community using Open WebUI for RP typically:
1. Sets up a custom system prompt per "model" (acting as a character profile)
2. Uses knowledge bases for world info
3. Connects to RP-tuned models via Ollama or a compatible API

The lack of character card import, greeting messages, or example dialogue formatting means significant manual setup compared to purpose-built RP frontends.

[Source](https://github.com/open-webui/open-webui)

---

## 5. Character Card Ecosystem

### V1 Spec (TavernCard V1)

The original format, standardized retroactively. [Source](https://github.com/malfoyslastname/character-card-spec-v2/blob/main/spec_v1.md)

```typescript
type TavernCardV1 = {
  name: string        // Character name
  description: string // Character description (included in every prompt)
  personality: string // Short personality summary
  scenario: string    // Current context/circumstances
  first_mes: string   // Opening greeting message
  mes_example: string // Example conversations (uses <START> delimiter)
}
```

**Embedding:** JSON string, base64-encoded, stored in the PNG `tEXt` chunk named `chara`. (The V1 spec originally said "EXIF metadata field" but the actual implementation across all tools uses PNG tEXt chunks.)

**Magic strings:** `{{char}}` / `<BOT>` replaced with character name; `{{user}}` / `<USER>` replaced with user's display name. Case-insensitive.

### V2 Spec (TavernCard V2)

Approved May 2023. Maintained by malfoyslastname. [Source](https://github.com/malfoyslastname/character-card-spec-v2/blob/main/spec_v2.md)

Key additions over V1:
- **`system_prompt`** — Botmaker-defined system prompt that MUST override the user's global system prompt by default
- **`post_history_instructions`** — Instructions injected after conversation history (the "jailbreak" / "UJB" position). MUST override user's setting by default
- **`alternate_greetings`** — Array of alternative opening messages
- **`character_book`** — Embedded lorebook (see Lorebook section below)
- **`creator_notes`** — Never included in prompts, for botmaker-to-user communication
- **`tags`**, **`creator`**, **`character_version`** — Metadata
- **`extensions`** — `Record<string, any>` for platform-specific data
- **`{{original}}`** placeholder — In system_prompt/post_history_instructions, replaced with what the frontend would have used otherwise

**Structure change:** V2 nests all fields under `data` to prevent V1-only editors from silently destroying V2 fields:
```typescript
type TavernCardV2 = {
  spec: 'chara_card_v2'
  spec_version: '2.0'
  data: { /* all fields */ }
}
```

**Embedding:** Same PNG tEXt chunk (`chara`), same base64 encoding. Detection: if `spec` field exists and equals `'chara_card_v2'`, it's V2.

### V3 Spec (CCv3)

Created by kwaroran (RisuAI developer). Status: Living Standard. [Source](https://github.com/kwaroran/character-card-spec-v3/blob/main/SPEC_V3.md)

Major additions:

**New embedding formats:**
- **CHARX** — A ZIP archive containing `card.json` at root plus embedded assets. Uses `.charx` extension. Assets organized by type (`assets/{type}/images/`, etc.)
- **PNG `ccv3` chunk** — New tEXt chunk named `ccv3` (separate from V2's `chara` chunk). If both exist, `ccv3` takes precedence
- PNG embedded assets via `chara-ext-asset_:{path}` tEXt chunks (deprecated in favor of CHARX)

**New fields:**
```typescript
interface CharacterCardV3 {
  spec: 'chara_card_v3'
  spec_version: '3.0'
  data: {
    // ... all V2 fields plus:
    assets?: Array<{type: string, uri: string, name: string, ext: string}>
    nickname?: string                              // Alternative {{char}} replacement
    creator_notes_multilingual?: Record<string, string>  // i18n creator notes
    source?: string[]                              // Provenance tracking
    group_only_greetings: Array<string>            // Greetings only for group chats
    creation_date?: number                         // Unix timestamp (seconds)
    modification_date?: number                     // Unix timestamp (seconds)
  }
}
```

**Asset types:** `icon` (character portraits), `background`, `user_icon`, `emotion`/`expression` (sprites). URIs can be `embeded://path`, `ccdefault:`, HTTP(S), or base64 data URLs.

**Lorebook decorators** — The biggest V3 innovation. Decorators are inline directives in lorebook entry `content` fields:
```
@@depth 5
@@activate_only_after 3
@@ignore_on_max_context

Prompt text here
```

Decorator examples:
- `@@depth N` — Insert at position N in the prompt
- `@@reverse_depth N` — Position from the end
- `@@role system|user|assistant` — Set the message role
- `@@scan_depth N` — Override lorebook-level scan_depth
- `@@activate_only_after N` — Only activate after N turns
- `@@activate_only_every N` — Activate every N turns
- `@@ignore_on_max_context` — Skip if context is full

Fallback decorators use `@@@` and chain: if a decorator is unsupported, the fallback is tried.

**New lorebook field:** `use_regex: boolean` — enables regex matching for keys.

**Implementation status:** SillyTavern has full CHARX support. RisuAI (created by the V3 spec author) has full support. Other frontends vary.

### V4 (Proposed)

A [V4 spec proposal](https://github.com/MnemoTeam/ccv4) exists (MnemoTeam) with 0 stars — appears to be very early/inactive. No adoption.

### PNG Metadata Embedding Format (Technical Detail)

The PNG format uses chunks. Character card data is stored in a `tEXt` chunk:

1. **Chunk structure:** 4-byte length + 4-byte type (`tEXt`) + data + 4-byte CRC32
2. **Keyword:** `chara` (V1/V2) or `ccv3` (V3)
3. **Null separator** between keyword and value
4. **Value:** The character card JSON, UTF-8 encoded, then base64 encoded

SillyTavern's `src/png/encode.js` shows the implementation — it constructs PNG chunks from scratch, inserting the `tEXt` chunk with the card data between other PNG chunks (after IHDR, before IEND).

For reading, tools use PNG chunk parsers (like `png-chunks-extract`) to find the `chara` or `ccv3` tEXt chunk, extract the base64 value, decode it, and parse as JSON.

[SillyTavern source](https://github.com/SillyTavern/SillyTavern/blob/main/src/png/encode.js), [SillyTavern CHARX parser](https://github.com/SillyTavern/SillyTavern/blob/main/src/charx.js)

### Card Sharing Sites

**Chub.ai (formerly characterhub.org / chub.ai):**
- Largest character card repository
- Hosts V1, V2, and V3 cards
- Cards downloadable as PNG (with embedded JSON) or JSON
- API available for programmatic access
- Tags, ratings, creator profiles
- Separate "lorebooks" section for standalone world info
- NSFW/SFW toggle and content warnings

**Venus.chub.ai:**
- Chub's built-in chat frontend — allows chatting directly with hosted characters
- Connects to various API providers

**Pygmalion Booru (booru.plus/+pygmalions):**
- One of the original card repositories
- More informal, community-driven
- NSFW-oriented

**RisuRealm (realm.risuai.net):**
- RisuAI's card sharing platform
- Supports V3/CHARX format natively
- Growing community

**JanitorAI:**
- Large commercial card platform with its own chat frontend
- Hosts character cards but uses a proprietary format internally
- Can import/export in Tavern-compatible formats

---

## 6. Lorebook / World Info Standards

### Common Format

The V2 spec's `CharacterBook` type has become the de facto lorebook standard:

```typescript
type CharacterBook = {
  name?: string
  description?: string
  scan_depth?: number       // How many recent messages to scan for keyword matches
  token_budget?: number     // Max tokens for all activated entries
  recursive_scanning?: boolean  // Can entry content trigger other entries?
  extensions: Record<string, any>
  entries: Array<{
    keys: Array<string>          // Trigger keywords
    content: string              // Text injected into prompt when triggered
    extensions: Record<string, any>
    enabled: boolean
    insertion_order: number      // Lower = inserted earlier/higher in prompt
    case_sensitive?: boolean
    name?: string
    priority?: number            // Lower priority = discarded first at budget limit
    id?: number
    comment?: string
    selective?: boolean          // Require match from BOTH keys and secondary_keys
    secondary_keys?: Array<string>
    constant?: boolean           // Always active regardless of key matching
    position?: 'before_char' | 'after_char'
  }>
}
```

### Platform Differences

**SillyTavern** has the richest implementation:
- "Character Book" (embedded in card) vs "World Info" (standalone global lorebooks)
- Multiple lorebooks can be stacked
- Advanced features: regex keys, probability-based activation, group weight, automation ID
- Uses `extensions` field heavily for ST-specific features (e.g., `extensions.depth`, `extensions.role`)
- Exports in `.json` format

**RisuAI:**
- Full V3 decorator support (since the spec author develops RisuAI)
- Supports regex keys, conditional activation
- CHARX-embedded lorebooks

**AgnAI (Agnaistic):**
- Supports the core V2 lorebook format
- Uses `priority` for token budget management
- "Memory: Chat History Depth" maps to `scan_depth`

**Standalone lorebook export** (V3):
```typescript
{ spec: 'lorebook_v3', data: Lorebook }
```

### Key Behavioral Differences

- **Scan depth:** How many messages are scanned for keyword matches varies. Some scan full history, some only last N messages.
- **Recursive scanning:** Whether activated entry content can trigger other entries. Powerful but can cause token budget blowouts.
- **Insertion position:** V2 only had `before_char`/`after_char`. V3 decorators add arbitrary depth positioning, role assignment, etc.
- **Token counting:** Different frontends count tokens differently (some use tiktoken, some approximate). Budget enforcement varies.

---

## 7. Emerging Trends (2025-2026)

### RAG for Character Voice & Memory

The most active area of innovation:

- **Long-term memory via vector search:** SillyTavern's "Vector Storage" extension and Jan's `rag-extension` both index past conversations for retrieval. For RP, this means characters can "remember" events from hundreds of messages ago.
- **Character knowledge bases:** Open WebUI's knowledge feature and SillyTavern's Data Bank allow uploading documents that get retrieved contextually — effectively a dynamic lorebook powered by embeddings rather than keyword matching.
- **Summarization chains:** Multiple frontends now offer automatic summarization of older conversation segments, keeping a compressed "memory" in context while freeing tokens for new content.

### Tool Use & Function Calling in RP

Emerging but still niche:
- **SillyTavern extensions** can call external tools (image generation, web search, dice rolling)
- **RisuAI** supports MCP (Model Context Protocol) clients — listed in their GitHub topics
- **DreamGen's interaction model** includes `instruction` type interactions, hinting at tool-use patterns
- Community experiments with models that output structured actions (e.g., `[ROLL: 2d6]`, `[GENERATE_IMAGE: description]`) parsed by the frontend

### Multi-Agent RP

- **Group chats** are a standard feature in SillyTavern, RisuAI, and AgnAI — multiple characters take turns responding
- **V3 spec** added `group_only_greetings` specifically for multi-character scenarios
- **DreamGen's entity system** with UUIDs and multiple `character` entities is designed for multi-agent scenarios
- **AgnAI** was built from the start as "Multi-user and Multi-bot" — supports multiple human users chatting with multiple AI characters simultaneously
- Experimental: community projects using agent frameworks (LangChain, CrewAI) where each character is an independent agent with its own memory and goals

### Persistent Memory & State

- **Open WebUI's `memories` system** — stores persistent facts that are injected into future conversations
- **SillyTavern variables** — `{{getvar::}}` / `{{setvar::}}` allow lorebook entries to track state across the conversation
- **Character state tracking:** Some advanced card creators use lorebook entries that activate based on turn count (`@@activate_only_after N` in V3) to simulate character development/relationship progression
- Community interest in "world state" systems that track locations, inventory, relationships — essentially lightweight game engines integrated with the chat

### Structured Output & Steering

- Growing use of **regex-based output formatting** (SillyTavern's regex extension can post-process model output)
- **JSON mode / structured generation** from models used to extract character actions, emotions, scene descriptions separately
- **Classifier-guided generation:** Running a small model to score outputs for in-character consistency before displaying them
- **Grammar-constrained generation** via llama.cpp's GBNF grammars to enforce output format

### CHARX as Standard Package Format

The V3 spec's CHARX format (ZIP archive) is gaining traction as the way to distribute rich characters:
- Embedded sprites/expressions for visual novel-style experiences
- Background images per scene
- Bundled lorebooks
- Potential for embedded LoRAs or voice samples

SillyTavern has full CHARX import/export. RisuAI created it. Adoption is still early but the direction is clear — cards are becoming multimedia packages.

---

## 8. Model Recommendations for RP (2025-2026)

### Current Community Favorites

Based on community discussions, HuggingFace model cards, and fine-tune releases:

**Large (65B+) — Best Quality:**
- **Llama 3.1 70B** and **Llama 3.3 70B** — Strong base for RP, good instruction following. Widely recommended on r/LocalLLaMA.
- **Qwen 2.5 72B** — Excellent multilingual RP, strong creative writing. Available in various quants.
- **Mistral Large (123B)** — Used via API; strong narrative ability.
- **DeepSeek V3 / R1** — Gaining traction for creative tasks due to large context and strong reasoning.

**Medium (13B-34B) — Best Balance:**
- **Qwen 2.5 32B** — The sweet spot for many users. Strong RP capability at runnable size.
- **Mistral Small 24B** — Good creative writing for its size.
- **Command R+ 35B** — Strong at following complex character instructions.
- **Llama 3.1 8B fine-tunes** — Surprisingly capable with good fine-tuning.

**Small (7B-13B) — Mobile/Low-End:**
- **Qwen 2.5 7B** — Best small model for RP in the community consensus.
- **Phi-3.5 / Phi-4** — Microsoft's small models, good at instruction following.
- **Gemma 2 9B** — Competitive at its size.
- **Llama 3.2 3B** — For mobile/edge deployment (what Maid targets).

### Notable RP Fine-Tunes

The fine-tune ecosystem is very active. Key creators and series:

- **Sao10k's L3-Lunaris, Euryale** series — Among the most popular RP fine-tunes, based on Llama 3 / 3.1. Known for vivid prose and strong character adherence. Available on HuggingFace.
- **NeverSleep's Llama-3-Lumimaid** — RP-focused fine-tune, popular in the SillyTavern community.
- **Lewdiculous / Pantheon** series — Various RP-optimized merges and fine-tunes.
- **DreamGen's own models** — DreamGen Opus series, trained with their DPO pipeline. Focused on structured storytelling.
- **WinterGoddess's Nethena** — RP fine-tune series.
- **Epicitious's Arcee and Luminia** — RP/creative writing fine-tunes.

### Quantization & Context

- **GGUF Q4_K_M** is the standard "good enough" quantization for most users
- **EXL2** (ExLlamaV2) for GPU-only users wanting the best speed/quality ratio
- **AWQ** for vLLM/API serving
- Context lengths: 8K-32K typical for RP. 128K context models exist (Llama 3.1, Qwen 2.5) but most RP sessions don't need it — summarization + lorebook is more token-efficient than raw context stuffing
- **Speculative decoding** gaining adoption for faster generation with large models

### API-Based Options

For users not running local models:
- **Claude 3.5 Sonnet / Opus** — Widely considered the best for RP quality, but expensive and has content filters
- **GPT-4o** — Good quality, moderate content restrictions
- **Google Gemini 2.0** — Large context window, increasingly popular
- **DeepSeek API** — Very cheap, surprisingly good for creative tasks
- **OpenRouter** — Aggregator that provides access to many models through a single API, popular in the RP community for model-hopping

---

## Other Notable Projects

### RisuAI
- **GitHub:** [kwaroran/Risuai](https://github.com/kwaroran/Risuai) — 1,357 stars
- TypeScript, Tauri-based desktop app
- Created the V3 spec and CHARX format
- Has its own card sharing platform (RisuRealm)
- Supports MCP clients
- Strong focus on advanced card features (expressions, backgrounds, decorators)

### AgnAI (Agnaistic)
- **GitHub:** [luminai-companion/agn-ai](https://github.com/luminai-companion/agn-ai) — 698 stars
- TypeScript, web-based (self-hosted or hosted)
- Multi-user and multi-bot from the ground up
- Scale-oriented architecture (MongoDB backend)
- V2 card support, lorebook support
- Good for shared/multiplayer RP scenarios

### SillyTavern (for reference)
- **GitHub:** [SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern) — 24,378 stars
- The dominant RP frontend
- Node.js/Express backend, vanilla JS frontend
- Full V2/V3/CHARX support
- Extensive extension system (vector storage, image gen, TTS, regex, etc.)
- The de facto standard that other tools measure against

---

## Key Takeaways

1. **The character card spec is the lingua franca.** V2 is universally supported. V3 is gaining adoption but still led by RisuAI/SillyTavern. Any new RP tool must support at least V2 import/export to tap into the existing card ecosystem.

2. **DreamGen's scenario-spec is the most advanced structured approach** but has near-zero adoption outside DreamGen itself. The UUID-based entity system and typed interactions are architecturally superior to character cards for complex scenarios but lack ecosystem support.

3. **General-purpose tools (Jan, Open WebUI) are poor fits for RP** without significant customization. They lack character cards, lorebooks, greeting messages, and the prompt engineering features that RP users expect.

4. **Mobile RP is underserved.** Maid is the main option and it lacks character card support. There's a clear gap for a mobile-first RP frontend with proper card/lorebook support.

5. **The lorebook is becoming the programmable layer.** V3 decorators essentially turn lorebook entries into a lightweight scripting system for prompt construction. This is where the most innovation is happening.

6. **RAG + summarization is replacing brute-force context.** Rather than relying on 128K context windows, the community is moving toward smarter memory management with vector search and progressive summarization.

7. **CHARX is the future format** for distributing characters as rich multimedia packages, not just text blobs in PNG metadata.

---

## Sources

- [Character Card V1 Spec](https://github.com/malfoyslastname/character-card-spec-v2/blob/main/spec_v1.md)
- [Character Card V2 Spec](https://github.com/malfoyslastname/character-card-spec-v2/blob/main/spec_v2.md)
- [Character Card V3 Spec](https://github.com/kwaroran/character-card-spec-v3/blob/main/SPEC_V3.md)
- [DreamGen Scenario Spec](https://github.com/DreamGenX/scenario-spec)
- [DreamGen Training Scripts](https://github.com/DreamGenX/DreamGenTrain)
- [Maid GitHub](https://github.com/Mobile-Artificial-Intelligence/maid)
- [Jan GitHub](https://github.com/janhq/jan)
- [Open WebUI GitHub](https://github.com/open-webui/open-webui)
- [SillyTavern GitHub](https://github.com/SillyTavern/SillyTavern)
- [RisuAI GitHub](https://github.com/kwaroran/Risuai)
- [AgnAI GitHub](https://github.com/luminai-companion/agn-ai)
- [SillyTavern CHARX Parser](https://github.com/SillyTavern/SillyTavern/blob/main/src/charx.js)
- [SillyTavern PNG Encoder](https://github.com/SillyTavern/SillyTavern/blob/main/src/png/encode.js)
- [character-card-utils npm](https://www.npmjs.com/package/character-card-utils)
