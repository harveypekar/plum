# RP Project — Improvement Plan

Written 2026-04-23 after deep analysis of every module, the active prompt template,
conv 97 report, and user quality/preference memories.

---

## 1. Post-prompt tiering

**Priority: highest — biggest token savings, most quality improvement per effort**

The post-prompt (`prompt.md ## post`) renders to ~1,142 tokens. On 8k context with
1,024 response reserve, that's ~16% of total budget before the system prompt adds
character descriptions. Conv 97: 36 of 86 messages dropped by the end. The model
writes without seeing half the conversation.

Many quality complaints (emotion arcs collapsing, stock phrases returning, voice
degrading) are symptoms of the model literally forgetting what happened.

### Plan

- Split post-prompt into tiers:
  - **Core** (every message): stay in character, don't write for `{{user}}`, correct
    pronouns, physical constraints persist. ~300 tokens.
  - **Style** (rotate 2-3 per turn): vary response length, ground in physical scene,
    don't mirror, messy emotions, active participation. Selected based on scene state
    or recent patterns.
- Move banned-phrases list out of the prompt entirely (see #3).
- Consider moving `mes_example` to dynamic fewshot injection instead of system prompt
  — only inject when voice is drifting, saving tokens when it's not needed.

### Key files

- `pipeline.py` — `assemble_prompt()`, `DEFAULT_PROMPT_TEMPLATE`
- `prompt.md` — active template
- `budget.py` — overhead calculation treats post-prompt as immovable
- `context.py` — strategies fit messages into whatever budget remains after overhead

### Notes

The budget system's 5-priority shrink cascade only shrinks messages and mes_example.
The post-prompt is immovable overhead — correct architecturally, but means a fat
post-prompt directly reduces message retention. Fix the post-prompt, not the budget.

---

## 2. SlidingWindow bridge message

**Priority: high — low-effort, high-impact coherence fix**

**Status: DONE** — SummaryBuffer is now fully wired up and active as the default
context strategy. Uses dedicated lightweight model (q25), has API endpoints for
viewing/triggering summaries, Summary tab in Under the Hood panel, and summary info
in NDJSON debug chunks.

`SlidingWindow.fit()` drops oldest messages silently. SummaryBuffer addresses this by
injecting a rolling summary of dropped messages after the greeting, so the model has
context about what happened before the window.

### Remaining opportunity

Even with SummaryBuffer active, a scene-state-based bridge message for conversations
that haven't accumulated enough messages for a summary (< 10 messages) would help.
The summary threshold means the first 10 messages get pure SlidingWindow behavior.

### Key files

- `context.py` — `SummaryBuffer.fit()` — injects summary, filters covered messages
- `summarize.py` — `maybe_generate_summary()` with dedicated model support
- `routes.py` — endpoints: GET/POST summaries, debug chunk includes summary info
- `static/app.js` — Summary tab in Under the Hood panel

---

## 3. Stock phrase post-hook

**Priority: high — mechanical fix for a frustrating recurring problem**

The post-prompt bans specific phrases ("heart pounded", "breath caught", etc.) but
conv 97 shows the model still uses them. Prompt-based bans are unreliable with 12B
models — the instruction competes with the training distribution, and training wins.

### Plan

- Add a response post-hook in the pipeline that checks for stock phrases using
  `lora_curate.STOCK_PHRASES` (already exists, 30+ phrases).
- On detection, either:
  - (a) Re-generate with explicit instruction: "Your response contained 'heart
    pounded'. Rewrite, replacing that phrase with a character-specific physical detail."
  - (b) Targeted edit via fast model call: "Replace 'her heart pounded' with a
    character-specific physical reaction for [Amber]."
- Track violations in response metadata (feeds into A/B compare analysis).
- Remove the banned list from the post-prompt once the hook works — recovers ~200
  tokens for conversation history.

### Key files

- `pipeline.py` — add post-hook after `clean_response`
- `lora_curate.py` — `STOCK_PHRASES` list (line 7), `_count_stock_phrases()`
- `prompt.md` — remove banned phrases section once hook is active

---

## 4. Dynamic response length

**Priority: high — small change, noticeable quality improvement**

Post-prompt says "Write 2-3 short paragraphs" but conv 97's first message was 509
words. `num_predict` caps tokens but doesn't enforce structure. The model doesn't know
what "short" means in this context.

### Plan

- Set `num_predict` dynamically based on user message length:
  `num_predict = max(256, min(1024, user_msg_tokens * 2))`
- Add a concrete word count to the post-prompt: "Write approximately 150-250 words"
  instead of "2-3 short paragraphs." Adjust per turn.
- This naturally varies response length to match the beat, which is what the prompt
  asks for but doesn't enforce.

### Key files

- `routes.py` — `_budget_ctx()` where `num_predict` is set
- `prompt.md` — replace vague length instruction with dynamic word count

---

## 5. Scene-state-driven prompt selection

**Priority: medium — builds on #1 and #6**

Scene state is computed and stored but only injected as flat text in the post-prompt.
Not used for: validating response coherence, guiding which instructions to include,
or fewshot retrieval.

### Plan

- Use scene state to select which tiered post-prompt instructions to include:
  - `Restraints: wrists bound` → inject constraint persistence instruction
  - `Mood: grieving` → inject "emotions don't reset" instruction
  - `Voice: nonverbal` → inject sensory detail emphasis
- Post-response scene state validation: compare response against scene state for
  contradictions. Flag if character described as bound but freely gesturing.
  Can be lightweight model call or regex for obvious violations.

### Key files

- `scene_state.py` — structured output with Location/Clothing/Restraints/Position/etc.
- `pipeline.py` — post-prompt instruction selection logic
- `routes.py` — wire scene state into prompt selection

### Depends on

- #1 (post-prompt tiering) — need tiered instructions before selecting among them
- #6 (routes.py decomposition) — easier to implement with extracted prompt builder

---

## 6. routes.py decomposition

**Priority: medium — enabler for everything else**

routes.py is 1,363 lines handling CRUD, streaming, prompt assembly, scene state,
research dispatch, fewshot injection, compare/eval, and auto-reply. Only file that
knows how to wire the pipeline together.

### Plan

- Extract `_build_pipeline_ctx` + `_build_chat_messages` + `_budget_ctx` →
  `prompt_builder.py`. Called from 4+ endpoints, don't need `_ollama`/`_pipeline`
  globals — receive as parameters.
- Extract streaming response generator → `streaming.py`. NDJSON protocol, chunked
  token emission, done-chunk assembly.
- Extract compare/eval endpoints → `eval_routes.py`. Self-contained feature with own
  models and DB functions.

No user-visible change. Unblocks testing prompt builder in isolation and adding
endpoints without touching the main file.

### Key files

- `routes.py` — everything
- New files: `prompt_builder.py`, `streaming.py`, `eval_routes.py`

---

## 7. Fewshot retrieval improvements

**Priority: low — harder to measure impact**

`fewshot.py` embeds `last_user + last_assistant` for vector similarity against stored
examples. But mes_example examples are about voice and style, not topic. A bar scene
might match a restaurant scene (similar topic) instead of a funeral scene that better
demonstrates the character's deflection style.

### Plan

- Embed the assistant message only for retrieval (matching writing style, not topic).
- Or embed a style descriptor: dialogue length, inner monologue ratio, sensory detail
  density. Match on those rather than semantic similarity.
- Weight recency: if last 3 messages show voice drift, increase fewshot injection.
  If voice is strong, skip to save tokens.

### Key files

- `fewshot.py` — `get_fewshot_messages()`, embedding construction (line 31)
- `db.py` — `search_fewshot_examples()`

---

## 8. A/B compare config defaults

**Priority: low — refine the eval system**

Current defaults are three temperature variants (0.6, 0.8, 1.0). Temperature affects
randomness but doesn't test the quality dimensions that actually matter — voice
consistency, stock phrase avoidance, response length, emotional depth.

### Plan

- Default configs should vary what's actually being evaluated:
  - Config A: baseline (T=0.8, standard post-prompt)
  - Config B: reduced post-prompt (core rules only, no style guidance) — tests
    whether model's base behavior or instructions produce better writing
  - Config C: higher response_reserve (512 vs 1024) — tests whether more history
    but less response room improves coherence
- Record structured preferences: tag selections with `voice_quality`, `length`,
  `coherence`, `creativity` — makes preference data actionable for LoRA training.

### Key files

- `static/app.js` — `compareMessage()` default configs (currently T=0.6/0.8/1.0)
- `models.py` — `CompareConfig`
- `routes.py` — compare endpoint
- `db.py` — eval CRUD

---

## 9. Quality auto-tagging and LoRA feedback loop

**Priority: low — builds the long-term feedback loop**

Live RP system and LoRA pipeline are separate worlds. A/B compare creates a bridge,
but no automated feedback path from live quality observations to training decisions.

### Plan

- Auto-tag assistant messages with quality signals as a post-hook:
  - Stock phrase count (reuse `lora_curate.STOCK_PHRASES`)
  - Trigram overlap with recent messages (reuse `lora_curate._trigram_overlap`)
  - Response/user length ratio
  - Pronoun accuracy (check `${char_pronouns}` appear correctly)
- Store in `quality_json JSONB` column on `rp_messages`.
- Export A/B preferences as DPO training pairs: selected candidate = "preferred",
  rejected = "dispreferred." Exactly what LoRA DPO training wants.
- Run `lora_curate.filter_message()` on every live assistant response and store the
  result. Builds a quality dashboard over time.

### Key files

- `lora_curate.py` — `filter_message()`, `STOCK_PHRASES`, `_trigram_overlap()`
- `db.py` — new `quality_json` column on rp_messages
- `schema.sql` — migration
- `routes.py` — post-hook wiring
- New file: `quality.py` — quality scoring logic

---

## 10. Pronoun enforcement post-hook

**Priority: low — quick win but narrow scope**

Conv 97 showed the model switching she/her → they/them despite explicit instructions.
12B models default to they/them from training data, overwhelming the instruction.

### Plan

- Add a pronoun post-hook: check response for incorrect pronoun usage. If character's
  pronouns are she/her and response uses "they" for the character (not genuinely
  plural), rewrite. Simple regex pass — no model call needed.
- Reinforce pronouns in assistant priming anchor. Currently `"{ai_name} "`. Change to
  `"{ai_name} [she/her] "` — nudges first tokens toward correct pronouns, propagates.

### Key files

- `pipeline.py` — add post-hook
- `budget.py` — `_render_for_count()` line 174, priming anchor
- `routes.py` — `_build_chat_messages()` priming anchor construction
