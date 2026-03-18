# Multi-Character Scenes and NPC Management in Open-Source RP Platforms

Date: 2026-03-15

## Problem Statement

When a character card like "The Wanderlust Guild" contains 5 characters, or when a character like Nora has a mother (Diane) mentioned in her description, how should the bot play multiple distinct characters in a scene? This research covers how open-source platforms solve this.

---

## 1. Group Chat / Multi-Character Modes (SillyTavern)

SillyTavern's group chat is the most mature open-source implementation. It treats multi-character scenes as **separate characters taking turns**, not one model playing everyone simultaneously.

### Architecture

Each group chat maintains its own member list, activation strategy, generation settings, and chat history. The chat history is always shared between all members. Any existing character card can be added, removed, muted, or re-ordered within the group [1].

### Character Selection Strategies

Three strategies determine who speaks next [1][2]:

1. **Natural Order** (default): Extracts mentions of group member names from the last message. Characters are also activated by their **Talkativeness** factor (0% = shy/never talks unless mentioned, 100% = chatty/always replies). If no one is activated, one speaker is selected randomly.

2. **List Order**: Characters respond in the order they appear in the group members list, no other rules applied.

3. **Random**: Purely random selection, ignoring all conditions.

Users can also manually trigger a specific character via the UI or the `/trigger` command.

### Prompt Construction Per Turn

This is the critical detail for our implementation. Two modes exist [1][2]:

**Default mode (single speaker):** Each time a message is generated, only the character card information of the **active speaker** is included in the context. The system swaps in that character's description, personality, scenario, and example messages. Other characters' definitions are excluded.

**Joined mode:** All group members' fields are joined into one combined prompt. You can define a prefix/suffix to separate them. This means the model sees all character descriptions at once. The resulting prompt has all character descriptions joined into "one big blob of text."

### Depth Prompts

Each character can have a "Character's Note" injected at a specific message depth in the chat. In group chats, these are aggregated via `getGroupDepthPrompts()` and passed to the prompt manager at their specified depths. This means each group member can contribute context at different levels of the conversation history [2].

### Auto-Mode

When enabled, the group chat follows the reply order and triggers message generation without user interaction. The next turn triggers after a 5-second delay when the last drafted character finishes [1].

### UX Implications

- Each character gets its own generation call (one API request per character turn)
- The user sees messages attributed to specific characters with their avatars
- This is expensive: a 5-character scene means 5 API calls per round
- Character voice separation is enforced by literally generating one character at a time

### Relevance to Our System

We use a **single generation call** approach (one card, one bot playing everyone). SillyTavern's group chat is the "correct" solution but requires N API calls per round. The alternative approach they support is the "joined" mode where all cards are merged, which is closer to our multi-character card scenario.

## 2. NPC Generation from Character Descriptions

When Nora's card mentions her mother Diane, how do platforms handle the bot playing Diane?

### Approach A: Embedded Lorebook / Character Book

The Character Card V2 spec includes a `character_book` field that embeds a lorebook directly into the card [3][4]. This is the standard approach:

```json
{
  "data": {
    "name": "Nora",
    "description": "...",
    "character_book": {
      "entries": [
        {
          "keys": ["Diane", "mother", "mom"],
          "secondary_keys": [],
          "content": "Diane is Nora's mother. She is 52, a former dancer...",
          "enabled": true,
          "insertion_order": 100,
          "selective": false,
          "constant": false,
          "position": "after_char"
        }
      ]
    }
  }
}
```

When the user or AI mentions "Diane" or "mother," the lorebook entry activates and injects Diane's description into the prompt. This is efficient because NPC details only consume tokens when relevant [5][6].

### Approach B: Include NPCs in the Main Description

Many card creators simply include NPC descriptions in the main character description or scenario fields. For example, The Wanderlust Guild card likely has all 5 characters described in the description field. This always consumes tokens but requires no special system support.

### Approach C: Narrator/Game Master Card

The card is framed not as a single character but as a narrator who controls all characters. The system prompt says something like "You are a narrator/game master controlling multiple characters in this scene" [7][8]. This naturally handles NPCs because the model is already in "control everyone" mode.

### Relevance to Our System

We should support **Approach A** (character_book / lorebook) since it's the V2 spec standard and cards from Chub/CharacterHub already include them. We should also handle **Approach B** gracefully since most multi-character cards use this pattern. Our prompt already works for Approach C (narrator mode).

## 3. Character Consistency in Multi-Character Scenes

The core challenge: preventing all NPCs from sounding the same in a single generation.

### Technique 1: Distinct Voice Definitions

Give each character specific speech patterns, vocabulary, and mannerisms in their definition. The more concrete and specific, the better [9]:

- BAD: "Diane is friendly and warm"
- GOOD: "Diane speaks in long, meandering sentences, always circles back to 'when I was your age,' drops her g's (runnin', thinkin'), calls everyone 'honey'"

### Technique 2: Role Tags / Dialogue Attribution

Enforce a formatting convention where each character's speech is clearly tagged [10]:

```
**Kael:** *leans against the doorframe* "We don't have time for this."
**Mira:** *adjusts her spectacles* "We don't have time to rush either, Kael."
```

This is the `Character Name: [action] "dialogue"` convention. The prompt should explicitly instruct this format for multi-character cards.

### Technique 3: Character Bleed Prevention via Prompt

Community-recommended prompt additions [11]:

- "Each character has a distinct voice. Do not let characters speak or act identically."
- "When writing dialogue for [Character], use their specific speech patterns as defined."
- Rotate example dialogue snippets to reinforce voice

### Technique 4: Separate Generation Calls (SillyTavern approach)

The nuclear option: generate each character's response separately. Eliminates bleed entirely but costs N API calls. SillyTavern's group chat does this [1].

### Technique 5: Miniscript / Compressed Character Defs

Use abbreviated attribute formats to pack more character distinction into limited tokens [12]:

```
[Kael: rogue, sarcastic, terse sentences, never says please]
[Mira: scholar, precise vocabulary, speaks in questions, adjusts spectacles when nervous]
```

### Relevance to Our System

For a single-generation approach, Techniques 1-3 and 5 are the most practical. Our prompt should:
1. Detect multi-character cards and add formatting instructions ("tag dialogue with character names")
2. Include distinct voice markers for each character
3. Add anti-bleed instructions

## 4. Lorebooks for World-Building

### Data Format (SillyTavern World Info)

A lorebook entry has these fields [5][6][13]:

| Field | Purpose |
|-------|---------|
| `keys` | Primary trigger words (array of strings, supports regex) |
| `secondary_keys` | AND-condition triggers (both primary + secondary must match) |
| `content` | Text injected into prompt when activated |
| `enabled` | Whether the entry is active |
| `constant` | If true, always injected regardless of keywords |
| `selective` | If true, requires both primary and secondary keys |
| `insertion_order` | Priority (higher = closer to end of context = more impact) |
| `position` | Where to inject: before_char, after_char, before_examples, at_depth |
| `depth` | For at_depth position, how many messages back to inject |
| `scan_depth` | How many recent messages to scan for keywords |
| `token_budget` | Max tokens allocated to this entry |
| `probability` | Chance of activation (0-100, default 100) |

### How Triggers Work

The system scans the N most recent messages (scan_depth) for keywords. When found, the entry's content is injected at the specified position. Recursive scanning means an activated entry's content can trigger other entries [5].

### Practical NPC Lorebook Entry

Using the NovelAI "Attributes" format [14]:

```
---
Diane [Nora's Mother]
AKA: Mom, Mother
Type: Person
Species: Human
Age: 52
Appearance: Tall, willowy build; silver-streaked auburn hair always in a loose bun; reading glasses on a chain; paint-stained fingers
Personality: Warm but overbearing; speaks in long winding sentences; prone to unsolicited advice; fiercely protective; former dancer with a bad knee
Relationships: Nora (daughter, complicated), Marcus (ex-husband)
Quote: "Honey, I'm not telling you what to do, I'm just saying what I would do, which is obviously the right thing."
---
```

### What Works and What Doesn't

**Works well:**
- Keyword-triggered entries for named NPCs (mention "Diane" -> inject Diane's description)
- Location descriptions triggered by place names
- Faction/organization lore with relationship context
- "Always active" entries for fundamental world rules

**Doesn't work well:**
- Pronoun-only references ("her mother" without naming Diane won't trigger)
- Overly broad keywords that fire constantly, wasting token budget
- Entries that are too long (eat the token budget, crowd out other entries)
- Entries without enough context (AI doesn't know how to use vague entries)

### Relevance to Our System

We should implement a lorebook/world info system that:
1. Parses `character_book` from imported V2/V3 cards
2. Scans recent messages for trigger keywords
3. Injects matching entries into the prompt at a configurable position
4. Respects a token budget to avoid overflowing context
5. Supports "always active" entries for key world facts

## 5. The Narrator Character

### How It Works

Instead of the AI playing a single character, it plays a **narrator/game master** who describes the scene and controls all characters. The system prompt shifts from "You are Nora" to "You are a narrator telling a story" [7][8].

### Implementation Patterns

**Pattern A: Dedicated narrator card.** Create a character called "Narrator" with a system prompt like:

> "You are a narrator/game master. You describe the scene from an omniscient perspective, controlling all NPCs. When characters speak, use their name followed by their dialogue. Describe the environment, character actions, and reactions."

**Pattern B: Narrator as a group chat member.** In SillyTavern group chats, you can add a "Narrator" character alongside the actual characters. The narrator describes scene transitions, environmental details, and actions, while individual character cards handle dialogue. This requires multiple generation calls [8].

**Pattern C: Narrator mode in single-card multi-character.** The card itself is written as a narrator card. The Wanderlust Guild card likely works this way -- it's not "you are Kael," it's "you are narrating a story about the guild."

### Benefits

- Naturally handles multi-character scenes without special system support
- The model doesn't get confused about "who it is" since it's everyone
- Environmental description and scene-setting come naturally
- Works for any number of characters

### Drawbacks

- Can feel less intimate than a single-character focus
- Character voices may blend since the model is playing everyone
- In SillyTavern group chats, the narrator mode "won't work as expected" because it takes over every turn [8]
- Less immersive for romance/relationship-focused RP where you want to feel like you're talking *to* someone

### Relevance to Our System

For multi-character cards like The Wanderlust Guild, our prompt should detect the multi-character nature and switch to narrator-style instructions. For single-character cards with mentioned NPCs (like Nora + Diane), we should keep the current single-character prompt but add NPC-handling instructions.

## 6. Dynamic Character Introduction

### How Platforms Handle New Characters Mid-Story

**No platform has a polished solution for this.** The approaches are:

**Lorebook pre-definition:** Define NPCs in the lorebook before the story starts. When the narrative reaches a point where they'd appear, their keyword triggers and the AI has context [5]. This requires advance planning.

**AI spontaneous creation:** The narrator/model invents characters on the fly. This works surprisingly well with strong models but has no consistency guarantees. The character might be described differently each time they appear [15].

**User-directed creation:** The user introduces a new character via an OOC message or by editing the lorebook mid-session. SillyTavern supports adding/editing world info entries during a chat [5].

**Soulkyn's approach:** Users describe their world and NPC personalities upfront. The AI manages introductions dynamically but within the pre-defined constraints. New NPCs introduced by the AI inherit the world's rules [16].

### Relevance to Our System

We should support:
1. Adding lorebook entries mid-chat (via UI)
2. The AI creating NPCs on the fly (just works with good prompts)
3. A mechanism to "pin" AI-created NPCs by extracting their details into a lorebook entry after they appear

## 7. Character Relationship Tracking

### Existing Extensions

Several SillyTavern extensions track relationships as structured data:

**BetterSimTracker** [17]: Tracks per-message relationship stats (affection, trust, desire, connection, mood, lastThought). Stores data per AI message. Visualizes progression with graphs. **Injects current relationship state into prompts** at a configurable depth (0-8). Includes JSON repair logic for malformed model output.

**RPG Companion** [18]: Tracks thoughts, relationships, and stats for all present characters. Shows floating thought bubbles next to character avatars. Has a "Present Characters Panel" with custom fields, relationship badges, character-specific stats, and internal thoughts. Tracker data is generated within the main AI response and automatically extracted. Each swipe preserves its own tracker data.

**Silly Sim Tracker** [19]: Parses JSON/YAML from code blocks in character messages. Renders visual tracker cards. Uses customizable templates. Integrates with SillyTavern's macro system for prompt injection.

### How Relationship Tracking Works (Implementation Pattern)

The common pattern across all these extensions:

1. **System prompt instruction** tells the model to include a JSON/YAML block at the end of each response with character stats
2. **Extension parses** the structured data from the response
3. **Data is stored** per-message (allowing rollback via swipes)
4. **Data is re-injected** into the prompt for the next generation at a specified depth
5. **UI visualizes** the data as cards, graphs, badges

Example prompt instruction (BetterSimTracker style):
```
At the end of your response, include a JSON block with relationship stats:
```json
{
  "characters": {
    "Nora": {
      "affection": 72,
      "trust": 85,
      "mood": "nervous but hopeful",
      "lastThought": "Did he notice my new dress?"
    },
    "Diane": {
      "affection": 45,
      "trust": 30,
      "mood": "suspicious",
      "lastThought": "He's not good enough for my daughter."
    }
  }
}
```

### Relevance to Our System

This is a v2/v3 feature, not needed now. But the pattern is clear:
- Add a prompt instruction to emit structured state
- Parse it from the response (strip it before displaying to the user)
- Store it in the database alongside the message
- Inject it back into the next prompt

---

## Summary: What To Implement

### Phase 1 (Now)
1. **Detect multi-character cards** (multiple names in description, or character_book present)
2. **Switch prompt mode**: For multi-char cards, add narrator-style instructions and dialogue attribution formatting ("tag each character's dialogue with their name in bold")
3. **Parse character_book** from imported V2 cards and store lorebook entries in DB
4. **Keyword-triggered lorebook injection**: Scan last N messages for trigger words, inject matching entries into prompt

### Phase 2 (Later)
5. **Lorebook UI**: Let users view/edit/add lorebook entries mid-chat
6. **NPC extraction**: After AI introduces a new character, offer to save them as a lorebook entry
7. **Character voice profiles**: Per-character speech pattern notes in the lorebook

### Phase 3 (Future)
8. **Relationship tracking**: Structured JSON state emitted by model, parsed, stored, re-injected
9. **Multi-generation mode**: Option to generate each character separately (expensive but higher quality)
10. **Dynamic lorebook from summaries**: Auto-generate lorebook entries from chat summaries

---

## Sources

1. [SillyTavern Group Chats Documentation](https://docs.sillytavern.app/usage/core-concepts/groupchats/)
2. [DeepWiki: SillyTavern Group Chats and Multi-Character Interactions](https://deepwiki.com/SillyTavern/SillyTavern/9-group-chats-and-multi-character-interactions)
3. [Character Card V2 Specification](https://github.com/malfoyslastname/character-card-spec-v2/blob/main/spec_v2.md)
4. [Character Card V3 Specification](https://github.com/kwaroran/character-card-spec-v3/blob/main/SPEC_V3.md)
5. [SillyTavern World Info Documentation](https://docs.sillytavern.app/usage/core-concepts/worldinfo/)
6. [World Info Encyclopedia](https://rentry.co/world-info-encyclopedia)
7. [SillyTavern Prompts Documentation](https://docs.sillytavern.app/usage/prompts/)
8. [SillyTavern FAQ: Narrator Mode](https://docs.sillytavern.app/usage/faq/)
9. [AI Character Prompts: Mastering Persona Creation](https://www.jenova.ai/en/resources/ai-character-prompts)
10. [Multi-Character Dialogue Dataset Format](https://huggingface.co/datasets/agentlans/multi-character-dialogue)
11. [SillyTavern Tutorials: Character Bleed Prevention](https://sider.ai/blog/ai-tools/best-sillytavern-tutorials-to-master-roleplay-ai-in-2025)
12. [NovelAI Lorebook: Using Attributes](https://tapwavezodiac.github.io/novelaiUKB/Using-Attributes.html)
13. [Chub AI Lorebooks Guide](https://docs.chub.ai/docs/advanced-setups/lorebooks)
14. [NovelAI Lorebook Documentation](https://docs.novelai.net/en/text/lorebook/)
15. [Soulkyn Multi-NPC Roleplay System](https://roleplay-bot.com/blog/building-entire-worlds-not-just-characters-soulkyns-revolutionary-multi-npc-roleplay-system/)
16. [Soulkyn AI Group Chat](https://landing.soulkyn.com/l/en-US/ai-group-chat)
17. [BetterSimTracker Extension](https://github.com/ghostd93/BetterSimTracker)
18. [RPG Companion Extension](https://github.com/SpicyMarinara/rpg-companion-sillytavern)
19. [Silly Sim Tracker Extension](https://github.com/prolix-oc/SillyTavern-SimTracker)
20. [SillyTavern Character Design Guide](https://docs.sillytavern.app/usage/core-concepts/characterdesign/)
21. [Lorebooks as Active Scenario Guidance Tool](https://huggingface.co/sphiratrioth666/Lorebooks_as_ACTIVE_scenario_and_character_guidance_tool)
22. [SillyTavern Extension-GroupGreetings](https://github.com/SillyTavern/Extension-GroupGreetings)
23. [AI Dungeon World Info Research](https://github.com/valahraban/AID-World-Info-research-sheet)
24. [SillyTavern Dynamic World Building Discussion](https://github.com/SillyTavern/SillyTavern/discussions/3466)
