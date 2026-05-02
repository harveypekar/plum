# Joon Sub-Project 3: DSL-Generated Shaders & Deferred Lighting

**Date:** 2026-05-01
**Status:** Approved
**Depends on:** Sub-project 2 (scene graph + hardcoded geometry pass, PR #134)

## Goal

Replace joon's hardcoded vertex/fragment shaders with a DSL-driven shader codegen system. Materials are DSL expressions that define surface properties (G-buffer outputs) and optionally a custom BRDF. The renderer evaluates BRDFs per-light in a deferred fullscreen pass. Un-inlineable DSL ops inside shader bodies are automatically extracted into compute pre-passes.

## DSL Syntax

### Material definition

```lisp
(def brick (shader
  :vertex (fn [pos normal uv]
    (set pos.y (+ pos.y (* 0.1 (sin (+ (* pos.x 8.0) time))))))
  :brdf (fn [normal light_dir view_dir albedo]
    (* albedo (step 0.3 (dot normal light_dir))))
  :fragment (fn [normal uv] -> [albedo vec4, normal vec4, roughmetal vec4]
    (set albedo (noise :scale 4.0 :octaves 2))
    (set normal (encode normal))
    (set roughmetal [0.7 0.0 0 0]))))
```

All three clauses are optional:
- **`:vertex`** — Custom vertex transform. Receives `pos`, `normal`, `uv` as mutable inputs plus `time` as a read-only built-in. Default: identity (standard MVP transform only).
- **`:fragment`** — Surface property writer. Arrow syntax `-> [name type, ...]` declares G-buffer outputs. Default: single `[albedo vec4]` output with white color.
- **`:brdf`** — Custom light response function. Receives `normal`, `light_dir`, `view_dir`, `albedo` (and any other G-buffer channels by name). Returns a `vec4` color contribution for one light. Default: Cook-Torrance GGX (metallic-roughness workflow).

### Scene usage

```lisp
(def wall (cube :scale 2.0 :material brick))
(def ball (sphere :radius 0.5 :material (shader
  :fragment (fn [normal uv] -> [albedo vec4, normal vec4, roughmetal vec4]
    (set albedo [0.9 0.1 0.1 1])
    (set normal (encode normal))
    (set roughmetal [0.3 1.0 0 0])))))

(camera :fov 60 :position [0 2 5])
(light :type directional :direction [-1 -1 -1])
(light :type point :position [2 3 0] :color [1 0.8 0.6])

(def gbuf (pass :outputs [albedo normal roughmetal depth]))
(def ao (ssao gbuf.depth gbuf.normal))
(def final (compose gbuf.albedo ao :mode multiply))
(output final)
```

### G-buffer access

The `pass` node's `:outputs` kwarg names the G-buffer channels. Individual channels are accessed via dot notation: `gbuf.albedo`, `gbuf.normal`, `gbuf.depth`. Each resolves to a `GpuImage` that downstream compute or output nodes can consume.

## Architecture

### Pipeline overview

```
DSL source
  |
  v
Parser (existing)
  |
  v
IR Graph (existing, extended with Tier::MATERIAL)
  |
  v
Shader Analyzer -----> Pre-pass Extractor
  |                         |
  | (inlineable ops)        | (compute pre-passes)
  v                         v
HLSL Emitter           Compute dispatch (existing)
  |                         |
  v                         v
DXC (HLSL -> SPIR-V)   Texture bindings for shader
  |
  v
PipelineCache (graphics pipelines per material)
  |
  v
Geometry Pass (MRT rendering, grouped by material)
  |
  v
G-Buffer [albedo, normal, roughmetal, depth]
  |
  v
Lighting Pass (fullscreen, per-BRDF variant)
  |
  v
Lit output image -> downstream compute graph
```

### Stage 1: Shader IR Analysis

Walk the `(shader ...)` AST and build a `ShaderIR` — a representation of the shader's vertex, fragment, and BRDF bodies as expression trees. Each sub-expression is classified:

- **Inlineable:** Has a direct HLSL equivalent. Compiles to inline code. Examples: `sin`, `dot`, `noise`, `mix`, `+`, `*`, `step`, `smoothstep`.
- **Pre-pass required:** Needs compute dispatch (multi-pixel access, iterative ops). Examples: `blur`, `levels`, `ssao`. These are extracted and replaced with texture samples.

Classification is driven by a registry: each node op declares whether it has an inline HLSL implementation. Unknown ops inside a shader body are a compile error.

### Stage 2: Pre-Pass Extraction

When a shader body contains an un-inlineable op:

```lisp
(set albedo (blur (noise :scale 4.0) :radius 3))
```

The extractor:
1. Identifies `blur` as non-inlineable.
2. Walks outward to find the largest sub-tree rooted at `blur` that is entirely non-inlineable or feeds only into the non-inlineable op.
3. Extracts `(blur (noise :scale 4.0) :radius 3)` as a standalone compute graph.
4. Allocates a pre-pass render target via `ResourcePool`.
5. Schedules the compute dispatch before the geometry pass.
6. Replaces the sub-tree in the shader IR with a texture sample: `sample(__prepass_0, uv)`.
7. Adds the pre-pass texture as a descriptor binding in the generated fragment shader.

The pre-pass compute graph is evaluated using the existing evaluator — no new compute infrastructure needed.

### Stage 3: HLSL Code Generation

The `HlslEmitter` walks the `ShaderIR` expression tree and emits HLSL source code.

**Fragment shader output:**

```hlsl
struct PSOut {
    float4 albedo    : SV_TARGET0;
    float4 normal    : SV_TARGET1;
    float4 roughmetal : SV_TARGET2;
};
```

The struct is generated from the `-> [...]` output declaration. Field order matches the pass's `:outputs` order.

**Vertex shader:**

```hlsl
struct UBO { float4x4 mvp; float4x4 model; float time; float3 pad; };
[[vk::binding(0, 0)]] ConstantBuffer<UBO> ubo;

struct VSIn  { float3 pos : POSITION; float3 nrm : NORMAL; float2 uv : TEXCOORD0; };
struct VSOut { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; float3 world_pos : TEXCOORD1; };

VSOut main(VSIn v) {
    float3 pos = v.pos;
    float3 normal = v.nrm;
    float2 uv = v.uv;
    float time = ubo.time;
    // --- user vertex body emitted here ---
    // pos.y = pos.y + 0.1 * sin(pos.x * 8.0 + time);
    // --- end user body ---
    VSOut o;
    o.sv = mul(ubo.mvp, float4(pos, 1.0));
    o.normal = normalize(mul((float3x3)ubo.model, normal));
    o.uv = uv;
    o.world_pos = mul(ubo.model, float4(pos, 1.0)).xyz;
    return o;
}
```

User vertex expressions modify `pos`, `normal`, `uv` in-place. The MVP transform and normal transform happen after the user body.

**Fragment shader:**

```hlsl
struct PSIn { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; float3 world_pos : TEXCOORD1; };

// Pre-pass textures (if any)
[[vk::binding(1, 0)]] Texture2D __prepass_0;
[[vk::binding(2, 0)]] SamplerState __sampler_0;

PSOut main(PSIn i) {
    float3 normal = normalize(i.normal);
    float2 uv = i.uv;
    PSOut o;
    // --- user fragment body emitted here ---
    // o.albedo = __prepass_0.Sample(__sampler_0, uv);
    // o.normal = float4(normal * 0.5 + 0.5, 1.0);
    // o.roughmetal = float4(0.7, 0.0, 0, 0);
    // --- end user body ---
    return o;
}
```

**Expression mapping:** DSL expressions map to HLSL:

| DSL | HLSL |
|-----|------|
| `(+ a b)` | `(a + b)` |
| `(* a b)` | `(a * b)` |
| `(sin x)` | `sin(x)` |
| `(dot a b)` | `dot(a, b)` |
| `(mix a b t)` | `lerp(a, b, t)` |
| `(step e x)` | `step(e, x)` |
| `(noise :scale s :octaves n)` | `fbm(world_pos * s, n)` (inline noise function, uses interpolated world position) |
| `(sample tex uv)` | `tex.Sample(sampler, uv)` |
| `(encode normal)` | `float4(normal * 0.5 + 0.5, 1.0)` |
| `(set target expr)` | `o.target = expr;` (fragment) or `target = expr;` (vertex) |
| `[a b c d]` | `float4(a, b, c, d)` |
| `[a b c]` | `float3(a, b, c)` |
| `time` | `ubo.time` (vertex) or `frag_ubo.time` (fragment, via separate fragment UBO) |

Inline procedural noise (`fbm`) is emitted as a helper function at the top of the generated shader — a standard gradient noise + fractal sum implementation.

### Stage 4: Deferred Lighting Pass

A fullscreen fragment shader reads the G-buffer and evaluates lighting:

```hlsl
struct LightData {
    float4 position_type;  // xyz = position/direction, w = type (0=dir, 1=point, 2=spot)
    float4 color_intensity; // xyz = color, w = intensity
    float4 spot_params;     // xyz = direction, w = cos(angle)
};

[[vk::binding(0, 0)]] Texture2D gbuf_albedo;
[[vk::binding(1, 0)]] Texture2D gbuf_normal;
[[vk::binding(2, 0)]] Texture2D gbuf_roughmetal;
[[vk::binding(3, 0)]] Texture2D gbuf_depth;
[[vk::binding(4, 0)]] SamplerState samp;

struct LightUBO { LightData lights[16]; int light_count; float3 camera_pos; float4x4 inv_view_proj; };
[[vk::binding(5, 0)]] ConstantBuffer<LightUBO> light_ubo;

float4 main(float4 sv : SV_POSITION, float2 uv : TEXCOORD0) : SV_TARGET {
    float4 albedo = gbuf_albedo.Sample(samp, uv);
    float3 N = gbuf_normal.Sample(samp, uv).xyz * 2.0 - 1.0;
    float4 rm = gbuf_roughmetal.Sample(samp, uv);
    float roughness = rm.x;
    float metallic = rm.y;

    // Reconstruct world position from depth + inverse VP matrix
    float depth = gbuf_depth.Sample(samp, uv).r;
    float4 clip = float4(uv * 2.0 - 1.0, depth, 1.0);
    clip.y = -clip.y; // Vulkan Y-flip
    float4 wp = mul(light_ubo.inv_view_proj, clip);
    float3 world_pos = wp.xyz / wp.w;

    // --- BRDF body (default or custom, emitted per-variant) ---
    float3 result = float3(0, 0, 0);
    // Loop-invariant expressions hoisted here by the emitter
    float3 V = normalize(light_ubo.camera_pos - world_pos);

    for (int i = 0; i < light_ubo.light_count; i++) {
        float3 light_dir = compute_light_dir(light_ubo.lights[i], world_pos);
        float3 light_color = compute_light_color(light_ubo.lights[i], world_pos);
        // Per-light BRDF evaluation
        result += evaluate_brdf(N, light_dir, V, albedo.rgb, roughness, metallic) * light_color;
    }
    // --- end BRDF body ---

    return float4(result, 1.0);
}
```

**Custom BRDFs:** When a material defines `:brdf`, the emitter generates a variant of the lighting shader where the inner-loop body is replaced with the user's BRDF expression. The emitter analyzes which sub-expressions in the BRDF body depend on `light_dir` / `light_color` and hoists the rest above the loop.

**BRDF variant caching:** Lighting shader variants are keyed by the hash of the BRDF expression tree. Materials with identical BRDF bodies share a variant. Materials without a `:brdf` share the default Cook-Torrance variant.

### Stage 5: Geometry Pass Changes

The geometry pass (currently in `geometry_pass.cpp`) changes to support:

- **Multiple render targets:** The framebuffer gets N color attachments matching `:outputs`.
- **Per-material pipelines:** Instead of one hardcoded pipeline, draws are grouped by material. Each material's compiled `VkGraphicsPipeline` is bound before its draws.
- **Material pipeline lookup:** `SceneObject::material_node_id` (currently unused) points to the `MATERIAL`-tier node whose compiled pipeline should be used.
- **Lighting pass dispatch:** After the geometry render pass ends, dispatch the fullscreen lighting pass reading the G-buffer and writing the final lit image. This lit image is what gets stored in `ResourcePool` as the pass output.

### New IR Tier: MATERIAL

`Tier::MATERIAL` is added between `GPU` and `SCENE` in the enum. Material nodes are evaluated before scene nodes — they compile shader source, invoke DXC, and cache the resulting pipeline. They don't produce images; they produce pipeline handles referenced by scene objects.

Evaluation order becomes: `CPU` -> `GPU` (compute) -> `MATERIAL` (shader compilation) -> `SCENE` (collection) -> `RENDER` (geometry + lighting pass).

### Built-in Shader Intrinsics

Operations available inside `(fn ...)` shader bodies:

| Category | Ops |
|----------|-----|
| Arithmetic | `+`, `-`, `*`, `/`, `pow`, `sqrt`, `abs`, `floor`, `ceil`, `fract`, `mod`, `clamp`, `min`, `max` |
| Trigonometry | `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2` |
| Vector | `dot`, `cross`, `normalize`, `length`, `reflect`, `refract`, `mix`, `step`, `smoothstep` |
| Procedural | `noise`, `fbm`, `voronoi` |
| Texture | `sample` |
| Utility | `encode`, `decode` |
| Assignment | `set` |
| Globals | `time` |

### G-Buffer Contract

All materials used in a single `(pass)` must declare the same fragment output signature. The pass's `:outputs` kwarg defines the canonical channel list. Validation happens at IR analysis time:

- If a material's `-> [...]` output list doesn't match the pass's `:outputs`, emit a diagnostic error with both signatures.
- The `depth` channel is always implicit (hardware depth buffer) and should not appear in the fragment output declaration — it appears only in the pass's `:outputs` for downstream access.

### Error Handling

| Condition | Behavior |
|-----------|----------|
| Un-inlineable op inside shader body | Auto-extract as pre-pass |
| Unknown op inside shader body | Compile error with diagnostic |
| G-buffer signature mismatch | Compile error listing expected vs actual |
| Shader compilation failure (DXC) | Surface DXC error as a diagnostic, skip material |
| No materials in pass | Fall back to hardcoded `scene_basic` shaders (backwards compat) |
| No lights in scene | Emit ambient-only lighting (albedo * 0.1) |
| No `:brdf` on material | Use default Cook-Torrance GGX |
| No `:vertex` on material | Use standard MVP-only vertex shader |
| No `:fragment` on material | Use default white albedo output |

### File Map

| Area | Action | Files |
|------|--------|-------|
| Shader IR | Create | `src/shader/shader_ir.h` — expression tree types for shader bodies |
| Shader analysis | Create | `src/shader/shader_analyzer.h`, `shader_analyzer.cpp` — classify ops, validate, build ShaderIR |
| Pre-pass extraction | Create | `src/shader/prepass_extractor.h`, `prepass_extractor.cpp` — extract compute pre-passes |
| HLSL emitter | Create | `src/shader/hlsl_emitter.h`, `hlsl_emitter.cpp` — ShaderIR -> HLSL source code |
| BRDF emitter | Create | `src/shader/brdf_emitter.h`, `brdf_emitter.cpp` — custom BRDF -> lighting shader variant |
| Inline noise | Create | `src/shader/noise_hlsl.h` — inline HLSL noise/fbm/voronoi source as string constants |
| Deferred lighting | Create | `src/scene/lighting_pass.h`, `lighting_pass.cpp` — fullscreen lighting dispatch |
| Default lighting shader | Create | `shaders/deferred_default.frag.hlsl` — Cook-Torrance GGX default |
| Fullscreen vertex | Create | `shaders/fullscreen.vert.hlsl` — passthrough quad vertex shader |
| IR tiers | Modify | `src/ir/node.h` — add `Tier::MATERIAL` |
| IR graph | Modify | `src/ir/ir_graph.cpp` — lower `shader` to `MATERIAL` tier |
| Types | Modify | `include/joon/types.h` — add `Type::MATERIAL` |
| Pipeline cache | Modify | `src/vulkan/pipeline_cache.h`, `.cpp` — accept generated HLSL source (not just filenames) |
| Render pass | Modify | `src/vulkan/render_pass.h`, `.cpp` — support N color attachments |
| Resource pool | Modify | `src/vulkan/resource_pool.h`, `.cpp` — MRT allocation helpers |
| Geometry pass | Modify | `src/scene/geometry_pass.cpp` — MRT framebuffer, per-material pipeline dispatch, lighting pass |
| Scene executors | Modify | `src/scene/scene_executors.cpp` — material executor (compile shader, cache pipeline) |
| Scene types | Modify | `include/joon/scene.h` — light UBO struct |
| Evaluator | Modify | `src/evaluator.cpp` — MATERIAL tier evaluation before SCENE |
| Interpreter | Modify | `src/interpreter/interpreter.cpp` — MATERIAL walk phase |
| Node registry | Modify | `src/nodes/node_registry.h` — EvalContext gains material registry |
| GUI app | Modify | `gui/app.cpp` — update default DSL to use shader materials |
| Tests | Create | `tests/test_shader_ir.cpp`, `test_hlsl_emitter.cpp`, `test_prepass.cpp`, `test_lighting_pass.cpp`, `test_deferred.cpp` |

### Backwards Compatibility

When a `(pass)` has no materials (no scene objects have `:material`), the geometry pass falls back to the existing hardcoded `scene_basic` shaders. This preserves sub-project 2's behavior for simple scenes without materials.

### Out of Scope

- Transparency / alpha blending (requires forward rendering or OIT — follow-up)
- Shadow mapping
- Post-processing effects as built-in nodes (bloom, tone mapping)
- Shader hot-reload during GUI editing (DXC compilation is fast enough for re-parse-on-edit)
- Texture file loading inside materials (only procedural + pre-pass textures for now)
