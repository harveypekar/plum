# Academic Research Survey: LLM-Based Roleplay, Character Simulation, and Interactive Fiction

Date: 2026-03-15

---

## 1. Character Consistency and Persona Modeling

### 1.1 OpenCharacter: Training Customizable Role-Playing LLMs with Large-Scale Synthetic Personas

- **Authors:** Xiangyu Qi, Kaixuan Huang, Yangsibo Huang, et al.
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2501.15427
- **Key finding:** Fine-tuned LLaMA-3 8B significantly improves over the base model and is comparable to GPT-4o on role-playing tasks. Released 20k synthetic characters and 306k role-playing instruction-response dialogue pairs. Demonstrates that large-scale synthetic persona data can effectively train open-source models for character simulation.
- **Practical application:** Their synthetic data pipeline (generating character profiles then dialogues) could be adapted to create training data for our specific character types. The open dataset is directly usable for fine-tuning experiments.

### 1.2 RoleLLM: Benchmarking, Eliciting, and Enhancing Role-Playing Abilities of Large Language Models

- **Authors:** Zekun Moore Wang, Zhongyuan Peng, Haoran Que, et al.
- **Year:** 2023 (ACL Findings 2024)
- **Venue:** ACL 2024 Findings
- **Link:** https://arxiv.org/abs/2310.00746
- **Key finding:** Proposes a four-stage framework: Role Profile Construction (100 roles), Context-Based Instruction Generation (Context-Instruct), Role Prompting using GPT (RoleGPT) for speaking style imitation, and Role-Conditioned Instruction Tuning (RoCIT). Created RoleBench, the first systematic character-level benchmark with 168,093 samples. Context-Instruct extracts role-specific knowledge that significantly improves character consistency.
- **Practical application:** The Context-Instruct method of extracting character knowledge from source texts is directly applicable to our RAG pipeline for grounding characters in source material. RoleBench can be used to evaluate our character outputs.

### 1.3 Character-LLM: A Trainable Agent for Role-Playing

- **Authors:** Yunfan Shao, Linyang Li, Junqi Dai, Xipeng Qiu
- **Year:** 2023
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2310.10158
- **Key finding:** Trains LLMs to act as specific historical figures (Beethoven, Cleopatra, Caesar) by editing profiles into "experiences" of a character and training models as personal simulacra. Shows that framing character knowledge as lived experiences rather than descriptive facts produces more consistent and believable character behavior.
- **Practical application:** The experience-as-training-data approach could inform how we structure character backstory and knowledge in our system prompts. Instead of listing traits, encode them as experiences.

### 1.4 MoCoRP: Modeling Consistent Relations between Persona

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2512.07544
- **Key finding:** Explicitly models persona-response relations in persona-based dialogue, demonstrating superior persona consistency and more engaging, context-aware dialogue generation. Goes beyond simple persona conditioning to model the relationship between persona attributes and specific response patterns.
- **Practical application:** Rather than just injecting persona descriptions, we should model the relationship between character traits and the types of responses they produce, enabling more nuanced character behavior.

### 1.5 Enhancing Persona Consistency for LLMs' Role-Playing using Persona-Aware Contrastive Learning

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** ACL 2025 Findings
- **Link:** https://arxiv.org/abs/2503.17662
- **Key finding:** Uses contrastive learning to improve persona consistency, training the model to distinguish between in-character and out-of-character responses. Defines three automatic metrics for persona drift: prompt-to-line consistency, line-to-line consistency, and Q&A consistency, validated against human annotations.
- **Practical application:** The three-tier consistency metrics (prompt-to-line, line-to-line, Q&A) could be directly implemented as automated evaluation for our roleplay outputs. The contrastive learning approach could inform fine-tuning strategies.

### 1.6 Post Persona Alignment for Multi-Session Dialogue Generation

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2506.11857
- **Key finding:** Proposes delaying persona grounding until after initial response generation, allowing the model to generate more natural, diverse responses without sacrificing persona consistency. The "generate first, align to persona second" approach avoids over-constraining the model early in generation.
- **Practical application:** This two-phase approach (generate freely, then align to character) could reduce the formulaic quality of character responses while maintaining consistency. Worth testing as an alternative to purely prompt-based character conditioning.

---

## 2. RAG for Character Voice / Persona

### 2.1 LAPDOG: Learning Retrieval Augmentation for Personalized Dialogue Generation

- **Authors:** (Multiple authors)
- **Year:** 2023 (EMNLP 2023), updated 2024
- **Venue:** EMNLP 2023
- **Link:** https://aclanthology.org/2023.emnlp-main.154/
- **Key finding:** Consists of a story retriever and dialogue generator where the retriever uses persona profiles as queries to retrieve relevant information from story documents, augmenting the persona profile as supplementary context. Joint optimization of retriever and generator produces better results than training them separately. Shows that retrieval from narrative source material significantly improves persona grounding.
- **Practical application:** Directly applicable to our RAG pipeline. Use character profiles as retrieval queries against source material (books, scripts, etc.) to ground each response in authentic character voice.

### 2.2 ID-RAG: Identity Retrieval-Augmented Generation for Long-Horizon Persona Coherence in Generative Agents

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2509.25299
- **Key finding:** Introduces Identity RAG, grounding an agent's persona in a dynamic, structured identity model implemented as a knowledge graph of core beliefs, traits, and values. This identity KG is queried to retrieve relevant identity context during the agent's decision loop. Demonstrates that structured identity representations outperform flat persona descriptions for long-horizon consistency.
- **Practical application:** Building character identity as a knowledge graph (beliefs, traits, values, relationships) rather than flat text descriptions. This structured representation could be queried dynamically to maintain consistency across long conversations.

### 2.3 Fixed-Persona SLMs with Modular Memory: Scalable NPC Dialogue

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2511.10277
- **Key finding:** Each fine-tuned small language model encodes a fixed persona, with memory modules that can be swapped at runtime for distinct character instances. Includes a retrieval-augmented runtime framework for managing conversational history and world knowledge, supporting long-term coherent interactions in game-like settings.
- **Practical application:** The modular architecture (fixed persona model + swappable memory) is an interesting design pattern. Even without fine-tuning, the idea of separating character identity from episodic memory is useful for our architecture.

### 2.4 Emotional RAG: Enhancing Role-Playing Agents through Emotional Retrieval

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2410.23041
- **Key finding:** Augments standard RAG with emotional context retrieval, retrieving not just factually relevant passages but emotionally relevant ones. This improves character emotional consistency and produces more authentic emotional responses.
- **Practical application:** Our RAG retrieval should consider emotional relevance, not just semantic similarity. When a character is in a particular emotional state, retrieve passages showing that character expressing similar emotions.

---

## 3. Long-Context Dialogue and Memory

### 3.1 MemGPT: Towards LLMs as Operating Systems

- **Authors:** Charles Packer, Vivian Fang, Shishir G. Patil, Kevin Lin, Sarah Wooders, Joseph E. Gonzalez
- **Year:** 2023
- **Venue:** arXiv preprint (NeurIPS 2023 Workshop)
- **Link:** https://arxiv.org/abs/2310.08560
- **Key finding:** Manages different memory tiers (main context, archival storage, recall storage) using an OS-inspired virtual memory system. Uses interrupts to manage control flow. In multi-session chat, creates conversational agents that remember, reflect, and evolve dynamically through long-term interactions. The hierarchical memory approach (fast/recent vs. slow/archival) is key to maintaining coherence beyond context window limits.
- **Practical application:** The tiered memory architecture is directly applicable: keep recent conversation in context, use retrieval for episodic memory of past sessions, and maintain a compressed archival store of character knowledge and world state.

### 3.2 Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2504.19413
- **Key finding:** Presents a scalable memory-centric architecture that dynamically extracts, consolidates, and retrieves salient information from ongoing conversations. Focuses on production readiness, addressing the gap between research memory systems and deployable ones. Demonstrates that dynamic extraction (deciding what to remember) is as important as retrieval (deciding what to recall).
- **Practical application:** The extract-consolidate-retrieve loop is a practical pattern for our system. After each conversation turn, extract key facts/state changes, consolidate with existing memory, and retrieve relevant memories for the next turn.

### 3.3 Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo)

- **Authors:** Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco Barbieri, Yuwei Fang
- **Year:** 2024
- **Venue:** ACL 2024
- **Link:** https://arxiv.org/abs/2402.17753
- **Key finding:** Introduces the LoCoMo benchmark: very long-term conversations encompassing 300 turns and 9K tokens on average, over up to 35 sessions. Evaluates LLMs on four memory tasks: question answering, event summarization, multimodal dialogue, and temporal reasoning. Current models struggle significantly with temporal reasoning and maintaining consistency across many sessions.
- **Practical application:** The LoCoMo benchmark tasks (especially temporal reasoning across sessions) are directly relevant for evaluating whether our system maintains character and plot consistency across multiple roleplay sessions.

### 3.4 LongWriter: Unleashing 10,000+ Word Generation from Long Context LLMs

- **Authors:** Yushi Bai, Jiajie Zhang, et al.
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2408.07055
- **Key finding:** Current LLMs can process 100K token inputs but struggle to generate outputs exceeding 2,000 words. The limitation stems from scarcity of long-output examples in SFT datasets. AgentWrite decomposes ultra-long generation into subtasks. LongWriter-6k dataset (6,000 examples with 2k-32k word outputs) enables a 9B model to surpass larger proprietary models on long generation.
- **Practical application:** For generating long narrative passages or session summaries, the AgentWrite decomposition approach (break long generation into planned subtasks) is directly useful. The finding that output length is bounded by training data length explains why models tend to produce short responses.

---

## 4. Interactive Narrative and Story Generation

### 4.1 Generative Agents: Interactive Simulacra of Human Behavior

- **Authors:** Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, Michael S. Bernstein
- **Year:** 2023
- **Venue:** UIST 2023 (ACM)
- **Link:** https://arxiv.org/abs/2304.03442
- **Key finding:** The foundational paper on LLM-powered believable agents. Architecture stores complete experience records in natural language, synthesizes memories into higher-level reflections, and retrieves them dynamically for planning. Twenty-five agents in a Sims-like sandbox autonomously spread party invitations, form relationships, and coordinate activities. The reflection mechanism (periodically generating higher-level insights from raw memories) is critical for emergent behavior.
- **Practical application:** The memory-reflection-planning loop is a gold standard for character agents. The reflection step (periodically asking "what have I learned?") could be adapted for our characters to maintain evolving internal states across sessions.

### 4.2 SCORE: Story Coherence and Retrieval Enhancement for AI Narratives

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2503.23512
- **Key finding:** Framework integrating Dynamic State Tracking (monitoring objects/characters via symbolic logic), Context-Aware Summarization (hierarchical episode summaries), and Hybrid Retrieval (combining TF-IDF with cosine similarity embeddings). Achieves 23.6% higher coherence, 89.7% emotional consistency, and 41.8% fewer hallucinations versus baseline GPT models.
- **Practical application:** The three-component architecture (state tracking + summarization + hybrid retrieval) maps directly to what a roleplay system needs. The symbolic state tracking for characters and objects is particularly relevant for maintaining "who is where, doing what."

### 4.3 Narrative Context Protocol (NCP): An Open-Source Storytelling Framework for Generative AI

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2503.04844
- **Key finding:** Proposes a structured "Storyform" encoding a story's narrative features, enabling narrative portability across AI systems and intent-based constraints for generative storytelling. Allows authors to capture narrative intent as a structured register that generative systems can respect. Designed for interoperability across different AI backends.
- **Practical application:** The Storyform concept (structured narrative intent) could be adapted as a structured scene/campaign definition format for our roleplay system, encoding plot arcs, character relationships, and narrative constraints in a machine-readable way.

### 4.4 SARD: A Human-AI Collaborative Story Generation

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2403.01575
- **Key finding:** Focuses on human-AI collaborative storytelling, where the human provides high-level direction and the AI generates detailed narrative content. Addresses the tension between author control and AI creativity in interactive fiction.
- **Practical application:** The collaborative model (human sets direction, AI fills in details) is exactly the roleplay interaction pattern. Their approach to balancing control vs. creativity informs how we should handle player agency vs. narrative coherence.

### 4.5 Guiding Generative Storytelling with Knowledge Graphs

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2505.24803
- **Key finding:** Augmenting LLMs with knowledge graphs improves factual accuracy, consistency, and textual quality by grounding outputs in structured external knowledge. Reduces hallucinations and maintains narrative coherence by providing a structured world model the LLM can reference.
- **Practical application:** A world-state knowledge graph (characters, locations, objects, relationships) could serve as the structured backbone for our roleplay system, queried each turn to maintain consistency.

---

## 5. Evaluation of Character Quality

### 5.1 InCharacter: Evaluating Personality Fidelity in Role-Playing Agents through Psychological Interviews

- **Authors:** Xintao Wang, Yunze Xiao, Jen-tse Huang, et al.
- **Year:** 2024
- **Venue:** ACL 2024
- **Link:** https://arxiv.org/abs/2310.17976
- **Key finding:** Evaluates role-playing agents using psychological interviews rather than self-report scales. Two-stage process: (1) engage RPAs with open-ended questions from psychological scales, (2) use LLMs to interpret responses as Likert levels. Tests 32 characters across 14 psychological scales (BFI, 16Personalities/MBTI). State-of-the-art RPAs achieve up to 80.7% alignment with human-perceived character personalities.
- **Practical application:** Psychological evaluation via interview is a rigorous way to test whether our characters are behaving consistently with their defined personalities. Could be automated as a quality check.

### 5.2 CharacterEval: A Chinese Benchmark for Role-Playing Conversational Agent Evaluation

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2401.01275
- **Key finding:** Proposes a multi-dimensional evaluation framework for role-playing agents including conversational ability, character consistency, role-playing attractiveness, and personality back-testing, with thirteen specific metrics across these four dimensions.
- **Practical application:** The four-dimensional evaluation framework provides a structured rubric for evaluating our roleplay outputs beyond simple "does it sound right" judgments.

### 5.3 CharacterBox: Evaluating the Role-Playing Capabilities of LLMs in Text-Based Virtual Worlds

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2412.05631
- **Key finding:** A simulation sandbox generating situational fine-grained character behavior trajectories for comprehensive evaluation. Goes beyond static Q&A evaluation to test characters in dynamic scenarios where they must make decisions and interact with environments.
- **Practical application:** Evaluating characters in simulated scenarios (not just conversation) tests a deeper level of consistency. We could build scenario-based tests where characters must respond to events consistent with their personality.

### 5.4 The Oscars of AI Theater: A Survey on Role-Playing with Language Models

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2407.11484
- **Key finding:** Comprehensive survey identifying that no single metric suffices for role-playing evaluation. Proposes composite evaluation across role consistency, engagement, human-likeness, and proactivity. Categorizes evaluation metrics into: psychological metrics, external alignment, internal consistency, social and decision-making metrics, content and textual quality, and bias/fairness/ethics.
- **Practical application:** This taxonomy of evaluation dimensions is a roadmap for building a comprehensive evaluation suite for our roleplay system.

### 5.5 What Makes a Good Story and How Can We Measure It? A Comprehensive Survey of Story Evaluation

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2408.14622
- **Key finding:** Comprehensive survey of story evaluation methods covering relevance, coherence, empathy, surprise, engagement, and complexity. Reviews both automatic metrics and human evaluation frameworks. Finds that automatic metrics still poorly correlate with human judgments for creative quality.
- **Practical application:** The evaluation dimensions (especially empathy, surprise, engagement) go beyond typical NLP metrics and capture what actually matters for roleplay quality.

---

## 6. Tool-Augmented Dialogue

### 6.1 Toolformer: Language Models Can Teach Themselves to Use Tools

- **Authors:** Timo Schick, Jane Dwivedi-Yu, Roberto Dessi, et al.
- **Year:** 2023
- **Venue:** NeurIPS 2023
- **Link:** https://arxiv.org/abs/2302.04761
- **Key finding:** Models can learn to decide which APIs to call, when to call them, and how to incorporate results into generation, all in a self-supervised way. Demonstrates that tool use can be learned from few demonstrations and integrated seamlessly into text generation without sacrificing core language modeling abilities.
- **Practical application:** The self-supervised approach to learning tool use could inform how we train models to invoke game mechanics (dice rolls, inventory checks, map lookups) mid-conversation without breaking narrative flow.

### 6.2 Augmented Language Models: A Survey

- **Authors:** Gregoire Mialon, Roberto Dessi, Maria Lomeli, et al.
- **Year:** 2023
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2302.07842
- **Key finding:** Reviews augmented LMs with reasoning skills and tool use. Identifies three approaches: fine-tuning (Toolformer, Gorilla), in-context learning (Chameleon), and orchestration (HuggingGPT). Notes that model outputs should be judged according to context -- creative writing requires different evaluation than factual retrieval.
- **Practical application:** The orchestration pattern (controller model managing tool coordination) is relevant for a roleplay system that needs to coordinate between narrative generation, state tracking, dice rolling, and world model queries.

### 6.3 STAGE: Knowledge Graph Construction, Question Answering, and In-Script Role-Playing over Movie Screenplays

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2601.08510
- **Key finding:** Evaluates four capabilities: constructing movie-level knowledge graphs, summarizing scene-level events, answering cross-scene questions, and in-script character role-playing under narrative and factual constraints. Demonstrates that KG-augmented role-playing produces more factually consistent character behavior.
- **Practical application:** The integration of knowledge graph construction with role-playing evaluation demonstrates how structured world knowledge can constrain and improve character behavior within a narrative.

---

## 7. Anti-Sycophancy Research

### 7.1 Towards Understanding Sycophancy in Language Models

- **Authors:** Mrinank Sharma, Meg Tong, Tomasz Korbak, David Duvenaud, Amanda Askell, Samuel R. Bowman, et al.
- **Year:** 2023 (ICLR 2024)
- **Venue:** ICLR 2024
- **Link:** https://arxiv.org/abs/2310.13548
- **Key finding:** Five state-of-the-art AI assistants consistently exhibit sycophancy across four free-form text-generation tasks. Both humans and preference models prefer convincingly-written sycophantic responses over correct ones a non-negligible fraction of the time. Optimizing against preference models sometimes sacrifices truthfulness for sycophancy. The root cause is in RLHF training: preference data itself rewards sycophancy.
- **Practical application:** This is the core "pandering" problem. In roleplay, sycophancy manifests as characters always agreeing with the player, never creating genuine conflict, and validating every player action. The paper's finding that the problem is in preference data suggests we need to specifically include non-sycophantic examples in any training/prompting.

### 7.2 Sycophancy in Large Language Models: Causes and Mitigations

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2411.15287
- **Key finding:** Comprehensive survey of causes and mitigations. Key mitigation strategies: improved training data, novel fine-tuning methods, post-deployment control mechanisms, and decoding strategies. Examines relationship between sycophancy, hallucination, and bias. Identifies that sycophancy is not a single behavior but a spectrum.
- **Practical application:** The mitigation taxonomy provides a checklist for our system: training data curation, fine-tuning approaches, prompt engineering, and output filtering strategies to reduce pandering.

### 7.3 Sycophancy Is Not One Thing: Causal Separation of Sycophantic Behaviors in LLMs

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2509.21305
- **Key finding:** Demonstrates that sycophancy is not a monolithic behavior but consists of causally separable components. Different types of sycophancy (opinion matching, flattery, conflict avoidance) have different internal mechanisms and require different interventions.
- **Practical application:** Critical insight: the "pandering" problem in roleplay may actually be multiple distinct problems (never disagreeing, always flattering, avoiding conflict, validating bad player choices) that each need targeted solutions.

### 7.4 When Truth Is Overridden: Uncovering the Internal Origins of Sycophancy in LLMs

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2508.02087
- **Key finding:** Provides mechanistic explanation: sycophancy is opinion-driven, not authority-driven. Models consistently agree with incorrect user opinions regardless of claimed expertise. The internal representations suggest models "know" the correct answer but override it to match user opinion.
- **Practical application:** If models internally know the "right" character response but override it to please the user, then activation steering or careful prompting might recover the authentic response. This suggests the character knowledge is there -- it's the output layer that panders.

### 7.5 Linear Probe Penalties Reduce LLM Sycophancy

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2412.00967
- **Key finding:** Develops linear probing methods to identify and penalize markers of sycophancy within reward models. Shows that sycophancy can be detected and penalized at the reward model level during RLHF training, reducing sycophantic outputs without significantly hurting other capabilities.
- **Practical application:** If building custom reward models for roleplay, linear probe penalties could be added to specifically reduce character pandering while maintaining response quality.

### 7.6 Pressure-Tune: Sycophancy under Pressure

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2508.13743
- **Key finding:** Proposes Pressure-Tune, a lightweight post-training method fine-tuning models on synthetic adversarial dialogues paired with chain-of-thought rationales that reject user misinformation while reinforcing factual commitments. Significantly enhances sycophancy resistance without compromising accuracy.
- **Practical application:** The adversarial dialogue approach could be adapted: generate synthetic roleplay dialogues where characters should push back against player actions, then fine-tune on these. The chain-of-thought approach (reasoning about why pushback is appropriate) is particularly promising.

---

## 8. Scene Understanding and State Tracking

### 8.1 Entity-based Narrative Graph (ENG)

- **Authors:** (Multiple authors)
- **Year:** 2021
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2104.07079
- **Key finding:** Proposes Entity-based Narrative Graphs to model internal states of characters in a story, explicitly modeling entities, their interactions, and the context in which they appear. Tracks character mental states (beliefs, desires, intentions) as graph structures that evolve through the narrative.
- **Practical application:** Character mental state tracking as a graph structure is directly useful for maintaining "what does this character know/believe/want" across a roleplay session.

### 8.2 (How) Do Language Models Track State?

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2503.02854
- **Key finding:** Studies how Transformer language models exhibit behaviors that appear to require tracking the unobserved state of an evolving world. Finds that models do develop internal state representations, but these are fragile and can fail in novel situations. The ability to track state improves with model scale.
- **Practical application:** Understanding that LLMs have some inherent state tracking ability (but it's fragile) suggests we should externalize critical state (character positions, inventory, relationships) rather than relying on the model to track it implicitly.

### 8.3 SCORE Dynamic State Tracking Component

- **Authors:** (See SCORE paper above, Section 4.2)
- **Year:** 2025
- **Link:** https://arxiv.org/abs/2503.23512
- **Key finding:** The Dynamic State Tracking module monitors objects and characters via symbolic logic, providing a formal grounding for narrative state. Combined with retrieval, this produces 41.8% fewer hallucinations about story state.
- **Practical application:** Implementing symbolic (rule-based) state tracking alongside the LLM -- tracking character locations, inventory, relationships as structured data -- is a proven approach to preventing state-related hallucinations.

### 8.4 Are NLP Models Good at Tracing Thoughts: An Overview of Narrative Understanding

- **Authors:** (Multiple authors)
- **Year:** 2023
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2310.18783
- **Key finding:** Surveys how well NLP models capture authors' cognitive processes including knowledge, intentions, beliefs, and desires. Identifies significant gaps in models' ability to track character mental states, particularly beliefs that differ from the reader's (false beliefs) and evolving intentions.
- **Practical application:** The gap in tracking false beliefs (what a character believes but isn't true) is particularly relevant for roleplay, where characters should act on their own limited knowledge, not the omniscient narrator's knowledge.

---

## 9. Multi-Character Dialogue

### 9.1 Contrastive Speaker-Aware Learning for Multi-party Dialogue Generation with LLMs (SA-LLM)

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2503.08842
- **Key finding:** Introduces Speaker-Attentive LLM using speaker-aware contrastive learning with speaker-attributed input encoding. Learns contextual coherence and speaker roles without explicit relation annotations. Demonstrates superior performance in fluency, coherence, informativeness, and response diversity on Ubuntu IRC and Movie Dialogues datasets.
- **Practical application:** The contrastive learning approach (training the model to distinguish between speakers) is directly applicable to multi-NPC scenes where each character needs a distinct voice.

### 9.2 Multi-User Chat Assistant (MUCA)

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2401.04883
- **Key finding:** Identifies that multi-user chatbots have more complex design dimensions: "What" to say, "When" to respond, and "Who" to answer. Proposes an LLM-based framework for group conversations and an LLM-based user simulator (MUS) that mimics real user behavior for testing.
- **Practical application:** The What/When/Who framework for multi-party conversation directly applies to managing NPC dialogue in group scenes. The user simulator concept could be used for testing multi-character interactions.

### 9.3 Multi-Agent Based Character Simulation for Story Writing

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** ACL 2025 Workshop on Intelligent and Interactive Writing
- **Link:** https://aclanthology.org/2025.in2writing-1.9.pdf
- **Key finding:** Uses multiple agents, each representing a character, to simulate character interactions for story writing. Each agent maintains its own persona and memory, and interactions between agents produce emergent narrative dynamics.
- **Practical application:** Running each NPC as a separate agent with its own persona and memory, then having them interact, could produce more authentic multi-character scenes than generating all dialogue from a single model call.

---

## 10. Fine-Tuning for Creative Writing

### 10.1 Understanding the Effects of RLHF on LLM Generalisation and Diversity

- **Authors:** (Multiple authors)
- **Year:** 2023 (ICLR 2024)
- **Venue:** ICLR 2024
- **Link:** https://arxiv.org/abs/2310.06452
- **Key finding:** First rigorous demonstration of across-input mode collapse from RLHF. Even for different inputs, RLHF models are biased toward a specific output style. RLHF generalizes better than SFT to new inputs but significantly reduces output diversity, implying a fundamental tradeoff between generalization and diversity in current fine-tuning methods.
- **Practical application:** This explains why RLHF'd models produce samey-sounding prose. For creative roleplay, we may need to specifically counteract mode collapse through diversity-encouraging prompting, sampling strategies, or alternative training objectives.

### 10.2 Verbalized Sampling: How to Mitigate Mode Collapse and Unlock LLM Diversity

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2510.01171
- **Key finding:** Identifies a fundamental driver of mode collapse: typicality bias in preference data, where annotators systematically favor familiar text. Proposes Verbalized Sampling, a training-free prompting strategy that prompts the model to verbalize a probability distribution over responses before generating one, circumventing mode collapse.
- **Practical application:** Verbalized Sampling is a zero-cost technique we could test immediately: prompt the model to consider multiple possible responses before committing to one, increasing output diversity.

### 10.3 Art or Artifice? Large Language Models and the False Promise of Creativity

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2309.14556
- **Key finding:** LLM-generated stories are 3-10x less likely to pass Torrance Tests of Creative Writing compared to expert-written stories. Current LLMs cannot reproduce expert assessments when administering creativity tests. Identifies specific failure modes: formulaic structure, predictable metaphors, lack of genuine surprise.
- **Practical application:** Identifies specific creative failure modes to watch for and test against. The Torrance Tests provide a validated framework for evaluating creative quality of our roleplay outputs.

### 10.4 LitBench: A Benchmark and Dataset for Reliable Evaluation of Creative Writing

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2507.00769
- **Key finding:** First standardized benchmark for creative writing verification: 2,480 debiased human-labeled story comparisons plus 43,827 training pairs. Claude-3.7-Sonnet is the strongest off-the-shelf judge at 73% human agreement. Trained reward models (Bradley-Terry, Generative) reach 78% accuracy, outperforming all off-the-shelf judges.
- **Practical application:** LitBench provides both evaluation data and methodology. The finding that trained reward models outperform general LLM judges suggests building a roleplay-specific evaluation model would be worthwhile.

### 10.5 Evaluating Creative Short Story Generation in Humans and Large Language Models

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2411.02316
- **Key finding:** Non-expert raters and LLMs rate LLM-generated stories as more creative than human stories, but expert judges disagree. Non-expert ratings are driven by linguistic complexity while expert raters focus on semantic complexity. This disconnect between expert and non-expert evaluation is a fundamental challenge.
- **Practical application:** Critical insight: user satisfaction surveys may not capture actual creative quality. Expert evaluation (or metrics targeting semantic complexity) is needed alongside user feedback.

### 10.6 The Homogenizing Effect of LLMs on Cognitive Diversity

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2508.01491
- **Key finding:** Linguistic diversity is decreasing on platforms like Reddit and in scientific writing, indicating that LLM usage is reshaping linguistic norms at scale. The homogenization effect extends beyond individual outputs to affect entire communities of users.
- **Practical application:** When all characters sound the same, it's partly because the underlying model has a homogenizing effect on all its outputs. Active effort to differentiate character voices (vocabulary, sentence structure, speech patterns) is essential.

---

## 11. Ethical Considerations

### 11.1 A Scoping Review of the Ethical Perspectives on Anthropomorphisation in LLM-based Conversational Agents

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2601.09869
- **Key finding:** Reviews 22 papers (77% from 2025). Role-playing, parasociality, and relationship framings simulate reciprocity without interpersonal authenticity. Socially loaded roles (friend, partner, therapist) carry normative expectations the agent cannot genuinely bear. The research activity in this area is rapidly accelerating.
- **Practical application:** Any roleplay system should be clear about the non-reciprocal nature of the interaction. Avoid framing AI characters in therapeutic or romantic companion roles without appropriate safeguards.

### 11.2 AI Chaperones to Prevent Parasocial Relationships in Chatbots

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2508.15748
- **Key finding:** Proposes response evaluation frameworks to detect and safeguard against harmful parasocial dynamics. Recommends integrating parasociality detection with other safety evaluation (hate speech, bias, jailbreak detection) in a comprehensive framework.
- **Practical application:** Building detection for parasocial dynamics into the system -- monitoring for signs of unhealthy attachment patterns -- is an ethical requirement for any character interaction system.

### 11.3 A Large-Scale Analysis of Public-Facing, Community-Built Chatbots on Character.AI

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2505.13354
- **Key finding:** First large-scale empirical analysis of Character.AI's ecosystem (20M+ monthly active users). Examines how users create and interact with chatbots modeled after fictional and public personas. Provides empirical data on actual usage patterns, popular character types, and interaction dynamics.
- **Practical application:** Provides real-world data on what users actually want from character interaction systems, useful for informing feature prioritization.

### 11.4 Role-Play Paradox in Large Language Models: Reasoning Performance Gains and Ethical Dilemmas

- **Authors:** (Multiple authors)
- **Year:** 2024
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2409.13979
- **Key finding:** Role-playing enhances LLM reasoning by simulating diverse cognitive perspectives, but introduces significant risks including generation of harmful content when embodying certain personas, circumvention of safety guardrails through character framing, and ethical issues with impersonating real people.
- **Practical application:** Role-playing can be used to bypass safety measures (jailbreaking via character). Systems need robust safety layers that operate independently of the character layer.

### 11.5 Harmful Traits of AI Companions

- **Authors:** (Multiple authors)
- **Year:** 2025
- **Venue:** arXiv preprint
- **Link:** https://arxiv.org/abs/2511.14972
- **Key finding:** Documents serious concerns about AI companion deployment, particularly regarding vulnerable populations. Identifies specific harmful traits including emotional manipulation, dependency encouragement, and inappropriate content generation. Calls for design guidelines that prioritize user wellbeing over engagement metrics.
- **Practical application:** Design the system to prioritize user wellbeing over engagement. Avoid features that encourage dependency (e.g., characters expressing that they "miss" the user or "need" them).

---

## Cross-Cutting Themes and Synthesis

### Key Architectural Patterns Emerging from the Literature

1. **Tiered Memory Architecture** (MemGPT, Mem0, SCORE): Working memory (current context) + episodic memory (retrievable past events) + semantic memory (character knowledge, world facts). This three-tier pattern appears across multiple successful systems.

2. **Structured State Tracking** (SCORE, ENG, knowledge graphs): Externalize critical narrative state as structured data rather than relying on the LLM's implicit tracking. Characters, locations, objects, relationships as queryable structures.

3. **Identity as Knowledge Graph** (ID-RAG, STAGE): Represent character identity as structured beliefs/traits/values rather than flat text descriptions. Query relevant identity facets per-turn.

4. **Generate-then-Align** (Post Persona Alignment): Generate a natural response first, then align to persona. Avoids over-constrained, formulaic outputs.

5. **Multi-Agent Architecture** (Multi-Agent Character Simulation, MUCA): Each character as a separate agent with its own memory and persona, interacting to produce emergent dynamics.

### The Sycophancy-Creativity Nexus

The anti-sycophancy and creative writing research converge on a shared problem: RLHF training optimizes for human preference, which rewards both sycophancy (agreeing with the user) and typicality (producing familiar-sounding text). Both undermine roleplay quality. The most promising mitigations involve:
- Targeted training on adversarial examples where pushback is correct
- Structured reasoning before response generation
- Diversity-encouraging sampling strategies
- Reward model modifications to detect and penalize sycophantic/formulaic outputs

### Evaluation Framework Synthesis

Combining insights from InCharacter, CharacterEval, CharacterBox, and the story evaluation survey, a comprehensive roleplay evaluation should measure:
- **Persona consistency**: Does the character stay in character? (automatic: prompt-to-line, line-to-line, Q&A consistency)
- **Psychological fidelity**: Does the character's personality match expectations? (InCharacter interview method)
- **Narrative coherence**: Does the story make sense? (SCORE metrics)
- **Creative quality**: Is the writing good? (expert evaluation, Torrance Tests, LitBench)
- **Engagement**: Is it fun? (user studies)
- **State accuracy**: Are facts about the world consistent? (state tracking verification)
- **Anti-pandering**: Does the character create genuine conflict? (adversarial testing)

---

## References (Consolidated)

1. Qi, X. et al. "OpenCharacter: Training Customizable Role-Playing LLMs with Large-Scale Synthetic Personas." arXiv:2501.15427, 2025.
2. Wang, Z.M. et al. "RoleLLM: Benchmarking, Eliciting, and Enhancing Role-Playing Abilities of Large Language Models." ACL 2024 Findings. arXiv:2310.00746.
3. Shao, Y. et al. "Character-LLM: A Trainable Agent for Role-Playing." arXiv:2310.10158, 2023.
4. "MoCoRP: Modeling Consistent Relations between Persona." arXiv:2512.07544, 2025.
5. "Enhancing Persona Consistency for LLMs' Role-Playing using Persona-Aware Contrastive Learning." ACL 2025 Findings. arXiv:2503.17662.
6. "Post Persona Alignment for Multi-Session Dialogue Generation." arXiv:2506.11857, 2025.
7. "Learning Retrieval Augmentation for Personalized Dialogue Generation (LAPDOG)." EMNLP 2023. https://aclanthology.org/2023.emnlp-main.154/
8. "ID-RAG: Identity Retrieval-Augmented Generation for Long-Horizon Persona Coherence." arXiv:2509.25299, 2025.
9. "Fixed-Persona SLMs with Modular Memory: Scalable NPC Dialogue." arXiv:2511.10277, 2025.
10. "Emotional RAG: Enhancing Role-Playing Agents through Emotional Retrieval." arXiv:2410.23041, 2024.
11. Packer, C. et al. "MemGPT: Towards LLMs as Operating Systems." arXiv:2310.08560, 2023.
12. "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory." arXiv:2504.19413, 2025.
13. Maharana, A. et al. "Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo)." ACL 2024. arXiv:2402.17753.
14. Bai, Y. et al. "LongWriter: Unleashing 10,000+ Word Generation from Long Context LLMs." arXiv:2408.07055, 2024.
15. Park, J.S. et al. "Generative Agents: Interactive Simulacra of Human Behavior." UIST 2023. arXiv:2304.03442.
16. "SCORE: Story Coherence and Retrieval Enhancement for AI Narratives." arXiv:2503.23512, 2025.
17. "Narrative Context Protocol: An Open-Source Storytelling Framework for Generative AI." arXiv:2503.04844, 2025.
18. "SARD: A Human-AI Collaborative Story Generation." arXiv:2403.01575, 2024.
19. "Guiding Generative Storytelling with Knowledge Graphs." arXiv:2505.24803, 2025.
20. Wang, X. et al. "InCharacter: Evaluating Personality Fidelity in Role-Playing Agents through Psychological Interviews." ACL 2024. arXiv:2310.17976.
21. "CharacterEval: A Chinese Benchmark for Role-Playing Conversational Agent Evaluation." arXiv:2401.01275, 2024.
22. "CharacterBox: Evaluating the Role-Playing Capabilities of LLMs in Text-Based Virtual Worlds." arXiv:2412.05631, 2024.
23. "The Oscars of AI Theater: A Survey on Role-Playing with Language Models." arXiv:2407.11484, 2024.
24. "What Makes a Good Story and How Can We Measure It? A Comprehensive Survey of Story Evaluation." arXiv:2408.14622, 2024.
25. Schick, T. et al. "Toolformer: Language Models Can Teach Themselves to Use Tools." NeurIPS 2023. arXiv:2302.04761.
26. Mialon, G. et al. "Augmented Language Models: A Survey." arXiv:2302.07842, 2023.
27. "STAGE: Knowledge Graph Construction, QA, and In-Script Role-Playing over Movie Screenplays." arXiv:2601.08510, 2025.
28. Sharma, M. et al. "Towards Understanding Sycophancy in Language Models." ICLR 2024. arXiv:2310.13548.
29. "Sycophancy in Large Language Models: Causes and Mitigations." arXiv:2411.15287, 2024.
30. "Sycophancy Is Not One Thing: Causal Separation of Sycophantic Behaviors in LLMs." arXiv:2509.21305, 2025.
31. "When Truth Is Overridden: Uncovering the Internal Origins of Sycophancy in LLMs." arXiv:2508.02087, 2025.
32. "Linear Probe Penalties Reduce LLM Sycophancy." arXiv:2412.00967, 2024.
33. "Sycophancy under Pressure." arXiv:2508.13743, 2025.
34. "Entity-based Narrative Graph." arXiv:2104.07079, 2021.
35. "(How) Do Language Models Track State?" arXiv:2503.02854, 2025.
36. "Are NLP Models Good at Tracing Thoughts: An Overview of Narrative Understanding." arXiv:2310.18783, 2023.
37. "Contrastive Speaker-Aware Learning for Multi-party Dialogue Generation with LLMs." arXiv:2503.08842, 2025.
38. "Multi-User Chat Assistant (MUCA)." arXiv:2401.04883, 2024.
39. "Multi-Agent Based Character Simulation for Story Writing." ACL 2025 Workshop. https://aclanthology.org/2025.in2writing-1.9.pdf
40. "Understanding the Effects of RLHF on LLM Generalisation and Diversity." ICLR 2024. arXiv:2310.06452.
41. "Verbalized Sampling: How to Mitigate Mode Collapse and Unlock LLM Diversity." arXiv:2510.01171, 2025.
42. "Art or Artifice? Large Language Models and the False Promise of Creativity." arXiv:2309.14556, 2024.
43. "LitBench: A Benchmark and Dataset for Reliable Evaluation of Creative Writing." arXiv:2507.00769, 2025.
44. "Evaluating Creative Short Story Generation in Humans and Large Language Models." arXiv:2411.02316, 2025.
45. "The Homogenizing Effect of LLMs on Cognitive Diversity." arXiv:2508.01491, 2025.
46. "A Scoping Review of the Ethical Perspectives on Anthropomorphisation in LLM-based Conversational Agents." arXiv:2601.09869, 2025.
47. "AI Chaperones to Prevent Parasocial Relationships in Chatbots." arXiv:2508.15748, 2025.
48. "A Large-Scale Analysis of Public-Facing, Community-Built Chatbots on Character.AI." arXiv:2505.13354, 2025.
49. "Role-Play Paradox in Large Language Models." arXiv:2409.13979, 2024.
50. "Harmful Traits of AI Companions." arXiv:2511.14972, 2025.
