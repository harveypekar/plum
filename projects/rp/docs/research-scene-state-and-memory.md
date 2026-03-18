# Research: Scene State Tracking & Long Conversation Memory in RP Frontends

**Date**: 2026-03-15

## Our Current Problems

1. Scene state loses track of clothing (undressed 10 messages ago, state says still clothed)
2. State too vague ("bound" instead of "chest harness in red jute, wrists behind back")
3. State regenerated from scratch each time instead of incrementally updated — FIXED, we now do incremental
4. Long conversations lose emotional continuity after ~30 messages
5. Context window overflow drops old messages with no summarization fallback

## Our Current Implementation

- **Incremental state update**: Feed previous state + last 8 messages to a cheap model (qwen2.5), ask it to update only what changed. This is already better than most approaches.
- **Structured categories**: Location, Clothing, Restraints, Position, Props, Mood, Voice
- **Injection point**: Scene state injected into `post_prompt` near the generation point with `[Current Scene State — do NOT contradict this]`
- **Context strategy**: Pure sliding window — keep first message (greeting), fill remaining budget newest-first
- **No summarization**: When messages drop out of context, their information is just lost
- **No vector/RAG**: No embedding-based retrieval of relevant past messages

---

## 1. SillyTavern's Approach

### World Info / Lorebook System

The lorebook is a keyword-triggered injection system. Each entry has:
- **Keys**: Words/phrases or regex patterns that trigger the entry
- **Content**: Text injected into the prompt when triggered
- **Position**: Where in the prompt it gets injected (configurable depth)
- **Token budget**: Global cap on how many tokens all WI entries can consume
- **Priority/Order**: Higher priority entries get budget first
- **Scan depth**: How many recent messages to scan for keywords (configurable)

**Activation flow** (`public/scripts/world-info.js`):
1. Scan the last N messages for keywords/regex matches
2. Activate matching entries (constant entries always active)
3. **Recursive scanning**: Activated entries' content is scanned for keywords that trigger other entries, with configurable recursion depth
4. Route activated entries to output buckets based on `entry.position`
5. Enforce token budget — if budget exhausted, remaining matches are dropped even if keys are present
6. Inject into prompt via the Prompt Manager pipeline (`public/scripts/openai.js`, `public/script.js`)

**Token budgeting**: Either a percentage of total context (`Context %`) or absolute token count (`Budget`). Entries with larger `order` numbers are inserted first. Constant entries always come first.

**Relevance to us**: We don't have a lorebook system. Our scene state is closer to a single always-on entry. A lorebook would let us define character-specific clothing defaults, location descriptions, prop details that activate when mentioned. Worth considering if scenes get complex enough.

### Summarization System (Chat Memory Extension)

SillyTavern's built-in summarization (`extensions/summarize/`):

- **Trigger**: Configurable — every N messages, or manual
- **Algorithm**: Send recent messages + previous summary to LLM, ask for updated summary
- **Budget formula**: `max_summary_buffer = context_size - summarization_prompt - previous_summary - response_length`
- **PADDING constant**: 64 tokens safety buffer for prompt overhead
- **Short-term vs Long-term memory**: Summaries stay in short-term until they exceed context limit, then can be promoted to long-term
- **Injection**: Summary injected at configurable position and role in the prompt
- **Backends**: Supports Extras API, Main API, and WebLLM for summarization

**Key insight**: The "Update every X messages" with auto-heuristic ("magic wand" button) tries to generate the first summary before initial messages would drop out of the context window. This is proactive rather than reactive.

### Vector Storage (formerly ChromaDB/Smart Context)

- Creates a vector DB per chat using sentence-transformers embeddings (`all-mpnet-base-v2`)
- After 10 messages, begins recording all messages into the DB
- On each new input, searches the DB for semantically similar past messages
- Injects retrieved messages into context alongside the normal chat history
- **Deprecated**: Smart Context → superseded by built-in Vector Storage extension

### ST-Outfits Extension (Clothing Tracking)

Directly relevant to our clothing-tracking problem. Slot-based system:
- Slots: Headwear, Topwear, TopUnderwear, Bottomwear, BottomUnderwear, Footwear, FootUnderwear, plus accessory slots for head, ears, eyes, mouth, neck, body, arms, hands, waist, bottom, legs, foot
- Uses SillyTavern global variables: `{{getglobalvar::<BOT>_headwear}}`
- **Auto Outfit Updates**: After every character response, checks recent messages and automatically updates clothing slots based on what happened
- Injected into prompt via Character Description, Author's Notes, or World Info Entry

**This is the closest thing to our structured clothing state**. Key difference: it's slot-based (discrete items per slot) rather than freeform text. Slot-based is more reliable because the LLM just needs to say "removed topwear" rather than rewriting a paragraph.

### SillyTavern-State Extension

By ThiagoRibas — configurable prompts that run after each AI response:
- Each prompt generates a "state message" appended to chat
- Can track clothes, positions, inventory, stats
- Configuration saved per-Character, not per-Chat
- State messages can be collapsed for cleaner UI
- "Unique" option ensures only one state message of each type exists

**This is essentially what we do** — a prompt that runs after each response to generate state. Main difference: they make it visible in the chat as collapsible messages rather than a hidden field.

### BetterSimTracker

Tracks relationship stats per message with prompt injection:
- Numeric, enum, boolean, text stat types
- Injects hidden relationship state guidance into generation prompts
- Configurable injection depth (0-8)
- Max delta per turn (prevents wild stat swings)
- Confidence dampening (scales changes by model confidence)
- Mood stickiness (keeps mood stable unless strongly supported)
- Latest summarization note can be added to injection

**Relevance**: The "max delta per turn" and "mood stickiness" concepts are directly applicable to our scene state. Our state currently has no dampening — the LLM can completely rewrite clothing state in one update.

---

## 2. Context Strategies Across Platforms

### Sliding Window (what we do)
- Keep last N messages that fit in budget
- Oldest messages drop off silently
- Simple, no LLM overhead
- **Fatal flaw**: Information from dropped messages is completely lost

### Summarization + Sliding Window (SillyTavern, JanitorAI)
- Periodically generate a summary of older messages
- Summary injected as permanent context
- Recent messages kept verbatim
- **Hybrid**: "Summarize everything older than 20 messages, keep last 10 verbatim"
- **Weakness**: Summary quality depends heavily on the summarization model. Small models miss critical details.

### Per-Message Summarization (qvink's MessageSummarize)
- Each message gets its own summary when it ages out of the window
- More granular than bulk summarization
- Reduces information loss per message
- Higher LLM cost (one summarization call per message)
- Summaries can be edited by user

### RAG / Vector Retrieval (SillyTavern Vector Storage, ChromaDB)
- Embed all messages into vector DB
- On each turn, retrieve semantically relevant past messages
- Inject alongside recent context
- **Strength**: Can recall specific details from 100+ messages ago if they're semantically relevant to current conversation
- **Weakness**: Embedding models may not capture RP-specific nuances well; retrieval can pull irrelevant matches

### KoboldAI "Smart Context"
- Searches entire text buffer for content related to recent text
- More aggressive than simple sliding window
- Can find and inject relevant older content even from far back

### Hierarchical Summarization
- Recent messages: verbatim
- Medium-old messages: detailed summary
- Very old messages: high-level summary
- Creates a compression gradient — more detail for recent events

---

## 3. Persistent Structured State Tracking

### Talemate — The Gold Standard for Open-Source State Tracking

Multi-agent architecture (Python, ChromaDB):
- **World State Manager agent**: Dedicated agent for tracking world state
- **Separate agents** for dialogue, narration, summarization, direction, editing
- State entries in a history tab — can add, edit, remove, regenerate
- Entries based on summarization show their source messages
- Long-term memory via ChromaDB
- Context management for character details, world info, past events, pinned info
- Jinja2 templates for all prompts
- **Node-based architecture** refactor for complex, dynamic scenes

**Key insight**: Talemate separates concerns — the narration model doesn't also track state. A dedicated state agent with its own prompt and model handles world state. This is what we're doing with our separate scene state generation call.

### RPG Companion (SillyTavern)

Structured JSON game state:
- Character stats with visual progress bars
- Info box dashboard: date, weather, temperature, time, location, recent events
- Per-swipe data storage (each regeneration preserves its own state)
- Context-aware: weather/stats/character states influence the narrative
- Multi-line parsing format for AI generation

### SimTracker (SillyTavern)

Visual tracker cards from JSON data in chat messages:
- Customizable templates
- Flexible data structures
- Macro system integration

### Codified Finite-State Machines (Academic — arXiv 2602.05905)

Most rigorous approach found:
- Parse character profiles to identify distinct states
- Generate executable transition functions that process scene events
- Each action updates current state through FSM logic
- **Probabilistic extension (CPFSMs)**: States as probability distributions with continuous transition matrix updates
- Grounded in traceable state trajectories

**Relevance**: Our scene state is currently freeform text. A structured/typed approach (like clothing slots, or state enums) would be more reliable than asking the LLM to maintain freeform text accurately.

### Graphiti / Zep — Temporal Knowledge Graphs

Not RP-specific but highly relevant architecture:
- **Bi-temporal model**: Tracks when an event occurred AND when it was ingested
- Every relationship has validity intervals (`t_valid`, `t_invalid`)
- Incremental processing — updates entities/relationships without batch recomputation
- Conflict resolution via semantic + keyword + graph search
- When new knowledge conflicts with existing, uses temporal metadata to update/invalidate (not discard)
- Hybrid indexing: semantic embeddings + keyword search + graph traversal
- Near-constant-time retrieval regardless of graph scale

**Key insight for us**: The bi-temporal model and conflict resolution are exactly what we need. When a character undresses, the "wearing X" fact should get an `t_invalid` timestamp, not just be overwritten. This prevents the "forgot they undressed" problem because the system can distinguish between "currently wearing X" and "was wearing X earlier."

---

## 4. Memory Systems for Long Conversations

### SillyTavern Character Memory Extension (bal-spec)

The most sophisticated automatic memory system found:
- Every N messages (default 20), sends recent conversation to LLM
- LLM extracts: relationships, events, facts, emotional moments
- Memories saved as markdown bullet points in SillyTavern's Data Bank
- **Vector-based retrieval**: Converts memories to embeddings, finds semantically similar ones to current conversation
- Relevant memories quietly injected into prompt
- Group chat support: each member gets own memory file
- **Injection Viewer**: Real-time sidebar showing which memories were injected for each message

### MemoryBooks Extension (aikohanasaki)

Scene-based memory creation:
- User marks scene start/end in chat
- AI generates JSON summary: `{ "title": "...", "content": "...", "keywords": ["..."] }`
- Stored as lorebook entries with auto-numbering
- Multiple summary formats: Synopsis (comprehensive), Sum Up (concise beats), Minimal (1-2 sentences)
- Automatically hides summarized messages from context

### ReMemory Extension (InspectorCaracal)

Simulates human recall:
- Three modes: Log Message (raw with keywords), Generate Memory (AI summary), End Scene (full scene summary)
- Uses SillyTavern's World Info system as storage
- **50% activation probability** by default — keyword-triggered memories only activate half the time, simulating imperfect recall
- Scene markers create summarization boundaries

### Arkhon Memory (kissg96)

Agentic AI memory for SillyTavern — less documented but another approach to persistent memory.

### SpicyChat Semantic Memory 2.0

Commercial but interesting approach:
- Compresses key interactions into lasting memories
- Organizes by themes/context (not raw text)
- User can edit/delete memories
- Persists beyond context window

---

## 5. What the Community Says Works

### Practical Advice from rpwithai.com and Forums

1. **Generate summaries BEFORE messages drop out** — proactive, not reactive
2. **Use lorebooks for critical details** — don't rely on context alone for important character facts
3. **Monitor token usage** — character definitions can eat context budget
4. **Manual intervention still needed** — even the best auto-systems miss details
5. **Smaller summarization models miss critical RP details** — use a capable model for summaries
6. **Hide summarized messages** from context to reclaim budget
7. **Author's Note for persistent state** — high-priority injection that survives context overflow

### Common Failure Modes Reported

- "AI forgets what happened 30 messages ago" — universal complaint, context window limit
- "Summaries miss the important details" — summarization models aren't great at knowing what matters for RP
- "Character reverts to original description" — state drift when card data overrides observed changes
- "Constant recap mode" — users spending time reminding AI instead of advancing story

### What Actually Helps (Community Consensus)

- **Strong initial prompts** with scene seed, author's note, style/pacing rules
- **World Info for persistent facts** that MUST survive context overflow
- **Regular manual checkpoints** — user verifies/edits state periodically
- **Dedicated state tracking extensions** (ST-Outfits, BetterSimTracker, RPG Companion)
- **Large context models** (128k+) reduce the pressure but don't eliminate it

---

## 6. Incremental vs Full Regeneration

### Our Approach (Already Incremental)

We feed `previous_state + last 8 messages → updated state`. This is already ahead of most platforms. The prompt says:
> "Keep everything from the previous state that still holds true. Only change what the new messages contradict or add."

### How Others Do It

- **SillyTavern's built-in Summarize**: Incremental — feeds previous summary + new messages to get updated summary
- **MemoryBooks**: NOT incremental — generates fresh summary of marked scene range
- **MessageSummarize**: Per-message summaries, no incremental aggregation
- **Character Memory**: Periodic extraction from recent messages, appends to growing memory file
- **Talemate**: Incremental world state updates via dedicated agent
- **SillyTavern-State**: Runs state prompts after each response, can be configured to keep only latest state message ("unique" mode)
- **BetterSimTracker**: Fully incremental — extracts deltas per message with dampening/clamping

### Nobody Does Graph-Based Incremental Updates for RP

Graphiti/Zep exist for general agent memory but nobody has applied temporal knowledge graphs to RP scene state tracking yet. This would be the most robust approach:
- Each fact has creation time and invalidation time
- "Alice wearing red dress" → valid from msg 5, invalid from msg 15
- "Alice naked" → valid from msg 15, still valid
- Query: "What is Alice wearing?" → check current valid facts → "naked"

---

## Recommendations for Our System

### Quick Wins

1. **Add summarization fallback to sliding window**: When messages drop out of context, generate a running summary. Inject it as the second message (after greeting). Cost: one cheap LLM call per N messages.

2. **Make scene state categories typed/structured**: Instead of freeform "Clothing: she's wearing a blue dress", use slots:
   ```
   Clothing:
     Alice.top: blue sundress
     Alice.bottom: none (dress)
     Alice.underwear: white lace bra, matching panties
     Alice.footwear: barefoot
     Bob.top: black t-shirt
     ...
   ```
   Slot-based is harder for the LLM to "forget" because each slot has an explicit value.

3. **Increase state window from 8 to 12-16 messages**: 8 messages may miss clothing changes that happened just outside the window. Since we're using a cheap model (qwen2.5), the cost is minimal.

4. **Add delta clamping**: Like BetterSimTracker — if the previous state says "Alice: naked" and the LLM tries to output "Alice: fully clothed" without any dressing happening in recent messages, flag or reject the update.

### Medium-Term

5. **Vector retrieval for old messages**: Embed all messages, retrieve relevant ones when context window is full. Inject as "Earlier in the conversation..." before recent messages.

6. **Proactive summarization**: Start summarizing before messages drop out of context, not after.

7. **Scene boundaries**: Let users mark scene transitions. Summarize completed scenes into compact entries. Current scene stays detailed.

### Long-Term / Experimental

8. **Temporal fact tracking**: Each scene state fact gets a message-number validity range. Query current facts by filtering for valid-at-current-message. This is the Graphiti approach applied to RP.

9. **Separate memory tiers**:
   - Tier 1: Current scene state (always in context, structured)
   - Tier 2: Recent scene summaries (last 2-3 scenes, in context)
   - Tier 3: Older scene summaries (vector-retrieved when relevant)
   - Tier 4: Character facts/lorebook (keyword-triggered)

---

## Sources

- [SillyTavern World Info docs](https://docs.sillytavern.app/usage/core-concepts/worldinfo/)
- [SillyTavern World Info System — DeepWiki](https://deepwiki.com/SillyTavern/SillyTavern/6.1-world-info-system)
- [SillyTavern Context and Memory Systems — DeepWiki](https://deepwiki.com/SillyTavern/SillyTavern/6-context-and-memory-systems)
- [SillyTavern Prompt Management — DeepWiki](https://deepwiki.com/SillyTavern/SillyTavern/3.3-prompt-management)
- [SillyTavern Summarize Extension docs](https://docs.sillytavern.app/extensions/summarize/)
- [SillyTavern Smart Context docs](https://docs.sillytavern.app/extensions/smart-context/)
- [SillyTavern Data Bank (RAG) docs](https://docs.sillytavern.app/usage/core-concepts/data-bank/)
- [SillyTavern Author's Note docs](https://docs.sillytavern.app/usage/core-concepts/authors-note/)
- [SillyTavern Function Calling docs](https://docs.sillytavern.app/for-contributors/function-calling/)
- [World Info Encyclopedia — rentry.co](https://rentry.co/world-info-encyclopedia)
- [Dynamic World Building Discussion #3466](https://github.com/SillyTavern/SillyTavern/discussions/3466)
- [Feature Request: Inventory Tracking — Issue #461](https://github.com/SillyTavern/SillyTavern/issues/461)
- [Feature Request: Memory system updates — Issue #2022](https://github.com/SillyTavern/SillyTavern/issues/2022)
- [ST-Outfits Extension](https://github.com/lannashelton/ST-Outfits/)
- [SillyTavern-State Extension](https://github.com/ThiagoRibas-dev/SillyTavern-State)
- [BetterSimTracker Extension](https://github.com/ghostd93/BetterSimTracker)
- [RPG Companion Extension](https://github.com/SpicyMarinara/rpg-companion-sillytavern)
- [SimTracker Extension](https://github.com/prolix-oc/SillyTavern-SimTracker)
- [MemoryBooks Extension](https://github.com/aikohanasaki/SillyTavern-MemoryBooks)
- [Character Memory Extension](https://github.com/bal-spec/sillytavern-character-memory)
- [ReMemory Extension](https://github.com/InspectorCaracal/SillyTavern-ReMemory)
- [MessageSummarize Extension](https://github.com/qvink/SillyTavern-MessageSummarize)
- [LorebookOrdering Extension](https://github.com/aikohanasaki/SillyTavern-LorebookOrdering)
- [Lore Variables Extension](https://github.com/LenAnderson/SillyTavern-Lore-Variables)
- [Talemate — vegu-ai](https://github.com/vegu-ai/talemate)
- [Talemate Documentation](https://vegu-ai.github.io/talemate/)
- [Graphiti — Temporal Knowledge Graphs](https://github.com/getzep/graphiti)
- [Zep: Temporal Knowledge Graph Architecture — arXiv 2501.13956](https://arxiv.org/abs/2501.13956)
- [Codified Finite-State Machines for Role-playing — arXiv 2602.05905](https://arxiv.org/html/2602.05905)
- [StateAct: State Tracking for LLM Agents — arXiv 2410.02810](https://arxiv.org/abs/2410.02810)
- [How To Manage Long Chats On SillyTavern — rpwithai.com](https://rpwithai.com/how-to-manage-long-chats-on-sillytavern/)
- [Context Window Management Strategies — getmaxim.ai](https://www.getmaxim.ai/articles/context-window-management-strategies-for-long-context-ai-agents-and-chatbots/)
- [LLM Chat History Summarization Guide — mem0.ai](https://mem0.ai/blog/llm-chat-history-summarization-guide-2025)
- [complex_memory — KoboldAI-like memory for oobabooga](https://github.com/theubie/complex_memory)
- [SillyTavern Extension-ChromaDB](https://github.com/SillyTavern/Extension-ChromaDB)
- [Advanced Memory and RLHF Extension](https://github.com/emogie/SillyTavern_Advanced_Memory_and_RLHF)
