# RP Chat — Design Document

Roleplay chat plugin for [aiserver](../aiserver/). Manages character cards, scenarios, prompt templates, and conversations with streaming LLM responses via Ollama. Includes scene state tracking, rolling summaries, A/B eval, few-shot examples, MCP tool integration, and stock phrase rewriting.

## Quick Start

```bash
cd projects/aiserver
source .venv/bin/activate
DATABASE_URL="$DATABASE_URL" python main.py
```

UI at `http://localhost:8080/rp/`.

**Prerequisites:**
- PostgreSQL with pgvector (`pgvector/pgvector:pg17` Docker image)
- Ollama running on the Windows host (accessed via wsl-gateway from WSL2)
- Python venv with aiserver + rp dependencies installed

```bash
cd projects/aiserver
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r ../rp/requirements.txt
```

## Architecture

RP is a FastAPI plugin loaded by aiserver via `config.json`:

```
aiserver/main.py → load_plugins() → rp/__init__.py:register()
                                      ├── routes.setup() — mounts all /rp/* routes
                                      ├── eval_routes.setup_eval_routes() — A/B eval routes
                                      └── db.init_schema() — creates tables on startup
```

### File Layout

```
projects/rp/
├── __init__.py        # Plugin entry point: register(app, ollama, resolve_model)
├── routes.py          # FastAPI routes under /rp/ (chat, cards, scenarios, conversations)
├── eval_routes.py     # A/B eval endpoints (compare, select, list)
├── prompt_builder.py  # Prompt assembly, budget calculation, Ollama option building
├── db.py              # asyncpg CRUD (pool with JSONB codec)
├── models.py          # Pydantic request/response models
├── pipeline.py        # Pre/post processing pipeline + Mustache-lite template engine
├── context.py         # Context window strategies (SlidingWindow, SummaryBuffer)
├── scene_state.py     # Scene state prompt building, cleaning, hallucination validation
├── summarize.py       # Rolling conversation summaries (used by SummaryBuffer)
├── budget.py          # Context budget allocation for injections (research, fewshot)
├── cards.py           # SillyTavern PNG import/export (tEXt chunk with base64 JSON)
├── fewshot.py         # Vector-similarity few-shot example retrieval
├── research.py        # Web research dispatch for grounding responses
├── stock_phrases.py   # Detect and rewrite cliché stock phrases via LLM
├── mcp_client.py      # MCP (Model Context Protocol) tool router
├── conv_log.py        # Conversation logging (prompts, responses, scene state)
├── tokenizer.py       # Token counting (tiktoken cl100k_base)
├── schema.sql         # PostgreSQL table definitions + migrations
├── prompt.md          # Default prompt template (re-read each request)
├── requirements.txt   # asyncpg, Pillow, python-multipart, tiktoken
└── static/
    ├── index.html     # Single-page app (dark theme, all CSS inline)
    └── app.js         # Client logic (IIFE, safe DOM via el() helper)
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `rp_character_cards` | Character cards (name, card_data JSONB, avatar BYTEA) |
| `rp_scenarios` | Scenarios (name, description, settings JSONB, first_message) |
| `rp_conversations` | Conversations linking user card + AI card + scenario + model + scene_state |
| `rp_messages` | Messages with role, content, sequence, raw_response, budget_json, prompt_json |
| `rp_first_message_cache` | Cached first messages keyed by hash (card + scenario + model) |
| `rp_fewshot_examples` | Few-shot examples with vector(768) embeddings for similarity search |
| `rp_conversation_summaries` | Rolling summaries with through_msg_id and through_sequence |
| `rp_eval_sets` | A/B eval sets (conversation_id, sequence, selected_id, preference_tags) |
| `rp_eval_candidates` | Generated candidates per eval set (label, model, config, content) |
| `rp_eval_metrics` | Eval metrics (domain, target_type, scores JSONB) |

Tables are auto-created on startup via `init_schema()`.

## API Routes

All routes are under `/rp/`.

**Cards:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/rp/cards` | List all character cards |
| POST | `/rp/cards` | Create card |
| POST | `/rp/cards/import` | Import SillyTavern PNG |
| POST | `/rp/cards/generate` | Generate a full card via LLM |
| POST | `/rp/cards/generate-field` | Generate a single card field via LLM |
| GET | `/rp/cards/{id}` | Get card |
| PUT | `/rp/cards/{id}` | Update card |
| DELETE | `/rp/cards/{id}` | Delete card |
| PUT | `/rp/cards/{id}/avatar` | Upload card avatar PNG |
| GET | `/rp/cards/{id}/avatar` | Get card avatar PNG |
| GET | `/rp/cards/{id}/export` | Export card as SillyTavern PNG |
| POST | `/rp/cards/{id}/extract-scenario` | Extract scenario from card data via LLM |

**Scenarios:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/rp/scenarios` | List scenarios |
| POST | `/rp/scenarios` | Create scenario |
| GET | `/rp/scenarios/{id}` | Get scenario |
| PUT | `/rp/scenarios/{id}` | Update scenario |
| DELETE | `/rp/scenarios/{id}` | Delete scenario |

**Conversations & Messages:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/rp/conversations` | List conversations |
| POST | `/rp/conversations` | Create conversation |
| GET | `/rp/conversations/{id}` | Get conversation detail (with messages) |
| DELETE | `/rp/conversations/{id}` | Delete conversation |
| POST | `/rp/conversations/{id}/restart` | Delete all messages, re-generate greeting |
| POST | `/rp/conversations/{id}/message` | Send message (streams NDJSON, MCP tool loop) |
| POST | `/rp/conversations/{id}/regenerate` | Regenerate last AI response (streams NDJSON) |
| POST | `/rp/conversations/{id}/continue` | Continue from truncated response (streams NDJSON) |
| POST | `/rp/conversations/{id}/auto-reply` | Generate next turn for whichever side (streams NDJSON) |
| POST | `/rp/conversations/{id}/save-partial` | Save partially streamed response to DB |
| PUT | `/rp/messages/{id}` | Edit message content |
| DELETE | `/rp/messages/{id}` | Delete message |

**Scene State & Summaries:**

| Method | Path | Description |
|--------|------|-------------|
| PUT | `/rp/conversations/{id}/scene-state` | Manually update scene state |
| POST | `/rp/conversations/{id}/refresh-scene-state` | Force re-generate scene state from messages |
| GET | `/rp/conversations/{id}/summaries` | List rolling summaries |
| POST | `/rp/conversations/{id}/summarize` | Force summary generation |

**A/B Eval:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/rp/conversations/{id}/compare` | Generate candidates with different configs |
| POST | `/rp/eval-sets/{id}/select` | Select winning candidate |
| GET | `/rp/eval-sets/{id}` | Get eval set detail with candidates |
| GET | `/rp/conversations/{id}/eval-sets` | List eval sets for conversation |

## Prompt Templates

Templates define how the system prompt and post-prompt are assembled from card data and scenario. They are stored in the `rp_prompt_templates` table and selected per scenario via `settings.template_id`.

A template has two sections separated by markdown headers:

- **`## system`** — The main system prompt (character description, personality, scenario context)
- **`## post`** — Behavioral directives injected as the final system message after chat history

### Template Syntax (Mustache-lite)

**Simple substitution:**
```
Character: {{description}}
```

**Conditional sections** (only rendered if the variable is non-empty):
```
{{#personality}}Personality: {{personality}}

{{/personality}}
```

### Available Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `{{scenario}}` | Scenario description | The scenario text |
| `{{description}}` | AI card `data.description` | Character description |
| `{{personality}}` | AI card `data.personality` | Character personality |
| `{{mes_example}}` | AI card `data.mes_example` | Example dialogue |
| `{{char}}` | AI card `data.name` | Character name |
| `{{user}}` | User card `data.name` | User's character name |

### Variable Expansion (Post-Template)

After the template is rendered, a second pass replaces these variables in both the system prompt and post prompt:

| Variable | Replacement |
|----------|-------------|
| `${user}` | User card name |
| `${char}` | AI card name |
| `${scenario}` | Scenario description |

### Default Template

When no template is selected, this built-in default is used:

```
## system
{{#scenario}}Scenario: {{scenario}}

{{/scenario}}{{#description}}Character: {{description}}

{{/description}}{{#personality}}Personality: {{personality}}

{{/personality}}{{#mes_example}}Example dialogue:
{{mes_example}}{{/mes_example}}

## post
Write only {{char}}'s next response. Stay in character. Do not narrate {{user}}'s actions.
```

### How It Works

```
prompt.md (re-read each request)
    → _split_template() splits by ## system / ## post headers
    → assemble_prompt() renders each section with card/scenario values
    → expand_variables() replaces ${user}/${char}/${scenario} in both sections
    → apply_context_strategy() trims messages to fit token budget
    → system section → first message in chat messages array
    → conversation messages → structured [{role, content}] array
    → post section → final system message in chat messages array
    → Sent to Ollama /api/chat with stop sequences
```

## Pipeline

The processing pipeline (`pipeline.py`) runs hooks before sending to the LLM (pre) and after receiving the response (post).

**Pre-hooks (in order):**
1. `assemble_prompt` — Read `prompt.md` template, render Mustache-lite sections into `system_prompt` + `post_prompt`
2. `expand_variables` — Replace `${user}`, `${char}`, `${scenario}` in system and post prompts
3. `apply_context_strategy` — Fit messages within token budget using configured strategy

**Post-hooks (in order):**
1. `clean_response` — Strip whitespace and character name prefix from LLM response
2. `stock_phrase_rewriter` — Detect cliché phrases and rewrite them via LLM (if configured)

### Context Strategies

| Strategy | Behavior |
|----------|----------|
| `sliding_window` | Drop oldest messages first, always keep first message (greeting) |
| `summary_buffer` | Inject rolling summary into context, only load messages after `summary.through_sequence`. Stale summaries (where `through_sequence >= max(msg sequences)`) are ignored. |

Configured via `scenario.settings.context_strategy`. Default is `summary_buffer`. Token counting uses tiktoken (`cl100k_base`).

## Streaming Protocol

Chat responses stream to the frontend as NDJSON (`application/x-ndjson`). Each line is a JSON object:

```jsonl
{"debug_prompt": "...", "debug_user_prompt": "...", "debug_messages": [...], "debug_summary": "..."}
{"token": "Hello"}                                  # Content token
{"token": " there", "thinking": true}               # Thinking token (hidden by default in UI)
{"tool_call": "search", "args": {...}}              # MCP tool invocation (send_message only)
{"tool_result": "search", "preview": "..."}         # MCP tool result
{"done": true, "total_duration": ..., ...}          # Final chunk with Ollama stats
{"error": "...", "done": true}                      # Error (if any)
```

The first chunk is the debug header with the assembled prompt, post-prompt, message history, and (if present) the current rolling summary. The `send_message` endpoint supports multi-round MCP tool calls (up to 3 rounds).

## UI Features

- **Chat view** — Scenario banner at top, colored dialogue (lime green for user quotes, magenta for AI quotes), streaming with thinking sections
- **Under the Hood** — Two tabs: "System Prompt" (the assembled prompt sent to LLM) and "Raw Response" (Ollama stats)
- **Cards view** — Grid of character cards, drag-and-drop SillyTavern PNG import, inline editor
- **Scenarios view** — List with editor (model override, context strategy, template selection)
- **Templates view** — CRUD for prompt templates with placeholder documentation

## Scenario Settings

Stored as JSONB in `rp_scenarios.settings`:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `context_strategy` | string | `"summary_buffer"` | Context window strategy |
| `model` | string | — | Model override (bypasses conversation model) |
| `num_ctx` | int | `16384` | Context window size |
| `num_predict` | int | `768` | Max tokens to generate |
| `temperature` | float | `1.05` | Sampling temperature |
| `repeat_penalty` | float | `1.08` | Repeat penalty |
| `min_p` | float | `0.1` | Min-p sampling |

Ollama options from scenario settings are merged with `CHAT_DEFAULTS` from `prompt_builder.py` and passed through to the Ollama `/api/chat` request. `num_predict` is dynamically scaled based on user message length via `scale_num_predict()` (floor=1024, ceiling=2048, formula: `max(floor, min(ceiling, user_tokens * 2))`).

## Scene State

Scene state tracks concrete physical facts about the current scene (location, clothing, restraints, position, props, mood). It is generated and updated by a dedicated LLM call after each message exchange.

**Flow:**
1. After each assistant message is saved, `_auto_update_scene_state()` fires as a background task
2. It reads the N most recent messages since the last scene state update
3. `build_scene_state_prompt()` (in `scene_state.py`) assembles the prompt with previous state, personality hints, and scenario context
4. The response is cleaned (`clean_scene_state_response`) and validated against hallucination (`validate_scene_state`)
5. Validated state is saved to `rp_conversations.scene_state` and injected into the system prompt

**Hallucination validation:** For each category that changed, `validate_scene_state()` checks whether the new content words appear in the source messages. Changes without evidence are reverted to the previous value. Interpretive categories (mood, voice) skip validation.

Scene state uses a dedicated model (`q36` = qwen3:latest) via `_scene_state_model`.

## Rolling Summaries

Long conversations use rolling summaries to fit within context windows. The `SummaryBuffer` strategy injects the latest summary into context and only loads messages after `through_sequence`.

**Flow:**
1. After each assistant message, `_maybe_summarize()` fires as a background task
2. If unsummarized message count exceeds threshold (10), a summary is generated
3. `build_summary_prompt()` includes previous summary + new messages for incremental summarization
4. Summary is stored in `rp_conversation_summaries` with `through_msg_id` and `through_sequence`

Summaries use a dedicated model (`q8` = qwen3:8b) via `SUMMARY_MODEL`.

## SillyTavern Card Format

Cards use the SillyTavern v2 format: a PNG image with JSON data base64-encoded in a `chara` tEXt chunk. The `card_data` JSONB column stores the decoded JSON, which typically has a `data` sub-object containing `name`, `description`, `personality`, `first_mes`, `mes_example`, `scenario`, and `tags`.

On import, the PNG itself is stored as `avatar` (BYTEA). On export, the card data is re-encoded into a PNG tEXt chunk.

## A/B Eval (Compare)

The compare endpoint generates multiple responses in parallel with different model configs, stores them as candidates, and lets the user pick a winner.

**Flow:**
1. `POST /rp/conversations/{id}/compare` receives user message + list of `CompareConfig` (label, model, temperature, num_predict)
2. Creates an `rp_eval_sets` row, then generates candidates concurrently via `asyncio.gather`
3. Each candidate is saved to `rp_eval_candidates` with its content, raw response, and prompt/budget JSON
4. `POST /rp/eval-sets/{id}/select` saves the selected candidate as the official assistant message and records preference tags
