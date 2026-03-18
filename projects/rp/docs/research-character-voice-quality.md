# Research: Character Voice Quality in Open-Source RP LLM Frontends

Date: 2026-03-15

## The Problem

Models fall into generic roleplay tropes instead of producing distinct character voices:
- **Pandering/sycophancy**: Models validate the user instead of having their own personality
- **Repetitive physical mannerisms**: "one eyebrow raised", "smirk tugging at corner of mouth", "shivers down spine"
- **Stock RP prose**: Purple prose cliches instead of novelistic writing
- **Reactive characters**: No agency, agenda, or preoccupations of their own
- **"Sarcastic but secretly sweet" trope**: The model adds "rare unguarded moments" no matter the character
- **System prompt ignorance**: Models drift from tone/style instructions over long conversations

---

## 1. SillyTavern's Approach

### Regex Extension (Post-Processing Filters)
SillyTavern's Regex extension [1] detects patterns in generated text and applies replacements in real-time as tokens stream in. This is the primary mechanism for filtering unwanted output. Users can:
- Strip specific phrases or words from output
- Remove OOC (out-of-character) replies
- Apply find-and-replace to fix formatting issues

Community regex script repositories exist at `github.com/ashuotaku/sillytavern` [2] and `github.com/draedr/sillytavernscripts` [3], though these focus more on formatting fixes than anti-slop filtering.

**Limitation**: SillyTavern itself rejected a feature request for native AntiSlop Sampler support (Issue #3014 [4]), marking it "Out of Scope" because phrase banning operates at the inference level, not the frontend level. SillyTavern delegates this to backends like KoboldCpp.

### Instruct Mode and Prompt Templates
SillyTavern's Instruct Mode [5] wraps conversation in model-specific prompt formats (Alpaca, ChatML, Llama2, etc.). The system prompt defines writing style instructions. A commonly shared pattern:

> "Always follow the prompt. When writing a character's response or behavior, remember to describe their appearance, act out their personality and describe their actions thoroughly. Continue the story at a slow and immersive pace. Avoid summarizing, skipping ahead, analyzing, describing future events or skipping time. Refrain from wrapping up or ending the story, try to give {{user}} something to respond to. Avoid repetition, loops, repeated or similar phrases."

### Author's Note (Mid-Context Injection)
The Author's Note [6] injects text at a configurable depth in the conversation context. Key parameters:
- **Depth**: How many messages from the bottom the note is inserted (depth 4 = before the last 3 messages)
- **Frequency**: How often it appears (every message, every 4th, etc.)
- Closer to depth 0 = stronger influence on the next response

This is used to reinforce character voice throughout long conversations without consuming the system prompt. Recommended depth: ~4, with personality traits or PList format. This is effectively the "keep reminding the model" approach to voice drift.

### Character Card Design: Ali:Chat Format
The Ali:Chat format [7][8] is the most widely recommended character card style in the SillyTavern community. Its core principle: **use dialogue examples as the formatting to express traits**, rather than describing traits in plain text.

Key techniques:
- Put dialogue examples in the Description box (permanent context)
- Include the character's name in action descriptions every 2-3 sentences: `*Harry Potter adjusts his glasses.*`
- Quality over quantity: a few well-written exchanges beat many bland ones
- The **First Message** matters most: "The model is more likely to pick up the style and length constraints from the first message than anything else"
- Ali:Chat can include multi-character exchanges to show how a character behaves differently with different people

Ali:Chat Lite (updated guide): https://rentry.co/kingbri-chara-guide [9]

### Example Dialogue (mes_example)
Example messages in the `<START>` block format use `{{char}}:` and `{{user}}:` prefixes. These are kept in context only while there's room (pushed out as chat history grows). Key insight from the docs [10]:

> "Before each example, you need to add the <START> tag. The blocks of example dialogue are only inserted if there is free space in the context for them and are pushed out of context block by block."

**Effective use**: Make example dialogues overlap with the First Message scenario for consistency. Write them in the exact prose style you want the model to produce. Include the character's distinctive speech patterns, vocabulary, and emotional range.

---

## 2. RisuAI's Approach

RisuAI [11] addresses character voice through several mechanisms:

### Prompt Order Customization
Users can reorder prompt blocks freely, allowing character descriptions, lorebook entries, and system instructions to be placed wherever they have the most impact in the context window.

### Regex Scripts and Lua Processing
RisuAI supports regex scripts to modify model output, plus Lua scripting for more complex transformations [12]. This enables pre-processing and post-processing of both input and output.

### Module System
Lorebooks, regex scripts, trigger scripts, and background embeddings can be packaged into a single deployable module (.risum file) [12]. These can be enabled globally or toggled per-chat, making it possible to distribute "voice quality" packages.

### Character Card Support
RisuAI supports the full V2 character card spec including `mes_example`, personality, scenario, and embedded character books (lorebook entries). It also supports extensions for RisuAI-specific features.

**Assessment**: RisuAI provides the infrastructure for voice quality solutions (especially the module + regex + Lua pipeline) but doesn't ship dedicated anti-slop or voice enforcement features out of the box. Solutions are community-driven.

---

## 3. KoboldCpp's Approach

### Anti-Slop Phrase Banning (Native)
KoboldCpp (v1.76+) implements the most direct solution: **phrase-level banning at inference time** [13][14]. Unlike token-level banning (which can break unrelated words), this:
1. Waits for the complete banned phrase to appear in generated tokens
2. Backtracks a configurable number of tokens
3. Reduces the probability of all tokens that would lead to that phrase
4. Re-generates from the backtrack point

**Parameters**: Initially limited to 48 phrases (v1.76), expanded significantly in v1.77 (November 2024). Streaming output is slightly delayed to allow backtracking.

### Sukino's Banned Token List
The most widely used curated list is Sukino's SillyTavern-Settings-and-Presets [15][16] on HuggingFace:
- Maintained specifically for KoboldCpp's phrase banning
- Targets cliches and repetitive phrases
- **Incompatible with other backends** (other backends ban individual tokens, not phrases, causing over-banning)
- Available at: `huggingface.co/Sukino/SillyTavern-Settings-and-Presets`

Example banned phrases (from community lists): "shivers down", "mind, body, and soul", "maybe, just maybe", "knuckles whitening", "sent a shiver running down", "tapestry of", "testament to".

---

## 4. Community Solutions

### The Antislop Sampler (sam-paech)
The most technically rigorous approach, now an **ICLR 2026 conference paper** [17][18]:

**How it works**: Backtracking-based suppression. When an undesirable phrase is detected mid-generation, the sampler backtracks and adjusts token probabilities to avoid that phrase path. Unlike token banning:
- Can suppress multi-token phrases ("voice barely above a whisper")
- Can use regex patterns ("It's not X, it's Y")
- Doesn't destroy vocabulary (the word "tapestry" can still appear when contextually appropriate; only overuse is suppressed)

**Scale**: Default list has ~500 sequences. The full research list has 50,000+ sequences. The `slop_phrase_prob_adjustments.json` was auto-generated by computing over-represented words in a large LLM-generated story dataset.

**Key finding from the paper**: The Antislop Sampler successfully suppresses 8,000+ patterns while maintaining quality, whereas naive token banning becomes unusable at just 2,000 patterns. Their FTPO (fine-tuning) approach achieves 90% slop reduction while maintaining or improving performance on GSM8K, MMLU, and creative writing benchmarks.

**Integration**: Works with any OpenAI-compatible API endpoint via `antislop-vllm` [19]. KoboldCpp adopted a version of this approach natively.

GitHub: `github.com/sam-paech/antislop-sampler` [18]

### XTC Sampler (Exclude Top Choices)
Discussed extensively on r/LocalLLaMA [20]. XTC boosts creativity by excluding the top-probability tokens when multiple "good" tokens exist:
- Only triggers when there are multiple viable tokens
- Always leaves at least one "good" token untouched
- Recommended values: `xtc_probability = 0.5`, `xtc_threshold = 0.1`
- Users report dramatic improvements in prose variety

**Key insight from the community**: "Slop is one of the worst things that comes up in creative use cases, as the longer the chat goes on, the more certain phrases and words keep getting repeated." XTC directly addresses this by preventing the model from always choosing the highest-probability (and therefore most generic) continuation.

### DRY Sampler (Don't Repeat Yourself)
Available in SillyTavern [21] and most local inference engines. Penalizes tokens that would extend the current text into a sequence that already occurred earlier:
- Works at word, phrase, sentence, and paragraph level
- Recommended: `dry_multiplier: 0.8`, `dry_base: 1.75`, `dry_allowed_length: 2`
- Disabled by default in SillyTavern (multiplier = 0)
- Uses "sequence breakers" to reset tracking at natural boundaries

**Community recommendation**: Enable DRY + XTC together for best results in creative writing/roleplay.

### Min-P Sampling
Considered "the most important sampler" for roleplay [22]. Sets a minimum probability threshold proportional to the highest-probability token. Anything below gets culled. This prevents garbage tokens without forcing generic high-probability outputs.

### System Prompts Targeting Pandering/Sycophancy
Community-developed prompts address the positivity bias problem directly. Key patterns:

**Anti-pandering instructions** (aggregated from multiple sources [23][24]):
- "Characters should exhibit a balance of positive and negative traits, refraining from consistently optimistic or simplistic behavior"
- "The AI must not assume or project the user's thoughts, actions, or feelings"
- Explicit instructions to avoid "positivity bias"
- Instructions for characters to pursue their own goals independently of user desires

**The "Ender" technique** (EnderRoleplaying on Medium [25][26]):
- A "Magic Portal" prompt designed specifically for character accuracy from known IPs
- Two-step approach: first establish the character's canonical behavior, then begin roleplay
- Works best with GPT-4o, DeepSeek V3, Claude Sonnet
- Not designed for OCs; relies on the model's training data knowledge of existing characters

### RAG-Based Approaches to Character Voice
Academic research has explored feeding actual character quotes/excerpts via retrieval:

**RoleRAG** [27]: Graph-guided retrieval that pulls character-specific dialogue examples from a knowledge base during generation. Grounds responses in verifiable source material.

**Emotional RAG** [28]: Incorporates emotional factors into retrieval, selecting memory fragments aligned with the character's emotional state for more human-like responses.

**Key finding**: In a study of 453 role-playing interactions, RAG-based approaches with reference demonstrations were "consistently judged as more authentic and remaining in-character more often than zero-shot methods" [27].

**Practical application**: In SillyTavern, this maps to using Lorebook entries with activation keywords that inject relevant character quotes/behavioral descriptions when certain topics come up in conversation.

---

## 5. What Users Say Works (Community Consensus)

### Model Selection Matters Most
From r/LocalLLaMA and community guides [29][30]:
- **70B+ models** are significantly better at maintaining voice than 7-13B models
- **Llama 3 70B** and derivatives: best ecosystem support, good character consistency
- **Midnight Miqu 70B v1.5**: strong for RP, benefits from descriptive system messages
- **MythoMax 13B**: historically the most popular RP model at small scale, now surpassed
- **Mag Mell 12B**: surprisingly good at character consistency even at small scale
- **Mistral Large 2**: excellent for detailed descriptions and natural dialogue, but requires serious hardware
- **Prose quality depends on the model itself**: "If a model struggles with prose quality, no matter how hard you prompt it, it will continue to struggle" [31]

### Fine-Tunes That Target Voice
Community-created RP fine-tunes (Euryale, Fimbulvetr, Midnight Miqu) are merges and fine-tunes specifically tuned on fiction/roleplay data. They tend to produce less "assistant-like" output than base instruction-tuned models.

### Techniques That Work (Ranked by Community Impact)
1. **First Message quality**: Write the first message in exactly the style you want. The model mirrors this more than anything else.
2. **Sampler stack**: Min-P + DRY + XTC together
3. **Anti-slop phrase banning** (KoboldCpp): direct elimination of known cliches
4. **Ali:Chat format character cards**: dialogue-as-description for personality
5. **Author's Note at depth 4**: continuous voice reinforcement
6. **Edit early messages**: If the model produces bad output in the first few exchanges, edit those messages. The model treats early chat history as a style guide.
7. **Example dialogues**: Write them in the exact prose style you want, with the character's distinctive vocabulary
8. **Periodic chat pruning**: Every 30-50 turns, write a recap, prune history, pin essentials

### What Doesn't Work
- Telling the model "don't use cliches" in the system prompt (models are poor at following negative instructions)
- Very long system prompts with extensive rules (models lose track)
- Relying on temperature alone to fix repetition (too high = incoherent; doesn't fix vocabulary choice)

---

## 6. Specific Techniques for Our Problems

### Against Pandering/Validation
- Include explicit character goals that conflict with user desires
- In the character card, describe situations where the character disagrees, refuses, or pushes back
- Use Ali:Chat examples showing the character being dismissive, annoyed, or indifferent
- Author's Note: "{{char}} pursues their own agenda regardless of {{user}}'s approval"

### Against Repetitive Mannerisms
- KoboldCpp phrase banning for the specific offending phrases
- DRY sampler to penalize repeated sequences across the conversation
- Regex post-processing in SillyTavern to catch and remove patterns

### Against Stock RP Prose
- Antislop sampler with curated phrase list
- XTC sampler to force lexical variety
- First Message written in the target prose style (novelistic, not RP)
- System prompt specifying prose models: "Write like [specific author]. Avoid purple prose."

### Against Reactive Characters
- Character card must include: current goals, preoccupations, things they're worried about, plans they're executing
- Author's Note: "{{char}} has their own thoughts and plans. They do not merely react to {{user}}."
- Example dialogues showing the character initiating topics, changing subjects, pursuing their own threads

### Against "Sarcastic but Secretly Sweet"
- Explicitly ban emotional reveals in the character card if the character wouldn't do that
- Example dialogues showing the character being consistently [the intended personality] without "softening moments"
- Phrase ban: "rare unguarded moment", "walls came down", "vulnerability", "softened"

### Against System Prompt Drift
- Author's Note at depth 4 with key voice instructions (re-injected every message)
- Periodic chat summarization to keep context fresh
- Rotate in example dialogue snippets every 30-50 turns
- Larger context windows help (8192+ tokens minimum)

---

## References

1. SillyTavern Regex Extension docs: https://docs.sillytavern.app/extensions/regex/
2. ashuotaku SillyTavern presets/regex: https://github.com/ashuotaku/sillytavern
3. draedr SillyTavern scripts: https://github.com/draedr/sillytavernscripts
4. SillyTavern Issue #3014 (AntiSlop Sampler request, closed as out of scope): https://github.com/SillyTavern/SillyTavern/issues/3014
5. SillyTavern Instruct Mode docs: https://docs.sillytavern.app/usage/core-concepts/instructmode/
6. SillyTavern Author's Note docs: https://docs.sillytavern.app/usage/core-concepts/authors-note/
7. Ali:Chat Style guide (v1.5): https://rentry.co/alichat
8. SillyTavern Character Design docs: https://docs.sillytavern.app/usage/core-concepts/characterdesign/
9. Ali:Chat Lite (kingbri): https://rentry.co/kingbri-chara-guide
10. SillyTavern Context Template docs: https://docs.sillytavern.app/usage/prompts/context-template/
11. RisuAI GitHub: https://github.com/kwaroran/Risuai
12. RisuAI DeepWiki (character cards and formats): https://deepwiki.com/kwaroran/RisuAI/3.1-character-cards-and-formats
13. KoboldCpp Issue #1141 (Implement antislop-sampler): https://github.com/LostRuins/koboldcpp/issues/1141
14. KoboldCpp Discussion #1166 (48 phrase limit): https://github.com/LostRuins/koboldcpp/discussions/1166
15. Sukino's SillyTavern-Settings-and-Presets (banned tokens): https://huggingface.co/Sukino/SillyTavern-Settings-and-Presets
16. Sukino's Banned Tokens for KoboldCPP: https://huggingface.co/Sukino/SillyTavern-Settings-and-Presets/blob/6ebf1822ba3aa972c95e42df14bb05fafff2fb2c/Banned%20Tokens%20for%20KoboldCPP.md
17. Antislop ICLR 2026 paper: https://openreview.net/pdf/6916f45661bf884811be66da937b7467b97a9114.pdf
18. Antislop Sampler GitHub: https://github.com/sam-paech/antislop-sampler
19. Antislop vLLM variant: https://github.com/sam-paech/antislop-vllm
20. r/LocalLLaMA XTC sampler discussion: https://reddit.garudalinux.org/r/LocalLLaMA/comments/1fv5kos/say_goodbye_to_gptisms_and_slop_xtc_sampler_for/
21. SillyTavern Common Settings (DRY sampler): https://docs.sillytavern.app/usage/common-settings/
22. RPWithAI sampler settings guide: https://rpwithai.com/understanding-sampler-settings-for-ai-roleplay/
23. Ithy enhanced roleplay system prompt: https://ithy.com/article/enhanced-ai-roleplay-prompt-nf1b9p0d
24. Negative feedback on LLM roleplay apps: https://cuckoo.network/blog/2025/04/17/negative-feedback-on-llm-powered-storytelling-and-roleplay-apps
25. Ender's "Magic Portal" prompt: https://medium.com/@enderdragon/one-prompt-any-character-perfect-roleplay-0af59386bf9d
26. Ender's 2026 updated guide: https://medium.com/@enderdragon/an-updated-guide-to-ai-roleplaying-in-2026-with-deepseek-27583dbf485f
27. RoleRAG paper: https://arxiv.org/html/2505.18541v1
28. Emotional RAG paper: https://arxiv.org/html/2410.23041v1
29. Best LLMs for roleplay 2026: https://nutstudio.imyfone.com/llm-tips/best-llm-for-roleplay/
30. ParasiticRogue Model Tips and Tricks: https://huggingface.co/ParasiticRogue/Model-Tips-and-Tricks
31. MarinaraSpaghetti SillyTavern Settings: https://huggingface.co/MarinaraSpaghetti/SillyTavern-Settings/discussions/2
32. Lemmy: Dealing with repetitive AI responses: https://lemmy.world/post/20540890
33. RPWithAI SillyTavern optimization: https://rpwithai.com/optimize-sillytavern-for-ai-roleplay/
34. KoboldCpp Issue #1233 (regex support for antislop): https://github.com/LostRuins/koboldcpp/issues/1233
35. KoboldCpp Issue #1234 (rewind on anti-slop): https://github.com/LostRuins/koboldcpp/issues/1234
