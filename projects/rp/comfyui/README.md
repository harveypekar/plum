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
1. Disconnect Node 13 (IPAdapterFaceID) MODEL output from Node 5 (KSampler) model input
2. Connect Node 1 (Checkpoint) MODEL output directly to Node 5 (KSampler) model input
3. Enter your character description in the positive prompt (Node 2), e.g.:
   > portrait of a tall elven woman with silver hair, emerald eyes, wearing ornate mithril armor, stern expression, fantasy style, dramatic lighting
4. Click "Queue Prompt"

### Reference Photo Mode (default wiring)
1. Ensure Node 13 MODEL → Node 5 model is connected (this is the default)
2. Load 1-2 reference photos into the Load Image nodes (Nodes 10 and 14)
3. Set the positive prompt (Node 2) to style/setting only, e.g.:
   > fantasy portrait, dramatic lighting, oil painting style, detailed
4. Click "Queue Prompt"

The generated face will resemble the reference photos. Multiple photos are averaged for a composite likeness.

## Outputs

| File | Resolution | Description |
|---|---|---|
| `portrait_00001.png` | 1024x1024 | Full character portrait |
| `avatar_00001.png` | 256x256 | Center-cropped face for use as avatar |

## Tuning

- **IP-Adapter weight** (Node 13): Higher = more reference likeness, lower = more text influence. Default: 0.7
- **LoRA strength** (Node 12): Controls the FaceID LoRA effect. Default: 0.7
- **CFG scale** (Node 5): Higher = stronger prompt adherence. Default: 7.0
- **Steps** (Node 5): More steps = more detail, slower generation. Default: 25
