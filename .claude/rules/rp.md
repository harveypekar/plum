---
paths:
  - "projects/rp/**"
---

# RP — Roleplay Chat System

FastAPI plugin for aiserver. Character chat with SillyTavern v2 card format, streaming LLM via Ollama, and MCP tool integration.

## Commands

```bash
# Run (via aiserver)
cd projects/aiserver && source .venv/bin/activate
DATABASE_URL="$DATABASE_URL" python main.py
# UI at http://localhost:8080/rp/

# Test
pytest projects/rp/tests/
```

## Architecture

- Plugin: `__init__.py:register(app, ollama, resolve_model)` called by aiserver at startup
- DB: PostgreSQL with asyncpg, JSONB columns. Schema auto-created via `init_schema()`
- Streaming: NDJSON (first chunk = debug prompt, middle = tokens, final = Ollama stats)
- Cards: SillyTavern v2 PNG with base64 JSON in `chara` tEXt chunk

## Key Files

- `routes.py` — FastAPI endpoints (`/rp/cards`, `/rp/scenarios`, `/rp/conversations`)
- `pipeline.py` — Pre/post hooks (assemble_prompt, expand_variables, context strategy)
- `context.py` — Context window strategy (SlidingWindow: drop oldest, keep greeting)
- `cards.py` — SillyTavern PNG import/export
- `db.py` — asyncpg CRUD with JSONB codec
- `models.py` — Pydantic schemas
- `static/app.js` — Vanilla JS SPA (IIFE, `el()` DOM helper, streaming NDJSON)
- `schema.sql` — 5 tables: cards, scenarios, conversations, messages, first_message_cache
- `DESIGN.md` — Architecture & API reference (read before major changes)

## Conventions

- Async/await throughout — all DB and HTTP calls are async
- Context dict pattern: `ctx` dict passed through pipeline with keys `user_card`, `ai_card`, `scenario`, `messages`, `system_prompt`, `post_prompt`, `scene_state`
- Prompt templating: Mustache-lite (`{{var}}`, `{{#var}}...{{/var}}`)
- Variable expansion: two-pass (template render, then `${user}/${char}/${scenario}` substitution)
- Frontend: vanilla JS IIFE, `el()` helper for safe DOM, no framework
