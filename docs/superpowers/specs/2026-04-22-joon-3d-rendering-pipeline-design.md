# Joon: 3D Rendering Pipeline

**Created:** 2026-04-22
**Status:** Design
**Extends:** `2026-03-29-joon-design.md`
**Project:** `projects/joon/`

## Overview

Adds a 3D rendering pipeline to joon alongside the existing 2D compute graph. The DSL gains scene description (meshes, cameras, lights), composable materials as shader functions, and a frame graph for multi-pass rendering. The renderer type (forward, deferred, forward+) is not an enum — it emerges from how the user wires passes together.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Compute alongside 3D | Yes | Compute generates textures that feed into 3D materials |
| Renderer selection | Inferred from graph structure | DSL is renderer-agnostic |
| Geometry source | Primitives + file loading | Primitives for testing, files for real content |
| Lighting model | Pluggable — BRDF is DSL-composable | No hardcoded Phong or PBR |
| Shader authoring | Full shader graph (vertex + fragment) | Both stages are DSL node graphs |
| Shader language | HLSL only | Remove GLSL, compile HLSL → SPIR-V via DXC |
| Material model | Material IS the fragment function | No separate material abstraction |
| Pass types | Geometry pass (vertex+fragment) + compute | Only geometry rasterization uses graphics pipelines; lighting, post-process, everything else is compute |
| Scene/object binding | Implicit | All scene objects go through geometry passes; system infers geometry vs compute passes |
| Render target default | RGBA8 | Override per-output with `:format` |
| Built-in uniforms | Implicit globals | `mvp`, `model`, `view`, `projection`, `time` always available in shader functions |
| User uniforms | `(param ...)` mechanism | Same system that already exists for GUI sliders |

## DSL Extensions

### Scene Nodes

```lisp
; Geometry — primitives
(cube :material mat :position [1 0 0] :scale 1.0)
(sphere :radius 0.5 :material mat :position [0 1 0])
(plane :size [10 10] :material mat)
(cylinder :radius 0.3 :height 2.0 :material mat)

; Geometry — file loading
(mesh "suzanne.obj" :material mat :position [0 0 0])

; Lighting
(light :type point :position [2 4 2] :color [1 1 1] :intensity 10.0)
(light :type directional :direction [0 -1 -1] :color [1 0.9 0.8])
(light :type spot :position [0 5 0] :direction [0 -1 0] :angle 30)

; Camera
(camera :fov 60 :position [0 2 5] :target [0 0 0])
```

### Shader Functions

Functions receive vertex attributes and return named outputs. The role (vertex/fragment) is determined by where the function is used, not by annotation.

```lisp
; Vertex function — transform is explicit
(def vs-standard (fn [position normal uv]
  {:position (* mvp position)
   :normal (* (transpose (inverse model)) normal)
   :uv uv}))

; Material/fragment function — composes with compute graph
(def albedo-tex (noise :scale 2.0))
(def normal-map (image "bricks_normal.png"))

(def mat (fn [position normal uv]
  (let [color (sample albedo-tex uv)
        n (sample normal-map uv)]
    {:albedo color
     :normal n
     :roughness 0.7})))
```

Built-in globals (`mvp`, `model`, `view`, `projection`, `time`, `resolution`) are always available inside shader functions. User-defined uniforms use the existing `(param ...)` mechanism.

### Geometry Pass

The one pass type that uses graphics pipelines. Rasterizes all scene objects.

```lisp
(pass gbuffer
  :outputs [albedo normal depth]
  :vertex vs-standard
  :fragment mat)
```

Render target format defaults to RGBA8, overridable:

```lisp
(pass gbuffer
  :outputs [(albedo :format rgba16f :clear [0 0 0 1]) normal depth]
  :vertex vs-standard
  :fragment mat)
```

### Post-Geometry Processing

Everything after rasterization is compute. Render targets from geometry passes become `GpuImage`s that flow into the compute graph.

```lisp
; Geometry pass
(pass gbuffer
  :outputs [albedo normal depth]
  :vertex vs-standard
  :fragment mat)

; Compute nodes — same as existing pipeline
(def lit (lighting albedo normal depth lights))
(def tonemapped (levels lit :contrast 1.2))
(output tonemapped)
```

`lighting` is a compute node like `noise` or `levels`. No fullscreen fragment passes.

### Full Example: Deferred Renderer

```lisp
; Scene
(camera :fov 60 :position [0 2 5] :target [0 0 0])
(light :type point :position [2 4 2] :color [1 1 1] :intensity 10.0)
(light :type directional :direction [0 -1 -1] :color [1 0.9 0.8])

; Materials
(def stone-tex (image "textures/stone.png"))
(def stone (fn [position normal uv]
  {:albedo (sample stone-tex uv)
   :normal normal
   :roughness 0.8
   :metallic 0.0}))

(def metal (fn [position normal uv]
  {:albedo [0.9 0.9 0.95]
   :normal normal
   :roughness 0.2
   :metallic 1.0}))

; Scene objects
(cube :material stone :position [0 0 0])
(sphere :radius 0.5 :material metal :position [2 1 0])
(plane :size [10 10] :material stone :position [0 -0.5 0])

; Vertex shader
(def vs (fn [position normal uv]
  {:position (* mvp position)
   :normal (* (transpose (inverse model)) normal)
   :uv uv}))

; G-buffer pass (the only graphics pass)
; :fragment sets the default; each object's :material overrides it
(pass gbuffer
  :outputs [albedo-rt normal-rt roughmetal-rt depth-rt]
  :vertex vs
  :fragment stone)

; Compute lighting
(param exposure float 1.0 :min 0.0 :max 5.0)
(def lit (deferred-lighting albedo-rt normal-rt roughmetal-rt depth-rt
           :exposure exposure))
(def final (levels lit :contrast 1.1))
(output final)
```

The renderer is deferred because the user wrote a gbuffer pass with multiple outputs followed by a compute lighting pass. A forward renderer would be a single pass that computes lighting in the fragment function. The system doesn't know or care which pattern is used.

## Architecture

### IR Extensions

New node tiers and types alongside existing `GPU` and `CPU`:

| Node op | Tier | Produces |
|---------|------|----------|
| `noise`, `levels`, `lighting` | GPU | GpuImage (compute) |
| `constant`, `param` | CPU | GpuImage (via upload) |
| `mesh`, `cube`, `sphere`, `plane`, `cylinder` | SCENE | SceneObject |
| `light` | SCENE | Light |
| `camera` | SCENE | Camera |
| `fn` | SHADER | ShaderFunction (compiles to HLSL) |
| `pass` | RENDER | RenderTarget(s) → GpuImage(s) |

Materials bridge compute and 3D: a fragment function can `(sample ...)` compute-produced textures.

### Shader Compiler

DSL function nodes compile to HLSL, then to SPIR-V via DXC.

**Translation rules:**

| DSL | HLSL |
|-----|------|
| `(* mvp position)` | `mul(mvp, float4(position, 1.0))` |
| `(sample texture uv)` | `texture.Sample(linearSampler, uv)` |
| `(let [x expr] body)` | `type x = expr; body` |
| `{:albedo a :normal n}` | Struct return with semantic mapping |
| `(+ a b)`, `(- a b)` | `a + b`, `a - b` |
| `(dot a b)`, `(cross a b)` | `dot(a, b)`, `cross(a, b)` |
| `(normalize v)`, `(length v)` | `normalize(v)`, `length(v)` |
| `(transpose m)`, `(inverse m)` | `transpose(m)`, `inverse(m)` |

Type inference propagates from known vertex attribute types through expressions.

**DXC integration:**
- Runtime compilation via dxc process (from Vulkan SDK) initially
- Switch to libdxcompiler when runtime shader generation needs it
- Input: generated HLSL
- Output: SPIR-V blob → `vkCreateShaderModule`
- Cached by source hash

### Frame Graph Execution

The evaluator analyzes the IR and builds an execution plan:

1. Compute-only subgraph → existing Interpreter (topological walk, unchanged)
2. Scene collection → gather all mesh/light/camera nodes
3. Geometry pass → VkRenderPass with graphics pipeline, draw all scene objects
4. Post-geometry compute → compute dispatches reading render targets as images

Render targets from geometry passes become `GpuImage` entries in the `ResourcePool`, keyed by the pass output node ID. Downstream compute nodes reference them the same way they reference any other image.

**Vulkan resource transitions:** After the geometry pass ends, render targets transition from `COLOR_ATTACHMENT_OPTIMAL` to `GENERAL` for compute shader read. The frame graph compiler inserts these barriers automatically.

### Backwards Compatibility

A DSL program with no scene/pass nodes runs exactly as today. The frame graph only activates when `(pass ...)` nodes are present.

## Sub-Projects

### Sub-project 1: HLSL Migration

Port existing compute infrastructure from GLSL to HLSL.

**Scope:**
- Port all 10 compute shaders to HLSL (`noise`, `levels`, `blur`, `blend`, `invert`, `threshold`, `add`, `sub`, `mul`, `div`)
- Integrate DXC for HLSL → SPIR-V compilation (shell out to `dxc` from Vulkan SDK)
- Update `PipelineCache` to compile HLSL at runtime instead of loading pre-compiled SPIR-V
- Remove GLSL shaders and any glslc/glslangValidator dependency
- All existing tests and GUI continue to work identically

**HLSL compute shader pattern:**

```hlsl
RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

cbuffer Params : register(b0) {
    float contrast;
    float brightness;
};

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 c = input_img[id.xy];
    float3 adjusted = (c.rgb - 0.5) * contrast + 0.5 + brightness;
    output_img[id.xy] = float4(saturate(adjusted), c.a);
}
```

**Key GLSL → HLSL mappings:**

| GLSL | HLSL |
|------|------|
| `layout(set=0, binding=N, rgba32f) uniform image2D` | `RWTexture2D<float4> : register(uN)` |
| `layout(push_constant) uniform Params { ... }` | `cbuffer Params : register(b0) { ... }` |
| `imageLoad(img, pos)` | `img[pos]` |
| `imageStore(img, pos, val)` | `img[pos] = val` |
| `imageSize(img)` | `img.GetDimensions(w, h)` |
| `gl_GlobalInvocationID` | `SV_DispatchThreadID` |
| `clamp(x, 0.0, 1.0)` | `saturate(x)` |
| `layout(local_size_x=16, local_size_y=16) in` | `[numthreads(16, 16, 1)]` |

### Sub-project 2: Scene Graph & Geometry Pass

New AST/IR nodes for meshes, cameras, lights, materials. Procedural primitives (cube, sphere, plane, cylinder). OBJ loading. A single hardcoded geometry pass with vertex + fragment shaders (hardcoded HLSL, not yet DSL-generated). Renders a 3D scene to a render target that feeds into the existing compute graph.

### Sub-project 3: Shader Compiler

DSL function nodes (`fn`) compile to HLSL via code generation. Type inference for shader expressions. Built-in globals. Materials as fragment functions. DXC compilation of generated HLSL. Replaces hardcoded shaders from sub-project 2.

### Sub-project 4: Frame Graph

`(pass ...)` nodes in the AST/IR. Render target allocation and format inference. Pass dependency analysis. Geometry pass outputs flow into compute graph. Vulkan barrier insertion. Multi-pass rendering.

## Non-Goals (This Design)

- Compiled/optimized mode (node fusion, shader merging)
- Shadow mapping, environment probes, global illumination
- Animation, skeletal meshes
- Voxel type support
- CSG or procedural mesh operations beyond primitives
- Async compute scheduling
