# RP Research Synthesis — March 2026

Compiled from 13 research documents, 50+ academic papers, and deep code analysis of SillyTavern, KoboldCpp, RisuAI, and Agnai.

## Where We Stand

Our RP app has a clean pipeline architecture (pre/post hooks, pluggable context strategies), automated scene state tracking with incremental updates, and an MCP tool-use PoC. These put us ahead of most platforms in specific areas. But we're behind on fundamentals that the community solved years ago.

## Top Priorities (Ordered by Impact)

### 1. Switch Models

**Problem:** `mn-12b-mag-mell-r1` is a weight merge, not a fine-tune. Merges compound weaknesses. The pandering, repetitive mannerisms, and stock RP prose are largely model-level.

**Action:**
- Pull `TheDrummer/Rocinante-X-12B-v1` (iMatrix Q5_K_M or Q6_K from bartowski)
- If VRAM allows 24B: `TheDrummer/Cydonia-24B-v4.3` is the standout model in the entire RP space
- Update sampling: temp 1.0-1.1, min_p 0.1-0.12, rep_pen 1.05-1.10

**Evidence:** Community consensus across r/LocalLLaMA, r/SillyTavern. Academic: RLHF mode collapse paper (ICLR 2024) explains why all models converge on generic style. Model capability is the ceiling; prompting only steers within it.

**Effort:** Low (ollama pull + config change)

### 2. Rewrite Nora's Card Using Community Best Practices

**Problem:** Our card puts behavioral instructions in system_prompt, has weak mes_example, and the first_mes — while good — doesn't fully demonstrate the prose register we want.

**Action:**
- **first_mes**: Rewrite to be the gold standard. Include inner thoughts, sensory details, a tangent, specific physical details (not stock descriptions). 400-500 tokens. The model will mirror this more than anything else.
- **mes_example**: Write 2-3 exchanges in full novelistic prose. Not asterisk-actions. Show: a moment where she disagrees, a tangent about her running/memoir, a moment of sideways warmth. Use Ali:Chat format (`{{char}}: ...` / `{{user}}: ...`).
- **Move behavioral rules to post_history_instructions**: "Write like Rachel Kushner, not AO3" and the prose register example belong here — injected right before generation, strongest influence position.
- **Keep system_prompt lean**: Character identity, scenario context, and the tool descriptions. Not behavioral instructions.
- **Use PList format for description**: Structured key-value traits instead of prose paragraphs.

**Evidence:** SillyTavern community, card creation guides, character voice research. first_mes confirmed as #1 lever by three independent research tracks. post_history_instructions is the "power position."

**Effort:** Medium (rewrite card fields, test)

### 3. Add Sampler-Level Anti-Slop

**Problem:** System prompt instructions like "don't use stock phrases" are ignored. The model generates "one eyebrow raised" because it's the highest-probability token sequence. You can't fix probability with instructions.

**Action:**
- Enable **DRY** sampler (penalizes repeated sequences within a response)
- Enable **XTC** sampler (excludes top-probability tokens, forcing lexical diversity)
- Investigate KoboldCpp's **phrase banning** (backtracks when banned phrases detected) — requires KoboldCpp backend or equivalent
- Reference: Sukino's anti-slop phrase list on HuggingFace, sam-paech/antislop-sampler (ICLR 2026 paper)

**Evidence:** Antislop Sampler paper shows 90% slop reduction. KoboldCpp's implementation is production-tested. SillyTavern refused to build this (Issue #3014) because it's a backend concern — correct, it belongs in the inference layer.

**Effort:** Medium (sampler config if using KoboldCpp; harder with Ollama which has limited sampler control)

### 4. Add Conversation Summarization

**Problem:** When messages drop out of the sliding window, their information is lost forever. Emotional continuity, callbacks, and narrative threads are destroyed.

**Action:**
- Before messages drop out of context, generate a running summary
- Inject summary as permanent context (similar to how memory works in KoboldCpp)
- Summary should capture: emotional beats, promises, revelations, relationship changes — not just physical state
- Consider hybrid approach: compressed summary + vector retrieval of specific relevant messages

**Evidence:** SillyTavern's summarize extension, MemGPT (tiered memory architecture), academic research on long-context dialogue. Scene state alone only tracks physical state — narrative continuity needs summarization.

**Effort:** Medium-High (new pipeline hook, LLM call per N messages, storage)

### 5. Upgrade Scene State to Slot-Based Tracking

**Problem:** Freeform text state is fragile. The LLM can accidentally overwrite facts ("Valentina is naked" becomes "Valentina, except for a top and panties"). Delta changes are hard to validate.

**Action:**
- Switch from freeform text to structured slots:
  - Per-character: Clothing (Topwear, Bottomwear, Underwear, Footwear, Accessories), Position, Location
  - Per-character: Restraints (type, material, body parts, pattern)
  - Scene: Props, Mood, Time
- LLM generates JSON updates, not freeform text
- Add delta clamping (max changes per turn) to prevent phantom state swings
- Consider Graphiti-style temporal validity (fact valid_from msg X, invalidated at msg Y)

**Evidence:** ST-Outfits extension, BetterSimTracker, SCORE paper (academic), Graphiti/Zep temporal knowledge graphs.

**Effort:** High (restructure state format, update prompt, update UI)

### 6. Implement RAG for Character Voice

**Problem:** The model has no concrete examples of Nora's voice beyond what's in the system prompt. It falls back to its training distribution (generic RP prose).

**Action:**
- Curate source material: Carrie Fisher quotes, interview excerpts, memoir passages, speech patterns — processed into distilled voice examples (not raw dumps)
- Embed chunks using `nomic-embed-text` via Ollama
- Store in pgvector (already in our postgres stack)
- Before each generation, retrieve 2-3 voice examples that match the current conversational energy (not topic — tone)
- Inject as "Voice reference" in the prompt

**Evidence:** SillyTavern Data Bank (v1.12.0), RAGs to Riches paper (35% better in-character under adversarial conditions), RoleLLM, ID-RAG. Warning from RoleLLM: structured extraction works better than raw chunks.

**Effort:** High (embedding pipeline, pgvector setup, retrieval logic, curation of source material)

### 7. Add Author's Note / Depth Injection

**Problem:** Voice drift in long conversations. The model gradually forgets prose instructions as more messages push them further from the generation point.

**Action:**
- Add configurable "Author's Note" injection at depth N (default: 4) in the message history
- Content: brief prose register reminder, scene-specific steering, tone instructions
- UI: editable field per conversation, not per card

**Evidence:** SillyTavern's Author's Note, community consensus on depth 2-4 as the sweet spot for behavioral control. This is the primary tool for mid-conversation steering.

**Effort:** Low (add field to conversation, inject in pipeline)

### 8. Implement Lorebook / World Info

**Problem:** Character descriptions are bloated because everything (NPCs, locations, backstory) is crammed into the description field. This wastes tokens on context that's only relevant when triggered.

**Action:**
- Implement keyword-triggered entries (V2 CharacterBook format for compatibility)
- Scan last N messages for keywords
- Inject matching entries into prompt (with token budget)
- Support: primary keys, secondary keys (AND logic), priority, weight

**Evidence:** Every major platform has this. SillyTavern's implementation is 6,193 lines with recursive scanning, timed effects, priority/weight/budget. Start simple (keyword match + budget), add sophistication later.

**Effort:** High (new data model, scanning logic, UI, token budgeting)

### 9. Token-Budget-First Prompt Assembly

**Problem:** Our pipeline assembles the prompt then trims to fit. SillyTavern's approach is better: start with a token budget, add items by priority until budget is exhausted.

**Action:**
- Refactor prompt assembly to use a decreasing token budget
- Priority order: system prompt > character card > world info > scene state > chat history (newest first)
- Requires actual token counting (not character estimation)
- Use sentencepiece tokenizer matching the active model

**Evidence:** SillyTavern's ChatCompletion class, Agnai's token-aware template filling.

**Effort:** High (tokenizer integration, pipeline refactor)

### 10. Vector Memory for Past Messages

**Problem:** Long conversations lose emotional continuity. The model forgets what happened 30+ messages ago.

**Action:**
- Embed each message as it's created (pgvector)
- Before generation, search for past messages relevant to current context
- Inject top 2-3 as "Earlier in this conversation: ..."
- Complement (don't replace) the summarization system

**Evidence:** SillyTavern Vector Storage extension, CharMemory extension (hybrid summarize + retrieve), LoCoMo benchmark paper, MemGPT architecture.

**Effort:** High (embedding pipeline, retrieval logic, prompt injection)

## What NOT To Build

- **Full extension system** — we're one user, not a platform. Build features directly.
- **40 backend adapters** — Ollama is enough. Don't abstract prematurely.
- **Visual novel sprites** — not our use case.
- **Multiplayer** — not needed.
- **Card sharing platform** — import from existing platforms, don't build one.

## Architecture Insights Worth Stealing

| From | What | Why |
|------|------|-----|
| SillyTavern | Token-budget-first prompt assembly | Correct approach to context management |
| SillyTavern | Drag-and-drop prompt section ordering | Great UX for prompt engineering |
| SillyTavern | World info recursive scanning | Lorebook entries can trigger other entries |
| KoboldCpp | Backend-level memory parameter | Memory survives context truncation correctly |
| KoboldCpp | Smart context shifting (KV cache surgery) | Performance trick for long conversations |
| KoboldCpp | Placeholder-based instruct tags | Model-portable saved conversations |
| RisuAI | HypaV3 memory (categorized summaries + embeddings + importance) | Most sophisticated memory in the space |
| RisuAI | MCP client integration | We built a PoC; they shipped it |
| Agnai | PEG grammar template parser | Robust, extensible, testable |
| Agnai | Saga/structured adventure system | Game engine on top of chat |
| DreamGen | Scenario-spec with UUID entities | Better data model than character cards |
| BetterSimTracker | Delta clamping on state changes | Prevents phantom state swings |
| Graphiti/Zep | Temporal validity on facts | Solves "forgot they undressed" definitively |

## Model Recommendations (March 2026)

| Size | Model | Notes |
|------|-------|-------|
| 12B | TheDrummer/Rocinante-X-12B-v1 | Best at size. Proper fine-tune, not merge. Mistral v3 Tekken format. |
| 24B | TheDrummer/Cydonia-24B-v4.3 | Standout in entire RP space. 14GB VRAM at Q4_K_M. |
| 70B | Sao10k/Euryale-v2.3-70B | Top tier. Llama 3.3 base. Needs serious hardware. |

Sampling: temp 1.0-1.1, min_p 0.1-0.12, rep_pen 1.05-1.10. iMatrix quants (bartowski) always.

## Quick Win Sequence

1. Pull Rocinante-X-12B (30 min)
2. Rewrite Nora's first_mes and mes_example (1 hour)
3. Move prose instructions to post_history_instructions (15 min)
4. Update sampling settings (5 min)
5. Add Author's Note field (1 hour code)
6. Test — this alone should fix 60-70% of our voice problems

Then: summarization → slot-based state → lorebooks → RAG → vector memory
