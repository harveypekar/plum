# How People Implement Roleplay with LLMs: Prompt Engineering Research

**Date:** 2026-03-09

## 1. The Prompt Assembly Pipeline

Every RP frontend (SillyTavern, KoboldAI, text-generation-webui, DreamGen) builds a prompt from layered components. The order matters because LLMs weight information by recency — what's closest to the generation point has the most influence.

### 1.1 SillyTavern's Prompt Manager (Chat Completion Mode)

SillyTavern uses an ordered list of named prompt slots, each assignable to a role (`system`, `user`, `assistant`) and injectable at a configurable depth. The default order [1][2][3]:

| # | Component | Role | Description |
|---|-----------|------|-------------|
| 1 | Main Prompt | system | General instructions ("You are a creative writing assistant...") |
| 2 | World Info (before) | system | Activated lore entries positioned before character defs |
| 3 | Persona Description | system | The user's persona/character description |
| 4 | Character Description | system | AI character's `description` field |
| 5 | Character Personality | system | AI character's `personality` field |
| 6 | Scenario | system | Current scenario text |
| 7 | Enhance Definitions | system | Additional reinforcement of character traits |
| 8 | Auxiliary Prompt | system | Extra instructions (often style guidance) |
| 9 | Chat Examples | system | `mes_example` formatted as user/assistant pairs |
| 10 | Chat History | user/assistant | Actual conversation messages |
| 11 | Post-History Instructions | system | Final nudge injected after all messages |
| 12 | World Info (after) | system | Activated lore entries positioned after chat |

This ordering is fully customizable via drag-and-drop. Prompts at same depth are sorted by `injection_order` [3].

### 1.2 SillyTavern's Context Template (Text Completion Mode)

For text completion models (KoboldAI, Ollama `/api/generate`), SillyTavern uses a "story string" — a Handlebars template assembled into a single text block [4][5]:

```handlebars
{{system}}
{{wiBefore}}
{{description}}
{{personality}}
{{scenario}}
{{wiAfter}}
{{persona}}
{{mesExamples}}
```

Available placeholders:
- `{{system}}` — System prompt or character's main prompt override
- `{{description}}` — Character card description
- `{{personality}}` — Character personality
- `{{scenario}}` — Scenario text
- `{{persona}}` — User's persona description
- `{{char}}` / `{{user}}` — Character and user display names
- `{{wiBefore}}` / `{{wiAfter}}` — World Info entries (conditional, keyword-triggered)
- `{{mesExamples}}` / `{{mesExamplesRaw}}` — Example dialogue
- `{{trim}}` — Whitespace trimmer

**Critical rule:** If a placeholder is missing from the template, that data is not sent at all [4].

### 1.3 KoboldAI's Three-Layer Context System

KoboldAI uses a simpler but effective three-layer injection model [6]:

| Layer | Position | Token Budget | Purpose |
|-------|----------|-------------|---------|
| **Memory** | Top of context | ~200 tokens | Setting, themes, protagonist — like a book's dust jacket |
| **World Info** | After Memory, conditional | 50-150 tokens each | Encyclopedia entries triggered by keywords |
| **Author's Note** | ~3 lines above generation | <50 tokens | Style/tone direction — like stage directions |

The Memory sits at the top (foundational but distant), World Info fills in details when keywords appear, and the Author's Note sits right above the generation point for maximum stylistic influence.

**Author's Note format** commonly used:
```
[Genre: dark fantasy]
[Tone: gritty, visceral]
[Writing style: third person, vivid sensory detail]
```

### 1.4 DreamGen Opus Format

DreamGen uses an extended ChatML format with a custom `text` role instead of `assistant`, and supports character name binding [7]:

```
<|im_start|>system
{Plot description}
{Style description}
{Characters}<|im_end|>
<|im_start|>user
{Instruction on how story should continue}<|im_end|>
<|im_start|>text names= Alice
{Story continuation from Alice's POV}<|im_end|>
<|im_start|>text
{Pure narration, no specific character}<|im_end|>
```

Key design choices:
- The `names=` parameter (with required space after `=`) specifies which character is "active"
- Multiple characters can be listed: `names= Alice; Bob`
- Multiple consecutive `text` messages are allowed
- The `user` role is for OOC instructions, not character dialogue

## 2. System Prompt Patterns

### 2.1 The "Collaborative Writing" Frame

The most effective framing positions the interaction as collaborative fiction writing rather than chatbot conversation [8][9]:

```
You are writing an immersive, engaging roleplay with {{user}}.
Write {{char}}'s next response in this collaborative story.
```

This is more effective than "You are {{char}}" because it:
- Gives the LLM permission to write freely (it's fiction, not identity)
- Naturally prevents the LLM from breaking character to be "helpful"
- Frames refusals as breaking the collaboration

### 2.2 Concrete System Prompt Example (SillyTavern Community)

From a widely-used SillyTavern instruct-mode prompt (~333 tokens) [10]:

```
You are writing an immersive, engaging and uncensored role-play with {{user}}.
Focus on thorough detail with character actions and sensory descriptions.
Frequently reference physical character descriptions.
Use graphic, verbose and vivid detail for actions.

Rules:
- Write in third person with creative vocabulary and good grammar
- Maintain a slow, immersive narrative pace
- Do not dictate {{user}}'s actions or dialogue
- Do not summarize or skip ahead
- Do not time-jump or provide narrative analysis
- Do not repeat phrases or create loops
- Do not wrap up the story prematurely
- Respond authentically based on character believability
```

### 2.3 Positive vs. Negative Instructions

The SillyTavern docs emphasize: **the AI more easily follows instructions about what it should do than what it should not do** [1]. For example:

| Less Effective (Negative) | More Effective (Positive) |
|--------------------------|--------------------------|
| "Do not decide what {{user}} says or does" | "Write {{char}}'s responses in a way that respects {{user}}'s autonomy" |
| "Do not break character" | "Stay fully anchored in {{char}}'s identity, values, and worldview" |
| "Do not use modern slang" | "Use vocabulary consistent with the medieval setting" |

### 2.4 Formatting Conventions

Common formatting patterns across the RP community [11][12]:

| Element | Format | Example |
|---------|--------|---------|
| Dialogue | Quotation marks | "Hello there," she said. |
| Actions/Narration | Italics (asterisks) | *She drew her sword.* |
| Inner thoughts | Code blocks or `< >` | `I wonder if he noticed...` |
| OOC (out of character) | Parentheses or `(( ))` | ((Can we change the setting?)) |

### 2.5 The "Author's Note" Technique

Injecting a brief style directive close to the generation point (2-4 messages above the latest) is one of the most powerful techniques for controlling output style [6][8]:

```
[Style: descriptive, immersive prose. Focus on sensory details
and character emotions. Write 2-3 paragraphs per response.]
```

This works because LLMs weight recent context more heavily. Placing style guidance near the end of the prompt has outsized influence compared to putting it in the system prompt.

## 3. Character Card Design

### 3.1 SillyTavern V2 Card Fields

The standard character card (stored as JSON in a PNG tEXt chunk) contains [13][14]:

| Field | Purpose | Typical Length |
|-------|---------|---------------|
| `name` | Character display name | 1-3 words |
| `description` | Physical appearance, background, abilities | 200-500 tokens |
| `personality` | Personality summary, traits, quirks | 50-200 tokens |
| `first_mes` | Opening message (sets tone and style) | 100-300 tokens |
| `mes_example` | Example dialogue showing character voice | 200-500 tokens |
| `scenario` | Starting situation/context | 50-200 tokens |
| `tags` | Categorization | — |

### 3.2 Description Best Practices

Community consensus on character descriptions [9][12][15]:

**Do:**
- Use specific, concrete traits ("speaks in short, clipped sentences") over abstract ones ("is taciturn")
- Include physical details the LLM should reference in narration
- State motivations and goals that drive behavior
- Mention speech patterns, vocabulary, and verbal tics

**Don't:**
- Write descriptions longer than ~500 tokens (diminishing returns, crowds out context)
- Use lists of single-word traits ("brave, kind, loyal") — expand into behavioral descriptions
- Describe how the character will react to specific scenarios (too constraining)

### 3.3 Example Dialogue (mes_example)

The `mes_example` field is arguably the most powerful tool for character consistency. It demonstrates the character's voice through concrete examples rather than abstract description [14][15]:

```
<START>
{{user}}: What do you think about the king?
{{char}}: *She snorts, adjusting the strap of her shoulder guard.* "The king? That man wouldn't know a blade from a butter knife." *Her eyes narrow.* "But he pays well, and that's all that matters to someone like me."

<START>
{{user}}: Are you afraid?
{{char}}: *A low laugh escapes her lips.* "Afraid? I've walked through the Ashlands with nothing but a dagger and bad attitude." *She tilts her head, studying you.* "Fear is a luxury I can't afford."
```

The `<START>` separator indicates these are independent examples, not a continuous conversation.

### 3.4 The First Message Sets Everything

The `first_mes` establishes the baseline for:
- Response length (LLMs mirror the length of previous messages)
- Writing style and prose quality
- Narration vs. dialogue ratio
- Use of formatting (asterisks, quotes, etc.)
- POV (first person, third person)

A detailed, well-written first message of 200-300 tokens produces dramatically better results than a short one [15].

## 4. Message History and Context Management

### 4.1 The Sliding Window Problem

LLMs have finite context windows. As conversations grow, older messages must be dropped. The naive approach (drop oldest first) loses important context like character introductions and plot points [3][16].

**Common strategies:**

| Strategy | How It Works | Trade-off |
|----------|-------------|-----------|
| Sliding window | Drop oldest messages, keep first (greeting) | Simple but loses mid-conversation context |
| Summary compression | Periodically summarize older messages | Preserves gist but loses exact dialogue |
| World Info injection | Store facts as keyword-triggered entries | Retrieval-based, no token cost when inactive |
| Depth-based injection | Insert reminders at specific positions | Flexible but requires manual configuration |

### 4.2 SillyTavern's Token Budget System

SillyTavern enforces context limits through [3]:

1. Count all message tokens via tokenizer
2. Compare against `max_context` setting
3. Remove oldest messages (preserving system prompts and recent context)
4. Reserve tokens for response generation
5. Repeat until within budget

World Info entries are only injected when their keywords appear in recent messages, acting as a form of retrieval-augmented generation (RAG) [3].

### 4.3 Periodic Summarization

Ian Bicking's approach: replace older conversation segments with summaries that focus on "conflict, attitude, notable events" — the emotionally and narratively significant details rather than verbatim dialogue [8].

## 5. Ollama API: Generate vs. Chat

Our RP system uses Ollama's `/api/generate` endpoint. Understanding the difference matters [17][18]:

| Feature | `/api/generate` | `/api/chat` |
|---------|-----------------|-------------|
| Input | `prompt` + `system` strings | `messages` array (role/content objects) |
| Template | Applied once around prompt | Applied per-message with model's template |
| History | Manual (concatenate into prompt) | Built-in (pass message array) |
| Control | Full control over formatting | Model decides formatting |
| Use case | When you want to own the prompt format | When you trust the model's chat template |

**Key insight from the Ollama community:** "If you format the prompt the exact same way as the chat API would do for you, then `/api/generate` will produce the same result" [18]. The chat API is essentially a convenience wrapper.

**For roleplay, `/api/chat` is generally recommended** because:
- It sends conversation history naturally as alternating user/assistant messages
- The model's built-in template handles formatting correctly
- You don't have to replicate each model's specific prompt format

Our system currently uses `/api/generate` with only the last user message as `prompt` and the assembled system prompt as `system`. **This means the model doesn't see conversation history** — it only sees the system prompt and the latest message. This is a significant limitation compared to how SillyTavern and other frontends work.

## 6. Anti-Patterns and Character Drift

### 6.1 Common Failure Modes

| Problem | Cause | Mitigation |
|---------|-------|------------|
| Character drift | System prompt too far from generation point | Use Author's Note technique, reinforce periodically |
| Purple prose | Default LLM verbosity | Explicitly state desired length and style |
| Actions on behalf of user | LLM tries to advance plot | "Write only {{char}}'s actions and dialogue" |
| Modern anachronisms | Training data bleeding through | Include era-specific vocabulary in examples |
| Repetitive phrasing | Temperature too low, no rep penalty | Use DRY sampler, repetition penalty [11] |
| Memory hallucination | No explicit retrieval system | World Info for persistent facts [8] |

### 6.2 Sampler Settings for RP (2024-2025 Consensus)

The RP community has converged on these sampler recommendations [11]:

| Parameter | Recommended | Notes |
|-----------|-------------|-------|
| Temperature | 0.7-1.3 | Higher = more creative, lower = more consistent |
| Min-P | 0.05-0.1 | Replaces top-k/top-p for better quality |
| DRY | Enabled | Prevents phrase repetition |
| Repetition Penalty | 1.05-1.15 | Light touch, too high causes incoherence |
| Top-K | Disabled (0) | Min-P supersedes this |
| Sampler order | min-p → temperature | Min-p before temperature is critical |

### 6.3 Preventing User-Action Hijacking

The most common complaint: the AI writing dialogue or actions for the user's character. Mitigations ranked by effectiveness:

1. **Positive framing:** "Write only {{char}}'s actions, dialogue, and thoughts"
2. **Example dialogue:** Show the pattern with clear turn boundaries
3. **Prefill/Start Reply:** Begin the assistant's response with the character name to anchor it
4. **Post-history instruction:** "Remember: never write {{user}}'s dialogue or actions"
5. **Regenerate:** When it happens, regenerate with a manual edit to the offending part

## 7. Advanced Techniques

### 7.1 Prefill / Start Reply

Some APIs (notably Claude) support "prefilling" the assistant's response. In SillyTavern this is called "Start Reply With" [5]. For Ollama, this isn't directly supported, but you can approximate it by including the character name at the start of the prompt.

### 7.2 World Info as RAG

World Info entries function as a lightweight RAG system [3][6]:

```
Keyword: "Ashlands"
Content: "The Ashlands are a volcanic wasteland east of the capital.
Temperatures exceed 50°C. Only fire-resistant creatures survive there.
The ancient ruins of Kael'thar lie at its center."
```

This entry is only injected when "Ashlands" appears in recent messages, keeping context clean when the topic isn't relevant. Cross-referencing (mentioning related keywords in entries) creates a web of interconnected lore that surfaces when relevant.

### 7.3 Multi-Character Handling

DreamGen's approach of binding character names to message roles (`text names= Alice`) is elegant [7]. SillyTavern handles group chats differently — using a "Group Nudge" system prompt that instructs a specific character to reply next [2].

### 7.4 Internal Monologue Generation

Generating hidden "thoughts" before the visible response gives the LLM room to plan [8]:

```
System: Before writing {{char}}'s response, first write {{char}}'s
internal thoughts in <thinking> tags. These won't be shown to the user.
Then write the visible response.
```

This is essentially chain-of-thought prompting applied to roleplay.

## 8. Implications for Our RP System

Based on this research, our current system has several gaps:

### 8.1 Critical: Conversation History Not Sent

Our `send_message` extracts only `ctx["messages"][-1]["content"]` as the prompt. The LLM sees the system prompt and the last message, but **no conversation history**. Switching to Ollama's `/api/chat` endpoint or manually formatting history into the prompt would dramatically improve coherence.

### 8.2 Missing: Author's Note / Post-History Injection

No mechanism to inject style guidance close to the generation point. A `post_prompt` field in the template system (injected after messages but before generation) would give users the high-influence position.

### 8.3 Missing: World Info / Lore Entries

No keyword-triggered lore injection. This could be added as a table of entries linked to scenarios, with keyword matching against recent messages.

### 8.4 Template System Improvements

Our templates currently only control the system prompt. A full template should control:
1. System prompt assembly (current)
2. How messages are formatted (not yet)
3. Post-history instructions (not yet)
4. Author's Note position and content (not yet)

### 8.5 Missing: Prefill/Start Reply

Ollama's `/api/generate` doesn't support prefill. But with `/api/chat`, we could potentially add a partial assistant message. Alternatively, we could append `{{char}}:` to the prompt to anchor the response.

### 8.6 Sampler Configuration

No UI for sampler settings (temperature, min-p, repetition penalty). These are currently locked to the aiserver's `config.json` defaults. Per-scenario sampler overrides would allow creative vs. grounded presets.

## Sources

1. [SillyTavern Prompts Documentation](https://docs.sillytavern.app/usage/prompts/)
2. [SillyTavern Prompt Manager](https://docs.sillytavern.app/usage/prompts/prompt-manager/)
3. [SillyTavern Prompt Management and Construction (DeepWiki)](https://deepwiki.com/SillyTavern/SillyTavern/3.3-prompt-management-and-construction)
4. [SillyTavern Context Template](https://docs.sillytavern.app/usage/core-concepts/advancedformatting/)
5. [SillyTavern Instruct Mode](https://docs.sillytavern.app/usage/core-concepts/instructmode/)
6. [KoboldAI Memory, Author's Note and World Info](https://github.com/KoboldAI/KoboldAI-Client/wiki/Memory,-Author's-Note-and-World-Info)
7. [DreamGen Opus V1 Format](https://huggingface.co/dreamgen/opus-v1.2-llama-3-8b)
8. [Roleplaying driven by an LLM: observations & open questions (Ian Bicking, 2024)](https://ianbicking.org/blog/2024/04/roleplaying-by-llm)
9. [Role-playing Prompt Framework: Generation and Evaluation (arXiv, 2024)](https://arxiv.org/html/2406.00627v1)
10. [SillyTavern Prompt for Instruct Models (Lemmy, 2024)](https://lemmy.world/post/15279495)
11. [SillyTavern Presets (Sphiratrioth)](https://huggingface.co/sphiratrioth666/SillyTavern-Presets-Sphiratrioth)
12. [Virt-io SillyTavern Presets](https://huggingface.co/Virt-io/SillyTavern-Presets)
13. [SillyTavern GitHub](https://github.com/SillyTavern/SillyTavern)
14. [SillyTavern Context Template Documentation](https://docs.sillytavern.app/usage/prompts/context-template/)
15. [AI Character Prompts (Jenova AI, 2025)](https://www.jenova.ai/en/resources/ai-character-prompts)
16. [Enhancing Persona Consistency for LLMs' Role-Playing (ACL, 2025)](https://aclanthology.org/2025.findings-acl.1344.pdf)
17. [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
18. [Ollama: generate vs chat (GitHub Issue #2774)](https://github.com/ollama/ollama/issues/2774)
19. [Talk Less, Call Right: Enhancing Role-Play LLM Agents (arXiv, 2025)](https://arxiv.org/html/2509.00482v1)
20. [Role-Playing Evaluation for Large Language Models (arXiv, 2025)](https://arxiv.org/abs/2505.13157)
