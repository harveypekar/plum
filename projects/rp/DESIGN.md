# RP Chat — Design Document

Roleplay chat plugin for [aiserver](../aiserver/). Manages character cards, scenarios, prompt templates, and conversations with streaming LLM responses via Ollama.

## Quick Start

```bash
cd projects/aiserver
source .venv/bin/activate
DATABASE_URL='postgresql://plum:Simatai0!@localhost/plum' python main.py
```

UI at `http://localhost:8080/rp/`.

**Prerequisites:**
- PostgreSQL running (`pgvector/pgvector:pg17` Docker image)
- Ollama running at `localhost:11434`
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
                                      └── db.init_schema() — creates tables on startup
```

### File Layout

```
projects/rp/
├── __init__.py       # Plugin entry point: register(app, ollama, resolve_model)
├── routes.py         # All FastAPI routes under /rp/
├── db.py             # asyncpg CRUD (pool with JSONB codec)
├── models.py         # Pydantic request/response models
├── pipeline.py       # Pre/post processing pipeline + template engine
├── context.py        # Context window strategies (SlidingWindow)
├── cards.py          # SillyTavern PNG import/export (tEXt chunk with base64 JSON)
├── schema.sql        # PostgreSQL table definitions
├── requirements.txt  # asyncpg, Pillow, python-multipart
└── static/
    ├── index.html    # Single-page app (dark theme, all CSS inline)
    └── app.js        # Client logic (IIFE, safe DOM via el() helper)
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `rp_character_cards` | Character cards (name, card_data JSONB, avatar BYTEA) |
| `rp_prompt_templates` | Reusable prompt templates (name, content TEXT) |
| `rp_scenarios` | Scenarios (name, description, settings JSONB) |
| `rp_conversations` | Conversations linking user card + AI card + scenario + model |
| `rp_messages` | Messages with role, content, sequence, raw_response JSONB |

Tables are auto-created on startup via `init_schema()`.

## API Routes

All routes are under `/rp/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/rp/cards` | List all character cards |
| POST | `/rp/cards` | Create card |
| POST | `/rp/cards/import` | Import SillyTavern PNG |
| GET | `/rp/cards/{id}` | Get card |
| PUT | `/rp/cards/{id}` | Update card |
| DELETE | `/rp/cards/{id}` | Delete card |
| GET | `/rp/cards/{id}/avatar` | Get card avatar PNG |
| GET | `/rp/cards/{id}/export` | Export card as SillyTavern PNG |
| GET | `/rp/templates` | List prompt templates |
| POST | `/rp/templates` | Create template |
| GET | `/rp/templates/{id}` | Get template |
| PUT | `/rp/templates/{id}` | Update template |
| DELETE | `/rp/templates/{id}` | Delete template |
| GET | `/rp/scenarios` | List scenarios |
| POST | `/rp/scenarios` | Create scenario |
| GET | `/rp/scenarios/{id}` | Get scenario |
| PUT | `/rp/scenarios/{id}` | Update scenario |
| DELETE | `/rp/scenarios/{id}` | Delete scenario |
| GET | `/rp/conversations` | List conversations |
| POST | `/rp/conversations` | Create conversation |
| GET | `/rp/conversations/{id}` | Get conversation detail |
| DELETE | `/rp/conversations/{id}` | Delete conversation |
| POST | `/rp/conversations/{id}/message` | Send message (streams NDJSON) |
| PUT | `/rp/messages/{id}` | Edit message |
| DELETE | `/rp/messages/{id}` | Delete message |
| POST | `/rp/conversations/{id}/regenerate` | Regenerate last AI response |

## Prompt Templates

Templates define how the system prompt is assembled from card data and scenario. They are stored in the `rp_prompt_templates` table and selected per scenario via `settings.template_id`.

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

After the template is rendered, a second pass replaces these variables in the assembled system prompt:

| Variable | Replacement |
|----------|-------------|
| `${user}` | User card name |
| `${char}` | AI card name |
| `${scenario}` | Scenario description |

These work in the system prompt only (not in user messages).

### Default Template

When no template is selected, this built-in default is used:

```
{{#scenario}}Scenario: {{scenario}}

{{/scenario}}{{#description}}Character: {{description}}

{{/description}}{{#personality}}Personality: {{personality}}

{{/personality}}{{#mes_example}}Example dialogue:
{{mes_example}}{{/mes_example}}
```

### Where Templates Are Used

```
Scenario settings.template_id → db.get_template() → pipeline ctx["prompt_template"]
    → assemble_prompt() renders template with card/scenario values
    → expand_variables() replaces ${user}/${char}/${scenario}
    → apply_context_strategy() trims messages to fit token budget
    → system prompt + last user message sent to Ollama
```

## Pipeline

The processing pipeline runs hooks before sending to the LLM (pre) and after receiving the response (post).

**Pre-hooks (in order):**
1. `assemble_prompt` — Render prompt template into system prompt
2. `expand_variables` — Replace `${user}`, `${char}`, `${scenario}` in system prompt
3. `apply_context_strategy` — Fit messages within token budget (default: sliding window, 2048 tokens)

**Post-hooks:**
1. `clean_response` — Strip whitespace from LLM response

### Context Strategies

| Strategy | Behavior |
|----------|----------|
| `sliding_window` | Drop oldest messages first, always keep first message (greeting) |

Configured via `scenario.settings.context_strategy`. Token counting uses `len(text) // 4` as approximation.

## Streaming Protocol

Chat responses stream as NDJSON (`application/x-ndjson`). Each line is a JSON object:

```jsonl
{"debug_prompt": "...", "debug_messages": [...]}   # First chunk: assembled prompt (for Under the Hood)
{"token": "Hello"}                                  # Content token
{"token": " there", "thinking": true}               # Thinking token (hidden by default in UI)
{"done": true, "total_duration": ..., ...}          # Final chunk with Ollama stats
{"error": "...", "done": true}                      # Error (if any)
```

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
| `context_strategy` | string | `"sliding_window"` | Context window strategy |
| `max_context_tokens` | int | `2048` | Token budget for message history |
| `model` | string | — | Model override (bypasses conversation model) |
| `template_id` | int | — | Prompt template ID (null = use default) |

## SillyTavern Card Format

Cards use the SillyTavern v2 format: a PNG image with JSON data base64-encoded in a `chara` tEXt chunk. The `card_data` JSONB column stores the decoded JSON, which typically has a `data` sub-object containing `name`, `description`, `personality`, `first_mes`, `mes_example`, `scenario`, and `tags`.

On import, the PNG itself is stored as `avatar` (BYTEA). On export, the card data is re-encoded into a PNG tEXt chunk.
