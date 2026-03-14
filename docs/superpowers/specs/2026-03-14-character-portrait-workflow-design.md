# Character Portrait ComfyUI Workflow — Design Spec

## Summary

A single ComfyUI workflow (`character-portrait.json`) that generates a character portrait from a text description, optionally using reference photos for face/body/clothing likeness. Outputs a full portrait and a cropped avatar.

## Two Modes

- **Text-only mode:** Character description drives the full generation. No reference photos.
- **Reference mode:** Reference photos drive character appearance via IP-Adapter FaceID Plus V2. Text prompt controls style/setting only.

Switching between modes: mute/unmute the IP-Adapter node group in ComfyUI. When no reference photos are loaded, the group is muted.

## Prerequisites

### Required Custom Nodes (already installed)

- `ComfyUI_IPAdapter_plus` — IP-Adapter FaceID Plus V2 nodes
- `comfyui-kjnodes` — Provides `GetImageSizeAndCount` and crop utilities for avatar extraction
- `comfyui-controlnet_aux` — Preprocessor nodes (available for future use)

### Models to Download

The following models are **missing** and must be downloaded before the workflow will function:

| Model | Purpose | Download to | Notes |
|---|---|---|---|
| InsightFace `antelopev2` | Face analysis for IP-Adapter FaceID | `models/insightface/models/antelopev2/` | Required `.onnx` files: `1k3d68.onnx`, `2d106det.onnx`, `det_10g.onnx`, `genderage.onnx`, `w600k_r50.onnx`. Download from InsightFace model zoo. The existing `buffalo_1/` directory is empty and `inswapper_128.onnx` is for face-swapping only. |

### Models Already Present

| Model | Purpose | File |
|---|---|---|
| JuggernautXL | Base checkpoint (SDXL) | `checkpoints/juggernautXL_ragnarokBy.safetensors` |
| IP-Adapter FaceID Plus V2 SDXL | Face/body reference transfer | `ipadapter/ip-adapter-faceid-plusv2_sdxl.bin` |
| IP-Adapter FaceID Plus V2 SDXL LoRA | Required companion LoRA | `loras/ip-adapter-faceid-plusv2_sdxl_lora.safetensors` |
| CLIP ViT-H-14 | CLIP vision for IP-Adapter | `clip_vision/model.safetensors` (3.7 GB, generic filename) |
| InsightFace inswapper | Face swapping (not used in this workflow) | `insightface/inswapper_128.onnx` |

All model paths are relative to `/mnt/c/Users/daan/Documents/ComfyUI/models/`.

## Node Groups

### 1. Base Generation (always active)

- **Checkpoint Loader:** JuggernautXL
- **CLIP Text Encode (positive):** Character description text. In reference mode, simplified to style/setting tags.
- **CLIP Text Encode (negative):** Standard quality negatives ("blurry, deformed, bad anatomy, watermark")
- **KSampler:** Euler a, 25 steps, CFG 7, 1024x1024 resolution
- **VAE Decode:** Built-in VAE from JuggernautXL

### 2. IP-Adapter Branch (muted when no reference photos)

- **Load Image node(s):** 0 to N reference photos
- **IPAdapter Unified Loader FaceID** (from `ComfyUI_IPAdapter_plus`): Loads the FaceID Plus V2 model, CLIP vision model, and companion LoRA. Returns an already-patched MODEL. The LoRA is loaded internally via the `lora_strength` parameter — do **not** add a separate LoRA Loader node (that would apply the LoRA twice, causing distorted output).
  - `lora_strength`: ~0.7
- **IPAdapter InsightFace Loader** (from `ComfyUI_IPAdapter_plus`): Loads `antelopev2` face analysis model (provider: CPU or CUDA)
- **IPAdapter FaceID node:** Applies face embeddings to the model
  - Weight: ~0.7 (strong likeness, allows style prompt influence)
- **Multiple references:** IP-Adapter batch input averages multiple photos for stronger likeness
- **Bypass:** ComfyUI native "Mute" grouping — muted when no photos loaded

### 3. Post-Processing

- **InsightFace face detection** (reuses the already-loaded `antelopev2` model): Detects face bounding box in the generated image.
- **Crop and resize** (using `comfyui-kjnodes` crop utilities or built-in ComfyUI ImageCrop): Square crop centered on detected face bounding box, resized to 256x256.
- **Save Image (portrait):** `portrait_[seed]` prefix — full 1024x1024 (ComfyUI appends counter automatically)
- **Save Image (avatar):** `avatar_[seed]` prefix — 256x256 face crop

## Inputs

| Input | Type | Description |
|---|---|---|
| Character description | Text field | Paste from character card description/personality |
| Reference photos | Load Image (0-N) | Optional. Face/body/clothing reference photos |
| Style tags | Text field | Style/setting overrides. Default: "fantasy portrait, dramatic lighting" |

## Outputs

| Output | Resolution | Filename |
|---|---|---|
| Full portrait | 1024x1024 | `portrait_[seed]_00001.png` |
| Avatar crop | 256x256 | `avatar_[seed]_00001.png` |

Output directory: ComfyUI default output folder. Filenames use ComfyUI's built-in prefix + counter pattern.

## Scope Boundaries

**In scope:**
- Single ComfyUI workflow file (.json)
- Text-only and reference-photo modes
- Portrait + avatar output
- JuggernautXL (SDXL) only

**Out of scope (future work):**
- App integration (API calls from RP app to ComfyUI)
- Automatic prompt generation from character cards via LLM
- Animation / Live2D
- Scene generation with multiple characters
- ControlNet pose/composition control
