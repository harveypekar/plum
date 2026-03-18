# Tool Use and RAG in RP LLM Frontends: Research

**Date:** 2026-03-15

## 1. Tool Use / Function Calling in RP Frontends

### 1.1 SillyTavern's Function Calling System

SillyTavern has a built-in function calling framework. The `ToolManager` is a static class acting as a central registry: extensions register tools via `registerFunctionTool()` from `SillyTavern.getContext()`, providing a name, description, JSON schema for parameters, and an async action handler [1][2].

Built-in function tools include: Image Generation, Web Search, RSS news fetching, Weather, and D&D Dice [1].

Supported backends for function calling: OpenAI, Claude, MistralAI, Groq, Cohere, OpenRouter, AI21, Google AI Studio, Google Vertex AI, DeepSeek, and custom OpenAI-compatible APIs [1]. Notably, **local models via text completion APIs (llama.cpp, Ollama raw) are NOT listed** as supported backends for native function calling.

Registration example [2]:

```javascript
SillyTavern.getContext().registerFunctionTool({
    name: "myFunction",
    displayName: "My Function",
    description: "Use when you need to do something.",
    parameters: {
        type: 'object',
        properties: {
            param1: { type: 'string', description: 'First param' }
        }
    },
    action: async ({ param1 }) => { return "Function result"; },
    formatMessage: ({ param1 }) => { return `Called with: ${param1}`; },
    stealth: true  // don't show tool call in chat history
});
```

### 1.2 MCP Integration in SillyTavern

Multiple community extensions bring MCP to SillyTavern:

- **SillyTavern-MCP-Servers-Universal** (by Inversity): Manages and auto-registers MCP servers, supports stdio/HTTP/SSE transport, with automatic function calling tool registration [3].
- **SillyTavern-MCP-Client** (by bmen25124): WebSocket-based tool execution with standardized interface and real-time status updates [4].
- **SillyTavern-MCP-Extension** (by CG-Labs): WebSocket-based registration and execution of external tools [5].

Setup: Install the MCP server plugin, install the client extension, configure servers via `mcp_settings.json`, then enable "Enable function calling" in sampler settings [3][5].

There was also a feature request (Issue #3335) on the main SillyTavern repo to implement MCP natively [6].

### 1.3 Known Tool Calling Problems

A significant architectural bug: tool calling fragments a single AI turn into multiple messages, breaking response integrity and making regeneration of multi-step tool call sequences impossible (Issue #4250) [7]. Model-specific issues include Claude thinking mode conflicts with tool calls, and DeepSeek V3.2 returning 400 errors due to missing `reasoning_content` [8][9].

### 1.4 Web Search Extension

SillyTavern has an official Web Search extension [10][11] with multiple activation methods:

- **Function tool usage**: The LLM decides when to search (requires supported Chat Completion API). Disables other activation methods when enabled.
- **Backticks**: Words in backticks trigger search.
- **Trigger phrases**: Configurable keyword triggers.
- **Regex matching**: Custom regex on user messages.

Search sources: Google, DuckDuckGo, SerpApi, SearXNG instances [10]. A Selenium add-on provides web browsing without the Extras API [12].

This is directly relevant to our Wikipedia use case -- the backtick/trigger/regex modes could work as **pipeline-level alternatives** when the model can't reliably call tools itself.

## 2. RAG for Character Voice

### 2.1 SillyTavern Data Bank

Since version 1.12.0, SillyTavern has a built-in **Data Bank** system for RAG [13]. You can attach documents at three scopes:

- **Character attachments**: Available only for the current character
- **Chat attachments**: Available only in the current chat
- **Global attachments**: Available in every chat

Documents can be uploaded from disk (text, PDF, and other convertible formats) or created in-app. The Vector Storage extension (bundled) indexes these documents and injects relevant chunks into the prompt at generation time [13].

This is exactly the architecture needed for character voice RAG -- upload books, interviews, transcripts as character attachments, and relevant passages get injected automatically.

### 2.2 Embedding Models Supported

SillyTavern supports a wide range of embedding providers [14]:

**Cloud**: OpenAI, Cohere, Google AI Studio, Google Vertex AI, TogetherAI, MistralAI, NomicAI, OpenRouter

**Local**: Ollama (e.g., `mxbai-embed-large`), llama.cpp server (with `--embedding` flag, e.g., `nomic-embed-text-v1.5` GGUF), vLLM

**Legacy**: SentenceTransformers via Extras API (`all-mpnet-base-v2`, deprecated)

Storage backend: Vectra library, stored as JSON files in `/vectors` directory [14].

### 2.3 Academic Approaches to Character Voice RAG

**RAGs to Riches** (arXiv 2509.12168, Sept 2025) [15]: Reformulates RP as a text retrieval problem. Curated reference demonstrations condition LLM responses. Key finding: under hostile user interactions, the model incorporates 35% more tokens from reference demos (i.e., it leans on source material more when challenged). Introduces IOO (Intersection over Output) and IOR (Intersection over References) metrics for measuring how much the model uses vs. improvises beyond reference material.

**Emotional RAG** (arXiv 2410.23041, Oct 2024) [16]: Based on Mood-Dependent Memory theory -- people recall events better when they reinstate the original emotion. Adds an "Emotional Retriever" that retrieves memories matching both semantic similarity AND emotional state. Uses combination and sequential retrieval strategies. Prompt-engineering-only approach (no fine-tuning needed).

**RoleLLM / Context-Instruct** (arXiv 2310.00746) [17]: Four-stage framework:
1. Role Profile Construction (100 roles)
2. Context-Instruct: extracts role-specific knowledge from segmented profiles (books, Wikipedia, scripts)
3. RoleGPT: speaking style imitation via few-shot prompting
4. RoCIT: role-conditioned instruction tuning for open-source models

Context-Instruct generates QA pairs from source material. Finding: raw retrieval augmentation can cause "distraction" -- the retrieved context is noisy and can hurt rather than help. Structured extraction is better than raw chunk injection.

**Character-LLM** (arXiv 2310.10158) [18]: Trains agents on character-specific data including experience, relationships, and personality profiles.

**The Oscars of AI Theater** (arXiv 2407.11484) [19]: Survey paper covering the full landscape of persona-driven LLM roleplay approaches.

## 3. RAG for Conversation Memory

### 3.1 SillyTavern Chat Vectorization

SillyTavern's bundled Vector Storage extension performs **chat vectorization** [20]:

- Recent messages (default: 2) are converted into a query vector
- Past messages are searched by cosine similarity
- Top matches (default: 3) are shuffled to the beginning or end of the chat history
- Score threshold: 25% minimum relevance
- Recent messages excluded from shuffling: 5 (configurable)
- Large messages are chunked for finer-grained retrieval
- Vectorization happens in the background on each send/receive

This is a working implementation of exactly what we want for conversation memory RAG.

### 3.2 CharMemory Extension

The `sillytavern-character-memory` extension by bal-spec [21] goes beyond raw chat vectorization:

- Every N messages (default: 20), sends recent chat to an LLM
- LLM extracts structured memories: relationships, events, facts, emotional moments
- Memories saved as markdown bullet points in the character's Data Bank
- At generation time, SillyTavern's Vector Storage retrieves relevant memories
- Three-part extraction prompt: character card + existing memories + recent messages, with boundary markers

This is a **hybrid summarization + retrieval** approach: an LLM summarizes/structures the memories, then vector search retrieves relevant ones. It avoids both pure-summarization lossyness and pure-retrieval noisiness.

### 3.3 Summarization vs. Embedding Retrieval (Academic)

Research findings on this comparison [22][23][24]:

- **Retrieval-augmented memory** reduces per-query token usage by 90-95% while maintaining or improving accuracy vs. full-context baselines
- **Recursive summarization** complements both long-context and retrieval-enhanced LLMs
- **Chunk granularity matters**: segment-level or multi-granularity retrieval yields higher precision than turn-level or session-level alone
- **Graph-based architectures** outperform chunked-only or learned summarization by 2-8% on multi-hop and temporal QA
- **Hybrid approaches** (summarization + retrieval) dominate 2025 research
- Some systems partition memory into user/assistant/shared slots with role-distinguishing tokens

The CharMemory extension's approach (LLM-extract then vector-retrieve) aligns well with current research consensus.

## 4. The Small Model Problem

### 4.1 Tool Calling Reliability

A 2025 study testing 7 models (7B-24B) on tool calling found [25]:

- 4 passed, 3 failed
- **Parameter count didn't predict success**: `qwen3:8b` (8B) passed while `qwen2.5-coder:14b` (14B) failed
- Failure modes were distinct per model: refusing to act, format confusion, retry loops
- All three Qwen 2.5 models failed; all three Qwen 3 models passed

Ollama issue #8717 documents broad tool support problems across models [26]. LangChain forum reports Llama-3.2-3B-Instruct cannot handle tool calling locally [27]. LocalAI issue #2293 shows function calling breaking across multiple models [28].

### 4.2 What Helps

From the Goose project's "toolshim" approach [29]:

- A **toolshim** is a thin layer between the main model and tools
- Models like Gemma3, Deepseek-r1, phi4 often fail to invoke tools or produce malformed calls
- Solution: **fine-tune a small model specifically for tool call formatting** (not for the actual task)
- Fine-tuned models tested: `mistral-nemo` (14b), `gemma-4-12b`, `qwen2.5-coder` 7-14b
- `phi4` (14b) and `gemma3` (27b) achieved close performance to `llama3.3` (70b) when using a toolshim

Other workarounds [25]:
- JSON fallback parsing (try to extract tool calls from malformed output)
- Question detection / re-prompting (catch when model asks instead of acting)
- **System prompt optimization** was the single biggest win ("invest in your system prompt before building workarounds")

### 4.3 Pipeline-Level Alternatives (Our Approach)

The research confirms our instinct: for small local models, **pipeline-level tool use** (detect topic -> pre-fetch -> inject) is more reliable than model-initiated tool calling. Evidence:

- SillyTavern's Web Search extension supports trigger phrases, regex, and backtick activation as alternatives to function calling [10]
- SillyTavern's Data Bank RAG is entirely pipeline-level: vectorize documents, retrieve on every message, inject automatically [13]
- The CharMemory extension is pipeline-level: extract every N messages, retrieve automatically [21]
- The Goose toolshim approach acknowledges that small models need external help for tool formatting [29]

Nobody in the RP space appears to be discussing exactly our pattern of "classifier model detects topic -> pipeline fetches from Wikipedia -> injects into context," but the building blocks are all there. SillyTavern's regex/trigger-based web search activation is the closest analog.

## 5. Vector Database Usage in the RP Space

### 5.1 SillyTavern's Approach

SillyTavern uses **Vectra** (JSON-file-based vector storage) [14]. This is simple but doesn't scale. There's no built-in support for external vector DBs like pgvector, ChromaDB, or Qdrant.

### 5.2 MCP Vector Servers

The MCP ecosystem has mature vector DB servers that could connect to SillyTavern via the MCP extensions:

- **Qdrant MCP Server** (official): Semantic memory layer on top of Qdrant [30]
- **vector-mcp** (by Knuckles-Team): Unified MCP server supporting ChromaDB, PGVector, Couchbase, MongoDB, and Qdrant with hybrid search and RAG capabilities [31]
- **ChromaDB MCP servers**: Multiple implementations (HumainLabs, privetin, viable) [32]

### 5.3 For Our Project

Since we already use PostgreSQL, **pgvector** is the natural choice. The `vector-mcp` server [31] supports pgvector and could theoretically connect to SillyTavern via an MCP extension. But for our custom pipeline, we can just use pgvector directly without MCP overhead.

Community RAG stack recommendations from r/LocalLLaMA [33]:
- FAISS for vector search (fast, in-memory)
- `sentence_transformers` with `all-mpnet-base-v2` for embeddings
- `bge-reranker` for re-ranking retrieved results
- For local embedding: `nomic-embed-text` via Ollama or `mxbai-embed-large`

## 6. Emerging Approaches

### 6.1 Key Papers and Repos

- **awesome-llm-role-playing-with-persona** [34]: Curated list of RP + persona resources
- **Awesome-Role-Play-Papers** [35]: Comprehensive paper collection
- **Awesome-Personalized-RAG-Agent** [36]: Survey of personalization from RAG to agent
- **Dynamic Context Adaptation** (arXiv 2508.02016) [37]: Consistent RP agents via dynamic retrieval-augmented generation
- **PersonaBOT** (arXiv 2505.17156) [38]: Customer personas brought to life with LLMs and RAG (Master's thesis, Volvo)

### 6.2 Observations from Practitioners

Ian Bicking's "Roleplaying driven by an LLM" [39] makes practical observations:
- RAG is usually imagined as automated: facts roughly tagged/labeled, inserted via heuristics + structured search + embedding search
- Splitting source material into chunks, embedding them, storing vectors with topic labels is the standard approach
- The quality of chunking and labeling dramatically affects results

## 7. Implications for Our Project

### What SillyTavern Already Solved (That We Can Learn From)

1. **Character voice RAG**: Data Bank + Vector Storage does this. Upload source material as character attachments, get automatic retrieval. We should implement the same pattern.

2. **Conversation memory RAG**: Chat vectorization + CharMemory extension. The hybrid approach (LLM-extract structured memories, then vector-retrieve) is the best pattern.

3. **Pipeline-level tool use**: Web Search extension's trigger/regex/backtick modes bypass the need for model-initiated function calling. Our topic-detection + pre-fetch approach is validated.

### What We Should Build

1. **pgvector-based embedding storage** for character source material (books, quotes, interviews) and conversation memories. Use `nomic-embed-text` via Ollama for local embedding.

2. **Pipeline-level Wikipedia retrieval**: On each user message, run a lightweight classifier or keyword extractor to detect factual topics, fetch from Wikipedia, inject relevant passages. Don't ask the 12B model to call tools.

3. **Structured memory extraction**: Every N messages, use the LLM to extract key facts/events/relationships into structured format. Store with embeddings. Retrieve relevant memories at generation time. Follow CharMemory's pattern.

4. **Source material chunking**: For character voice, chunk reference texts into ~200-500 token segments with topic labels. Embed and store in pgvector. Retrieve top-K most relevant chunks on each generation.

5. **Emotional state tracking**: Per the Emotional RAG paper, track conversation emotional state and factor it into memory retrieval (not just semantic similarity).

## References

[1] https://docs.sillytavern.app/for-contributors/function-calling/
[2] https://deepwiki.com/SillyTavern/SillyTavern/3.5-reasoning-system
[3] https://github.com/Inversity/SillyTavern-MCP-Servers-Universal
[4] https://github.com/bmen25124/SillyTavern-MCP-Client
[5] https://github.com/CG-Labs/SillyTavern-MCP-Extension
[6] https://github.com/SillyTavern/SillyTavern/issues/3335
[7] https://github.com/SillyTavern/SillyTavern/issues/4250
[8] https://github.com/SillyTavern/SillyTavern/issues/3817
[9] https://github.com/SillyTavern/SillyTavern/issues/4857
[10] https://docs.sillytavern.app/extensions/websearch/
[11] https://github.com/SillyTavern/Extension-WebSearch
[12] https://github.com/SillyTavern/SillyTavern-WebSearch-Selenium
[13] https://docs.sillytavern.app/usage/core-concepts/data-bank/
[14] https://docs.sillytavern.app/extensions/chat-vectorization/
[15] https://arxiv.org/abs/2509.12168
[16] https://arxiv.org/abs/2410.23041
[17] https://arxiv.org/abs/2310.00746
[18] https://arxiv.org/abs/2310.10158
[19] https://arxiv.org/abs/2407.11484
[20] https://docs.sillytavern.app/extensions/chat-vectorization/
[21] https://github.com/bal-spec/sillytavern-character-memory
[22] https://arxiv.org/abs/2308.15022
[23] https://mem0.ai/blog/llm-chat-history-summarization-guide-2025
[24] https://arxiv.org/html/2511.17208v2
[25] https://dev.to/kuroko1t/what-happens-when-local-llms-fail-at-tool-calling-testing-7-models-with-a-rust-coding-agent-cep
[26] https://github.com/ollama/ollama/issues/8717
[27] https://forum.langchain.com/t/tool-function-calling-with-llama-3-2-3b-instruct-model-local/2574
[28] https://github.com/mudler/LocalAI/issues/2293
[29] https://block.github.io/goose/blog/2025/04/11/finetuning-toolshim/
[30] https://github.com/qdrant/mcp-server-qdrant
[31] https://github.com/Knuckles-Team/vector-mcp
[32] https://github.com/HumainLabs/chromaDB-mcp
[33] https://www.reddit.com/r/LocalLLaMA/comments/1jxqz8e/whats_your_rag_stack/
[34] https://github.com/Neph0s/awesome-llm-role-playing-with-persona
[35] https://github.com/nuochenpku/Awesome-Role-Play-Papers
[36] https://github.com/Applied-Machine-Learning-Lab/Awesome-Personalized-RAG-Agent
[37] https://arxiv.org/html/2508.02016
[38] https://arxiv.org/html/2505.17156v1
[39] https://ianbicking.org/blog/2024/04/roleplaying-by-llm
