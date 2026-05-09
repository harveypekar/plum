# Sponza PBR Shader via DSL BRDF

**Date:** 2026-05-08
**Status:** Draft

## Goal

Add a Cook-Torrance PBR shader to the Sponza scene graph, defined as a `(shader :brdf ...)` node in the Joon DSL. Per-material roughness and metallic values are derived from the OBJ/MTL `Ns` and `Ks` properties and encoded in the G-buffer's unused alpha channels.

## Architecture

The BRDF applies scene-wide via the deferred lighting pass. The geometry pass continues using the built-in `scene_textured` pipeline for all Sponza submeshes (25 materials with albedo + normal textures from the MTL file). No custom fragment shader is needed.

```
MTL file ──► obj_loader extracts Ns/Ks ──► SceneObject.roughness/metallic
                                                    │
Geometry pass: scene_textured.frag ◄────────────────┘
  writes albedo.a = roughness, normal.a = metallic to G-buffer
                                                    │
Lighting pass: BrdfEmitter ◄────────────────────────┘
  extracts roughness/metallic from G-buffer alpha
  executes Cook-Torrance BRDF body
```

## Changes by Layer

### 1. Asset Loading (`obj_loader.h`, `obj_loader.cpp`)

Extend `MaterialInfo`:
```cpp
struct MaterialInfo {
    std::string diffuse_tex;
    std::string normal_tex;
    float roughness = 0.5f;
    float metallic  = 0.0f;
};
```

In `load_obj_with_materials()`, after extracting texture paths, also compute:
```cpp
auto& m = materials[mat_id];
float ns = std::clamp(m.shininess, 0.0f, 1000.0f);
sm.material.roughness = std::clamp(1.0f - std::sqrt(ns / 1000.0f), 0.04f, 1.0f);
float ks_lum = 0.2126f * m.specular[0] + 0.7152f * m.specular[1] + 0.0722f * m.specular[2];
sm.material.metallic = ks_lum > 0.5f ? 1.0f : 0.0f;
```

The `sqrt` mapping produces a perceptually linear roughness curve from the Phong exponent. Metallic is binary-thresholded on specular luminance (OBJ/MTL doesn't express metalness directly).

### 2. Scene Data (`scene.h`)

Add to `SceneObject`:
```cpp
float roughness = 0.5f;
float metallic  = 0.0f;
```

### 3. Scene Executor (`scene_executors.cpp`)

In `exec_mesh()`, when building SceneObjects from SubMeshes, copy the material properties:
```cpp
o.roughness = sm.material.roughness;
o.metallic  = sm.material.metallic;
```

### 4. Geometry Pass (`scene_textured.frag.hlsl`, `geometry_pass.cpp`)

**Fragment shader** — add push constant block and write alpha channels:
```hlsl
[[vk::push_constant]]
struct { float roughness; float metallic; } pc;

// In main():
output.albedo  = float4(tex_color.rgb, pc.roughness);
output.normal  = float4(encode(normal), pc.metallic);
```

**C++ side** — define push constant struct for textured pipeline:
```cpp
struct TexturedPC {
    float roughness;
    float metallic;
};
```

Before each textured draw call, push the object's roughness/metallic:
```cpp
TexturedPC tpc{ obj.roughness, obj.metallic };
vkCmdPushConstants(cmd, cur_gp->layout, VK_SHADER_STAGE_FRAGMENT_BIT,
                   0, sizeof(TexturedPC), &tpc);
```

The textured pipeline layout needs updating to include the push constant range.

### 5. BRDF Emitter (`brdf_emitter.cpp`)

After sampling the G-buffer, inject roughness/metallic as local variables:
```hlsl
float roughness = gbuf_albedo.Sample(samp, i.uv).a;
float metallic  = gbuf_normal.Sample(samp, i.uv).a;
```

These are available alongside the existing `normal`, `light_dir`, `view_dir`, `albedo` in the BRDF body. No change to the BRDF function signature or DSL parser needed.

Also change `albedo` from float4 to float3 (from `.rgb`) since `.a` is now roughness:
```hlsl
float3 albedo = gbuf_albedo.Sample(samp, i.uv).rgb;
```

Note: this changes `albedo` from `float4` to `float3` in the BRDF. Existing BRDFs that reference `albedo.a` or treat it as float4 would need updating. The existing toon BRDF test uses `(* albedo ...)` which works with float3.

### 6. DSL Scene Graph (`gui/app.cpp`)

The Sponza example becomes:
```lisp
(def pbr (shader
  :brdf (fn [normal light_dir view_dir albedo]
    (set n_dot_l (max (dot normal light_dir) 0.0))
    (set h (normalize (+ light_dir view_dir)))
    (set n_dot_h (max (dot normal h) 0.0))
    (set n_dot_v (max (dot normal view_dir) 0.001))
    (set a2 (* roughness roughness))
    (set d (/ a2 (* 3.14159
      (pow (+ (* n_dot_h n_dot_h (- a2 1.0)) 1.0) 2.0))))
    (set f0 (lerp [0.04 0.04 0.04] albedo metallic))
    (set f (+ f0 (* (- 1.0 f0) (pow (- 1.0 (max (dot h view_dir) 0.0)) 5.0))))
    (set k (/ (* (+ roughness 1.0) (+ roughness 1.0)) 8.0))
    (set g1 (/ n_dot_v (+ (* n_dot_v (- 1.0 k)) k)))
    (set g2 (/ n_dot_l (+ (* n_dot_l (- 1.0 k)) k)))
    (set spec (/ (* d f g1 g2) (+ (* 4.0 n_dot_v n_dot_l) 0.001)))
    (set diffuse (* (/ (- 1.0 f) 3.14159) (- 1.0 metallic) albedo))
    (* (+ diffuse spec) n_dot_l))))

(def sponza (mesh "assets/scenes/sponza/sponza.obj"))
(def cam (camera :fov 75 :position [-500 400 0] :target [500 400 0] :near 1 :far 5000))
(def sun (light :direction [-0.5 -1 -0.3] :intensity 0.7))
(def gbuf (pass))
(output gbuf)
```

## DSL Compatibility Risks

1. **Variadic `*`**: Expressions like `(* n_dot_h n_dot_h (- a2 1.0))` require 3+ arguments to `*`. If the parser only supports binary operators, these need to be nested: `(* (* n_dot_h n_dot_h) (- a2 1.0))`. Verify during implementation.

2. **`albedo` type change**: Changing `albedo` from float4 to float3 in the BRDF is a breaking change for any existing BRDF that uses `albedo.a`. The toon BRDF test should be checked and updated.

3. **`lerp` as direct name**: Using `lerp` bypasses the `mix→lerp` rename in the HLSL emitter. Both work; `lerp` is preferred since it matches HLSL natively.

## Testing

1. **Unit test**: Add a test in `test_deferred.cpp` that defines the PBR BRDF shader and verifies it compiles to valid HLSL via the emitter.

2. **OBJ loader test**: Verify `load_obj_with_materials()` extracts roughness/metallic from a test MTL file with known Ns/Ks values.

3. **Visual verification**: Build and run the GUI, load the Sponza scene. Compare the PBR-lit result against the previous Lambert shading — stone should look matte, metal fixtures should have specular highlights, fabric should be soft.

## Out of Scope

- Per-pixel roughness/metallic texture maps (would require different asset format)
- Image-based lighting (IBL) / environment maps
- Ambient occlusion
- Multiple BRDFs per scene (current architecture uses a single BRDF for the entire lighting pass)
- glTF Sponza asset with PBR textures
