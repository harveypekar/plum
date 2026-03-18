# Character Portrait ComfyUI Workflow — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single ComfyUI workflow that generates character portraits from text descriptions, optionally using reference photos for face/body likeness via IP-Adapter FaceID Plus V2.

**Architecture:** A ComfyUI workflow JSON with three node groups: base generation (always active), IP-Adapter FaceID branch (optional), and post-processing (face crop for avatar). Mode switching: the workflow ships wired for reference mode. For text-only mode, the user manually reconnects the checkpoint MODEL output directly to the KSampler, bypassing the IP-Adapter chain.

**Tech Stack:** ComfyUI, JuggernautXL (SDXL), IP-Adapter FaceID Plus V2, InsightFace antelopev2, comfyui-kjnodes

---

## File Structure

| File | Responsibility |
|---|---|
| `projects/rp/comfyui/character-portrait.json` | The ComfyUI workflow (full UI format with node positions) |
| `projects/rp/comfyui/README.md` | Usage instructions: how to load, which inputs to fill, how to switch modes |

## Prerequisites

The workflow depends on InsightFace `antelopev2` models that are not yet on disk. This must be resolved before the IP-Adapter branch can be tested.

---

## Chunk 1: Prerequisites and Base Workflow

### Task 1: Download InsightFace antelopev2 models

**Files:**
- Create: `models/insightface/models/antelopev2/` (in ComfyUI models directory)

- [ ] **Step 1: Create the antelopev2 directory**

```bash
mkdir -p "/mnt/c/Users/daan/Documents/ComfyUI/models/insightface/models/antelopev2"
```

- [ ] **Step 2: Download the antelopev2 model pack**

The antelopev2 models are distributed via InsightFace. Download the 5 required `.onnx` files:

```bash
cd "/mnt/c/Users/daan/Documents/ComfyUI/models/insightface/models/antelopev2"

# Download from the InsightFace model zoo (GitHub release)
# These are the 5 required files:
# - 1k3d68.onnx (face 3D landmark)
# - 2d106det.onnx (face 2D landmark)
# - det_10g.onnx (face detection)
# - genderage.onnx (gender/age estimation)
# - w600k_r50.onnx (face recognition embedding)

# Option A: If `insightface` Python package is installed:
python3 -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='antelopev2', root='/mnt/c/Users/daan/Documents/ComfyUI/models/insightface')
app.prepare(ctx_id=0, det_size=(640, 640))
print('antelopev2 downloaded successfully')
"

# Option B: Manual download from https://github.com/deepinsight/insightface/releases
# Download the antelopev2.zip and extract the 5 .onnx files into the directory above.
```

- [ ] **Step 3: Verify the models are in place**

```bash
ls -la "/mnt/c/Users/daan/Documents/ComfyUI/models/insightface/models/antelopev2/"
```

Expected: 5 `.onnx` files present (`1k3d68.onnx`, `2d106det.onnx`, `det_10g.onnx`, `genderage.onnx`, `w600k_r50.onnx`).

---

### Task 2: Create base text-only workflow

This is the foundation — a working portrait generation workflow using only text prompts. No IP-Adapter yet.

**Files:**
- Create: `projects/rp/comfyui/character-portrait.json`

- [ ] **Step 1: Create the workflow directory**

```bash
mkdir -p /mnt/d/prg/plum-character-portrait/projects/rp/comfyui
```

- [ ] **Step 2: Write the base workflow JSON**

Create `projects/rp/comfyui/character-portrait.json` with these nodes:

**Nodes (API format IDs):**

| ID | Node | Key Parameters |
|---|---|---|
| 1 | `CheckpointLoaderSimple` | `ckpt_name`: `juggernautXL_ragnarokBy.safetensors` |
| 2 | `CLIPTextEncode` (positive) | `text`: character description input |
| 3 | `CLIPTextEncode` (negative) | `text`: `"blurry, deformed, bad anatomy, watermark, low quality, ugly, disfigured, extra limbs"` |
| 4 | `EmptyLatentImage` | `width`: 1024, `height`: 1024, `batch_size`: 1 |
| 5 | `KSampler` | `seed`: 0 (random), `steps`: 25, `cfg`: 7.0, `sampler_name`: `euler_ancestral`, `scheduler`: `normal`, `denoise`: 1.0 |
| 6 | `VAEDecode` | — |
| 7 | `SaveImage` | `filename_prefix`: `portrait` (ComfyUI appends `_00001`, `_00002`, etc. Seed is stored in PNG metadata, not filename.) |

**Connections:**
- Node 1 MODEL → Node 5 model
- Node 1 CLIP → Node 2 clip
- Node 1 CLIP → Node 3 clip
- Node 1 VAE → Node 6 vae
- Node 2 CONDITIONING → Node 5 positive
- Node 3 CONDITIONING → Node 5 negative
- Node 4 LATENT → Node 5 latent_image
- Node 5 LATENT → Node 6 samples
- Node 6 IMAGE → Node 7 images

The positive prompt text field (node 2) is where the user pastes the character description.

- [ ] **Step 3: Test in ComfyUI**

1. Open ComfyUI in browser
2. Load `character-portrait.json` via "Load" button
3. Enter a test prompt in the positive text field: `"portrait of a young woman with red hair, green eyes, freckles, wearing a leather jacket, fantasy style, dramatic lighting, detailed face"`
4. Click "Queue Prompt"
5. Verify: a 1024x1024 portrait is generated and saved to the output folder

- [ ] **Step 4: Commit**

```bash
cd /mnt/d/prg/plum-character-portrait
git add projects/rp/comfyui/character-portrait.json
git commit -m "feat(rp): add base character portrait ComfyUI workflow (text-only)"
```

---

## Chunk 2: IP-Adapter FaceID Branch

### Task 3: Add IP-Adapter FaceID Plus V2 nodes

Add the reference photo branch to the existing workflow. The workflow ships wired for reference mode by default.

**Files:**
- Modify: `projects/rp/comfyui/character-portrait.json`

- [ ] **Step 1: Add IP-Adapter nodes to the workflow**

Add these nodes to the existing workflow JSON:

| ID | Node | Key Parameters |
|---|---|---|
| 10 | `LoadImage` | Reference photo input (user loads an image) |
| 11 | `IPAdapterInsightFaceLoader` | `provider`: `CPU`, `model_name`: `antelopev2`. This is from `ComfyUI_IPAdapter_plus`, not ReActor. |
| 12 | `IPAdapterUnifiedLoaderFaceID` | `preset`: `FACEID PLUS V2`, `lora_strength`: 0.7, `provider`: `CPU`. Auto-loads the FaceID model, CLIP vision model (auto-detected from `clip_vision/` dir), and companion LoRA internally. Returns an already-patched MODEL. |
| 13 | `IPAdapterFaceID` | `weight`: 0.7, `weight_faceidv2`: 0.7, `weight_type`: `linear`, `combine_embeds`: `average`, `start_at`: 0.0, `end_at`: 1.0, `embeds_scaling`: `V only` |

**Node responsibilities:**
- Node 11 (`IPAdapterInsightFaceLoader`): Loads the InsightFace `antelopev2` face analysis model. This is a **separate** node from the unified loader — `IPAdapterUnifiedLoaderFaceID` does NOT load InsightFace internally. The InsightFace output is passed to node 13.
- Node 12 (`IPAdapterUnifiedLoaderFaceID`): Loads the IP-Adapter FaceID model, auto-detects CLIP vision model from `clip_vision/` directory, and applies the companion LoRA with the specified `lora_strength`. Do **not** add a separate LoRA Loader — the LoRA is handled internally.

**Connections:**
- Node 1 MODEL → Node 12 model (checkpoint feeds into unified loader)
- Node 12 MODEL → Node 13 model (patched model with LoRA)
- Node 12 IPADAPTER → Node 13 ipadapter
- Node 10 IMAGE → Node 13 image (reference photo)
- Node 11 INSIGHTFACE → Node 13 insightface
- Node 13 MODEL → Node 5 model (**replaces** the direct Node 1 → Node 5 connection)

**Mode switching:** The workflow ships wired for reference mode:
- **Reference mode (default wiring):** Node 1 → Node 12 → Node 13 → Node 5
- **Text-only mode:** User manually drags Node 1 MODEL output directly to Node 5 model input, disconnecting the IP-Adapter chain. This is a single drag operation in ComfyUI. To return to reference mode, reconnect Node 13 MODEL → Node 5 model.

ComfyUI group muting does **not** auto-reroute connections — it simply skips the muted nodes, leaving the KSampler's model input disconnected and causing an error. Manual rewiring is the correct approach.

- [ ] **Step 2: Group the IP-Adapter nodes**

In the workflow JSON, wrap nodes 10-13 in a group titled "IP-Adapter FaceID (disconnect for text-only)". ComfyUI groups are stored in the `extra.groups` array of the workflow JSON:

```json
{
  "title": "IP-Adapter FaceID (disconnect for text-only)",
  "bounding": [x, y, width, height],
  "color": "#3f789e"
}
```

Position the group visually between the checkpoint loader and the KSampler.

- [ ] **Step 3: Test reference mode**

1. Load the updated workflow in ComfyUI
2. Load a reference photo into node 10 (any clear face photo)
3. Set the positive prompt to style/setting only: `"fantasy portrait, dramatic lighting, oil painting style, detailed"`
4. Queue prompt
5. Verify: the generated portrait resembles the reference photo's face, with the style from the text prompt

- [ ] **Step 4: Test text-only mode**

1. Disconnect Node 13 MODEL → Node 5 model
2. Connect Node 1 MODEL → Node 5 model directly
3. Set the positive prompt to a full character description: `"portrait of a young woman with red hair, green eyes, freckles, wearing a leather jacket, fantasy style, dramatic lighting"`
4. Queue prompt
5. Verify: portrait generates without errors, driven entirely by the text
6. Reconnect Node 13 MODEL → Node 5 model to restore reference mode

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/prg/plum-character-portrait
git add projects/rp/comfyui/character-portrait.json
git commit -m "feat(rp): add IP-Adapter FaceID Plus V2 branch to portrait workflow"
```

---

### Task 4: Support multiple reference photos

Extend the workflow to accept additional reference photos for mix-and-match (face from one person, body/clothes from another) or multiple angles of the same person.

**Files:**
- Modify: `projects/rp/comfyui/character-portrait.json`

- [ ] **Step 1: Add a second LoadImage node**

Add node:

| ID | Node | Key Parameters |
|---|---|---|
| 14 | `LoadImage` | Second reference photo input |

- [ ] **Step 2: Add a batch combine node**

To feed multiple images to IP-Adapter, use the `ImageBatch` built-in node:

| ID | Node | Key Parameters |
|---|---|---|
| 15 | `ImageBatch` | Combines two images into a batch |

**Connections:**
- Node 10 IMAGE → Node 15 image1
- Node 14 IMAGE → Node 15 image2
- Node 15 IMAGE → Node 13 image (**replaces** the direct Node 10 → Node 13 connection)

With `combine_embeds: "average"` on node 13, multiple face references are averaged for a composite likeness.

- [ ] **Step 3: Test with two reference photos**

1. Load two different face photos into nodes 10 and 14
2. Queue prompt with a style-only prompt
3. Verify: the output blends features from both references

- [ ] **Step 4: Commit**

```bash
cd /mnt/d/prg/plum-character-portrait
git add projects/rp/comfyui/character-portrait.json
git commit -m "feat(rp): support multiple reference photos via image batching"
```

---

## Chunk 3: Post-Processing and Documentation

### Task 5: Add avatar face crop

Add post-processing nodes that detect the face in the generated portrait and crop it to a 256x256 avatar.

**Files:**
- Modify: `projects/rp/comfyui/character-portrait.json`

- [ ] **Step 1: Add face crop nodes**

The portrait is a single-face 1024x1024 image where the subject is naturally centered (standard for portrait generation with prompts like "portrait of..."). A center crop reliably captures the face without needing a separate face detection pass on the output.

Note: InsightFace is loaded in node 11, but there is no standalone "detect face bbox in image" node in `ComfyUI_IPAdapter_plus` — the face detection happens internally within `IPAdapterFaceID`. Using `ImageResizeKJv2` with center crop is the pragmatic approach for single-face portraits.

| ID | Node | Key Parameters |
|---|---|---|
| 20 | `ImageResizeKJv2` | `width`: 256, `height`: 256, `upscale_method`: `lanczos`, `keep_proportion`: `crop`, `crop_position`: `center` |
| 21 | `SaveImage` | `filename_prefix`: `avatar` |

**Connections:**
- Node 6 IMAGE → Node 20 image (full portrait → center crop + resize)
- Node 20 IMAGE → Node 21 images (save avatar)

- [ ] **Step 2: Test avatar output**

1. Run the workflow (either mode)
2. Check the output folder for both `portrait_*.png` (1024x1024) and `avatar_*.png` (256x256)
3. Verify the avatar is a clean face crop

- [ ] **Step 3: Commit**

```bash
cd /mnt/d/prg/plum-character-portrait
git add projects/rp/comfyui/character-portrait.json
git commit -m "feat(rp): add avatar face crop to portrait workflow"
```

---

### Task 6: Write usage documentation

**Files:**
- Create: `projects/rp/comfyui/README.md`

- [ ] **Step 1: Write README**

Create `projects/rp/comfyui/README.md` with:

```markdown
# Character Portrait ComfyUI Workflow

Generates character portraits from text descriptions, optionally using reference photos.

## Setup

### Prerequisites
1. ComfyUI with these custom nodes installed:
   - `ComfyUI_IPAdapter_plus`
   - `comfyui-kjnodes`
2. Models (in ComfyUI models directory):
   - `checkpoints/juggernautXL_ragnarokBy.safetensors`
   - `ipadapter/ip-adapter-faceid-plusv2_sdxl.bin`
   - `loras/ip-adapter-faceid-plusv2_sdxl_lora.safetensors`
   - `clip_vision/model.safetensors` (CLIP ViT-H-14, 3.7GB)
   - `insightface/models/antelopev2/` (5 .onnx files)

### Loading
1. Open ComfyUI
2. Click "Load" → select `character-portrait.json`

## Usage

### Text-Only Mode (no reference photos)
1. Disconnect Node 13 (IPAdapterFaceID) MODEL output → Node 5 (KSampler) model input
2. Connect Node 1 (Checkpoint) MODEL output → Node 5 (KSampler) model input directly
3. Enter your character description in the positive prompt, e.g.:
   > portrait of a tall elven woman with silver hair, emerald eyes, wearing ornate mithril armor, stern expression, fantasy style, dramatic lighting
4. Click "Queue Prompt"

### Reference Photo Mode (default wiring)
1. Ensure Node 13 MODEL → Node 5 model is connected (this is the default)
2. Load 1-2 reference photos into the Load Image nodes
3. Set the positive prompt to style/setting only, e.g.:
   > fantasy portrait, dramatic lighting, oil painting style, detailed
4. Click "Queue Prompt"

The generated face will resemble the reference photos. Multiple photos are averaged for a composite likeness.

## Outputs

| File | Resolution | Description |
|---|---|---|
| `portrait_*.png` | 1024x1024 | Full character portrait |
| `avatar_*.png` | 256x256 | Center-cropped face for use as avatar |

## Tuning

- **IP-Adapter weight** (node 13): Higher = more reference likeness, lower = more text influence. Default: 0.7
- **LoRA strength** (node 12): Controls the FaceID LoRA effect. Default: 0.7
- **CFG scale** (node 5): Higher = stronger prompt adherence. Default: 7.0
- **Steps** (node 5): More steps = more detail. Default: 25
```

- [ ] **Step 2: Commit**

```bash
cd /mnt/d/prg/plum-character-portrait
git add projects/rp/comfyui/README.md
git commit -m "docs(rp): add character portrait workflow usage guide"
```

---

## Execution Notes

- The workflow JSON must be in ComfyUI's full UI format (with node positions, dimensions, widget values) — not the simplified API format. This is because the user loads it in the visual editor.
- Node positions should be arranged left-to-right: Checkpoint → (IP-Adapter branch) → KSampler → VAE Decode → Save. The IP-Adapter group sits above/below the main flow.
- Test each mode (text-only, single reference, two references) after each chunk to catch wiring issues early.
