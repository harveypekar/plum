# Sponza PBR Shader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Cook-Torrance PBR shader to the Sponza scene graph via a DSL `(shader :brdf ...)` node, with per-material roughness/metallic derived from MTL properties.

**Architecture:** The OBJ loader extracts Ns/Ks from MTL files into roughness/metallic values stored on each SceneObject. The textured geometry pass encodes these in the G-buffer alpha channels via push constants. The BRDF emitter injects them as local variables in the deferred lighting shader. A Cook-Torrance BRDF defined in the DSL uses these values for physically-based lighting.

**Tech Stack:** C++20, Vulkan, HLSL (compiled via DXC to SPIR-V), tinyobjloader, Catch2

**Worktree:** `cd /mnt/d/prg/plum-joon-sponza-pbr` (branch `joon-sponza-pbr`)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/scene/obj_loader.h` | Add roughness/metallic to `MaterialInfo` |
| Modify | `src/scene/obj_loader.cpp` | Extract Ns/Ks from MTL, compute roughness/metallic |
| Modify | `include/joon/scene.h` | Add roughness/metallic to `SceneObject` |
| Modify | `src/scene/scene_executors.cpp` | Copy material roughness/metallic to SceneObject |
| Modify | `shaders/scene_textured.frag.hlsl` | Accept push constants, write roughness/metallic to G-buffer alpha |
| Modify | `src/vulkan/pipeline_cache.h` | Add push_constant_size param to `get_graphics_textured` |
| Modify | `src/vulkan/pipeline_cache.cpp` | Wire push constant range into textured pipeline layout |
| Modify | `src/scene/geometry_pass.cpp` | Push roughness/metallic per-object for textured draws |
| Modify | `src/shader/brdf_emitter.cpp` | Inject roughness/metallic from G-buffer alpha; change albedo to float3 |
| Modify | `gui/app.cpp` | Add PBR BRDF to Sponza graph entry |
| Modify | `tests/test_obj_loader.cpp` | Test roughness/metallic extraction from MTL |
| Modify | `tests/test_hlsl_emitter.cpp` | Test BRDF emitter injects roughness/metallic |
| Modify | `tests/test_deferred.cpp` | Update toon BRDF test for float3 albedo; add PBR BRDF compile test |

All paths are relative to `projects/joon/`.

---

### Task 1: OBJ Loader — Extract Roughness/Metallic from MTL

**Files:**
- Modify: `src/scene/obj_loader.h:11-14`
- Modify: `src/scene/obj_loader.cpp:149-161`
- Modify: `tests/test_obj_loader.cpp`

- [ ] **Step 1: Write failing test for roughness/metallic extraction**

In `tests/test_obj_loader.cpp`, add a test that creates a temp OBJ+MTL with known Ns/Ks values and verifies `load_obj_with_materials()` returns correct roughness/metallic on the resulting SubMesh.

```cpp
#include <fstream>
#include <filesystem>

TEST_CASE("MTL roughness/metallic extraction", "[obj]") {
    namespace fs = std::filesystem;
    auto dir = fs::temp_directory_path() / "joon_test_mtl";
    fs::create_directories(dir);

    // Ns=250 → roughness ≈ 1-sqrt(0.25) = 0.5
    // Ks=(0.8,0.8,0.8) → luminance≈0.8 > 0.5 → metallic=1.0
    {
        std::ofstream f(dir / "test.mtl");
        f << "newmtl shiny_metal\n"
          << "Ns 250.0\n"
          << "Ks 0.8 0.8 0.8\n"
          << "map_Kd dummy.tga\n";
    }
    {
        std::ofstream f(dir / "test.obj");
        f << "mtllib test.mtl\n"
          << "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
          << "vn 0 0 1\n"
          << "usemtl shiny_metal\n"
          << "f 1//1 2//1 3//1\n";
    }

    auto submeshes = load_obj_with_materials((dir / "test.obj").string());
    REQUIRE(submeshes.size() == 1);
    CHECK(submeshes[0].material.roughness == Approx(0.5f).margin(0.01f));
    CHECK(submeshes[0].material.metallic == Approx(1.0f));

    fs::remove_all(dir);
}

TEST_CASE("MTL defaults when no Ns/Ks", "[obj]") {
    namespace fs = std::filesystem;
    auto dir = fs::temp_directory_path() / "joon_test_mtl2";
    fs::create_directories(dir);

    {
        std::ofstream f(dir / "test.mtl");
        f << "newmtl plain\n";
    }
    {
        std::ofstream f(dir / "test.obj");
        f << "mtllib test.mtl\n"
          << "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
          << "vn 0 0 1\n"
          << "usemtl plain\n"
          << "f 1//1 2//1 3//1\n";
    }

    auto submeshes = load_obj_with_materials((dir / "test.obj").string());
    REQUIRE(submeshes.size() == 1);
    // tinyobjloader defaults: shininess=0.0, specular=[0,0,0]
    // roughness = clamp(1.0 - sqrt(0/1000), 0.04, 1.0) = 1.0
    // metallic = 0.0 (luminance 0 < 0.5)
    CHECK(submeshes[0].material.roughness == Approx(1.0f));
    CHECK(submeshes[0].material.metallic == Approx(0.0f));

    fs::remove_all(dir);
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
premake5 gmake2 && make config=debug joon-tests -j$(nproc) 2>&1 | tail -5
./build/bin/Debug/joon-tests "[obj]" -v 2>&1 | tail -20
```

Expected: compilation error — `MaterialInfo` has no member `roughness`.

- [ ] **Step 3: Add roughness/metallic to MaterialInfo**

In `src/scene/obj_loader.h`, extend the struct:

```cpp
struct MaterialInfo {
    std::string diffuse_tex;
    std::string normal_tex;
    float roughness = 0.5f;
    float metallic  = 0.0f;
};
```

- [ ] **Step 4: Extract Ns/Ks in load_obj_with_materials**

In `src/scene/obj_loader.cpp`, add `<algorithm>` and `<cmath>` to includes. Inside the `for (auto& [mat_id, mesh] : meshes_by_mat)` loop, after the existing texture extraction block (lines 152-159), add the roughness/metallic computation:

```cpp
        if (mat_id >= 0 && mat_id < static_cast<int>(materials.size())) {
            auto& m = materials[mat_id];
            if (!m.diffuse_texname.empty())
                sm.material.diffuse_tex = mtl_dir + m.diffuse_texname;
            if (!m.displacement_texname.empty())
                sm.material.normal_tex = mtl_dir + m.displacement_texname;
            else if (!m.bump_texname.empty())
                sm.material.normal_tex = mtl_dir + m.bump_texname;

            float ns = std::clamp(m.shininess, 0.0f, 1000.0f);
            sm.material.roughness = std::clamp(
                1.0f - std::sqrt(ns / 1000.0f), 0.04f, 1.0f);
            float ks_lum = 0.2126f * m.specular[0]
                         + 0.7152f * m.specular[1]
                         + 0.0722f * m.specular[2];
            sm.material.metallic = ks_lum > 0.5f ? 1.0f : 0.0f;
        }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
make config=debug joon-tests -j$(nproc) 2>&1 | tail -5
./build/bin/Debug/joon-tests "[obj]" -v
```

Expected: all `[obj]` tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr
git add projects/joon/src/scene/obj_loader.h projects/joon/src/scene/obj_loader.cpp projects/joon/tests/test_obj_loader.cpp
git commit --author="Claude <noreply@anthropic.com>" -m "feat(joon): extract roughness/metallic from MTL Ns/Ks properties"
```

---

### Task 2: Scene Data — Add Roughness/Metallic to SceneObject

**Files:**
- Modify: `include/joon/scene.h:21-29`
- Modify: `src/scene/scene_executors.cpp:85-101`

- [ ] **Step 1: Add fields to SceneObject**

In `include/joon/scene.h`, add two fields after `normal_texture`:

```cpp
struct SceneObject {
    Mesh mesh;
    vec3 position{0, 0, 0};
    vec3 rotation{0, 0, 0};   // Euler XYZ, radians
    vec3 scale{1, 1, 1};
    uint32_t material_node_id = UINT32_MAX;
    GpuImage* albedo_texture = nullptr;
    GpuImage* normal_texture = nullptr;
    float roughness = 0.5f;
    float metallic  = 0.0f;
};
```

- [ ] **Step 2: Copy material properties in exec_mesh**

In `src/scene/scene_executors.cpp`, inside the `exec_mesh` function's submesh loop (after line 96 where `o.normal_texture` is set), add:

```cpp
            o.roughness = sm.material.roughness;
            o.metallic  = sm.material.metallic;
```

The full block becomes:

```cpp
        for (auto& sm : submeshes) {
            SceneObject o;
            o.mesh = std::move(sm.mesh);
            o.position = pos;
            o.rotation = rot;
            o.material_node_id = mat_id;
            if (!sm.material.diffuse_tex.empty())
                o.albedo_texture = ctx.texture_cache->load(sm.material.diffuse_tex);
            if (!sm.material.normal_tex.empty())
                o.normal_texture = ctx.texture_cache->load(sm.material.normal_tex);
            if (!o.albedo_texture)
                o.albedo_texture = ctx.texture_cache->default_albedo();
            if (!o.normal_texture)
                o.normal_texture = ctx.texture_cache->default_normal();
            o.roughness = sm.material.roughness;
            o.metallic  = sm.material.metallic;
            ctx.scene.add_object(std::move(o));
        }
```

- [ ] **Step 3: Verify build succeeds**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
make config=debug joon-tests -j$(nproc) 2>&1 | tail -5
./build/bin/Debug/joon-tests -v 2>&1 | tail -10
```

Expected: build succeeds, all existing tests pass (roughness/metallic fields are purely additive).

- [ ] **Step 4: Commit**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr
git add projects/joon/include/joon/scene.h projects/joon/src/scene/scene_executors.cpp
git commit --author="Claude <noreply@anthropic.com>" -m "feat(joon): add roughness/metallic fields to SceneObject"
```

---

### Task 3: Textured Pipeline — Push Constants for Roughness/Metallic

**Files:**
- Modify: `shaders/scene_textured.frag.hlsl`
- Modify: `src/vulkan/pipeline_cache.h:62-64`
- Modify: `src/vulkan/pipeline_cache.cpp:330-403`
- Modify: `src/scene/geometry_pass.cpp:63-67,128-147,175`

- [ ] **Step 1: Add push constant block to the textured fragment shader**

Replace the entire content of `shaders/scene_textured.frag.hlsl`:

```hlsl
[[vk::binding(1, 0)]] Texture2D albedo_tex;
[[vk::binding(2, 0)]] SamplerState samp;
[[vk::binding(3, 0)]] Texture2D normal_tex;

[[vk::push_constant]]
struct PushConstants {
    float roughness;
    float metallic;
} pc;

struct PSIn {
    float4 sv        : SV_POSITION;
    float3 normal    : NORMAL;
    float2 uv        : TEXCOORD0;
    float3 world_pos : TEXCOORD1;
};

struct PSOut {
    float4 albedo     : SV_TARGET0;
    float4 normal_out : SV_TARGET1;
};

PSOut main(PSIn i) {
    PSOut o;
    float4 tex_color = albedo_tex.Sample(samp, i.uv);
    o.albedo = float4(tex_color.rgb, pc.roughness);

    float3 N = normalize(i.normal);

    float3 dp1 = ddx(i.world_pos);
    float3 dp2 = ddy(i.world_pos);
    float2 duv1 = ddx(i.uv);
    float2 duv2 = ddy(i.uv);

    float det = duv1.x * duv2.y - duv1.y * duv2.x;
    float3 T = normalize((dp1 * duv2.y - dp2 * duv1.y) * sign(det));
    float3 B = normalize(cross(N, T)) * sign(det);

    float3 ts = normal_tex.Sample(samp, i.uv).xyz * 2.0 - 1.0;
    float3 mapped = normalize(T * ts.x + B * ts.y + N * ts.z);

    o.normal_out = float4(mapped * 0.5 + 0.5, pc.metallic);
    return o;
}
```

- [ ] **Step 2: Add push_constant_size param to get_graphics_textured**

In `src/vulkan/pipeline_cache.h`, change the signature:

```cpp
    const GraphicsPipeline& get_graphics_textured(const std::string& name,
                                                   VkRenderPass render_pass,
                                                   uint32_t num_color_attachments = 2,
                                                   uint32_t push_constant_size = 0);
```

- [ ] **Step 3: Wire push constant range in get_graphics_textured implementation**

In `src/vulkan/pipeline_cache.cpp`, update `get_graphics_textured`:

1. Add `push_constant_size` to the cache key (line ~333):

```cpp
    std::string key = "tex_" + name + ":" +
                      std::to_string(reinterpret_cast<uintptr_t>(render_pass)) +
                      ":" + std::to_string(num_color_attachments) +
                      ":" + std::to_string(push_constant_size);
```

2. Add push constant range to pipeline layout (replace lines 389-396):

```cpp
    VkPipelineLayoutCreateInfo layout_info{};
    layout_info.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    layout_info.setLayoutCount = 1;
    layout_info.pSetLayouts = &p.desc_layout;

    VkPushConstantRange push_range{};
    if (push_constant_size > 0) {
        push_range.stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;
        push_range.offset = 0;
        push_range.size = push_constant_size;
        layout_info.pushConstantRangeCount = 1;
        layout_info.pPushConstantRanges = &push_range;
    }
    if (vkCreatePipelineLayout(m_device.device, &layout_info, nullptr,
                               &p.layout) != VK_SUCCESS)
        throw std::runtime_error(
            "graphics_textured: vkCreatePipelineLayout failed");
```

- [ ] **Step 4: Push roughness/metallic per-object in geometry pass**

In `src/scene/geometry_pass.cpp`:

1. Add a struct after `PushLight` (around line 24):

```cpp
struct TexturedPC {
    float roughness;
    float metallic;
};
```

2. Change the `get_graphics_textured` call (line ~67) to pass push constant size:

```cpp
    if (has_textures)
        tex_gp = &ctx.pipelines.get_graphics_textured(
            "scene_textured", rp.pass, num_color, sizeof(TexturedPC));
```

3. Add push constants for textured objects. After the pipeline-bind block (after line ~147), add a push for textured objects. Replace the entire pipeline-bind-and-push-constants block:

```cpp
        if (cur_gp->pipeline != bound_pipeline) {
            vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, cur_gp->pipeline);
            bound_pipeline = cur_gp->pipeline;
            if (cur_gp == &gp)
                vkCmdPushConstants(cmd, gp.layout, VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(pc), &pc);
        }

        if (use_textured) {
            TexturedPC tpc{ obj.roughness, obj.metallic };
            vkCmdPushConstants(cmd, cur_gp->layout, VK_SHADER_STAGE_FRAGMENT_BIT,
                               0, sizeof(TexturedPC), &tpc);
        }
```

Note: the textured push constant is per-object (not per-pipeline-bind), because each submesh has different roughness/metallic.

- [ ] **Step 5: Delete stale .spv to force recompile**

```bash
rm -f /mnt/d/prg/plum-joon-sponza-pbr/projects/joon/shaders/scene_textured.frag.spv
```

- [ ] **Step 6: Build and run all tests**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
premake5 gmake2 && make config=debug joon-tests -j$(nproc) 2>&1 | tail -10
./build/bin/Debug/joon-tests -v 2>&1 | tail -20
```

Expected: build succeeds, all tests pass. The textured pipeline now encodes roughness/metallic but existing tests don't use textured objects so they're unaffected.

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr
git add projects/joon/shaders/scene_textured.frag.hlsl \
        projects/joon/src/vulkan/pipeline_cache.h \
        projects/joon/src/vulkan/pipeline_cache.cpp \
        projects/joon/src/scene/geometry_pass.cpp
git commit --author="Claude <noreply@anthropic.com>" -m "feat(joon): encode roughness/metallic in G-buffer alpha via push constants"
```

---

### Task 4: BRDF Emitter — Inject Roughness/Metallic Variables

**Files:**
- Modify: `src/shader/brdf_emitter.cpp:7-49`
- Modify: `tests/test_hlsl_emitter.cpp`
- Modify: `tests/test_deferred.cpp:41-67`

- [ ] **Step 1: Write failing test for roughness/metallic in emitted BRDF shader**

In `tests/test_hlsl_emitter.cpp`, add:

```cpp
#include "shader/brdf_emitter.h"

TEST_CASE("BRDF emitter injects roughness and metallic", "[shader][brdf]") {
    BrdfEmitter emitter;

    ShaderFnIR brdf;
    brdf.params = {"normal", "light_dir", "view_dir", "albedo"};

    // Simple BRDF body: just uses roughness and metallic
    ShaderCall mul_call;
    mul_call.op = "*";
    mul_call.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"roughness"}));
    mul_call.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"metallic"}));
    brdf.body.push_back(std::make_unique<ShaderExpr>(std::move(mul_call)));

    auto hlsl = emitter.emit_lighting_shader(brdf);

    CHECK(hlsl.find("float roughness") != std::string::npos);
    CHECK(hlsl.find("float metallic") != std::string::npos);
    CHECK(hlsl.find("float3 albedo") != std::string::npos);
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
make config=debug joon-tests -j$(nproc) 2>&1 | tail -5
./build/bin/Debug/joon-tests "BRDF emitter injects roughness and metallic" -v
```

Expected: FAIL — the emitter currently outputs `float4 albedo` not `float3 albedo`, and has no `roughness`/`metallic` variables.

- [ ] **Step 3: Update brdf_emitter.cpp**

Replace the `emit_lighting_shader` method body in `src/shader/brdf_emitter.cpp`:

```cpp
std::string BrdfEmitter::emit_lighting_shader(const ShaderFnIR& brdf) {
    HlslEmitter hlsl;
    std::ostringstream ss;

    ss << "[[vk::binding(0, 0)]] Texture2D gbuf_albedo;\n";
    ss << "[[vk::binding(1, 0)]] SamplerState samp;\n";
    ss << "[[vk::binding(3, 0)]] Texture2D gbuf_normal;\n\n";

    ss << "struct LightData { float4 position_type; float4 color_intensity; float4 spot_params; };\n";
    ss << "struct LightUBO { LightData lights[16]; int light_count; float3 camera_pos; float4x4 inv_view_proj; };\n";
    ss << "[[vk::binding(2, 0)]] ConstantBuffer<LightUBO> light_ubo;\n\n";

    ss << "struct PSIn { float4 sv : SV_POSITION; float2 uv : TEXCOORD0; };\n\n";

    ss << "float4 main(PSIn i) : SV_TARGET {\n";
    ss << "    float4 albedo_raw = gbuf_albedo.Sample(samp, i.uv);\n";
    ss << "    if (albedo_raw.r < 0.001 && albedo_raw.g < 0.001 && albedo_raw.b < 0.001) discard;\n\n";

    ss << "    float3 albedo = albedo_raw.rgb;\n";
    ss << "    float roughness = albedo_raw.a;\n";
    ss << "    float metallic = gbuf_normal.Sample(samp, i.uv).a;\n\n";

    ss << "    float3 normal = gbuf_normal.Sample(samp, i.uv).xyz * 2.0 - 1.0;\n";
    ss << "    float3 view_dir = normalize(light_ubo.camera_pos);\n";
    ss << "    float3 result = float3(0, 0, 0);\n\n";

    ss << "    for (int li = 0; li < light_ubo.light_count; li++) {\n";
    ss << "        float3 light_dir = -normalize(light_ubo.lights[li].position_type.xyz);\n";
    ss << "        float3 light_color = light_ubo.lights[li].color_intensity.xyz;\n";

    for (auto& stmt : brdf.body) {
        std::string expr_str = hlsl.emit_expr(*stmt);
        if (auto* assign = std::get_if<ShaderAssign>(stmt.get())) {
            ss << "        " << expr_str << ";\n";
        } else {
            ss << "        result += (" << expr_str << ").xyz * light_color;\n";
        }
    }

    ss << "    }\n\n";
    ss << "    return float4(result, 1.0);\n";
    ss << "}\n";

    return ss.str();
}
```

Key changes from the original:
- `albedo` is now `float3` (from `.rgb`), with a separate `albedo_raw` for the full sample
- `roughness` extracted from `albedo_raw.a`
- `metallic` extracted from `gbuf_normal` `.a`
- Discard check uses RGB near zero (`.a` is now roughness, not opacity; G-buffer clears alpha to 1.0)

- [ ] **Step 4: Update the toon BRDF test**

In `tests/test_deferred.cpp`, the toon BRDF test at line 41 uses `(* albedo ...)`. Since `albedo` is now float3 in the BRDF, but `step` returns a scalar, `(* albedo (step ...))` produces float3 which is fine — the emitter wraps the result in `.xyz`. No code change needed, but verify it passes.

- [ ] **Step 5: Run tests**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
make config=debug joon-tests -j$(nproc) 2>&1 | tail -5
./build/bin/Debug/joon-tests "[shader]" -v 2>&1 | tail -20
./build/bin/Debug/joon-tests "[brdf]" -v 2>&1 | tail -20
```

Expected: all tests PASS including the new BRDF emitter test and existing toon BRDF test.

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr
git add projects/joon/src/shader/brdf_emitter.cpp \
        projects/joon/tests/test_hlsl_emitter.cpp \
        projects/joon/tests/test_deferred.cpp
git commit --author="Claude <noreply@anthropic.com>" -m "feat(joon): inject roughness/metallic into BRDF lighting shader"
```

---

### Task 5: Cook-Torrance BRDF in DSL — Sponza Scene Graph

**Files:**
- Modify: `gui/app.cpp:41-47`
- Modify: `tests/test_deferred.cpp`

- [ ] **Step 1: Write a test that compiles the PBR BRDF**

In `tests/test_deferred.cpp`, add:

```cpp
TEST_CASE("PBR Cook-Torrance BRDF compiles and produces lit output", "[shader][brdf][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def pbr (shader
          :brdf (fn [normal light_dir view_dir albedo]
            (set n_dot_l (max (dot normal light_dir) 0.0))
            (set h (normalize (+ light_dir view_dir)))
            (set n_dot_h (max (dot normal h) 0.0))
            (set n_dot_v (max (dot normal view_dir) 0.001))
            (set a2 (* roughness roughness))
            (set denom_inner (+ (* (* n_dot_h n_dot_h) (- a2 1.0)) 1.0))
            (set d (/ a2 (* 3.14159 (* denom_inner denom_inner))))
            (set f0 (lerp [0.04 0.04 0.04] albedo metallic))
            (set h_dot_v (max (dot h view_dir) 0.0))
            (set f (+ f0 (* (- 1.0 f0) (pow (- 1.0 h_dot_v) 5.0))))
            (set r1 (+ roughness 1.0))
            (set k (/ (* r1 r1) 8.0))
            (set g1 (/ n_dot_v (+ (* n_dot_v (- 1.0 k)) k)))
            (set g2 (/ n_dot_l (+ (* n_dot_l (- 1.0 k)) k)))
            (set spec (/ (* (* d f) (* g1 g2)) (+ (* (* 4.0 n_dot_v) n_dot_l) 0.001)))
            (set kd (* (- 1.0 metallic) (/ (- 1.0 f) 3.14159)))
            (set diffuse (* kd albedo))
            (* (+ diffuse spec) n_dot_l))
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [0.5 0.5 0.5 1]))))
        (def c (cube :material pbr))
        (def cam (camera))
        (def l (light))
        (def gbuf (pass))
        (output gbuf)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);
    int lit = 0;
    for (size_t i = 0; i < px.size(); i += 4)
        if (px[i] > 0.01f) ++lit;
    CHECK(lit > 50);
}
```

Note: all `*` operations use exactly 2 arguments (nested for 3+ operands) since the HLSL emitter's `BINARY_OPS` check requires `args.size() == 2`. For example, `(* a b c)` becomes `(* (* a b) c)`.

- [ ] **Step 2: Run test to verify it compiles and passes**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
make config=debug joon-tests -j$(nproc) 2>&1 | tail -5
./build/bin/Debug/joon-tests "PBR Cook-Torrance" -v 2>&1 | tail -20
```

Expected: PASS — the shader compiles via DXC and produces lit pixels.

- [ ] **Step 3: Update the Sponza graph entry in app.cpp**

In `gui/app.cpp`, replace the Sponza entry (lines 41-47):

```cpp
        {"Sponza", R"(; Sponza atrium with PBR lighting
(def pbr (shader
  :brdf (fn [normal light_dir view_dir albedo]
    (set n_dot_l (max (dot normal light_dir) 0.0))
    (set h (normalize (+ light_dir view_dir)))
    (set n_dot_h (max (dot normal h) 0.0))
    (set n_dot_v (max (dot normal view_dir) 0.001))
    (set a2 (* roughness roughness))
    (set denom_inner (+ (* (* n_dot_h n_dot_h) (- a2 1.0)) 1.0))
    (set d (/ a2 (* 3.14159 (* denom_inner denom_inner))))
    (set f0 (lerp [0.04 0.04 0.04] albedo metallic))
    (set h_dot_v (max (dot h view_dir) 0.0))
    (set f (+ f0 (* (- 1.0 f0) (pow (- 1.0 h_dot_v) 5.0))))
    (set r1 (+ roughness 1.0))
    (set k (/ (* r1 r1) 8.0))
    (set g1 (/ n_dot_v (+ (* n_dot_v (- 1.0 k)) k)))
    (set g2 (/ n_dot_l (+ (* n_dot_l (- 1.0 k)) k)))
    (set spec (/ (* (* d f) (* g1 g2)) (+ (* (* 4.0 n_dot_v) n_dot_l) 0.001)))
    (set kd (* (- 1.0 metallic) (/ (- 1.0 f) 3.14159)))
    (set diffuse (* kd albedo))
    (* (+ diffuse spec) n_dot_l))))

(def sponza (mesh "assets/scenes/sponza/sponza.obj"))
(def cam (camera :fov 75 :position [-500 400 0] :target [500 400 0] :near 1 :far 5000))
(def sun (light :direction [-0.5 -1 -0.3] :intensity 0.7))
(def gbuf (pass))
(output gbuf)
)"},
```

- [ ] **Step 4: Build and run full test suite**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
make config=debug joon-tests -j$(nproc) 2>&1 | tail -5
./build/bin/Debug/joon-tests -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 5: Build the GUI and visually verify Sponza**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr/projects/joon
make config=debug joon-gui -j$(nproc) 2>&1 | tail -5
# Launch the GUI on Windows:
# ./build/bin/Debug/joon-gui.exe
# Select the "Sponza" graph from the dropdown
# Verify: stone columns should appear matte, metal fixtures should have specular highlights
```

Check the runtime log for shader compilation errors:
```bash
cat /mnt/d/prg/plum-joon-sponza-pbr/projects/joon/build/bin/Debug/joon-gui.log
```

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/prg/plum-joon-sponza-pbr
git add projects/joon/gui/app.cpp projects/joon/tests/test_deferred.cpp
git commit --author="Claude <noreply@anthropic.com>" -m "feat(joon): add Cook-Torrance PBR BRDF to Sponza scene graph"
```
