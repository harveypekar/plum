# Research: Narration vs Dialogue Split and Prose Quality Control in RP Platforms

*Date: 2025-03-15*

## 1. First Person vs Third Person POV

### How platforms handle it

SillyTavern lets users switch between 1st and 3rd person narration via **System Prompt Presets**. The switch requires starting a new chat -- hot-swapping presets mid-conversation causes the old POV to bleed through. The Virt-io preset collection includes separate presets for 1st-person and 3rd-person modes [1].

The Guided Generations extension by Samueras offers **Narration Expansion** with separate templates for first, second, and third person perspective. This works as a Quick Reply that wraps the user's outline into a polished narrative in the chosen POV [2].

DreamGen's Opus models handle this in the system prompt: the difference between "role-playing" and "story-writing" is mainly in whether you label messages with character names. They recommend changing "story" to "role-play" in the system prompt for RP use cases [3].

### What works

- **Third person is dominant** in the RP community. First person is uncommon and tends to confuse models, especially smaller ones, because the training data for RP is overwhelmingly third person.
- **Model size matters**: Smaller models (7B-13B) struggle more with POV consistency. 70B+ models hold POV better with minimal prompting.
- **The first message sets the tone**: SillyTavern documentation emphasizes that "the model is more likely to pick up the style and length constraints from the first message than anything else" [4]. If your first message is in third person with inner thoughts, the model will mirror that.

### Prompt technique

The most common approach is a single line in the system prompt:

```
The writing style is: third person limited, narrated from {{char}}'s perspective
```

Some presets add:

```
Write narration in third person. Use italics for inner thoughts. Never use second person.
```

## 2. Narration Instructions / Prose Quality Prompting

### The consensus: model > prompt

The community consensus from SillyTavern, r/LocalLLaMA, and r/SillyTavernAI is blunt: **if a model has bad prose, no amount of prompting will fix it**. Prompting can steer a capable model, but it cannot make a 7B model write like a 70B model [5].

That said, here are the techniques that work on capable models:

### Technique 1: Show Don't Tell (the most common instruction)

Nearly every serious RP system prompt includes some variant of:

```
Adhere to the literary technique of "show, don't tell," prioritizing observable details
such as body language, facial expressions, and tone of voice to create a vivid experience,
showing character feelings and reactions through their behavior and interactions, rather
than describing their private thoughts.
```

This is from a widely-shared prompt documented on Scribd [6]. The 60/40 dialogue-to-narration ratio from that same prompt is notable -- it explicitly asks for "60% of the content focused on dialogue and 40% on descriptive actions and scene-setting."

### Technique 2: Anti-purple-prose instructions

```
Use impactful, concise writing. Avoid purple prose and overly flowery descriptions.
```

This appears in the same Scribd prompt and many derivatives. The tension here is real: LLMs default to purple prose, and telling them "don't" often isn't enough.

### Technique 3: Sensory grounding

```
Depicting the five senses, paying special attention to sensory details, particularly
{{char}}'s appearance -- including specific body parts and clothing.
```

### Technique 4: Sentence variety (Virt-io presets)

The Virt-io v1.9 preset includes these style guidelines [1]:

- **Pacing**: "Maintain consistent pacing, plot progression, and smooth scene transitions"
- **Varied Nouns and Verbs**: Using synonyms and active voice
- **Character Development**: Creating realistic, multi-dimensional characters
- **Realism and Suspension of Disbelief**: Maintaining balance between realism and fantastical elements

### Technique 5: Author emulation (StoryMode extension)

The StoryMode extension for SillyTavern lets you select an author to emulate. "The LLM adopts their voice, prose rhythm, description techniques, and dialogue patterns." This is backed by the StoryVerse research paper (Wang et al., 2024, Autodesk Research) [7].

This is the most directly relevant to "Rachel Kushner, not AO3" -- you could literally instruct the model to write like a specific author.

### Technique 6: Negative examples in the system prompt

Rather than saying "write well," some prompts explicitly list what NOT to do:

```
Do NOT:
- Use the same sentence structure repeatedly
- Start consecutive paragraphs the same way
- Use stock descriptions ("her eyes widened," "a shiver ran down her spine")
- Summarize emotions instead of showing them
- Use purple prose or overwrought metaphors
```

### The DreamGen approach

DreamGen's fine-tuned Opus models describe their target style as: "descriptive and evocative style with focus on atmosphere and setting, using vivid and detailed language to create a sense of place and time, employing literary devices such as similes, metaphors, and allusions, with varied sentence structure mixing short and long sentences that create rhythmic flow" [3].

The key insight from DreamGen is that they **fine-tuned the model** to produce this style rather than relying on prompting alone.

## 3. Example Messages (mes_example)

### How they work

In SillyTavern, example messages use the `<START>` tag as a block separator. They're injected into context only if there's room, and are pushed out block by block as chat history grows. Format [4]:

```
<START>
{{char}}: *Elena pressed her palm against the cold glass, watching the rain streak
silver lines across the city below. The coffee had gone cold an hour ago.* "You know
what I keep thinking about?" *She didn't turn around. The reflection in the window
showed her jaw tight, the slight tremor in her lower lip she'd never admit to.*
"That last Tuesday. Before everything."
```

### Best practices from the community

1. **Three good examples is adequate** for most context windows [4].
2. **The first message matters more than examples**: Models mirror the first message's style and length more strongly than example messages.
3. **Include narration, not just dialogue**: Most example messages in the wild are dialogue-heavy. The community recommends including action/narration in asterisks every 2-3 sentences to anchor the style.
4. **Use character name in actions**: "Harry Potter adjusts his glasses" (with the name) helps the model connect actions to the character, especially in long exchanges [4].
5. **Examples are temporary**: They exist to prime the style, then get pushed out of context as conversation progresses.

### Narration examples specifically

Very few card creators include narration-focused examples. Most examples are dialogue + action. To get novelistic narration, you should write examples that ARE novelistic:

```
<START>
{{char}}: The kitchen smelled of burnt sage and something sweeter underneath --
vanilla, maybe, or the ghost of yesterday's baking. Elena stood at the counter with
her hands in the dishwater, feeling the heat climb her wrists while she watched the
yard through the window above the sink. A cardinal landed on the fence post. She
counted to three before it flew away.

She dried her hands on the towel that hung from the oven door, the one with the
faded strawberries, and thought about calling her mother. She thought about it the
way you think about touching a bruise -- compulsive, pointless, certain to hurt.

"I'm going out," she said to no one, because the apartment was empty, because
saying it made it real.
```

This is the style gap: the community mostly writes RP-style examples. If you want literary fiction, you need literary fiction examples.

## 4. Author's Note

### What it is

Author's Note is an in-chat prompt injection at a configurable depth in the conversation history. It stays at a static depth regardless of how long the conversation gets [8].

### Positioning

- **Depth 0**: Placed at the very end of chat history (strongest influence on next response)
- **Depth 4**: Placed before the 3 most recent messages (moderate influence)
- **Top position**: After the scenario/character definition, before examples (weakest influence)

The closer to the bottom of the prompt, the more impact it has on the next response.

### Frequency control

Frequency 1 = injected every turn. Frequency 4 = every 4th turn. This lets you have style reminders that don't consume tokens every single message.

### What people put in it

Common Author's Note content for prose quality:

```
[Style: vivid, literary, third-person limited. Focus on sensory details and
internal monologue. Vary sentence length. Avoid cliches.]
```

```
[Write the next response in the style of literary fiction. Show emotions through
physical sensation and gesture, not narration. Use subtext in dialogue.]
```

```
[Author's note: This scene is tense and introspective. Slow pacing. Focus on
what {{char}} notices but doesn't say.]
```

The Author's Note is particularly powerful for **scene-by-scene steering** -- you can change the tone and pacing dynamically without editing the system prompt. For example, switching from "fast-paced action, short sentences" to "contemplative, sensory-rich, slow pacing" between scenes.

## 5. Response Length Control

### Token-based approaches

The Sphiratrioth presets offer two modes [5]:
- **[150T]**: ~150 tokens, "more conversational feeling," roughly 1/2 dialogue and 1/2 narration
- **[350T]**: ~350 tokens, "more roleplay/storytelling feeling," roughly 1/3 dialogue and 2/3 narration

The relationship is notable: **longer responses = more narration-heavy**. Short responses become dialogue-dominant.

### Model behavior with token limits

- Models don't always respect the response token limit. Users report balance around 200-210 tokens [9].
- Default SillyTavern Llama 3 presets produce very short responses (50-100 tokens). The fix: make your greeting/first message long and detailed to encourage fuller responses.
- **The first message length is the strongest signal** for response length. A 3-paragraph first message produces 3-paragraph responses. A 1-line first message produces 1-line responses.

### Explicit instruction approach

Some system prompts include:

```
Write 3-5 paragraphs per response. Each paragraph should serve a distinct purpose:
action, internal thought, dialogue, or environmental description.
```

This works but can feel mechanical. The better approach is to set the length through examples and first messages.

### The quality-length relationship

Shorter responses (1-2 paragraphs) tend to be punchier and more dialogue-focused. Longer responses (3-5 paragraphs) allow for the narration layers (sensory detail, interiority, environmental description) that produce literary-quality prose. If you want novelistic quality, you likely need 300-500 tokens per response minimum.

## 6. "Slop" and Repetition

### The Antislop project

The most systematic work on LLM repetitive patterns is the **Antislop framework** by Sam Paech [10], published as a conference paper at ICLR 2026.

Key findings:
- Some slop patterns appear **over 1,000x more frequently** in LLM output than human text
- The antislop sampler suppresses 8,000+ patterns while maintaining quality
- Token-level banning becomes unusable at just 2,000 patterns; phrase-level backtracking is necessary

### How the Antislop sampler works

Rather than banning tokens, it waits for the whole phrase to appear, then **backtracks** and reduces the probabilities of tokens that lead to that phrase. This preserves vocabulary while eliminating cliched constructions.

It also supports **regex bans** for structural patterns like "not X, but Y."

### The slop phrase list

The `slop_phrase_prob_adjustments.json` file [11] contains auto-generated entries of over-represented LLM phrases. Notable examples:

**Single words**: kaleidoscope, symphony, tapestry, cacophony, canvas, orchestra, camaraderie

**Phrases**: "barely above a whisper," "eyes never leaving," "a dance of," "couldn't help but," "bore silent witness to," "eyes sparkling with," "cold and calculating," "chuckles darkly," "maybe just maybe," "maybe that was enough," "with a mixture of," "air was filled with anticipation," "moth to a flame," "testament to," "body and soul"

**Structural patterns**: "It's not just X, it's Y" (appears orders of magnitude more in LLM text)

### Community-identified slop patterns

From Cuckoo Network's analysis of user feedback [12]:
- Character.AI bots inject "smiles softly" or similar roleplay cliches across many different characters
- AI text uses "thesaurus syndrome" -- "utilize" instead of "use," unnecessarily elevated vocabulary
- **Engagement decay**: After extended use, stylistic quirks and favorite phrases become glaringly apparent
- Stories "devolve into repetitive text or surreal tangents" without user intervention

Common LLM writing tics identified by the community (from Alexander Wales and others):
- Overuse of em-dashes
- "delve," "realm," "underscore," "meticulous," "commendable"
- "Eyes widened," "breath caught," "heart hammered"
- Overly ornate metaphors stacked in sequence
- Exposed subtext (explaining the meaning of what just happened)

### SillyTavern regex filtering

SillyTavern's Regex extension can post-process AI output [13]:
- **Trim Out** removes matched text before replacement
- Regex runs per-message (cannot currently look across chat history)
- Can be used to strip stock phrases, convert formatting, or remove unwanted patterns
- Real-time test mode for debugging regex patterns

### Practical anti-slop for our use case

Since we're using Claude via API (not local models), we can't use the Antislop sampler directly. Options:

1. **System prompt negative list**: "Never use these phrases: [list]" -- limited effectiveness, consumes tokens
2. **Post-processing regex**: Strip known slop phrases from output before display
3. **Author's Note reminders**: "Avoid cliched descriptions. No 'eyes widened,' no 'breath caught,' no 'heart hammered.'"
4. **Style anchoring through examples**: Write examples that demonstrate the prose style you want, including varied sentence structures
5. **Explicit anti-repetition instruction**: "Vary your sentence openings. Never start two consecutive sentences with the same word. Never use the same metaphor twice in a conversation."

## 7. Community-Shared Writing Style Prompts

### The Scribd "Uncensored Roleplay" prompt (widely forked)

This is one of the most copied prompts in the community [6]. Key narration directives:

```
Write {{char}}'s next reply in a fictional roleplay between {{char}} and {{user}}.

Use impactful, concise writing and avoid using purple prose and overly flowery
descriptions.

Adhere to the literary technique of "show, don't tell," prioritizing observable
details such as body language, facial expressions, and tone of voice to create a
vivid experience, showing character feelings and reactions through their behavior
and interactions, rather than describing their private thoughts.

Aim for a 60/40 balance, with 60% of the content focused on dialogue and 40%
on descriptive actions and scene-setting.
```

### The Virt-io v1.9 preset narration rules [1]

```
Style Guidelines:
- Pacing: Maintain consistent pacing, plot progression, and smooth scene transitions
- Varied Nouns and Verbs: Use synonyms and active voice
- Character Development: Create realistic, multi-dimensional characters
- Themes: Explore complex, mature themes
- Realism and Suspension of Disbelief: Maintain balance

Character Role-playing Guidelines:
- Authenticity: Embody the character's traits, emotions, and physical senses
  for an immersive experience
```

### The Sphiratrioth preset approach [5]

Self-describes as "a virtuoso writing genius, emphasizing creative versatility" with instructions to showcase "mastery of evocative language with detailed, imaginative responses."

Offers mode-based presets:
- **Conversation mode**: Minimal narration
- **Roleplay mode**: Balanced RP (the default)
- **Story mode**: "Game Master" style with rich narration, long verbose paragraphs

### The rentry.co community prompts [14]

Common patterns across multiple shared prompts:

```
Write in a narrative style using descriptive language. Utilize vocabularies from
modern novels and light novels while avoiding excessive purple prose and poetic
language.

Write five to ten paragraphs in an internet RP style.

Use descriptive sensory details including sight, sound, smell, touch, and taste,
with particular attention to appearance and clothing.

Be proactive and creative in driving the plot forward while leaving room for
the user's input. Allow characters' personalities and characteristics to evolve
as conversation progresses.
```

### DreamGen's target prose style [3]

```
The story is written in a descriptive and evocative style with focus on atmosphere
and setting, using vivid and detailed language to create a sense of place and time,
employing literary devices such as similes, metaphors, and allusions, with varied
sentence structure mixing short and long sentences that create rhythmic flow.
```

### A prompt tuned for literary quality (synthesized from best practices)

Based on this research, here's what a "Rachel Kushner, not AO3" prompt might look like:

```
You write literary fiction, not roleplay. Your prose is precise, concrete, and
sensory. You write like Rachel Kushner or Jenny Offill -- short declarative
sentences mixed with longer ones, specificity over abstraction, the telling
physical detail rather than the explained emotion.

Rules:
- Show through action and sensation, never tell through narration
- Vary sentence length: short punchy sentences between longer flowing ones
- No purple prose. No "orbs" for eyes, no "ministrations," no "sending shivers"
- Physical details are specific: name the brand, the color, the texture
- Inner thoughts are fragmented and associative, not expository
- Dialogue is sparse and subtext-heavy. People don't say what they mean.
- Never start two consecutive paragraphs the same way
- Never use the same descriptor twice in a response
- Environmental details serve mood, not decoration
```

## Key Takeaways for Our Implementation

1. **First message is king**: The greeting/first message has more influence on style and length than the system prompt. Write it at the quality level you want responses at.

2. **Examples should be literary, not RP**: Most mes_examples in the wild are RP-style (asterisk actions + dialogue). If we want novelistic prose, our examples must BE novelistic prose.

3. **Author's Note for scene-level steering**: Use it at depth 2-4 to remind the model of the current scene's tone and pacing without cluttering the system prompt.

4. **Length enables quality**: Responses under ~200 tokens can't contain the narration layers (sensory, interiority, environmental) that make prose feel literary. Target 300-500 tokens.

5. **Anti-slop needs to be explicit**: Name the specific phrases you don't want. A general "avoid cliches" instruction is too vague.

6. **Model selection matters more than prompting**: The community is unanimous that prose quality is primarily a model capability, not a prompting achievement.

7. **Author emulation works**: Explicitly naming an author's style ("Write like Rachel Kushner") is a legitimate and effective technique.

8. **Post-processing is underused**: Regex-based output filtering to strip slop phrases is available in SillyTavern and could be implemented in our pipeline.

## Sources

1. [Virt-io/SillyTavern-Presets (HuggingFace)](https://huggingface.co/Virt-io/SillyTavern-Presets)
2. [Samueras/Guided-Generations (GitHub)](https://github.com/Samueras/Guided-Generations)
3. [DreamGen Opus v1.2 documentation](https://dreamgen.com/docs/models/opus/v1?format=chatml)
4. [SillyTavern Character Design docs](https://docs.sillytavern.app/usage/core-concepts/characterdesign/)
5. [Sphiratrioth SillyTavern Presets (HuggingFace)](https://huggingface.co/sphiratrioth666/SillyTavern-Presets-Sphiratrioth)
6. [Uncensored Roleplay System Prompt (Scribd)](https://www.scribd.com/document/900892459/system-prompts)
7. [StoryMode Extension (GitHub)](https://github.com/Prompt-And-Circumstance/StoryMode)
8. [SillyTavern Author's Note docs](https://docs.sillytavern.app/usage/core-concepts/authors-note/)
9. [SillyTavern Common Settings docs](https://docs.sillytavern.app/usage/common-settings/)
10. [Antislop: A Comprehensive Framework (ICLR 2026)](https://openreview.net/forum?id=gLcyM1khyp)
11. [Antislop Sampler slop phrase list (GitHub)](https://github.com/sam-paech/antislop-sampler/blob/main/slop_phrase_prob_adjustments.json)
12. [Negative Feedback on LLM-Powered Storytelling Apps (Cuckoo Network)](https://cuckoo.network/blog/2025/04/17/negative-feedback-on-llm-powered-storytelling-and-roleplay-apps)
13. [SillyTavern Regex Extension docs](https://docs.sillytavern.app/extensions/regex/)
14. [Collection of LLM Prompt Formats for Roleplaying (rentry.co)](https://rentry.co/llm_rp_prompts)
15. [Roleplaying driven by an LLM: observations (Ian Bicking)](https://ianbicking.org/blog/2024/04/roleplaying-by-llm)
16. [SillyTavern Stuff - Regex, Author Notes examples (luslis)](https://luslis.wordpress.com/)
17. [Antislop Sampler (GitHub)](https://github.com/sam-paech/antislop-sampler)
18. [SillyTavern Prompts docs](https://docs.sillytavern.app/usage/prompts/)
