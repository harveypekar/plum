---
name: rp-report
description: Generate a detailed quality report for an RP conversation by ID
---

# RP Report

Generate a comprehensive quality report for a roleplay conversation.

## Arguments

Takes a conversation ID as the argument (e.g., `/rp-report 89`).

## Output

Always write the full report to `projects/rp/reports/conv-<ID>.md`. Create the `reports/` directory if it doesn't exist. Do not print the report to the conversation — write it all to the file, then tell the user the file path.

## Instructions

### 1. Fetch conversation data

Run these SQL queries via `bash -c 'set -a && source /mnt/d/prg/plum/.env && set +a && psql "$DATABASE_URL" ...'`:

**Metadata:**
```sql
SELECT c.id, c.model, c.scene_state, c.category,
       u.name as user_name, a.name as ai_name,
       s.name as scenario_name, s.description as scenario_desc,
       s.first_message
FROM rp_conversations c
JOIN rp_character_cards u ON c.user_card_id = u.id
JOIN rp_character_cards a ON c.ai_card_id = a.id
LEFT JOIN rp_scenarios s ON c.scenario_id = s.id
WHERE c.id = <ID>
```

**Messages (with pipeline context):**
```sql
SELECT id, role, content, sequence, system_prompt, scene_state, post_prompt, budget_json,
       created_at::text
FROM rp_messages WHERE conversation_id = <ID> ORDER BY sequence
```

**Stats:**
```sql
SELECT COUNT(*) as total,
  COUNT(*) FILTER (WHERE role = 'user') as user_msgs,
  COUNT(*) FILTER (WHERE role = 'assistant') as ai_msgs,
  SUM(length(content)) as total_chars,
  SUM(length(content)) FILTER (WHERE role = 'user') as user_chars,
  SUM(length(content)) FILTER (WHERE role = 'assistant') as ai_chars,
  MIN(created_at)::date as started,
  MAX(created_at)::date as ended
FROM rp_messages WHERE conversation_id = <ID>
```

### 2. Part 1 — Conversation transcript

Print each message in this format:

```
### [seq] [role] (msg ID: [id])
[content]
```

Use `user` and `assistant` labels. Include the full content, untruncated.

### 3. Part 2 — Quality analysis

Write a detailed analysis covering:

- **Header**: Characters, scenario, model, dates, message counts, char counts, user:AI ratio
- **Arc structure**: Identify 2-4 acts with message ranges and brief descriptions
- **Strengths**: What works well (character voice, pacing, emotional beats, user-AI dynamic)
- **Recurring problems**: Table format with issue, example message numbers, severity (high/moderate/low). Look for:
  - Repetitive physical tics or gestures
  - Stock phrases recycled across messages
  - Permission-asking loops ("you sure?", "this okay?")
  - Overused adverbs or filler words ("absently", "hyperaware")
  - Scene coherence errors (contradicting established facts)
  - Voice collapse (character losing their distinctive voice)
  - Emotional shortcuts (feelings resolving too fast)
- **Voice consistency**: Does the AI character maintain a distinct voice throughout? Where does it degrade?
- **NSFW quality** (if applicable): Does writing quality drop in intimate scenes?
- **Emotional depth score**: Rate each act on a 1-10 scale with brief notes
- **Key takeaways**: 3-5 bullet points summarizing what to improve

**Important**: Valentina is always the user's character. Never evaluate Valentina's writing quality — she is the human player.

### 4. Part 3 — Per-message prompt replay

For each **assistant** message, print the prompt context that was used to generate it:

```
---
### Message [seq] (ID: [id]) — Prompt Context

**System prompt** ([char count] chars):
> [first 500 chars of system_prompt, or "(not stored)" if NULL]

**Post prompt** ([char count] chars):
> [first 500 chars of post_prompt, or "(not stored)" if NULL]

**Scene state**:
> [scene_state content, or "(not stored)" if NULL]

**Budget**:
[If budget_json is stored, show: model_ctx, response_reserve, available, overhead,
 messages_budget, messages_kept/dropped, estimator_tokens, actual_tokens, warnings]
[If not stored, show "(not stored — conversation predates budget tracking)"]

**Messages in context window**: [messages_kept] of [total messages at this point]
**Messages dropped**: [messages_dropped]

**AI response** ([char count] chars, [word count] words):
> [first 200 chars]...
---
```

For user messages, just show:
```
---
### Message [seq] (ID: [id]) — User input
> [first 200 chars]...
---
```

### Notes

- If the output is very long, it's OK to split across multiple response messages
- Use the stored pipeline data (system_prompt, scene_state, post_prompt, budget_json) when available
- For older conversations without stored data, note "(not stored)" and skip reconstruction
- The report is for the user's analysis — be honest about quality issues, don't sugarcoat
