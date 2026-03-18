# Research: Image Generation for Local RP Chat

Date: 2026-03-09

## 1. Local Image Generation Options

### Model Families

| Model | Architecture | Base Resolution | Min VRAM | Recommended VRAM | Notes |
|-------|-------------|-----------------|----------|-------------------|-------|
| SD 1.5 | UNet | 512x512 | 4 GB | 6 GB | Legacy, huge LoRA ecosystem, fast |
| SDXL | UNet | 1024x1024 | 8 GB | 12 GB | Current workhorse for anime/RP |
| SD 3.5 | DiT (MMDiT) | 1024x1024 | 8 GB | 12 GB | Better text rendering, less community adoption |
| Flux.1 Schnell | DiT | 1024x1024 | 8 GB (Q5 GGUF) | 12 GB | 1-4 steps, Apache 2.0 license, very fast |
| Flux.1 Dev | DiT | 1024x1024 | 12 GB (Q5 GGUF) | 24 GB (FP16) | 20-50 steps, highest quality, non-commercial license |
| Flux.2 Dev | DiT | 1024x1024 | 18-20 GB (Q4) | 24 GB | Latest generation from Black Forest Labs |

**GGUF Quantization** (critical for consumer hardware): Q8 maintains ~98% of FP16 quality with 60% less VRAM. Q5 is the sweet spot for 8 GB cards. Q3 is usable but degraded. Q2 is unusable [1].

**System RAM**: Flux models need ~50 GB system RAM for quantization at startup. SDXL is comfortable with 32 GB [2].

### Anime/RP-Optimized Models (SDXL-based)

| Model | Prompting Style | Strengths | NSFW | Notes |
|-------|----------------|-----------|------|-------|
| **Pony Diffusion V6 XL** | Danbooru/e621 tags | Precise control, massive LoRA ecosystem | Yes | Most popular for anime, booru tag syntax required [3] |
| **Illustrious XL** | Natural language | Clean linework, better anatomy, knows more characters | Yes | Trained on Danbooru2023 (~13M images) [4] |
| **NoobAI XL** | Natural language | Illustrious fine-tune with more stylistic range | Yes | Rapidly gaining popularity, based on Illustrious [4] |
| **Pony Diffusion V7** | Danbooru tags | Successor to V6, improved quality | Yes | Newer, fewer community resources [5] |
| **WAI-Illustrious** | Natural language | NSFW-focused Illustrious variant | Yes | Specifically optimized for NSFW content [6] |

For realistic character art: ThinkDiffusionXL handles both photorealism and anime, trained on 1000+ uncensored images [7].

**Recommendation**: Start with **NoobAI XL** (natural language prompts, good quality, Illustrious-compatible LoRAs) or **Pony V6 XL** (if you prefer precise booru-tag control and the larger ecosystem).

### Frontend/Server Options

| Tool | Type | API | Performance | Best For |
|------|------|-----|-------------|----------|
| **ComfyUI** | Node-based workflow | WebSocket + REST | Fastest (2x A1111) | Programmatic use, complex workflows |
| **Forge** | A1111 fork | REST (A1111-compatible) | 30-75% faster than A1111 | Drop-in A1111 replacement |
| **AUTOMATIC1111** | WebUI | REST | Baseline | Largest extension ecosystem |
| **stable-diffusion.cpp** | C/C++ binary | CLI / LocalAI REST | Lightweight, CPU-capable | Minimal footprint, GGUF models |
| **LocalAI** | OpenAI-compatible server | OpenAI REST API | Varies by backend | Drop-in OpenAI replacement |
| **diffusers** (Python) | Library | In-process | Slower than ComfyUI without tuning | Research, simple pipelines |

**ComfyUI wins for programmatic use**: backend/frontend separation, headless mode (`--listen 0.0.0.0`), native WebSocket progress streaming, workflow-as-JSON architecture. It runs well on WSL2 with CUDA [8][9][10].

**diffusers is slower**: In benchmarks, diffusers takes ~15s/iteration vs ComfyUI's ~1s for SDXL 1024x1024. Enabling model CPU offloading closes the gap but ComfyUI's memory management is superior [11].

## 2. APIs and Integration

### ComfyUI API (Recommended)

ComfyUI exposes a full REST + WebSocket API [12]:

**Core Endpoints:**
- `POST /prompt` -- Submit a workflow JSON, returns `prompt_id` and queue position
- `GET /prompt` -- Current queue status
- `GET /history/{prompt_id}` -- Get results for a completed prompt
- `GET /view?filename=...&type=output` -- Retrieve generated images
- `POST /upload/image` -- Upload reference images
- `POST /interrupt` -- Cancel current generation
- `POST /queue` -- Clear queue
- `POST /free` -- Unload models to free VRAM
- `GET /system_stats` -- VRAM usage, Python version, device info
- `GET /models/{folder}` -- List available models

**WebSocket** (`ws://host:8188/ws?clientId={uuid}`):
Messages: `status`, `execution_start`, `executing`, `progress`, `executed`. Provides node-by-node progress tracking and can stream images directly via `SaveImageWebsocket` node.

**Python Integration Pattern:**

```python
import json, uuid, urllib.request, websocket

server = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

# Connect WebSocket for progress
ws = websocket.WebSocket()
ws.connect(f"ws://{server}/ws?clientId={client_id}")

# Submit workflow
def queue_prompt(workflow):
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(f"http://{server}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

# Wait for completion
def wait_for_completion(prompt_id):
    while True:
        msg = json.loads(ws.recv()) if isinstance(ws.recv(), str) else None
        if msg and msg["type"] == "executing":
            if msg["data"]["node"] is None and msg["data"]["prompt_id"] == prompt_id:
                return

# Retrieve images from history
def get_images(prompt_id):
    resp = urllib.request.urlopen(f"http://{server}/history/{prompt_id}")
    history = json.loads(resp.read())[prompt_id]
    images = []
    for node_id, output in history["outputs"].items():
        for img in output.get("images", []):
            url = f"http://{server}/view?filename={img['filename']}&subfolder={img['subfolder']}&type={img['type']}"
            images.append(urllib.request.urlopen(url).read())
    return images
```

**Workflow customization**: Export a workflow JSON from ComfyUI's UI ("Save (API Format)"), then modify node inputs programmatically:
```python
workflow["6"]["inputs"]["text"] = "1girl, green eyes, brown hair"  # positive prompt
workflow["7"]["inputs"]["text"] = "bad quality, watermark"          # negative prompt
workflow["3"]["inputs"]["seed"] = random.randint(0, 2**32)          # random seed
```

**Existing libraries:**
- `comfy-api-client` (PyPI) -- async client with WebSocket support [13]
- `ComfyAPI` -- queue workflows, monitor progress, retrieve outputs [14]
- `ComfyUI-to-Python-Extension` -- converts workflows to standalone Python scripts [15]

### A1111/Forge REST API

```
POST /sdapi/v1/txt2img
POST /sdapi/v1/img2img
GET  /sdapi/v1/sd-models
GET  /sdapi/v1/samplers
```

Simpler than ComfyUI but less flexible. No native WebSocket progress.

### LocalAI (OpenAI-Compatible)

```
POST /v1/images/generations  {"prompt": "...", "size": "512x512"}
```

Drop-in replacement for OpenAI's image API. Backend uses stable-diffusion.cpp [16].

### stable-diffusion-cpp-python

Direct Python bindings for stable-diffusion.cpp. Lightweight, supports GGUF models, no server needed [17]:

```python
from stable_diffusion_cpp import StableDiffusion
sd = StableDiffusion(model_path="model.gguf")
images = sd.txt_to_img(prompt="1girl, anime", steps=20)
```

## 3. How RP Frontends Do It

### SillyTavern's Approach (The Reference Implementation)

SillyTavern supports **24+ image generation backends** behind a unified interface [18]:

**Generation Modes:**
| Mode | Trigger | What It Does |
|------|---------|--------------|
| Character Portrait | `/sd you` | Full-body portrait from character description |
| Character Face | `/sd face` | Close-up portrait (portrait aspect ratio) |
| Scene Illustration | `/sd last` | Visual recap of the most recent message |
| Story Summary | `/sd scene` | Visual recap of all chat events |
| Raw Message | `/sd raw_last` | Use message text verbatim as SD prompt |
| Free Mode | `/sd (anything)` | Custom prompt, optionally extended by LLM |
| Interactive | Auto-detect | Function tool calling detects image intent |

**LLM-Assisted Prompt Generation** (the key innovation):
Every mode except raw and free triggers the main LLM to convert chat context into an SD prompt. The system uses customizable "SD Prompt Templates" that instruct the LLM how to write prompts. This is configurable per generation mode [18].

**Character Consistency via Prompt Prefixes:**
- Each character card has a "SD Prompt Prefix" field (e.g., `female, green eyes, brown hair, pink shirt`)
- This prefix is prepended to every generated prompt for that character
- Supports LoRA triggers: `<lora:CharacterName:1>`
- A common prefix sets overall style (e.g., `best quality, anime lineart`)
- Negative prompt prefix excludes unwanted features (`bad quality, watermark`)

**ComfyUI Integration:**
SillyTavern supports ComfyUI with placeholder substitution in workflow JSONs:
`%prompt%`, `%negative_prompt%`, `%model%`, `%steps%`, `%scale%`, `%width%`, `%height%`, `%sampler%`, `%scheduler%`, `%denoise%`, `%seed%`, `%clip_skip%`, `%vae%`, `%user_avatar%`, `%char_avatar%` [18].

### SillyTavern Auto-Illustrator Extension

A third-party extension that generates images automatically during conversation [19]:
- The LLM generates invisible image prompts at appropriate story moments
- The extension detects these prompts and generates images via SD
- Images appear inline in the conversation, replacing the invisible markers
- Supports streaming -- generates images during response streaming
- Users can click images to update prompts with natural language feedback

### Other RP Tools

- **platberlitz/sillytavern-image-gen**: Multi-message context selection for richer scene descriptions, resizable popup display [20]
- **st-image-auto-generation**: Automatic generation based on context/story changes [21]

## 4. LLM-Assisted Prompt Generation

### Techniques for Converting Narrative to Image Prompts

**Approach 1: System Prompt Instruction**
Tell the LLM to output image prompts in a specific format. SillyTavern uses customizable templates per generation mode [18]. Example system instruction:

```
Given the following roleplay scene, write a Stable Diffusion prompt describing
the visual scene. Use comma-separated tags. Include: characters present, their
appearance, clothing, pose, expression, setting, lighting, and art style.
Do NOT include narrative text, only visual descriptors.
```

**Approach 2: Danbooru Tag Generation (DanTagGen)**
A specialized LLM trained to generate Danbooru tags from descriptions [22][23]:
- Input: character description or scene text
- Output: structured booru tags (e.g., `1girl, solo, blonde_hair, blue_eyes, school_uniform, sitting, classroom, window, sunlight`)
- Available as ComfyUI node (ComfyUI_DanTagGen) or standalone
- Best for Pony Diffusion and other booru-trained models

**Approach 3: Prompt Upsampling**
Use a 7B-class LLM to expand short prompts into detailed ones, similar to DALL-E 3's approach [24]. Models like Zephyr-7B-alpha work well for this.

### Booru Tags vs Natural Language

| Aspect | Booru Tags | Natural Language |
|--------|-----------|------------------|
| Precision | Very high (exact attributes) | Moderate (interpreted) |
| Best models | Pony, e621-trained | Illustrious, NoobAI, Flux |
| Learning curve | Must know tag vocabulary | Write normally |
| Composability | Easy to add/remove traits | Harder to control specifics |
| LLM generation | Needs specialized model (DanTagGen) | Any capable LLM works |

**Recommendation**: Use natural language prompts with Illustrious/NoobAI. The LLM already speaks natural language -- forcing it through a booru-tag translation step adds complexity and failure modes.

### Style Consistency Across a Conversation

1. **Fixed style prefix**: Prepend the same style tags to every prompt (e.g., `anime, digital art, soft lighting, detailed`)
2. **Character prefix**: Always include character appearance tags
3. **Negative prompt consistency**: Same negative prompt every time
4. **Model consistency**: Don't switch checkpoint models mid-conversation
5. **Seed pinning** (optional): Use a consistent seed with slight variations for similar compositions

## 5. Character Consistency (The Hard Problem)

### Approach Comparison

| Technology | How It Works | Identity Fidelity | Expression Flexibility | VRAM Overhead | Best For |
|-----------|-------------|-------------------|----------------------|---------------|----------|
| **Prompt-only** | Same text description each time | Low (~60%) | High | None | Simple cases |
| **LoRA** | Fine-tuned model weights for character | Very High (~95%) | High | +100-200 MB | Known/static characters |
| **IP-Adapter** | Image embedding conditions generation | Medium (~75%) | Medium | +1-2 GB | Style transfer |
| **IP-Adapter FaceID Plus V2** | InsightFace + ViT-H + LoRA | High (~85%) | Medium | +2-3 GB | Face consistency |
| **InstantID** | InsightFace + IP-Adapter conditioning | Highest (~86%) | Balanced | +3-4 GB (most intensive) | Premium face consistency |
| **PuLID** | Contrastive learning face transfer | Medium-High | Most restrictive | +2 GB | Resource-constrained |

### Practical Recommendations

**For RP characters (anime style):**

1. **Start simple**: Character prompt prefix in every generation. This is what SillyTavern does and it works surprisingly well for anime where stylistic consistency matters more than photorealistic identity.

2. **Level up with IP-Adapter FaceID Plus V2**: Use the character's avatar as a reference image. ComfyUI workflow: load avatar -> PrepImageForInsightFace -> IPAdapter FaceID Plus node. Requires insightface + a LoRA, recommended weight 0.5-1.0 [25][26].

3. **Best results with LoRA training**: Train a character-specific LoRA with 10-20 reference images. Takes ~30 min on a 12 GB GPU. The LoRA then ensures consistent character appearance with just a trigger word [27][28].

4. **InstantID for realistic characters**: Best for photorealistic face consistency. Combine with FaceDetailer for highest quality. Resource-intensive [29][30].

### LoRA Training for Character Consistency

**Requirements:** 10-20 images of the character, 8 GB+ VRAM (16 GB recommended for SDXL), ~30 minutes training time [27].

**Tools:** Kohya SS GUI (most popular), SimpleTuner, OneTrainer.

**Process:**
1. Generate a character sheet (consistent face from multiple angles)
2. Crop and tag images
3. Train LoRA with appropriate settings (network rank 16-32 for characters)
4. Use trigger word in prompts: `<lora:MyCharacter:0.8> my_character_trigger`

**For RP use case:** Pre-train LoRAs for recurring characters. For new/dynamic characters, use IP-Adapter FaceID with the character avatar as reference.

### ComfyUI Consistency Workflow

A practical ComfyUI workflow for RP character consistency:
1. Load character avatar (from the RP app's card avatar)
2. InsightFace analysis -> face embeddings
3. IP-Adapter FaceID Plus V2 conditioning
4. KSampler with text prompt (from LLM) + face conditioning
5. Optional: FaceDetailer post-processing for face quality

## 6. Architecture Recommendations

### ComfyUI as Sidecar Service (Recommended)

```
┌─────────────────┐     ┌──────────────────┐
│  RP Chat App     │     │  ComfyUI Server   │
│  (FastAPI)       │────>│  (headless)       │
│                  │ WS  │                   │
│  /rp/generate    │<────│  :8188            │
│  /rp/images/{id} │     │                   │
└─────────────────┘     └──────────────────┘
        │                        │
        v                        v
   PostgreSQL              models/ folder
   (image metadata)        (checkpoints, LoRAs)
```

**Why sidecar over in-process diffusers:**
- ComfyUI handles VRAM management, model loading/unloading automatically
- Workflow JSON is declarative and composable (add IP-Adapter, ControlNet, etc. without code changes)
- ComfyUI is 2x faster than diffusers in benchmarks
- Can restart ComfyUI independently without restarting the chat app
- ComfyUI community provides ready-made workflows for every technique
- The `/free` endpoint lets you unload image models when doing heavy LLM work

**Why NOT in-process diffusers:**
- VRAM contention with Ollama (both want the GPU)
- No built-in model management
- Slower without extensive optimization
- Every new technique (IP-Adapter, ControlNet, etc.) requires code changes

### Proposed Integration for the RP App

**New routes:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/rp/conversations/{id}/generate-image` | Generate image from conversation context |
| GET | `/rp/images/{id}` | Retrieve a generated image |
| GET | `/rp/images/{id}/status` | Check generation progress |
| POST | `/rp/generate-image` | Free-form image generation |

**New database table:**
```sql
CREATE TABLE IF NOT EXISTS rp_images (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES rp_conversations(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES rp_messages(id) ON DELETE SET NULL,
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    image_data BYTEA,
    thumbnail BYTEA,
    width INTEGER,
    height INTEGER,
    model TEXT,
    seed BIGINT,
    steps INTEGER,
    cfg_scale REAL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Generation Flow:**

```
User clicks "Generate Image" on a message
    │
    v
POST /rp/conversations/{id}/generate-image
    │
    ├── 1. Gather context: last N messages + character descriptions
    │
    ├── 2. Ask Ollama to write an image prompt:
    │      System: "Convert this RP scene to a Stable Diffusion prompt..."
    │      User: [recent messages + character card descriptions]
    │      Response: "1girl, green_eyes, brown_hair, sitting, cafe, warm_lighting..."
    │
    ├── 3. Construct ComfyUI workflow JSON:
    │      - Insert prompt + character prefix into text nodes
    │      - Optionally attach character avatar for IP-Adapter
    │      - Set model, sampler, seed, steps, cfg
    │
    ├── 4. Submit to ComfyUI via POST /prompt
    │
    ├── 5. Stream progress via WebSocket to client
    │
    ├── 6. Retrieve image from ComfyUI /view endpoint
    │
    └── 7. Store in rp_images, return to client
```

**VRAM Sharing Between Ollama and ComfyUI:**
This is the key challenge on a single-GPU system. Options:
1. **Sequential**: Call ComfyUI's `POST /free` before heavy Ollama inference, and vice versa. Adds latency from model swapping.
2. **Dedicated VRAM budgets**: Run Ollama with `OLLAMA_MAX_VRAM` and ComfyUI with `--reserve-vram`. Requires enough total VRAM.
3. **CPU offloading**: Use Ollama for text (GPU) and ComfyUI with `--cpu` for images (slow but no contention).
4. **On-demand loading**: Only start ComfyUI when image generation is requested. Use `POST /free` aggressively.

**Recommendation**: Option 4 (on-demand) for a single-GPU setup. Keep ComfyUI running but call `POST /free` after each generation batch. Ollama already handles its own model loading/unloading.

### Queue Management

For single-user local use, ComfyUI's built-in queue is sufficient. The WebSocket connection provides progress updates that can be forwarded to the frontend via SSE or WebSocket.

For the streaming protocol, extend the existing NDJSON format:
```jsonl
{"image_generating": true, "prompt_id": "abc-123"}
{"image_progress": 0.5, "step": 10, "total_steps": 20}
{"image_done": true, "image_url": "/rp/images/42"}
```

## 7. Implementation Phases

**Phase 1 -- Basic Generation (MVP)**
- Add ComfyUI client to the RP app (WebSocket + REST)
- "Generate Image" button on messages
- LLM prompt conversion (Ollama writes the SD prompt)
- Character prompt prefix from card data
- Store and display images in chat

**Phase 2 -- Character Consistency**
- IP-Adapter FaceID workflow using character avatars
- Character-specific SD prompt prefixes in card data
- Style presets (anime, realistic, etc.)

**Phase 3 -- Automatic Generation**
- Auto-generate on scene changes (LLM decides when)
- Function calling or marker-based triggers
- Background generation queue

**Phase 4 -- Advanced Consistency**
- LoRA training pipeline for recurring characters
- Reference image gallery per character
- Multi-character scene composition

## References

[1] GGUF Quantized Models Complete Guide 2025. Apatero Blog, 2025. https://apatero.com/blog/gguf-quantized-models-complete-guide-2025

[2] SDXL System Requirements. StableDiffusionXL.com, 2025. https://stablediffusionxl.com/sdxl-system-requirements/

[3] Pony Diffusion V6 XL. Civitai, 2024. https://civitai.com/models/257749/pony-diffusion-v6-xl

[4] Pony Diffusion V7 vs Illustrious Models Comparison 2025. Apatero Blog, 2025. https://apatero.com/blog/pony-diffusion-v7-vs-illustrious-models-comparison-2025

[5] ILXL (Illustrious-XL) / NAI-XL (NoobAI-XL) model comparison. Civitai, 2024. https://civitai.com/articles/8642/ilxl-illustrious-xl-nai-xl-noobai-xl-model-comparison

[6] WAI-illustrious-SDXL. Civitai, 2025. https://civitai.com/models/827184/wai-nsfw-illustrious-sdxl

[7] ThinkDiffusionXL. Civitai, 2024. https://civitai.com/articles/2712/thinkdiffusionxl-is-the-premier-stable-diffusion-model

[8] ComfyUI vs AUTOMATIC1111: Which is Better in 2025? Apatero Blog, 2025. https://apatero.com/blog/comfyui-vs-automatic1111-comparison-2025

[9] Getting Started with ComfyUI on WSL2. FollowFox AI, 2025. https://followfoxai.substack.com/p/getting-started-with-comfyui-on-wsl2

[10] Setting up your RTX 5070/5080/5090 for AI - ComfyUI on Windows through WSL. Code Calamity, 2025. https://codecalamity.com/setting-up-your-rtx-5070-5080-or-5090-for-ai-comfyui-on-windows-through-wsl/

[11] Why is diffusers so much slower than ComfyUI? Hugging Face Forums, 2024. https://discuss.huggingface.co/t/why-is-diffusers-so-much-slower-than-comfyui/51145

[12] ComfyUI API Routes Documentation. ComfyUI Docs, 2025. https://docs.comfy.org/development/comfyui-server/comms_routes

[13] comfy-api-client. PyPI, 2025. https://pypi.org/project/comfy-api-client/

[14] ComfyAPI. GitHub (SamratBarai), 2025. https://github.com/SamratBarai/ComfyAPI

[15] ComfyUI-to-Python-Extension. GitHub (pydn), 2024. https://github.com/pydn/ComfyUI-to-Python-Extension

[16] LocalAI Image Generation. LocalAI Docs, 2025. https://localai.io/features/image-generation/

[17] stable-diffusion-cpp-python. PyPI, 2025. https://pypi.org/project/stable-diffusion-cpp-python/

[18] SillyTavern Image Generation Documentation. SillyTavern Docs, 2025. https://docs.sillytavern.app/extensions/stable-diffusion/

[19] sillytavern-auto-illustrator. GitHub (gamer-mitsuha), 2025. https://github.com/gamer-mitsuha/sillytavern-auto-illustrator

[20] sillytavern-image-gen. GitHub (platberlitz), 2025. https://github.com/platberlitz/sillytavern-image-gen

[21] st-image-auto-generation. GitHub (wickedcode01), 2024. https://github.com/wickedcode01/st-image-auto-generation

[22] sd-danbooru-tags-upsampler. GitHub (p1atdev), 2024. https://github.com/p1atdev/sd-danbooru-tags-upsampler

[23] ComfyUI_DanTagGen. GitHub (huchenlei), 2024. https://github.com/huchenlei/ComfyUI_DanTagGen

[24] TIPO: Text to Image with Text Presampling for Prompt Optimization. arXiv, 2024. https://arxiv.org/html/2411.08127v2

[25] ComfyUI_IPAdapter_plus. GitHub (cubiq), 2025. https://github.com/cubiq/ComfyUI_IPAdapter_plus

[26] IP-Adapter FaceID Plus - Create Consistent Characters in ComfyUI. RunComfy, 2025. https://www.runcomfy.com/comfyui-workflows/create-consistent-characters-in-comfyui-with-ipadapter-faceid-plus

[27] LoRA Training Best Practices Guide 2025. Apatero Blog, 2025. https://apatero.com/blog/lora-training-best-practices-flux-stable-diffusion-2025

[28] How to train Lora models. Stable Diffusion Art, 2025. https://stable-diffusion-art.com/train-lora/

[29] AI Face Swap Showdown: PuLID vs InstantID vs FaceID. MyAIForce, 2024. https://myaiforce.com/pulid-vs-instantid-vs-faceid/

[30] ComfyUI-FastAPI. GitHub (alexisrolland), 2024. https://github.com/alexisrolland/ComfyUI-FastAPI

[31] Building a FastAPI Application for ComfyUI Workflows. Medium (Irsal Khan), 2025. https://medium.com/@arsalkhan963/building-a-fastapi-application-for-comfyui-workflows-771bb610ac47

[32] Flux.1 Quickstart Guide. Civitai Education, 2025. https://education.civitai.com/quickstart-guide-to-flux-1/

[33] How to Run FLUX.2 Locally on an RTX 3090. DataCamp, 2025. https://www.datacamp.com/tutorial/how-to-run-flux2-locally

[34] stable-diffusion.cpp. GitHub (leejet), 2025. https://github.com/leejet/stable-diffusion.cpp

[35] Flux: Dev vs Schnell vs Pro (Detailed Comparison). StableDiffusionTutorials, 2025. https://www.stablediffusiontutorials.com/2025/04/flux-schnell-dev-pro.html

[36] SillyTavern Image Generation Extensions (DeepWiki). DeepWiki, 2025. https://deepwiki.com/SillyTavern/SillyTavern/8.2-image-generation-extensions

[37] IP-Adapters: All you need to know. Stable Diffusion Art, 2024. https://stable-diffusion-art.com/ip-adapter/

[38] Consistent portraits using IP-Adapters for SDXL. myByways, 2024. https://mybyways.com/blog/consistent-portraits-using-ip-adapters-for-sdxl
