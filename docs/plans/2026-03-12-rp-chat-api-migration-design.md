# RP Chat: Migrate to /api/chat + Post-History Instructions

Date: 2026-03-12

## Problem

The RP chat uses Ollama's `/api/generate` (text completion), sending conversation history as a flat `Name: content` text blob. This causes:

1. **Name duplication** — history format prepends `Name:`, model adds it again, accumulates over turns
2. **Multi-turn generation** — model has no structural turn boundary, generates both sides of the conversation
3. **No stop boundary** — flat text gives no signal for "stop here, user's turn"

## Solution

Migrate to Ollama's `/api/chat` endpoint with structured messages, and add a post-history instruction slot.

## Design

### 1. Ollama Client — `chat_stream()` method

New method alongside existing `generate_stream()`:

- Accepts `model`, `messages: [{role, content}, ...]`, `options`
- Uses `/api/chat` endpoint
- Yields same chunk format (`{token, thinking, done}`) — streaming UI unchanged
- `generate_stream()` stays untouched for other aiserver uses

### 2. Prompt Template — Structured messages

Template sections change from `## system` + `## prompt` to `## system` + `## post`:

- `## system` — Character/world context (same as today)
- `## post` — Behavioral directives, injected as final system message after all chat history (most influential prompt position)
- `## prompt` and `{{mes_history}}` removed entirely — history sent as structured messages

Final message array:

```
system   →  rendered ## system
assistant →  first_mes
user      →  message 1
assistant →  message 2
...
system   →  rendered ## post  (post-history instruction)
```

### 3. Pipeline Changes

- `assemble_prompt` — Renders `system_prompt` + `post_prompt`, passes messages as structured list
- `expand_variables` — Also expands variables in `post_prompt`
- `apply_context_strategy` — Operates on message array (same sliding window logic)
- `_format_history()` removed
- Pipeline context produces `system_prompt`, `post_prompt`, `messages[]` (no more `user_prompt`)

### 4. Routes

- `send_message` and `regenerate` use `chat_stream()`
- Assemble: `[system] + messages + [post system]`
- Pass stop sequences (`["<user_name>:"]`) as safety net
- Debug output shows structured messages

### 5. Template Migration

```markdown
## system
You are writing an immersive, engaging roleplay with {{user}} where you are {{char}}.
{{#scenario}}Scenario: {{scenario}}
{{/scenario}}{{#description}}Character: {{description}}
{{/description}}{{#personality}}Personality: {{personality}}
{{/personality}}{{#mes_example}}
Example dialogue, do not repeat:
{{mes_example}}
{{/mes_example}}
The genres are: romance, slice of life
Tones are: introspective, cute, feminine
The writing style is: third person, vivid sensory detail and inner monologue
Frequently reference physical character descriptions.
Use graphic, verbose and vivid detail for actions.
Respond authentically based on character believability
Continue the story, prefer "yes, and" and "no, but"

## post
Write only {{char}}'s next response in this collaborative story.
Keep writing in character. Stay in the current scene.
Do not narrate {{user}}'s actions or dialogue.
Write 2-3 paragraphs per response.
Leave space for {{user}} to respond.
```

## Changes by File

| Component | Change |
|---|---|
| `aiserver/ollama.py` | Add `chat_stream()` using `/api/chat` |
| `rp/pipeline.py` | `assemble_prompt` produces `system_prompt` + `post_prompt` + message array. Remove `_format_history()` and `{{mes_history}}`. Add `## post` parsing. Update default template. |
| `rp/routes.py` | Use `chat_stream()`. Assemble messages array. Pass stop sequences. Update debug output. |
| `rp/prompt.md` | Move behavioral directives to `## post`. Remove `## prompt` / `{{mes_history}}` |

## What Doesn't Change

- Streaming UI, chunk format, card management, scenario settings
- Context strategies, variable expansion
- Under the Hood panel (just shows different content)
