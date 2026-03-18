# Research: ComfyUI Practical Workflows

Date: 2026-03-13

## 1. 3D Face/Body Extraction from Images

### DECA/FLAME (Face-Specific, Animation-Ready)

FLAME is a parametric face model (~300 shape params, ~100 expression params) from Max Planck Institute. DECA is a neural network that regresses FLAME parameters from a single 2D photo, producing a textured, expression-aware 3D face mesh.

**Setup:**
```bash
git clone https://github.com/yfeng95/DECA.git
cd DECA
conda create -n deca python=3.9
conda activate deca
pip install -r requirements.txt
pip install "git+https://github.com/facebookresearch/pytorch3d.git"
```

**Model downloads (manual):**
1. Register at https://flame.is.tue.mpg.de/ (free academic account)
2. Download `FLAME 2020` → place `generic_model.pkl` in `DECA/data/`
3. Download `FLAME texture space` → place `FLAME_albedo_from_BFM.npz` in `DECA/data/`
4. Download DECA pretrained weights from repo README (Google Drive) → `DECA/data/deca_model.tar`

**Usage:**
```bash
python demos/demo_reconstruct.py \
  --inputpath /path/to/photo.jpg \
  --savefolder output \
  --saveObj True \
  --useTex True
```

**Output:**
- `.obj` — 3D mesh (5023 vertices, consistent topology across all faces)
- `.mtl` — material file
- `_albedo.png` — face texture map
- `_detail.png` — detail normal map

**Key flags:** `--saveDepth True`, `--saveMat True` (saves FLAME parameters), `--rasterizer_type pytorch3d`

**FLAME topology advantages:**
- Consistent vertex layout → transfer expressions between faces
- Built-in blendshapes (jaw, smile, brow, etc.)
- Animation-ready with consistent UV layout
- Clean low-poly mesh vs raw neural reconstruction

**EMOCA** (successor to DECA with better expression accuracy): https://github.com/radekd91/emoca

**Note:** No native ComfyUI node exists for DECA/FLAME. Run standalone, then load `.obj` back into ComfyUI if needed.

### Other Local Image-to-3D Options

| Tool | VRAM | Speed | Quality | Notes |
|------|------|-------|---------|-------|
| TripoSR | ~6 GB | ~10s | Good for prototypes | ComfyUI-3D-Pack or standalone [1] |
| InstantMesh | ~8 GB | ~30-60s | Better geometry | Part of ComfyUI-3D-Pack [2] |
| Trellis | ~12 GB | ~1-2 min | Best mesh quality | Microsoft, `ComfyUI-Trellis` node [3] |
| CRM | ~8 GB | ~30s | Good, clean topology | Part of ComfyUI-3D-Pack |
| Meshroom | 4 GB+ | Varies | Best (multi-photo) | Photogrammetry, AliceVision-based [4] |

For TripoSR standalone:
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/MrForExample/ComfyUI-3D-Pack.git
cd ComfyUI-3D-Pack
pip install -r requirements.txt
```

## 2. ControlNet Workflows

### ControlNet Lineart

**Nodes:**
1. **Load Image** → source image
2. **LineArt Preprocessor** (under `ControlNet Preprocessors → Line Extractors`)
   - `resolution`: 512 or 768 (match generation resolution)
   - `coarse`: disable for fine lines, enable for sketch-like
3. **ControlNetLoader** → `control_v11p_sd15_lineart.pth`
4. **Apply ControlNet** → strength 0.6-0.8
5. **KSampler** → standard generation

**Chain:**
```
Load Image → LineArt Preprocessor → Apply ControlNet ← ControlNetLoader
                                         ↑
                                   CLIP Text Encode (positive/negative)
                                         ↓
                                   KSampler ← Checkpoint, Empty Latent
                                         ↓
                                   VAE Decode → Save Image
```

### ControlNet Canny

Same as lineart but:
- Use **Canny** preprocessor node (`low_threshold`: 0.4, `high_threshold`: 0.8)
- Use `control_v11p_sd15_canny.pth` model

### Tips

- **Strength 0.6-0.8** is the sweet spot; 1.0 makes outputs look stiff
- **Always preview** the preprocessor output before full generation
- **Resolution must match** between Empty Latent Image and preprocessor
- **SD 1.5 ControlNets don't work with SDXL checkpoints** (and vice versa)
- If model file gives "PytorchStreamReader failed reading zip archive" → file is corrupted, re-download

### Downloading ControlNet Models

```bash
cd ComfyUI/models/controlnet

# Canny
wget https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_canny.pth

# Lineart
wget https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_lineart.pth

# FP16 safetensors variants (smaller)
wget https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/resolve/main/control_v11p_sd15_canny_fp16.safetensors
wget https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/resolve/main/control_v11p_sd15_lineart_fp16.safetensors
```

## 3. IP-Adapter (Image-Guided Generation)

### IP-Adapter FaceID (Face Identity Transfer)

Transfers face likeness from reference photos to generated images using InsightFace embeddings.

**Models required (SD 1.5):**

| File | Size | Location |
|------|------|----------|
| `ip-adapter-faceid-plusv2_sd15.bin` | ~1.4 GB | `models/ipadapter/` |
| `ip-adapter-faceid-plusv2_sd15_lora.safetensors` | ~150 MB | `models/loras/` |
| `model.safetensors` (CLIP ViT-H-14) | ~3.9 GB | `models/clip_vision/` |
| InsightFace `buffalo_1` | — | `models/insightface/` |

**Download:**
```bash
# IP-Adapter FaceID model
wget -O models/ipadapter/ip-adapter-faceid-plusv2_sd15.bin \
  https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sd15.bin

# FaceID LoRA
wget -O models/loras/ip-adapter-faceid-plusv2_sd15_lora.safetensors \
  https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sd15_lora.safetensors

# CLIP Vision (required for IP-Adapter)
wget -O models/clip_vision/model.safetensors \
  https://huggingface.co/laion/CLIP-ViT-H-14-laion2B-s32B-b79K/resolve/main/model.safetensors
```

**Install custom nodes:** `ComfyUI_IPAdapter_plus` via ComfyUI Manager [5]

**Workflow:**
```
Load Image (face reference)
  → IPAdapter FaceID (weight: 0.7)
    → MODEL → KSampler
```

### Multiple Face References (Blending)

IP-Adapter FaceID Batch averages face embeddings from multiple images:

- **Same person, multiple angles** → more accurate likeness of one person
- **Different people** → blends features (person A's eyes + person B's jaw)

```
Load Image Batch (folder of faces)
  → IPAdapter FaceID Batch → MODEL
```

Control blend with weights:
```
IPAdapter FaceID (face A, weight: 0.7)    ← dominant
  → IPAdapter FaceID (face B, weight: 0.3)  ← subtle influence
    → KSampler
```

### IP-Adapter Style Transfer

Uses a regular IP-Adapter (not FaceID) to transfer aesthetic/style — colors, lighting, mood, texture.

**Additional model:**
```bash
wget -O models/ipadapter/ip-adapter-plus_sd15.bin \
  https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter-plus_sd15.bin
```

**Workflow:**
```
Load Image (style reference)
  → IPAdapter Advanced (weight: 0.6-0.8, weight_type: "style transfer")
    → MODEL → KSampler
```

**Weight types in IPAdapter Advanced:**

| Weight Type | Extracts |
|-------------|----------|
| `linear` | Everything (composition + style + content) |
| `style transfer` | Colors, lighting, texture, mood |
| `composition` | Layout/framing, ignores colors |
| `style and composition` | Both style and layout |

### Stacking Multiple Controls

IP-Adapter modifies MODEL. ControlNet modifies CONDITIONING. They're independent and stackable:

```
Checkpoint MODEL
  │
  ├─ IPAdapter FaceID ← face reference (controls identity)
  │
  ├─ IPAdapter Advanced (style transfer) ← style reference (controls aesthetic)
  │
  ├─ ControlNet OpenPose ← pose reference (controls pose)
  │
  ├─ ControlNet Lineart ← body reference (controls structure)
  │
  └─ Text prompt → "piercings, septum ring..." (controls details)
        ↓
    KSampler → VAEDecode → SaveImage
```

ControlNets daisy-chain through conditioning:
```
CLIP Encode (positive)
  → Apply ControlNet (OpenPose)
    → Apply ControlNet (Lineart)
      → KSampler
```

### Recommended Folder Structure for References

```
ref/
  head/       ← multiple face angles for IP-Adapter FaceID Batch
  style/      ← aesthetic/mood references for IP-Adapter style transfer
  pose/       ← single pose reference for OpenPose ControlNet
  body/       ← single body reference for Lineart/Canny ControlNet
  piercing/   ← close-ups for inpainting or secondary IP-Adapter
```

## 4. Image Preprocessing

### Background Removal

Essential before ControlNet preprocessing to avoid background clutter in line extraction.

- **RMBG** node (built into newer ComfyUI) — `Image → RMBG`
- **ComfyUI-BiRefNet** (via ComfyUI Manager) — slightly better quality

Chain: `Load Image → RMBG → LineArt Preprocessor → ...`

### Feature Enhancement / Normalization

For making features stand out before preprocessing:

| Node | Purpose |
|------|---------|
| **ImageContrast** | Increase to 1.3-1.5 for sharper edges |
| **ImageSharpen** | Sharpens details |
| **ColorCorrect** (KJNodes) | Brightness, contrast, saturation, gamma |
| **CLAHE** (via ComfyUI Manager) | Adaptive histogram equalization — best for local feature enhancement |

**Recommended chain before ControlNet:**
```
Load Image → RMBG → ImageContrast (1.3-1.5) → ImageSharpen → LineArt Preprocessor → Preview
```

### ControlNet Preprocessors (Feature Extraction)

Under `ControlNet Preprocessors` in the node menu:

| Preprocessor | Output | Use For |
|-------------|--------|---------|
| LineArt | Clean line drawing | Structure, outlines |
| Canny | Edge detection | Hard edges, details |
| Depth (MiDaS/Zoe) | Depth map | 3D structure |
| Normal Map (BAE) | Surface normals | Contours, surface angles |
| OpenPose | Body/face keypoints | Pose control |
| MediaPipe Face Mesh | Facial landmarks | Face structure |

## 5. Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `PytorchStreamReader failed reading zip archive` | Corrupted/incomplete model file | Re-download the model |
| `Value not in list: control_net_name` | Model file not in expected directory | Download to `models/controlnet/` or pick available model from dropdown |
| Swirly/abstract output | ControlNet strength too high, wrong preprocessor, or resolution mismatch | Lower strength to 0.6-0.8, verify preprocessor type matches ControlNet model, match resolutions |
| Stiff/overcooked output | CFG too high | Lower CFG from 9+ to 7 |
| SD 1.5 ControlNet with SDXL checkpoint | Architecture mismatch | Use matching versions |

## References

[1] TripoSR. GitHub (VAST-AI-Research), 2024. https://github.com/VAST-AI-Research/TripoSR

[2] InstantMesh. GitHub (TencentARC), 2024. https://github.com/TencentARC/InstantMesh

[3] TRELLIS. GitHub (Microsoft), 2024. https://github.com/microsoft/TRELLIS

[4] Meshroom. GitHub (AliceVision), 2024. https://github.com/alicevision/Meshroom

[5] ComfyUI_IPAdapter_plus. GitHub (cubiq), 2025. https://github.com/cubiq/ComfyUI_IPAdapter_plus

[6] IP-Adapter. Hugging Face (h94), 2024. https://huggingface.co/h94/IP-Adapter

[7] IP-Adapter FaceID. Hugging Face (h94), 2024. https://huggingface.co/h94/IP-Adapter-FaceID

[8] DECA: Detailed Expression Capture and Animation. GitHub (yfeng95), 2021. https://github.com/yfeng95/DECA

[9] FLAME: Faces Learned with an Articulated Model and Expressions. Max Planck Institute, 2017. https://flame.is.tue.mpg.de/

[10] ControlNet v1.1. Hugging Face (lllyasviel), 2023. https://huggingface.co/lllyasviel/ControlNet-v1-1
