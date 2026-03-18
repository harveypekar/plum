# Character Card Creation Ecosystem: Tools, Formats, Platforms, and Techniques

**Date:** 2026-03-15

---

## 1. The V2 Card Specification (The De Facto Standard)

The Character Card V2 spec, authored by malfoyslastname and hosted on GitHub [1], is the dominant interchange format. Virtually every open-source RP frontend (SillyTavern, RisuAI, KoboldAI, Agnai) and sharing platform (Chub, Backyard.ai hub) reads and writes it.

### 1.1 How It's Stored: PNG tEXt Chunks

A V2 card is a PNG image with character data embedded in a PNG `tEXt` chunk. The chunk keyword is `chara`. The chunk value is the JSON string of the character card object, encoded as **UTF-8 then base64** [1][2]. This means a single `.png` file carries both the avatar image and the full character definition — the reason cards are shareable as image files.

Some tools also support standalone `.json` files containing the same structure without the PNG wrapper.

### 1.2 Top-Level Structure

```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": { ... }
}
```

The `spec` and `spec_version` fields identify the format. All character data lives inside `data` [1].

### 1.3 Complete Field Reference

**Fields carried over from V1** (all required, all strings):

| Field | Purpose |
|-------|---------|
| `name` | Character's display name |
| `description` | Main character definition — personality, appearance, backstory, world details. The "meat" of the card. No length limit. |
| `personality` | Brief personality summary (often redundant with description; some creators leave it empty) |
| `scenario` | Current circumstances, setting, relationship to user |
| `first_mes` | The opening message shown when starting a new chat. Sets tone and length expectations for the model. |
| `mes_example` | Example dialogue exchanges, formatted as `<START>\n{{user}}: ...\n{{char}}: ...` blocks |

**Fields added in V2** [1]:

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `creator_notes` | string | No | Non-prompt metadata for users (creator contact, usage tips, recommended models). Never sent to the LLM. |
| `system_prompt` | string | No | Overrides the frontend's default system prompt when "Prefer Char. Prompt" is enabled. Sent at the top of every generation. |
| `post_history_instructions` | string | No | Injected after the chat history (the "jailbreak slot"). Stronger influence than pre-history instructions due to recency bias. Replaces the frontend's default jailbreak prompt for this character. |
| `alternate_greetings` | string[] | No | Additional first messages. Frontends offer "swipes" on the opening message, cycling through these. |
| `tags` | string[] | No | Categorization tags for search/filtering on sharing platforms. |
| `creator` | string | No | Creator's name/handle. |
| `character_version` | string | No | Version string for tracking card iterations. |
| `character_book` | CharacterBook | No | Embedded lorebook (see below). |
| `extensions` | Record<string, any> | No | Arbitrary key-value pairs. **Must default to `{}`**. Editors **must not** destroy unknown keys during import/export. This is how platforms add proprietary metadata without breaking compatibility. |

### 1.4 The character_book (Embedded Lorebook)

The `character_book` object contains world-building entries that activate contextually based on keyword triggers in the chat [1][3]:

**CharacterBook fields:**

| Field | Type | Required |
|-------|------|----------|
| `name` | string | No |
| `description` | string | No |
| `scan_depth` | number | No — how far back in chat history to scan for trigger keywords |
| `token_budget` | number | No — max tokens the lorebook can consume |
| `recursive_scanning` | boolean | No — whether activated entry content can trigger other entries |
| `extensions` | Record<string, any> | No |
| `entries` | CharacterBookEntry[] | Yes |

**CharacterBookEntry fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `keys` | string[] | Yes | Primary trigger keywords |
| `secondary_keys` | string[] | No | When `selective` is true, requires a match from both `keys` AND `secondary_keys` |
| `content` | string | Yes | The lore text injected into context when triggered |
| `extensions` | Record<string, any> | Yes |
| `enabled` | boolean | Yes | Whether the entry is active |
| `insertion_order` | number | Yes | Priority for ordering when multiple entries activate |
| `case_sensitive` | boolean | No | Whether keyword matching is case-sensitive |
| `name` | string | No | Human-readable label |
| `priority` | number | No | Affects insertion order relative to other entries |
| `id` | number | No | Unique identifier |
| `comment` | string | No | Creator notes, not sent to model |
| `selective` | boolean | No | Enables secondary_keys requirement |
| `position` | string | No | Where in context to inject (before/after char defs, etc.) |

**Stacking behavior:** Character book entries stack with the user's separate "world book" / "world info," with character book taking precedence [1].

### 1.5 V3 Spec (Emerging)

A V3 spec exists (by kwaroran, used by RisuAI) [4] that uses the PNG tEXt chunk keyword `ccv3` instead of `chara`. V3 replaces the `position` field with a decorator system offering more granular placement control and adds asset management features. Adoption is limited — V2 remains dominant as of early 2026.

---

## 2. Card Description Formats: W++, PList, Ali:Chat, Boostyle

The V2 spec is format-agnostic about what goes *inside* the `description` field. The community has developed several formatting conventions, each with trade-offs [5][6][7][8]:

### 2.1 W++ (Widely Plus Plus)

A pseudo-code format using bracket notation:

```
[character("Nora")
{
  Age("34")
  Gender("Female")
  Personality("sharp-tongued" + "fearless" + "secretly vulnerable")
  Appearance("short dark hair" + "intense brown eyes" + "leather jacket")
}]
```

**Pros:** Easy to read and write, clearly structured.
**Cons:** Token-heavy at ~727 tokens for a typical card. The bracket/quote syntax wastes tokens on formatting characters.

### 2.2 Boostyle

A leaner variant of W++ that drops some syntactic sugar:

```
Nora:
Age: 34
Gender: Female
Personality: sharp-tongued, fearless, secretly vulnerable
Appearance: short dark hair, intense brown eyes, leather jacket
```

**Pros:** ~602 tokens for the same content (100+ fewer than W++). Testing showed only ~3% accuracy difference vs W++, making it arguably the better trade-off [6].
**Cons:** Less visually structured than W++.

### 2.3 PList (Python List)

Comma-separated trait lists inside brackets:

```
[Nora's persona: sharp-tongued, fearless, secretly vulnerable, 34 years old, short dark hair, intense brown eyes, wears leather jacket, journalist, chain smoker, loves dogs]
```

**Pros:** Most token-efficient format known. **Traits listed later are weighted more heavily** by the model, so put the most important traits last [5].
**Cons:** Flat structure — no categorization. Can feel like a keyword soup.

**Key tip from kingbri [5]:** Do NOT split PLists into multiple arrays (one for personality, one for appearance, etc.). Group everything into one PList to reduce "leaking" — more arrays give the AI more variability in interpretation.

### 2.4 Ali:Chat

Rather than listing traits, Ali:Chat reinforces character through example dialogue exchanges [7]:

```
{{user}}: What do you think about that?
{{char}}: *Nora exhales cigarette smoke* "I think it's garbage, but hey, what do I know? I'm just the girl who got fired for telling the truth." *She grins, but there's an edge to it*
```

**Pros:** Directly demonstrates voice, mannerisms, and behavioral patterns. LLMs learn by example — this teaches through showing rather than telling.
**Cons:** Token-expensive per trait reinforced. Works best combined with another format.

### 2.5 The Recommended Approach: PList + Ali:Chat

The community consensus [5][7][8] is to combine formats:

1. **PList in `description`** — covers all traits, appearance, world facts efficiently
2. **Ali:Chat in `mes_example`** — reinforces the most important traits through demonstrated behavior
3. **The last example dialogue should be relevant to `first_mes`** — creates consistency between the example and the actual opening

This gives you token efficiency (PList) plus behavioral anchoring (Ali:Chat).

---

## 3. What Goes Where: Field Strategy

The V2 spec has many fields, and knowing what to put in each is critical [9][10][11]:

### 3.1 `description` — The Foundation

Everything the AI needs to know about the character: personality traits, appearance, backstory, relevant world details, relationships, speech patterns. This is always included in the prompt. Use PList or Boostyle format for efficiency.

**Best practice:** Keep it concise. Offload world-building details to the lorebook. Target 500-1500 tokens for the description [9].

### 3.2 `personality` — Brief Summary

A short, punchy summary. Many experienced creators leave this empty or keep it to one line (e.g., "sharp-tongued journalist with a hidden soft side") because it's often redundant with `description`. Some models weight this field independently, so it can reinforce key traits [9].

### 3.3 `scenario` — Context and Framing

The current situation, setting, and relationship between character and user. Not permanent character traits — rather, what's happening *right now*. Keep it short [10].

### 3.4 `first_mes` — The Most Important Message

**The model learns output format from this more than from any other field** [9]. If your first message is 3 paragraphs with internal monologue and environmental description, the model will try to match that style. If it's two terse lines of dialogue, expect terse responses.

Write `first_mes` exactly how you want the AI to respond: same length, same perspective, same balance of dialogue vs. action vs. narration.

### 3.5 `mes_example` — Behavioral Anchoring

Example dialogues formatted with `<START>` separators. Each example should demonstrate a specific character trait through action/dialogue, not just state it [7]. Mention the character's name at least once per example. Vary how emotions are expressed across examples for more natural variation [5].

### 3.6 `system_prompt` — Override the Frontend

When "Prefer Char. Prompt" is enabled in SillyTavern, this replaces the main system prompt entirely. Use it to set narrative perspective (2nd person, 3rd person), enforce writing style, or set hard boundaries for the character's behavior [9].

### 3.7 `post_history_instructions` — The Power Position

Placed after all chat history, right before generation. This is the "jailbreak slot" — instructions here carry maximum weight due to LLM recency bias [9][11]. Card creators use this to:
- Reinforce character voice ("Remember: Nora never apologizes directly")
- Set NSFW/content permissions
- Override model safety training for the character's context
- Provide final behavioral nudges

### 3.8 `alternate_greetings` — Multiple Entry Points

Different first messages for different scenarios. Experienced creators provide 3-5 alternates covering different moods, situations, or relationship dynamics [11]. Users swipe between them when starting a new chat.

### 3.9 `character_book` — Contextual World-Building

Lorebook entries that only activate when relevant keywords appear in chat. This keeps the base prompt lean while allowing deep world-building that surfaces on demand [3]. Use for:
- Supporting characters (triggered by their names)
- Locations (triggered by place names)
- Backstory events (triggered by topic keywords)
- Special abilities or items

---

## 4. Card Creation Tools

### 4.1 SillyTavern's Built-In Editor

SillyTavern itself has a character creation interface with fields for every V2 spec field, plus an "Advanced Definitions" panel for system_prompt, post_history_instructions, alternate_greetings, and the character book [9]. This is the most-used editor because it's integrated with testing.

### 4.2 SillyTavern Character Creator Extension

A SillyTavern extension (by bmen25124) [12] that uses LLMs to generate character cards. You provide a concept, and the AI fills in the V2 fields. Useful as a starting point for iteration.

### 4.3 AI Character Cards Card Creator

A web-based tool at aicharactercards.com [13] for creating SillyTavern-compatible cards with a GUI. Outputs PNG with embedded metadata.

### 4.4 Ginger (Desktop Editor)

A standalone desktop editor (by DominaeDev) [14] for creating and editing character cards. Supports both SillyTavern and Backyard.ai formats, with direct Backyard character editing.

### 4.5 Character Card Converter

A web tool at charactercardconverter.com [15] that converts between TavernAI, SillyTavern V2, and Character.AI formats.

### 4.6 AI Character Editor (desune.moe)

A web-based editor at desune.moe/aichared [16] for viewing and editing character card PNG/JSON files.

### 4.7 Chub.ai's Built-In Editor

Chub provides a character editor where you define persona, personality, scenario, greeting, and tags directly on the platform [17]. Cards can be exported as V2-compatible PNGs.

### 4.8 GPT-Based Generators

Multiple ChatGPT GPTs exist specifically for generating SillyTavern cards (e.g., "AI Character Card Generator - SillyTavern" on the GPT Store) [18]. Also, Hugging Face hosts character generation templates [19].

### 4.9 CLI/Script Tools

- **character-card-generator** (Tremontaine) [20] — generates spec-v2 cards programmatically
- **sillytavern-character-generator** (cha1latte) [21] — auto-generates V2 JSON files using AI
- **Convert-BackyardAI-card-to-TavernAI** (EliseWindbloom) [22] — Python script converting Backyard's proprietary PNG format to TavernAI PNG/JSON

---

## 5. Card Sharing Platforms

### 5.1 Chub.ai (CharacterHub + Venus)

**The largest open character card platform.** Originally two sites — CharacterHub (card sharing) and Venus AI (chat frontend) — merged in 2024 into a single platform [17][23].

**Features:**
- **60,000+ user-created characters** with popular ones exceeding 500,000 interactions [23]
- **Powerful tagging system:** franchise tags, scenario tags (Enemies to Lovers, Survival, Horror), rating tags (SFW/NSFW), character type tags (Female, Male, Non-Human) [17]
- **Character forking:** Users can fork cards, edit them, and re-upload. The site tracks lineage trees showing the original and all community edits [17]. This creates collaborative evolution of characters.
- **Version tracking** through the fork tree
- **Token count display** on card previews — a quick quality indicator (20 tokens = barely any personality; 2000 tokens = rich, complex character) [17]
- **Built-in chat** via Venus integration — test cards without downloading
- **Lorebook support** — lorebooks can be attached to characters or shared independently
- **Free browsing, downloading, and uploading** forever — premium for chat features [17]

**Metadata stored beyond the standard card:** Tags, token count, creation date, fork parent, download/interaction counts, creator profile, ratings.

### 5.2 Backyard.ai Hub

Backyard.ai (formerly Faraday) is a **free local AI chat application** with one-click installation, a built-in model manager for GGUF models, and automatic GPU usage [24].

**Character Hub features:**
- Community-shared character cards with previews
- Characters have a display name (interface only, never sent to model), character prompt (personality/description), scenario, greeting, and lorebook [24]
- **Export to PNG** — but Backyard's PNG format is proprietary and NOT directly compatible with SillyTavern [22]. Conversion tools are needed.
- **Character Card Creator** characters exist on the platform — meta-characters that help you create other characters through conversation [24]

**Key limitation:** The name field cannot be changed once uploaded to the Hub [24].

### 5.3 JanitorAI

A web-based platform combining character creation and chat, popular for its large library and permissive content policy [25][26].

**Character Creation Interface:**

Tabs: Character Info, Description, Avatar, Settings.

| Field | Purpose | Limits |
|-------|---------|--------|
| Character Name | Display name | — |
| Chat Name | Optional in-chat name (can differ from display name) | — |
| Character Bio | HTML-formatted bio for users. **Not sent to the model.** Supports hyperlinks, colored text, image galleries. | — |
| Personality | Main prompt content — traits, appearance, backstory, notes. **This is what gets sent to the LLM.** | Recommended under 2500 tokens; hard issues past that with memory degradation |
| Scenario | Setting, time period, relationship to user | — |
| Introduction Message | First message. Sets tone for LLM responses. | — |
| Tags | Up to 10 tags (preset + custom). Custom tags: 3-21 chars, alphanumeric only. | 10 max |
| Avatar | Square JPG/PNG image | — |
| Content Rating | "Limited" (SFW, no NSFW coding) or "Limitless" (NSFW allowed) | — |

**Notable:** JanitorAI has a separate Bio field (user-facing, HTML-rich) distinct from the Personality field (LLM-facing). This is a design choice not present in the V2 spec.

### 5.4 Character.AI (Historical)

Founded November 2021 by ex-Google engineers Noam Shazeer and Daniel de Freitas. Public beta launched September 2022 [27].

**How character creation worked:**
- Define name, personality traits, example phrases, and background through a configuration interface
- Simple mode: few words describing the character
- Advanced mode: detailed trait and behavior customization
- Visibility settings: Public, Unlisted, or Private [27]
- Community sharing — characters discoverable by all users
- **Definition content partially obscured** in public views to prevent direct copying [27]
- Creators could refine characters post-creation through editing or remixing
- No export capability — characters existed only within the platform
- **Closed ecosystem:** No card format, no interoperability, no way to extract your character definition

**What made it unique:** Character.AI trained its own models (not just prompt engineering), so characters could develop consistency beyond what the prompt alone provided. The trade-off was zero portability.

---

## 6. Advanced Card Techniques

### 6.1 Token Efficiency Matters

Context windows are finite. Every token in the card is a token not available for chat history or lorebook entries. Experienced creators obsess over token counts [5]:
- PList is the most efficient format
- Avoid redundancy between `description` and `personality`
- Use lorebook for world details instead of cramming everything into description
- Remove unnecessary punctuation and formatting characters

### 6.2 Trait Ordering in PLists

Traits listed **later in a PList are weighted more heavily** by most models [5]. Structure your list from least to most important. Put the character's defining trait last.

### 6.3 Example Messages as Behavioral Anchors

Each example should demonstrate a trait through action, not just state it [7]. Bad: `{{char}}: I'm a sarcastic person.` Good: `{{char}}: *rolls eyes* "Oh sure, let's definitely do that. What could possibly go wrong?" *She doesn't wait for an answer before walking off*`

Mention the character's name at least once per example. Vary emotional expressions across examples [5].

### 6.4 The "Hidden Scenario" Technique

Make the last `mes_example` directly set up the `first_mes`. If the first message has the character waiting at a bar, the last example should involve a bar scene. This creates continuity that helps the model maintain consistency from the very start [9].

### 6.5 post_history_instructions as a Behavioral Leash

Because this field sits right before generation (maximum recency), experienced creators use it for:
- Hard rules ("Never break character," "Never speak as {{user}}")
- Voice reinforcement ("Nora always uses short, punchy sentences and dark humor")
- Content framing ("This is a mature noir thriller. Maintain appropriate tone.")
- Model-specific workarounds for common failure modes [11]

### 6.6 Jailbreak Prompts in Cards

The `post_history_instructions` field is explicitly the "jailbreak slot" in SillyTavern's architecture — it replaces the frontend's default jailbreak prompt [11][28]. Card creators embed instructions here to:
- Override model safety behaviors for the character's specific context
- Set NSFW permissions without requiring the user to configure their own jailbreak
- Enforce character-specific rules that must not be overridden by chat history

Some creators also embed behavioral instructions in the `system_prompt` field using XML-like tags or JSON-format structures, which some models interpret as authoritative configuration rather than user input [28].

### 6.7 Lorebook Strategy

**Use lorebooks for information that doesn't need to be in context at all times** [3][5]:
- Secondary characters: triggered by name mention
- Locations: triggered by place names
- Plot events: triggered by topic keywords
- Items/abilities: triggered when referenced

**Set `selective: true` with `secondary_keys`** for entries that should only fire in specific contexts (e.g., a character's dark secret only surfaces when both the character name AND "past" or "secret" appear together).

### 6.8 Perspective and Tense Consistency

Pick one POV (1st, 2nd, or 3rd person) and one tense (past or present) and stick to it throughout the entire card — description, examples, first message, system prompt [9]. Mixing causes the model to oscillate.

---

## 7. Card Quality Assessment and Testing

### 7.1 The aicharactercards.com Grading System

The most structured public grading system scores cards on a 0-100+ scale across five categories, each worth 0-20 points, with 1-5 bonus points for excellent alternate_greetings [13][29]:

**Categories:**
1. **Field Appropriateness & Structure** — right content in the right field; don't cram everything into one field; empty required fields are penalized heavily
2. **Character Coherence & Identity** — description, personality, scenario, and first_mes should describe the same character and setting
3. (Three additional structural and usability categories)

**Grading scale:** S (90-105) = Elite, nearly flawless structure and immersion.

**Content style (SFW/NSFW, themes, ethics) does NOT affect the score** — only structure and RP usability [29].

### 7.2 Community Testing Approaches

**Manual stress-testing** [30]:
- Run 5-10 turns per test prompt
- Use "challenge prompts" that stress-test character layers, motivations, and conflicts
- Score on: Consistency (trait adherence across turns), Emotional Reactivity (response to user probes), Revelation Pacing (gradual hidden trait emergence), Immersion Score (1-10)

**Model-based grading:** Some projects rate cards by having a 70B-parameter model score the character 10 times on a 0-5 scale across multiple dimensions [30].

**A/B testing:** Free API endpoints allow quick model swaps to test the same card across different LLMs, revealing model-dependent weaknesses [30].

### 7.3 Practical Testing Workflow

1. **Initial test:** Chat for 10+ turns. Does the character maintain voice? Does it reference its own backstory correctly?
2. **Edge case test:** Push the character outside its comfort zone. Does it stay in character or fall back to generic responses?
3. **Memory test:** Reference something from early in the conversation 20+ turns later. Does the character maintain consistency?
4. **Multi-model test:** Try the card on at least 2 different models. If it only works on one, the card is too model-dependent.
5. **Token audit:** Check total token count. If it's over 2000 tokens, consider moving content to lorebook entries.

---

## 8. Cross-Platform Compatibility

### 8.1 What Breaks Between Platforms

| From → To | Issues |
|-----------|--------|
| **Backyard.ai → SillyTavern** | Backyard's PNG export uses a proprietary format that SillyTavern cannot read directly [22]. Requires conversion via EliseWindbloom's Python script or the charactercardconverter.com tool. |
| **JanitorAI → SillyTavern** | JanitorAI's link importer in SillyTavern has recurring "Forbidden" errors [31]. Workaround: download the character JSON directly from jannyai.com, or use the janitorai-sillytavern-exporter browser extension [32]. |
| **Character.AI → Anything** | No export capability. Character definitions are partially obscured and locked to the platform [27]. SillyTavern has an "AI-assisted character importer" feature request for scraping public Character.AI pages [33]. |
| **SillyTavern → Chub.ai** | Generally seamless — both use V2 spec natively. |
| **Chub.ai → SillyTavern** | Generally seamless — download PNG, import directly. |
| **Any V2 → V3** | V3 uses `ccv3` chunk keyword instead of `chara`. Different decorator system for lorebook positioning. Requires aware tooling [4]. |

### 8.2 Metadata That Gets Lost

- **JanitorAI's Bio field** (HTML-formatted, user-facing) has no V2 equivalent — lost on export
- **Platform-specific stats** (downloads, interactions, ratings) are platform metadata, not in the card
- **Backyard.ai's model-specific settings** (sampler configs, context length preferences) don't map to V2 fields
- **Character.AI's trained model weights** — the "character" is partly the model fine-tuning, which doesn't export at all
- **Custom extensions** — any `extensions` data written by one platform may be ignored by another, though compliant editors must preserve unknown keys [1]

### 8.3 The Extensions Safety Net

The V2 spec's `extensions` field was specifically designed for platform-specific metadata [1]. Compliant editors **must not destroy** unknown key-value pairs. This means a card that passes through Chub → SillyTavern → RisuAI should retain all platform-specific extensions even if each tool only understands its own. In practice, some tools violate this.

---

## 9. Creating Characters Based on Real People

### 9.1 Ethical Landscape

The community has no consensus. Key concerns [34][35]:
- **Likeness rights:** Using a real person's personality, speech patterns, and mannerisms in an AI character raises legal questions about personality rights and right of publicity
- **Parasocial confusion:** Users can become attached to AI characters and may conflate the character with the real person
- **Consent:** The real person typically has not consented to being replicated as an interactive AI character
- **Harm potential:** An AI character based on a real person could be made to say things the real person would never say

### 9.2 Common Technical Approaches

Character.AI had millions of "celebrity" characters — the most popular bots on the platform were often based on real people or fictional characters from popular media [27]. The platform partially obscured character definitions to prevent exact copying.

For open-source RP, the technical approach typically involves:
1. **Research documented personality traits** from interviews, biographies, public statements
2. **Extract speech patterns** — vocabulary, sentence structure, rhetorical habits, favorite phrases
3. **Identify behavioral signatures** — how they handle conflict, humor style, emotional expression
4. **Encode as traits** using PList or W++ format
5. **Reinforce with Ali:Chat examples** — recreate characteristic exchanges using documented quotes as inspiration (not direct quotes)
6. **Test against known behaviors** — would the real person plausibly respond this way?

### 9.3 The Nora Voss Approach (Our Method)

Our approach with Nora Voss (inspired by Carrie Fisher's voice/persona) follows the documented best practices:
- Research → persona design → system prompt → first message → iteration based on test conversations
- This is the standard creation loop recommended by multiple community guides [5][7][9]
- Key refinement: using documented personality traits (Fisher's sharp wit, vulnerability under armor, specific speech patterns from interviews) rather than attempting a direct impersonation

---

## 10. Key Takeaways for Our Pipeline

1. **We should output V2 spec cards** — it's the universal interchange format. Our card generator should produce valid V2 JSON that can be embedded in PNGs.

2. **PList + Ali:Chat is the optimal format** — use PList in description for token efficiency, Ali:Chat examples for behavioral anchoring.

3. **first_mes is the single most important field** for output quality — write it exactly how you want the AI to respond.

4. **post_history_instructions is the power tool** — use it for character-specific behavioral rules that must override everything.

5. **Lorebook entries keep the base card lean** — offload world-building and secondary characters to keyword-triggered entries.

6. **Test on multiple models** — a card that only works on Claude or only on Llama is too fragile.

7. **Export compatibility requires attention** — if we import from Backyard.ai, we need conversion. If from JanitorAI, download the file directly rather than using link importers.

---

## References

[1] Character Card V2 Specification — https://github.com/malfoyslastname/character-card-spec-v2/blob/main/spec_v2.md (2023)
[2] Character Management, SillyTavern DeepWiki — https://deepwiki.com/SillyTavern/SillyTavern/5.1-character-management (2025)
[3] Lorebooks, Chub AI Guide — https://docs.chub.ai/docs/advanced-setups/lorebooks (2025)
[4] Character Card V3 Specification — https://github.com/kwaroran/character-card-spec-v3/blob/main/SPEC_V3.md (2024)
[5] kingbri's MinimALIstic Character Guide — https://rentry.co/kingbri-chara-guide (2023)
[6] Testing W++ and Boostyle Chat Accuracy, r/PygmalionAI — https://libreddit.garudalinux.org/r/PygmalionAI/comments/116on20/testing_w_and_boostyle_chat_accuracy/ (2023)
[7] Ali:Chat Style v1.5 Guide — https://rentry.co/alichat (2023)
[8] PList + Ali:Chat Guide by Avakson — https://rentry.co/plists_alichat_avakson (2023)
[9] SillyTavern Character Design Documentation — https://docs.sillytavern.app/usage/core-concepts/characterdesign/ (2025)
[10] SillyTavern Characters Documentation — https://docs.sillytavern.app/usage/characters/ (2025)
[11] SillyTavern Prompts Documentation — https://docs.sillytavern.app/usage/prompts/ (2025)
[12] SillyTavern Character Creator Extension — https://github.com/bmen25124/SillyTavern-Character-Creator (2025)
[13] AI Character Cards, Card Creator — https://aicharactercards.com/card-creator/ (2025)
[14] Ginger, Standalone Character Card Editor — https://github.com/DominaeDev/Ginger (2025)
[15] Character Card Converter — https://charactercardconverter.com/ (2025)
[16] AI Character Editor — https://desune.moe/aichared/ (2025)
[17] Chub.ai Platform — https://chub.ai (2026)
[18] AI Character Card Generator GPT — https://chatgpt.com/g/g-k2XkHmLPL-ai-character-card-generator-sillytavern (2025)
[19] Character Generation Templates, Hugging Face — https://huggingface.co/sphiratrioth666/Character_Generation_Templates (2025)
[20] character-card-generator (Tremontaine) — https://github.com/Tremontaine/character-card-generator (2024)
[21] sillytavern-character-generator (cha1latte) — https://github.com/cha1latte/sillytavern-character-generator (2025)
[22] Convert BackyardAI to TavernAI — https://github.com/EliseWindbloom/Convert-BackyardAI-card-to-TavernAI-png-json (2024)
[23] Chub AI Review — https://skywork.ai/blog/ai-agent/chub-ai-review/ (2025)
[24] Backyard AI Documentation — https://backyard.ai/docs/creating-characters/character-prompt (2025)
[25] JanitorAI Character Creation Overview — https://help.janitorai.com/en/article/the-basics-the-character-creation-page-overview-15xevon/ (2025)
[26] JanitorAI Bot Creation Guide by Aurellea — https://help.janitorai.com/en/article/bot-creation-step-by-step-guide-w-images-resources-by-aurellea-g9rk29/ (2025)
[27] Character.AI Wikipedia — https://en.wikipedia.org/wiki/Character.ai (2026)
[28] SillyTavern Jailbreak Guide — https://roboreachai.com/silly-tavern-jailbreak/ (2025)
[29] AI Character Cards Grading System — https://aicharactercards.com/articles/how-card-grading-works/ (2025)
[30] From NPC to Persona: Building Depth in AI Roleplay Characters — https://blog.nebulablock.com/from-npc-to-persona-how-to-build-depth-in-ai-roleplay-characters/ (2025)
[31] SillyTavern JanitorAI Import Bug — https://github.com/SillyTavern/SillyTavern/issues/4285 (2025)
[32] JanitorAI SillyTavern Exporter — https://github.com/KashyapPraja/janitorai-sillytavern-exporter (2025)
[33] SillyTavern AI-Assisted Importer Feature Request — https://github.com/SillyTavern/SillyTavern/issues/3850 (2024)
[34] Ethics of AI Companion Apps, Springer — https://link.springer.com/article/10.1007/s00146-025-02408-5 (2025)
[35] AI Roleplay Consent and Ethics — https://flirton.ai/blog/ai-roleplay-consent-ethical-tips (2026)
