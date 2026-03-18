# Research: LLM Fine-Tunes for Roleplay & Creative Writing (2025-2026)

*Date: 2026-03-15*

## 1. The RP Fine-Tune Landscape

The local RP model ecosystem revolves around a handful of prolific creators who fine-tune base models from Meta (Llama), Mistral, Google (Gemma), and Alibaba (Qwen) specifically for creative writing and roleplay. The major players:

### Key Creators

| Creator | HuggingFace | Notable Models | Approach |
|---------|------------|----------------|----------|
| **TheDrummer** | [TheDrummer](https://huggingface.co/TheDrummer) (215 models) | Rocinante, Cydonia, Skyfall, Valkyrie, Anubis | Full fine-tunes prioritizing creativity over alignment |
| **Sao10K** | [Sao10K](https://huggingface.co/Sao10K) (34 models) | Euryale, Kunou, Vulpecula, Freya | LoRA + full fine-tunes with curated RP datasets |
| **Anthracite-org** | [anthracite-org](https://huggingface.co/anthracite-org) (55 models) | Magnum v2/v4 series | Full-parameter fine-tunes aimed at Claude-level prose |
| **sophosympatheia** | [sophosympatheia](https://huggingface.co/sophosympatheia) | Midnight Miqu 70B/103B | DARE Linear merges of Miqu-based models |
| **Epiculous** | [Epiculous](https://huggingface.co/Epiculous) (36 models) | Violet Twilight, Crimson Dawn, Azure Dusk | SLERP merges + dataset creation (SynthRP) |
| **openerotica** | [openerotica](https://huggingface.co/openerotica) | writing-roleplay-20k-context-nemo-12b | QLoRA on Nemo base with 20k context |

### Current Model Recommendations by Size

| Size | Model | Base | Notes |
|------|-------|------|-------|
| **8B** | TheDrummer/Anubis-Mini-8B-v1 | Llama 3.3 8B | Smallest viable RP model [1] |
| **12B** | **TheDrummer/Rocinante-X-12B-v1** | Mistral Nemo 12B | Community consensus best-in-class at 12B. "Feels bigger than 12B." Users report it outperforms many 24B models for RP [2] |
| **12B** | Epiculous/Violet_Twilight-v0.2 | Mistral Nemo 12B (SLERP merge) | Strong alternative, 14.3k GGUF downloads [3] |
| **14B** | Sao10K/14B-Qwen2.5-Kunou-v1 | Qwen 2.5 14B | Cleaned Euryale/Stheno dataset, ChatML format [4] |
| **22B** | anthracite-org/magnum-v4-22b | Mistral (unknown base) | Part of Magnum v4 series [5] |
| **24B** | **TheDrummer/Cydonia-24B-v4.3** | Mistral Small 3.2 24B | 415k downloads, 1.64k likes. Excellent character differentiation, maintains unique voice per card, 32k context [6] |
| **27B** | anthracite-org/magnum-v4-27b | Gemma 2 27B | Claude-like prose, 9 curated datasets [7] |
| **31B** | TheDrummer/Skyfall-31B-v4.1 | Mistral Small 3.1/3.2 + Magistral | Tested at 16-32k context [8] |
| **49B** | TheDrummer/Valkyrie-49B-v2.1 | Nvidia Llama-3.3-Nemotron-Super-49B | "Behemoth-lite" -- introspective, consistent plots [9] |
| **70B** | **Sao10K/L3.3-70B-Euryale-v2.3** | Llama 3.3 70B | Full fine-tune with dedicated RP dataset, 82 derivative merges [10] |
| **70B** | TheDrummer/Anubis-70B-v1.2 | Llama 3.3 70B | Excellent prose, 4-6 paragraph outputs, strong lorebook use [11] |
| **70B** | Sao10K/Llama-3.3-70B-Vulpecula-r1 | Llama 3.3 70B | SFT + light RL, thinking-mode capable, 270M token dataset [12] |
| **70B** | sophosympatheia/Midnight-Miqu-70B-v1.5 | Miqu 70B (leaked Mistral) | DARE merge, Vicuna format, legendary prose but legally gray [13] |
| **72B** | anthracite-org/magnum-v4-72b | Qwen 2.5 72B | Full-parameter fine-tune on 8xMI300X, Claude-like prose [14] |
| **123B** | anthracite-org/magnum-v4-123b | Unknown (likely Mistral Large) | Largest Magnum, 217 downloads [5] |

---

## 2. What Makes an RP Fine-Tune Good

### Generic Instruct vs RP Fine-Tune

A generic instruct model (e.g., Llama-3.3-70B-Instruct) is trained to be helpful, harmless, and honest. This creates several problems for RP:

- **Positivity bias**: Always steers toward happy/safe outcomes
- **Refusal patterns**: Won't engage with dark, morally complex, or mature themes
- **Speaking for the user**: Takes agency away from the player
- **Generic prose**: Corporate-sounding, avoids vivid language
- **Sycophancy**: Agrees with everything, no genuine character conflict

An RP fine-tune addresses these by training on data that demonstrates:

1. **Character consistency over helpfulness** -- maintaining a character voice even when it conflicts with being "helpful"
2. **Unrestricted creative expression** -- using datasets with "no-refusal" filtering (e.g., `kalo-opus-instruct-22k-no-refusal` [15])
3. **Novelistic prose** -- training on Claude Opus/Sonnet outputs and high-quality creative writing
4. **Not speaking for the user** -- explicit guidelines baked into training data (Magnum's forbidden list includes "Writing for, speaking, thinking, acting, or replying as {{user}}" [7])
5. **Sensory detail** -- training data that emphasizes five-sense descriptions, internal monologue, onomatopoeia

### Key Training Principles (from Magnum v4 model cards)

The Magnum series includes explicit SillyTavern guidelines in their training:

**Encouraged behaviors:**
- Maintain character persona but allow evolution
- Be creative and proactive; drive narrative forward
- Include dialogues, actions, and thoughts
- Utilize all five senses in descriptions
- Act as secondary characters/NPCs as needed

**Forbidden behaviors:**
- Excessive purple prose (unless fitting character)
- Writing for/as the user
- Repetitive, monotonous outputs
- Positivity bias
- Being overly extreme when context is inappropriate

### TheDrummer's Philosophy

TheDrummer (creator of Rocinante, Cydonia, Skyfall, Anubis) articulates the core problem well:

> "AI's use of language speaks volumes about their 'perception' of reality. If a language model has been skewed and limited to a positive perception, then its ability to imagine is also limited."

Their models prioritize three axes [2]:
1. **Creativity** -- writing quality, dynamism, imagination
2. **(Dis)alignment** -- attitude, morality, formatting flexibility
3. **Intelligence** -- instruction adherence, knowledge, nuance

### Tool Calling / Structured Output

Tool calling at the 12B level is unreliable for RP fine-tunes. These models are trained specifically for creative text generation, not function calling. At 70B+, some models (particularly Qwen-based and Llama 3.3-based) retain enough of the base model's tool-calling ability to be usable, but it's not a focus of RP fine-tuners. Vulpecula-r1 (70B) supports `<think>` tags for reasoning, which is the closest thing to structured output in the RP space [12].

---

## 3. The Midnight Miqu / Magnum / Nemo Ecosystem

### Your Model: mn-12b-mag-mell-r1

The model `nchapman/mn-12b-mag-mell-r1` is a community merge in the **Mistral Nemo 12B** family. Breaking down the name:
- **mn** = Mistral Nemo
- **12b** = 12 billion parameters
- **mag** = likely Magnum influence
- **mell** = likely Mellowmax or another merge component
- **r1** = revision 1

This is a merge/blend, not a dedicated fine-tune. Merges combine weights from multiple models but can produce inconsistent behavior -- they inherit the strengths of components but also compound weaknesses, and the merge process itself can degrade coherence.

### The Mistral Nemo 12B Family

**Base model**: `mistralai/Mistral-Nemo-Base-2407` (released July 2024)
- 12B parameters, Tekken tokenizer
- Trained by Mistral AI, relatively capable base
- Became the go-to base for 12B RP fine-tunes in 2024

**Key derivatives:**
- **Rocinante-X-12B-v1** (TheDrummer) -- fine-tune, community best at 12B [2]
- **Violet Twilight v0.2** (Epiculous) -- SLERP merge of two Nemo fine-tunes [3]
- **writing-roleplay-20k-context-nemo-12b** (openerotica) -- QLoRA fine-tune with 20k context [16]
- **Magnum v2 12B** (anthracite-org) -- earlier generation, Claude-like prose

### Midnight Miqu

**Not related to Nemo.** Midnight Miqu is based on `miqu-1-70b`, a **leaked Mistral model** (70B, Llama architecture). It's a DARE Linear merge of the leaked Miqu with Tess-70B-v1.6. Key facts [13]:
- Excellent prose quality, rich sensory descriptions
- Requires "warming up" with few-shot examples
- Uses Vicuna or Mistral instruct format (NOT ChatML)
- **Legally gray** -- based on leaked weights, personal use only
- 11.2k downloads/month, 247 likes
- Available at 70B and 103B

### Magnum Series (Anthracite)

The Magnum v4 series (November 2024) represents dedicated fine-tunes on multiple base architectures [5, 7, 14]:
- **Magnum v4-22b**: Mistral-based
- **Magnum v4-27b**: Gemma 2 27B base, 8 datasets, 8xH100
- **Magnum v4-72b**: Qwen 2.5 72B base, 6 datasets, 8xMI300X
- **Magnum v4-123b**: Largest, for high-end hardware

All trained with Axolotl framework, full-parameter (not LoRA), on curated Claude-output datasets. Goal: replicate Claude 3 Sonnet/Opus prose quality.

---

## 4. Model Size vs Quality Tradeoffs

### Character Voice & Instruction Following

| Size | Character Consistency | Complex System Prompts | Prose Quality | Tool Use |
|------|----------------------|----------------------|---------------|----------|
| **7-8B** | Basic. Loses voice over long contexts | Follows simple prompts, ignores nuance | Serviceable but flat | Not viable |
| **12B** | Good with the right fine-tune (Rocinante). Occasional slips | Follows moderately complex prompts | Can be surprisingly good (Rocinante "feels bigger than 12B") | Not viable |
| **14B** | Solid, Qwen 2.5 14B base is strong | Good compliance | Good, benefits from Qwen's training | Marginal |
| **24B** | Very good. Cydonia maintains unique voice per character in group chats | Strong compliance, remembers details from 5k tokens back | Excellent, "prose expert" | Marginal |
| **27-32B** | Excellent | Strong | Very good, approaches Claude quality | Possible with Qwen base |
| **49B** | Excellent, "consistent plot keeping up with tons of introspection" | Strong | Excellent | Possible |
| **70B** | Excellent across all tested models | Reliable, handles complex multi-character scenarios | Near-professional | Viable (esp. Llama 3.3 base) |
| **123B** | Top tier | Top tier | Top tier | Viable |

### The Sweet Spot for Local RP

**12B** is the minimum for quality RP. Below that, models can't maintain character voice reliably.

**24B** (Cydonia) is the sweet spot for quality-per-VRAM. It runs comfortably on a single 24GB GPU at Q4-Q5 quantization and delivers prose that rivals much larger models. TheDrummer's Cydonia-24B-v4.3 has 415k downloads for a reason [6].

**70B** is where models become reliably excellent across all dimensions. Requires 40-48GB VRAM at Q4, or split across CPU+GPU.

### VRAM Requirements (approximate)

| Model Size | Q4_K_M | Q5_K_M | Q6_K | Q8_0 | FP16 |
|-----------|--------|--------|------|------|------|
| 12B | ~7.5 GB | ~8.7 GB | ~10 GB | ~13 GB | ~24.5 GB |
| 24B | ~14 GB | ~17 GB | ~20 GB | ~26 GB | ~48 GB |
| 70B | ~40 GB | ~48 GB | ~56 GB | ~72 GB | ~140 GB |

---

## 5. Quantization Impact on RP Quality

### Community Consensus

Quantization impact is one of the most debated topics. The general hierarchy:

- **FP16/BF16**: Reference quality. Only if you have the VRAM.
- **Q8_0**: Virtually indistinguishable from FP16 in all testing. Safe to use always.
- **Q6_K**: Very high quality. Most users report no perceptible difference from Q8. This is the "quality floor" recommended by bartowski (the most prolific GGUF quantizer) [17].
- **Q5_K_M**: High quality. Slight degradation in creative vocabulary diversity. Still excellent.
- **Q4_K_M**: Good quality. This is where the tradeoff becomes noticeable -- prose gets slightly more generic, vocabulary narrows, rare words become less likely. But still very usable.
- **Q3 and below**: Noticeable quality loss. Characters lose nuance, prose becomes more repetitive.

### The iMatrix Advantage

**iMatrix quantization** (importance matrix) significantly improves quality at lower bit depths. Instead of uniformly quantizing all weights, it measures which weights matter most during inference on a calibration dataset and preserves those at higher precision. Bartowski's iMatrix quants are the community standard [17].

**Recommendation**: Always prefer iMatrix quants (bartowski versions) over standard quants, especially at Q4 and below.

### For RP Specifically

The consensus from model creators:
- **Q6_K or Q5_K_M**: Best balance for RP quality
- **Q4_K_M**: Acceptable if VRAM-constrained, but you'll notice more repetition and less creative word choices
- **Bigger model at Q4 usually beats smaller model at Q8** -- a 24B Q4 will generally outperform a 12B Q8 for prose quality

### Embed/Output Weight Preservation

Some newer quants (Q3_K_XL, Q4_K_L, Q5_K_L, Q6_K_L) keep embedding and output weights at Q8_0 even when the rest of the model is at lower precision. This disproportionately helps text quality because the output layer directly controls token probabilities [17].

---

## 6. Recommended Models for 2026

### At 12B: TheDrummer/Rocinante-X-12B-v1

- **Base**: Mistral Nemo 12B
- **Format**: Mistral v3 Tekken (NOT v7, remove [SYSTEM_PROMPT])
- **Why**: Community consensus best 12B. Updated prose, fun dialogue, strong character adherence. Supports `<thinking>` tags. Outperforms many 24B models for RP.
- **Quant**: Q5_K_M or Q6_K via bartowski iMatrix [2, 17]
- **Known issues**: Occasional GPT-isms ("it's not just X, it's Y"), less detailed than 24B+
- **HuggingFace**: https://huggingface.co/TheDrummer/Rocinante-X-12B-v1
- **GGUF**: https://huggingface.co/bartowski/TheDrummer_Rocinante-X-12B-v1-GGUF

**Runner-up**: Epiculous/Violet_Twilight-v0.2 (SLERP merge, different flavor)

### At 22-24B: TheDrummer/Cydonia-24B-v4.3

- **Base**: Mistral Small 3.2 24B
- **Format**: Mistral v7 Tekken
- **Why**: 415k downloads. Excellent character differentiation in group chats, maintains unique voice per card, remembers details from 5k tokens back, stable and not gratuitous unless pushed.
- **Quant**: Q6 or Q8 with iMatrix recommended by creator [6]
- **HuggingFace**: https://huggingface.co/TheDrummer/Cydonia-24B-v4.3
- **GGUF**: https://huggingface.co/bartowski/TheDrummer_Cydonia-24B-v4.3-GGUF

### At 70B: Sao10K/L3.3-70B-Euryale-v2.3 or TheDrummer/Anubis-70B-v1.2

**Euryale v2.3**:
- **Base**: Llama 3.3 70B
- **Training**: Full fine-tune with dedicated RP dataset (amoral + RP + instruct data)
- **Why**: 82 derivative merges attest to its quality. Strong creative performance, reduced restrictions.
- **Settings**: temp 1.1, min_p 0.1, Llama 3 instruct format [10]

**Anubis 70B v1.2**:
- **Base**: Llama 3.3 70B
- **Why**: Excellent prose (4-6 paragraph outputs), strong context retention at 24-32k, good system prompt adherence. Users report it "beats out favorite 70B overall" [11]

**For thinking/reasoning RP**: Sao10K/Llama-3.3-70B-Vulpecula-r1 -- SFT + RL with 270M token creative dataset, supports `<think>` mode [12]

### Honorable Mention: anthracite-org/magnum-v4-72b

If you prefer the Qwen 2.5 base (better for multilingual, potentially better structured output), Magnum v4-72b offers Claude-like prose with full-parameter fine-tuning on curated datasets [14].

---

## 7. Training Datasets

### Major RP Training Datasets

| Dataset | Size | Description | Used By |
|---------|------|-------------|---------|
| **anthracite-org/kalo-opus-instruct-22k-no-refusal** | 22.3k examples, 78.9 MB | Multi-turn instruction-following from Claude outputs. "No-refusal" means safety filters removed. System prompt: "You are Claude created by Anthropic." | Magnum, Violet Twilight, 481+ models [15] |
| **Epiculous/SynthRP-Gens-v1.1-Filtered-n-Cleaned** | 2,740 examples, 38.2 MB | Synthetically generated RP conversations across genres (combat, urban fantasy, sci-fi, cyberpunk, mil-sim). 4-24 turns per example. | Magnum v4-27b, 382+ models [18] |
| **Epiculous/Synthstruct-Gens-v1.1-Filtered-n-Cleaned** | ~15.1k downloads | Structured synthetic training data | Magnum v4-27b, many models [3] |
| **anthracite-org/nopm_claude_writing_fixed** | 6.35k examples | Claude creative writing outputs | Magnum, Violet Twilight [7, 14] |
| **anthracite-org/c2_logs_32k_llama3_qwen2_v1.2** | Unknown | Long-context conversation logs | Magnum v4-72b [14] |
| **Gryphe/Sonnet3.5-Charcard-Roleplay** | 9.74k examples | Claude Sonnet 3.5 outputs on character cards | Violet Twilight [3] |
| **Chaser-cz/sonnet35-charcard-roleplay-sharegpt** | Unknown | Similar to above, ShareGPT format | openerotica nemo-12b [16] |
| **anthracite-org/stheno-filtered-v1.1** | Unknown | Filtered RP data | openerotica nemo-12b [16] |
| **anthracite-org/kalo_opus_misc_240827** | 1.56k examples | Miscellaneous Claude Opus outputs | Magnum series [7, 14] |

### How RP Datasets Are Constructed

1. **Synthetic generation from frontier models**: The most common approach. Take character cards from chub.ai or similar, feed them to Claude Opus/Sonnet or GPT-4, generate multi-turn RP conversations, then filter for quality. This is how SynthRP-Gens and the Sonnet3.5-Charcard-Roleplay datasets work [18].

2. **Claude output distillation**: Capture high-quality Claude outputs across instruct and creative writing tasks, remove refusal patterns, clean formatting. This is the kalo-opus-instruct approach [15].

3. **Community conversation logs**: Cleaned, anonymized logs from actual RP platforms. The `c2_logs` datasets likely come from this approach.

4. **Merging multiple sources**: Most fine-tunes use 5-9 datasets simultaneously, mixing RP-specific data with general instruct data to maintain the model's general capabilities.

### Quality Concerns

**Claude-mimicry problem**: The vast majority of RP training data is generated by Claude Opus/Sonnet. This means fine-tuned models tend to converge on Claude's specific writing style -- which is eloquent but can be predictable. Some community members argue this creates a "monoculture" where all RP models sound like Claude variations.

**Dataset filtering**: Quality filtering is critical but inconsistent. Epiculous's datasets are filtered for repetition and low quality [18]. The kalo-opus-instruct dataset explicitly removes refusals [15]. But many community datasets have less rigorous filtering, leading to models that inherit noise.

**Synthetic data limitations**: The openerotica model creator notes that story writing data is "single-shot" -- it lacks examples of "continue in X direction" or conditional rewrites, which limits the model's ability to follow mid-story redirections [16].

**Bias toward stock RP tropes**: If training data comes from character cards on RP platforms, it inherits the biases of those platforms -- certain character archetypes, relationship dynamics, and narrative patterns are overrepresented. This is likely contributing to the "generic tropes and pandering" problem you're experiencing.

---

## 8. Practical Recommendations for Your Setup

### Immediate Upgrade: Rocinante-X-12B

If you're staying at 12B, switch from `mn-12b-mag-mell-r1` (a community merge) to **Rocinante-X-12B-v1** (a dedicated fine-tune). The difference should be significant:

```bash
# Pull from Ollama (if available) or download GGUF
# Check bartowski's iMatrix quant:
# https://huggingface.co/bartowski/TheDrummer_Rocinante-X-12B-v1-GGUF
```

**Important**: Use Mistral v3 Tekken format, NOT v7. Remove `[SYSTEM_PROMPT]` from the template.

### If You Can Run 24B

**Cydonia-24B-v4.3** at Q4_K_M (~14GB VRAM) will be a dramatic upgrade over any 12B model. This is the community's most-downloaded RP model for a reason [6].

### Sampling Settings Matter

Most RP fine-tune creators recommend:
- **Temperature**: 1.0-1.1 (higher than default)
- **min_p**: 0.1-0.12 (instead of top_p/top_k)
- **Repetition penalty**: 1.05-1.10 (low, to avoid flattening prose)
- **Smoothing factor**: 0.2-0.23 (quadratic sampling, if supported)

These settings favor creative vocabulary diversity over safe/predictable token choices.

---

## References

1. TheDrummer/Anubis-Mini-8B-v1, HuggingFace model card -- https://huggingface.co/TheDrummer/Anubis-Mini-8B-v1 (retrieved 2026-03-15)
2. TheDrummer/Rocinante-X-12B-v1, HuggingFace model card -- https://huggingface.co/TheDrummer/Rocinante-X-12B-v1 (retrieved 2026-03-15)
3. Epiculous/Violet_Twilight-v0.2, HuggingFace model card -- https://huggingface.co/Epiculous/Violet_Twilight-v0.2 (retrieved 2026-03-15)
4. Sao10K/14B-Qwen2.5-Kunou-v1, HuggingFace model card -- https://huggingface.co/Sao10K/14B-Qwen2.5-Kunou-v1 (retrieved 2026-03-15)
5. Anthracite-org HuggingFace organization page -- https://huggingface.co/anthracite-org (retrieved 2026-03-15)
6. TheDrummer/Cydonia-24B-v4.3, HuggingFace model card -- https://huggingface.co/TheDrummer/Cydonia-24B-v4.3 (retrieved 2026-03-15)
7. anthracite-org/magnum-v4-27b, HuggingFace model card -- https://huggingface.co/anthracite-org/magnum-v4-27b (retrieved 2026-03-15)
8. TheDrummer/Skyfall-31B-v4.1, HuggingFace model card -- https://huggingface.co/TheDrummer/Skyfall-31B-v4.1 (retrieved 2026-03-15)
9. TheDrummer/Valkyrie-49B-v2.1, HuggingFace model card -- https://huggingface.co/TheDrummer/Valkyrie-49B-v2.1 (retrieved 2026-03-15)
10. Sao10K/L3.3-70B-Euryale-v2.3, HuggingFace model card -- https://huggingface.co/Sao10K/L3.3-70B-Euryale-v2.3 (retrieved 2026-03-15)
11. TheDrummer/Anubis-70B-v1.2, HuggingFace model card -- https://huggingface.co/TheDrummer/Anubis-70B-v1.2 (retrieved 2026-03-15)
12. Sao10K/Llama-3.3-70B-Vulpecula-r1, HuggingFace model card -- https://huggingface.co/Sao10K/Llama-3.3-70B-Vulpecula-r1 (retrieved 2026-03-15)
13. sophosympatheia/Midnight-Miqu-70B-v1.5, HuggingFace model card -- https://huggingface.co/sophosympatheia/Midnight-Miqu-70B-v1.5 (retrieved 2026-03-15)
14. anthracite-org/magnum-v4-72b, HuggingFace model card -- https://huggingface.co/anthracite-org/magnum-v4-72b (retrieved 2026-03-15)
15. anthracite-org/kalo-opus-instruct-22k-no-refusal, HuggingFace dataset card -- https://huggingface.co/datasets/anthracite-org/kalo-opus-instruct-22k-no-refusal (retrieved 2026-03-15)
16. openerotica/writing-roleplay-20k-context-nemo-12b-v1.0, HuggingFace model card -- https://huggingface.co/openerotica/writing-roleplay-20k-context-nemo-12b-v1.0 (retrieved 2026-03-15)
17. bartowski/TheDrummer_Rocinante-X-12B-v1-GGUF, HuggingFace model card -- https://huggingface.co/bartowski/TheDrummer_Rocinante-X-12B-v1-GGUF (retrieved 2026-03-15)
18. Epiculous/SynthRP-Gens-v1.1-Filtered-n-Cleaned, HuggingFace dataset card -- https://huggingface.co/datasets/Epiculous/SynthRP-Gens-v1.1-Filtered-n-Cleaned (retrieved 2026-03-15)
