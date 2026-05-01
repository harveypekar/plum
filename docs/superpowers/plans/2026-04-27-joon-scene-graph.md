# Joon Scene Graph & Geometry Pass — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a 3D scene graph and a single hardcoded geometry pass to joon. Scenes (meshes, cameras, lights) are described in the DSL, rasterized to a render target via a Vulkan graphics pipeline, and the result feeds back into the existing compute graph as a `GpuImage`.

**Architecture:** Two new IR tiers — `SCENE` (collected, not dispatched: meshes/lights/camera) and `RENDER` (executed once after compute setup: the `(pass ...)` node). Scene-tier executors mutate a `SceneCollection` on `EvalContext` rather than producing images. The `pass` executor allocates color + depth render-target images via an extended `ResourcePool`, builds a `VkRenderPass` and `VkGraphicsPipeline` (cached by `PipelineCache::get_graphics`), records draws for every collected mesh, and transitions outputs to `GENERAL` so downstream compute nodes can sample them. Vertex/fragment shaders are **hardcoded HLSL** for this sub-project; DSL-generated shaders are sub-project 3.

**Tech Stack:** C++20, Vulkan, VMA, HLSL, DXC, Catch2, tinyobjloader (vendored single header).

**Worktree:** `D:/prg/plum-joon-scene-graph` (branch `joon-scene-graph`)

**Branch base:** `main` at `eb38067` (post PR #115 + #118 merge)

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `src/ir/node.h` | Add `Tier::SCENE`, `Tier::RENDER` |
| Modify | `include/joon/types.h` | Add `Type::SCENE_OBJECT`, `Type::LIGHT`, `Type::CAMERA`, `Type::RENDER_TARGET` |
| Modify | `src/ir/ir_graph.cpp` | Lower `cube`/`sphere`/`plane`/`cylinder`/`mesh`/`light`/`camera`/`pass` to correct tier + type |
| Create | `include/joon/scene.h` | `Mesh`, `SceneObject`, `Light`, `Camera`, `SceneCollection` value types |
| Create | `src/scene/scene_collection.cpp` | `SceneCollection::clear()`, `add_object()`, `add_light()`, `set_camera()` |
| Create | `src/scene/primitives.h`, `primitives.cpp` | `gen_cube()`, `gen_sphere()`, `gen_plane()`, `gen_cylinder()` returning `Mesh` |
| Create | `third_party/tinyobjloader/tiny_obj_loader.h` | Vendored single-header OBJ parser (v2.0.0-rc13) |
| Create | `src/scene/obj_loader.h`, `obj_loader.cpp` | `Mesh load_obj(const std::string& path)` wrapper around tinyobjloader |
| Modify | `src/nodes/node_registry.h` | Extend `EvalContext` with `SceneCollection& scene` + helpers |
| Create | `src/scene/scene_executors.h`, `scene_executors.cpp` | Register `cube`/`sphere`/`plane`/`cylinder`/`mesh`/`light`/`camera`/`pass` executors |
| Modify | `src/nodes/node_registry.cpp` | Call `register_scene_nodes()` in `create_default()` |
| Modify | `src/interpreter/interpreter.cpp` | Walk SCENE nodes first to populate `SceneCollection`, then GPU+CPU, then RENDER |
| Modify | `src/vulkan/resource_pool.h`, `resource_pool.cpp` | Add `alloc_render_target(node_id, w, h, format)`, `alloc_depth(node_id, w, h)`, format/usage tracking |
| Create | `src/vulkan/buffer.h`, `buffer.cpp` | `VertexBuffer`, `IndexBuffer` thin wrappers over VMA |
| Create | `src/vulkan/render_pass.h`, `render_pass.cpp` | `RenderPass` (VkRenderPass + framebuffer factory), color+depth attachment setup |
| Modify | `src/vulkan/pipeline_cache.h`, `pipeline_cache.cpp` | Add `GraphicsPipeline` struct + `get_graphics(name, render_pass, vertex_layout)` |
| Create | `shaders/scene_basic.vert.hlsl` | Hardcoded vertex shader — applies MVP, passes normal & uv |
| Create | `shaders/scene_basic.frag.hlsl` | Hardcoded fragment shader — N·L lambert with first directional light |
| Modify | `src/evaluator.cpp` | Allocate descriptor pool slots for uniform buffers; reset `SceneCollection` each `evaluate()` |
| Modify | `premake5.lua` | Add new `src/scene/`, `src/vulkan/buffer.cpp`, `src/vulkan/render_pass.cpp` (already covered by `src/**.cpp` glob — verify only) |
| Create | `tests/test_scene_ir.cpp` | IR tests: scene ops produce SCENE-tier, pass produces RENDER-tier |
| Create | `tests/test_primitives.cpp` | Geometry tests: cube has 24 vertices (per-face normals) / 36 indices, sphere closed manifold |
| Create | `tests/test_obj_loader.cpp` | Embedded OBJ string round-trips through loader |
| Create | `tests/test_scene_collection.cpp` | Scene executors populate collection; eval clears between runs |
| Create | `tests/test_geometry_pass.cpp` | Full GPU integration: scene + pass renders non-clear pixels; chained compute reads pass output |
| Modify | `gui/app.cpp` | Default DSL becomes a minimal 3D scene (cube + camera + light + pass + levels) |

---

## Conventions for All Tasks

- TDD: write the failing test first, run it, see the exact failure, then implement.
- Each commit message starts with `feat(joon):`, `test(joon):`, or `fix(joon):` and is one imperative sentence.
- After every task: build the full solution and run **all** tests. If anything regresses, stop and fix before moving on.
- Co-author trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  ```
- Build command (Windows, from `projects/joon/build/`):
  ```bash
  "/c/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" \
    Joon.sln -p:Configuration=Debug -p:Platform=x64 -m -v:minimal
  ```
- Test command (from `projects/joon/`):
  ```bash
  ./build/bin/Debug/joon-tests.exe
  ```

---

## Phase 1: IR Tier Extensions

### Task 1: Add SCENE and RENDER tiers

**Files:**
- Modify: `projects/joon/src/ir/node.h`
- Modify: `projects/joon/include/joon/types.h`
- Modify: `projects/joon/src/ir/ir_graph.cpp`
- Create: `projects/joon/tests/test_scene_ir.cpp`

**Step 1: Write the failing test**

```cpp
// tests/test_scene_ir.cpp
#include "catch_amalgamated.hpp"
#include <joon/joon.h>
using namespace joon;

TEST_CASE("Scene ops are tagged with SCENE tier", "[scene][ir]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (cube :scale 1.0)
        (sphere :radius 0.5)
        (light :type directional :direction [0 -1 0])
        (camera :fov 60 :position [0 0 5])
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto& ir = graph.ir();
    int scene_count = 0;
    for (auto& n : ir.nodes)
        if (n.tier == Tier::SCENE) ++scene_count;
    CHECK(scene_count == 4);
}

TEST_CASE("pass op is tagged with RENDER tier", "[scene][ir]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (cube)
        (camera :position [0 0 5])
        (def out (pass scene :outputs [albedo depth]))
        (output out)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto& ir = graph.ir();
    bool found_render = false;
    for (auto& n : ir.nodes)
        if (n.tier == Tier::RENDER) { found_render = true; break; }
    CHECK(found_render);
}
```

**Step 2: Run to verify it fails**

```bash
./build/bin/Debug/joon-tests.exe "[scene][ir]"
```
Expected: compile error — `Tier::SCENE` undefined.

**Step 3: Add tier values**

In `src/ir/node.h`, extend the enum:
```cpp
enum class Tier { CPU, GPU, SCENE, RENDER };
```

In `include/joon/types.h`, extend `Type`:
```cpp
enum class Type {
    /* existing... */
    SCENE_OBJECT,
    LIGHT,
    CAMERA,
    RENDER_TARGET,
};
```

**Step 4: Lower scene/render ops to correct tier**

In `src/ir/ir_graph.cpp` near line 99–104, replace the `if (op == "image" || ...)` block with:
```cpp
static const std::unordered_set<std::string> SCENE_OPS{
    "cube", "sphere", "plane", "cylinder", "mesh", "light", "camera"
};
static const std::unordered_set<std::string> RENDER_OPS{ "pass" };
static const std::unordered_set<std::string> CPU_OPS{ "image", "color", "save" };

if (SCENE_OPS.count(op)) {
    n.tier = Tier::SCENE;
    n.output_type = (op == "light") ? Type::LIGHT
                  : (op == "camera") ? Type::CAMERA
                  : Type::SCENE_OBJECT;
} else if (RENDER_OPS.count(op)) {
    n.tier = Tier::RENDER;
    n.output_type = Type::RENDER_TARGET;
} else if (CPU_OPS.count(op)) {
    n.tier = Tier::CPU;
} else {
    n.tier = Tier::GPU;
}
```

**Step 5: Run tests, verify pass**

```bash
./build/bin/Debug/joon-tests.exe "[scene][ir]"
```
Expected: 2 cases pass.

**Step 6: Run full suite**
```bash
./build/bin/Debug/joon-tests.exe
```
Expected: 38 + 2 = 40 cases pass, no regressions.

**Step 7: Commit**
```bash
git add -A
git commit -m "feat(joon): add SCENE and RENDER IR tiers for scene graph"
```

---

## Phase 2: Scene Value Types & Primitives

### Task 2: Define Mesh / SceneObject / Light / Camera value types

**Files:**
- Create: `projects/joon/include/joon/scene.h`
- Create: `projects/joon/src/scene/scene_collection.cpp`

**Step 1: Write failing test**

```cpp
// tests/test_scene_collection.cpp
#include "catch_amalgamated.hpp"
#include <joon/scene.h>

using namespace joon;

TEST_CASE("SceneCollection clear/add roundtrip", "[scene]") {
    SceneCollection s;
    s.add_object(SceneObject{Mesh{}, vec3{1,0,0}, vec3{0,0,0}, vec3{1,1,1}});
    s.add_light(Light{LightType::Directional, {0,-1,0}, {1,1,1}, 1.0f});
    s.set_camera(Camera{60.f, {0,0,5}, {0,0,0}});

    CHECK(s.objects.size() == 1);
    CHECK(s.lights.size() == 1);
    CHECK(s.camera.fov_deg == Approx(60.f));

    s.clear();
    CHECK(s.objects.empty());
    CHECK(s.lights.empty());
}
```

**Step 2: Run to verify fail** — compile error, header missing.

**Step 3: Create header**

```cpp
// include/joon/scene.h
#pragma once
#include <joon/types.h>
#include <vector>
#include <string>
#include <cstdint>

namespace joon {

struct Vertex {
    vec3 position;
    vec3 normal;
    vec2 uv;
};

struct Mesh {
    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;
};

struct SceneObject {
    Mesh mesh;
    vec3 position{0,0,0};
    vec3 rotation{0,0,0};   // euler XYZ in radians
    vec3 scale{1,1,1};
    // material slot — wired to a node id when fragment shading is per-object.
    // For sub-project 2 this is unused (single hardcoded fragment).
    uint32_t material_node_id = 0;
};

enum class LightType { Directional, Point, Spot };

struct Light {
    LightType type = LightType::Directional;
    vec3 direction{0,-1,0};   // for directional / spot
    vec3 position{0,0,0};     // for point / spot
    vec3 color{1,1,1};
    float intensity = 1.0f;
    float spot_angle_deg = 30.0f;
};

struct Camera {
    float fov_deg = 60.0f;
    vec3 position{0,0,5};
    vec3 target{0,0,0};
    vec3 up{0,1,0};
    float near_z = 0.1f;
    float far_z = 100.0f;
};

struct SceneCollection {
    std::vector<SceneObject> objects;
    std::vector<Light> lights;
    Camera camera;

    void clear();
    void add_object(SceneObject obj);
    void add_light(Light l);
    void set_camera(Camera c);
};

} // namespace joon
```

**Step 4: Implement**

```cpp
// src/scene/scene_collection.cpp
#include <joon/scene.h>

namespace joon {

void SceneCollection::clear() {
    objects.clear();
    lights.clear();
    camera = Camera{};
}
void SceneCollection::add_object(SceneObject o) { objects.push_back(std::move(o)); }
void SceneCollection::add_light(Light l) { lights.push_back(l); }
void SceneCollection::set_camera(Camera c) { camera = c; }

} // namespace joon
```

**Step 5: Run, verify pass.**

**Step 6: Commit**
```bash
git commit -am "feat(joon): add Mesh / SceneObject / Light / Camera value types"
```

---

### Task 3: Procedural primitive generators

**Files:**
- Create: `projects/joon/src/scene/primitives.h`, `primitives.cpp`
- Create: `projects/joon/tests/test_primitives.cpp`

**Step 1: Failing test**

```cpp
// tests/test_primitives.cpp
#include "catch_amalgamated.hpp"
#include "scene/primitives.h"
using namespace joon;

TEST_CASE("Cube has 24 vertices / 36 indices, axis-aligned bounds", "[primitives]") {
    auto m = gen_cube(1.0f);
    CHECK(m.vertices.size() == 24);   // 4 verts/face × 6 faces (so per-face normals)
    CHECK(m.indices.size() == 36);    // 2 tris/face × 3 indices × 6 faces
    float minc = 999, maxc = -999;
    for (auto& v : m.vertices) {
        minc = std::min({minc, v.position.x, v.position.y, v.position.z});
        maxc = std::max({maxc, v.position.x, v.position.y, v.position.z});
    }
    CHECK(minc == Approx(-0.5f));
    CHECK(maxc == Approx( 0.5f));
}

TEST_CASE("Sphere has consistent vertex/index counts for given segments", "[primitives]") {
    auto m = gen_sphere(0.5f, /*lat=*/16, /*lon=*/32);
    // (lat+1) * (lon+1) verts, lat*lon*6 indices
    CHECK(m.vertices.size() == 17 * 33);
    CHECK(m.indices.size()  == 16 * 32 * 6);
}

TEST_CASE("Plane is 4 verts / 6 indices, lies in XZ at y=0", "[primitives]") {
    auto m = gen_plane(2.0f, 2.0f);
    CHECK(m.vertices.size() == 4);
    CHECK(m.indices.size() == 6);
    for (auto& v : m.vertices) CHECK(v.position.y == Approx(0.f));
}
```

**Step 2: Run, fail (header missing).**

**Step 3: Implement primitives**

`src/scene/primitives.h`:
```cpp
#pragma once
#include <joon/scene.h>

namespace joon {

Mesh gen_cube(float size = 1.0f);
Mesh gen_sphere(float radius = 0.5f, int lat = 16, int lon = 32);
Mesh gen_plane(float w = 1.0f, float h = 1.0f);
Mesh gen_cylinder(float radius = 0.5f, float height = 1.0f, int segments = 32);

} // namespace joon
```

`src/scene/primitives.cpp` (cube fully shown — sphere/plane/cylinder analogous, write each one task-by-task or in bulk if pattern clear):
```cpp
#include "scene/primitives.h"
#include <cmath>

namespace joon {

Mesh gen_cube(float size) {
    const float h = size * 0.5f;
    // 6 faces × 4 unique verts each (so normals are flat per-face)
    const vec3 normals[6] = {
        { 0, 0, 1}, { 0, 0,-1},   // +Z, -Z
        { 1, 0, 0}, {-1, 0, 0},   // +X, -X
        { 0, 1, 0}, { 0,-1, 0},   // +Y, -Y
    };
    const vec3 corners[6][4] = {
        {{-h,-h, h},{ h,-h, h},{ h, h, h},{-h, h, h}},  // +Z
        {{ h,-h,-h},{-h,-h,-h},{-h, h,-h},{ h, h,-h}},  // -Z
        {{ h,-h, h},{ h,-h,-h},{ h, h,-h},{ h, h, h}},  // +X
        {{-h,-h,-h},{-h,-h, h},{-h, h, h},{-h, h,-h}},  // -X
        {{-h, h, h},{ h, h, h},{ h, h,-h},{-h, h,-h}},  // +Y
        {{-h,-h,-h},{ h,-h,-h},{ h,-h, h},{-h,-h, h}},  // -Y
    };
    const vec2 uvs[4] = { {0,0},{1,0},{1,1},{0,1} };

    Mesh m;
    m.vertices.reserve(24);
    m.indices.reserve(36);
    for (int f = 0; f < 6; ++f) {
        uint32_t base = static_cast<uint32_t>(m.vertices.size());
        for (int c = 0; c < 4; ++c)
            m.vertices.push_back({corners[f][c], normals[f], uvs[c]});
        // two triangles per face: 0-1-2, 0-2-3
        m.indices.insert(m.indices.end(), { base, base+1, base+2, base, base+2, base+3 });
    }
    return m;
}

// gen_sphere, gen_plane, gen_cylinder — implement following the same pattern.
// Sphere: (lat+1) latitude rings × (lon+1) longitude verts; faces wind CCW.
// Plane: 4 corners at (±w/2, 0, ±h/2), normal +Y.
// Cylinder: top cap + bottom cap + side strip; segments around.

} // namespace joon
```

**Step 4: Run primitives tests** (`[primitives]`), verify pass.

**Step 5: Run full suite.**

**Step 6: Commit**
```bash
git commit -am "feat(joon): procedural primitives (cube, sphere, plane, cylinder)"
```

---

### Task 4: OBJ loader (vendored tinyobjloader)

**Files:**
- Create: `projects/joon/third_party/tinyobjloader/tiny_obj_loader.h`  (vendor v2.0.0-rc13)
- Create: `projects/joon/src/scene/obj_loader.h`, `obj_loader.cpp`
- Create: `projects/joon/tests/test_obj_loader.cpp`

**Step 1: Failing test using an in-memory cube OBJ**

```cpp
// tests/test_obj_loader.cpp
#include "catch_amalgamated.hpp"
#include "scene/obj_loader.h"
using namespace joon;

static const char* CUBE_OBJ = R"(
v -0.5 -0.5 -0.5
v  0.5 -0.5 -0.5
v  0.5  0.5 -0.5
v -0.5  0.5 -0.5
v -0.5 -0.5  0.5
v  0.5 -0.5  0.5
v  0.5  0.5  0.5
v -0.5  0.5  0.5
vn 0 0 -1
vn 0 0  1
f 1//1 2//1 3//1
f 1//1 3//1 4//1
f 5//2 6//2 7//2
f 5//2 7//2 8//2
)";

TEST_CASE("OBJ loader parses positions and indices", "[obj]") {
    auto mesh = load_obj_string(CUBE_OBJ);
    REQUIRE(mesh.vertices.size() >= 12);   // 4 verts/face × 2 faces with split normals
    REQUIRE(mesh.indices.size() == 12);    // 2 tris × 3 indices × 2 faces
}
```

**Step 2: Run, fail — header missing.**

**Step 3: Vendor tinyobjloader**

Download `tiny_obj_loader.h` v2.0.0-rc13 from `https://github.com/tinyobjloader/tinyobjloader/blob/release/tiny_obj_loader.h` and place at `third_party/tinyobjloader/tiny_obj_loader.h`. Add a `LICENSE` file alongside.

**Step 4: Implement loader**

`src/scene/obj_loader.h`:
```cpp
#pragma once
#include <joon/scene.h>
#include <string>

namespace joon {
Mesh load_obj_string(const std::string& obj_text);
Mesh load_obj_file(const std::string& path);
} // namespace joon
```

`src/scene/obj_loader.cpp`:
```cpp
#define TINYOBJLOADER_IMPLEMENTATION
#include "tinyobjloader/tiny_obj_loader.h"
#include "scene/obj_loader.h"
#include <sstream>
#include <stdexcept>

namespace joon {

static Mesh build_mesh(const tinyobj::attrib_t& attrib,
                        const std::vector<tinyobj::shape_t>& shapes) {
    Mesh out;
    for (auto& shape : shapes) {
        for (auto& idx : shape.mesh.indices) {
            Vertex v{};
            v.position = {
                attrib.vertices[3*idx.vertex_index + 0],
                attrib.vertices[3*idx.vertex_index + 1],
                attrib.vertices[3*idx.vertex_index + 2],
            };
            if (idx.normal_index >= 0) {
                v.normal = {
                    attrib.normals[3*idx.normal_index + 0],
                    attrib.normals[3*idx.normal_index + 1],
                    attrib.normals[3*idx.normal_index + 2],
                };
            }
            if (idx.texcoord_index >= 0) {
                v.uv = {
                    attrib.texcoords[2*idx.texcoord_index + 0],
                    attrib.texcoords[2*idx.texcoord_index + 1],
                };
            }
            out.vertices.push_back(v);
            out.indices.push_back(static_cast<uint32_t>(out.indices.size()));
        }
    }
    return out;
}

Mesh load_obj_string(const std::string& obj_text) {
    tinyobj::attrib_t attrib;
    std::vector<tinyobj::shape_t> shapes;
    std::vector<tinyobj::material_t> materials;
    std::string warn, err;
    std::istringstream iss(obj_text);
    if (!tinyobj::LoadObj(&attrib, &shapes, &materials, &warn, &err, &iss))
        throw std::runtime_error("OBJ parse failed: " + err);
    return build_mesh(attrib, shapes);
}

Mesh load_obj_file(const std::string& path) {
    tinyobj::attrib_t attrib;
    std::vector<tinyobj::shape_t> shapes;
    std::vector<tinyobj::material_t> materials;
    std::string warn, err;
    if (!tinyobj::LoadObj(&attrib, &shapes, &materials, &warn, &err, path.c_str()))
        throw std::runtime_error("OBJ load failed: " + err);
    return build_mesh(attrib, shapes);
}

} // namespace joon
```

**Step 5: Run, pass.**

**Step 6: Commit**
```bash
git add third_party/tinyobjloader/ src/scene/obj_loader.* tests/test_obj_loader.cpp
git commit -m "feat(joon): vendor tinyobjloader and add OBJ mesh loader"
```

---

## Phase 3: Scene Collection in Evaluator

### Task 5: Extend EvalContext with SceneCollection; register scene executors

**Files:**
- Modify: `projects/joon/src/nodes/node_registry.h`
- Create: `projects/joon/src/scene/scene_executors.h`, `scene_executors.cpp`
- Modify: `projects/joon/src/nodes/node_registry.cpp` (call `register_scene_nodes`)
- Modify: `projects/joon/src/evaluator.cpp` (own a `SceneCollection`, expose to `EvalContext`, clear before each evaluate)
- Modify: `projects/joon/src/interpreter/interpreter.cpp` (skip SCENE/RENDER for now, but call SCENE executors first; defer RENDER to after the GPU walk — see Task 8)

**Step 1: Failing test**

```cpp
// tests/test_scene_collection.cpp (extend existing or new file)
TEST_CASE("Evaluating a scene populates SceneCollection", "[scene][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (cube :scale 1.0 :position [0 0 0])
        (sphere :radius 0.5 :position [2 0 0])
        (light :type directional :direction [0 -1 0] :color [1 1 1])
        (camera :fov 60 :position [0 2 5])
        (output 0.5)
    )");
    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto& scene = eval->scene_for_test();   // new debug-accessor
    CHECK(scene.objects.size() == 2);
    CHECK(scene.lights.size() == 1);
    CHECK(scene.camera.fov_deg == Approx(60.0f));
}
```

**Step 2-4: Implement (one logical commit per concern below — but write & test the whole task end-to-end)**

a) `EvalContext` (in `src/nodes/node_registry.h`) gains a `SceneCollection& scene` reference.
b) `Evaluator::Impl` owns `SceneCollection scene_;` and clears it at the top of `evaluate()`.
c) `register_scene_nodes()` registers 7 executors (`cube`, `sphere`, `plane`, `cylinder`, `mesh`, `light`, `camera`). Each pulls kwargs (`:position`, `:scale`, `:radius`, `:fov`, etc.), builds the right value-type, and calls `ctx.scene.add_object(...)` / `add_light(...)` / `set_camera(...)`.
d) `Interpreter::evaluate` walks the topo order: when it hits a `SCENE`-tier node, dispatch to its executor; when it hits a `RENDER`-tier node, defer (collected into a list) and execute after the compute walk completes.
e) Add a debug accessor `Evaluator::scene_for_test()` (under `#ifdef JOON_TEST` or just always available — pragmatic over pure).

Example executor (in `scene_executors.cpp`):
```cpp
static void exec_cube(const Node& n, EvalContext& ctx) {
    SceneObject o;
    o.mesh = gen_cube(get_kwarg_float(n, "scale", 1.0f));
    o.position = get_kwarg_vec3(n, "position", {0,0,0});
    o.rotation = get_kwarg_vec3(n, "rotation", {0,0,0});
    ctx.scene.add_object(std::move(o));
}
```

`get_kwarg_*` helpers live in a new tiny `src/scene/kwarg_helpers.h` (or extend an existing one if present).

**Step 5: Run, verify pass.**

**Step 6: Commit**
```bash
git commit -am "feat(joon): scene executors populate SceneCollection during evaluate"
```

---

## Phase 4: Vulkan Graphics Pipeline Infrastructure

### Task 6: Vertex / index buffer wrappers

**Files:**
- Create: `projects/joon/src/vulkan/buffer.h`, `buffer.cpp`

`buffer.h`:
```cpp
#pragma once
#include "vulkan/device.h"
#include <cstdint>

namespace joon {

struct GpuBuffer {
    VkBuffer buffer = VK_NULL_HANDLE;
    VmaAllocation alloc = VK_NULL_HANDLE;
    size_t size = 0;
};

GpuBuffer create_vertex_buffer(Device& dev, const void* data, size_t size_bytes);
GpuBuffer create_index_buffer (Device& dev, const void* data, size_t size_bytes);
GpuBuffer create_uniform_buffer(Device& dev, size_t size_bytes);  // host-visible
void      update_uniform_buffer(Device& dev, GpuBuffer& buf, const void* data, size_t size);
void      destroy_buffer(Device& dev, GpuBuffer& buf);

} // namespace joon
```

Implement using VMA: vertex/index → DEVICE_LOCAL with staging upload via `begin_single_command`; uniform → CPU_TO_GPU mapped. Bookkeep allocations so the geometry-pass executor can dispose them at the end of an evaluate (or pool them — keep it simple for sub-project 2: create per-evaluate, free at end).

**Test:** `[buffer]` tag, allocate a buffer, upload 64 bytes, read back via a host-visible roundtrip is overkill — assert `buffer != VK_NULL_HANDLE` and `size == 64`. Real exercise comes via the geometry pass.

**Commit:** `feat(joon): vertex/index/uniform buffer wrappers (VMA)`

---

### Task 7: RenderPass + GraphicsPipeline

**Files:**
- Create: `projects/joon/src/vulkan/render_pass.h`, `render_pass.cpp`
- Modify: `projects/joon/src/vulkan/pipeline_cache.h`, `pipeline_cache.cpp`
- Create: `projects/joon/shaders/scene_basic.vert.hlsl`
- Create: `projects/joon/shaders/scene_basic.frag.hlsl`

**HLSL shaders (write first, simplest possible).**

`shaders/scene_basic.vert.hlsl`:
```hlsl
struct UBO { float4x4 mvp; float4x4 model; };
[[vk::binding(0, 0)]] ConstantBuffer<UBO> ubo;

struct VSIn  { float3 pos : POSITION; float3 nrm : NORMAL; float2 uv : TEXCOORD0; };
struct VSOut { float4 sv  : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; };

VSOut main(VSIn v) {
    VSOut o;
    o.sv = mul(ubo.mvp, float4(v.pos, 1.0));
    o.normal = normalize(mul((float3x3)ubo.model, v.nrm));
    o.uv = v.uv;
    return o;
}
```

`shaders/scene_basic.frag.hlsl`:
```hlsl
struct PushLight { float3 light_dir; float pad0; float3 light_color; float pad1; };
[[vk::push_constant]] PushLight pc;

struct PSIn { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; };

float4 main(PSIn i) : SV_TARGET {
    float ndotl = saturate(dot(normalize(i.normal), -normalize(pc.light_dir)));
    float3 col = pc.light_color * (0.1 + 0.9 * ndotl);   // ambient + diffuse
    return float4(col, 1.0);
}
```

**`render_pass.h`:**
```cpp
#pragma once
#include "vulkan/device.h"
#include <vector>

namespace joon {

struct RenderPass {
    VkRenderPass pass = VK_NULL_HANDLE;
    std::vector<VkFormat> color_formats;
    VkFormat depth_format = VK_FORMAT_D32_SFLOAT;
};

RenderPass create_color_depth_renderpass(
    Device& dev,
    const std::vector<VkFormat>& color_formats,
    VkFormat depth_format = VK_FORMAT_D32_SFLOAT);

VkFramebuffer create_framebuffer(
    Device& dev, const RenderPass& rp,
    const std::vector<VkImageView>& color_views,
    VkImageView depth_view, uint32_t w, uint32_t h);

void destroy_renderpass(Device& dev, RenderPass& rp);

} // namespace joon
```

Standard Vulkan boilerplate — color attachments load=`CLEAR`, store=`STORE`, finalLayout=`COLOR_ATTACHMENT_OPTIMAL` (we manually transition to `GENERAL` after end). Depth attachment load=`CLEAR`, finalLayout=`DEPTH_STENCIL_ATTACHMENT_OPTIMAL`.

**PipelineCache extension:** add a parallel `m_graphics_pipelines` keyed by render-pass handle + shader name. `get_graphics(name, render_pass, vertex_layout)` compiles `name.vert.hlsl` and `name.frag.hlsl` via existing DXC path (factored helper), creates pipeline layout matching the shaders' bindings (1 UBO at set 0 binding 0; push constant range for fragment), then `vkCreateGraphicsPipelines` with the supplied vertex input description.

**Test:** `[pipeline][gpu]` — compile both shaders, create a render pass, create a graphics pipeline, assert `pipeline != VK_NULL_HANDLE`. No drawing yet.

**Commit:** `feat(joon): VkRenderPass + VkGraphicsPipeline via PipelineCache::get_graphics`

---

## Phase 5: Geometry Pass Executor

### Task 8: pass executor — render scene to color/depth targets

**Files:**
- Modify: `projects/joon/src/vulkan/resource_pool.h`, `resource_pool.cpp` (add color-attachment-capable images + depth allocation)
- Modify: `projects/joon/src/scene/scene_executors.cpp` (`exec_pass` + register `pass`)
- Modify: `projects/joon/src/interpreter/interpreter.cpp` (defer RENDER nodes to a second walk after compute walk; see Task 5e)

**Step 1: Failing test (full integration)**

```cpp
// tests/test_geometry_pass.cpp
#include "catch_amalgamated.hpp"
#include <joon/joon.h>
using namespace joon;

TEST_CASE("Geometry pass renders non-clear pixels", "[render][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (cube :scale 1.5 :position [0 0 0])
        (camera :fov 60 :position [0 0 4] :target [0 0 0])
        (light :type directional :direction [-1 -1 -1] :color [1 1 1])
        (def gbuf (pass scene :outputs [albedo depth]))
        (output gbuf)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    // Expect *some* lit pixels (not all clear color {0,0,0,1})
    int lit = 0;
    for (size_t i = 0; i < px.size(); i += 4)
        if (px[i] > 0.05f || px[i+1] > 0.05f || px[i+2] > 0.05f) ++lit;
    CHECK(lit > 100);   // arbitrary, just "non-empty"
}

TEST_CASE("Compute can read geometry-pass output", "[render][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (cube :scale 1.0)
        (camera :position [0 0 4])
        (light :type directional :direction [0 -1 0])
        (def gbuf (pass scene :outputs [albedo depth]))
        (def adjusted (levels gbuf :contrast 1.5))
        (output adjusted)
    )");
    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    // Just make sure it runs end-to-end without crashing and produces data.
    REQUIRE(px.size() == 512 * 512 * 4);
}
```

**Step 2-4: Implement**

`resource_pool.h` extension:
```cpp
GpuImage* alloc_render_target(uint32_t node_id, uint32_t w, uint32_t h,
                               VkFormat format = VK_FORMAT_R8G8B8A8_UNORM);
GpuImage* alloc_depth(uint32_t node_id, uint32_t w, uint32_t h,
                       VkFormat format = VK_FORMAT_D32_SFLOAT);
```

Implementations differ from `alloc_image` only in the `usage` flags (`COLOR_ATTACHMENT_BIT`, `DEPTH_STENCIL_ATTACHMENT_BIT`) and the aspect mask of the image view.

`exec_pass` outline (write straight-through, no sub-extraction at first):
```cpp
static void exec_pass(const Node& n, EvalContext& ctx) {
    // 1. Collect outputs from node kwargs (e.g. :outputs [albedo depth])
    auto outputs = parse_outputs_kwarg(n);
    auto albedo = ctx.pool.alloc_render_target(n.id /*color out node id*/, ctx.width, ctx.height);
    auto depth  = ctx.pool.alloc_depth(n.id + 0x10000000, ctx.width, ctx.height);

    // 2. Build render pass + framebuffer
    static auto rp = create_color_depth_renderpass(ctx.device, {albedo->format});
    auto fb = create_framebuffer(ctx.device, rp, {albedo->view}, depth->view, ctx.width, ctx.height);

    // 3. Get/build graphics pipeline
    VertexLayout layout = vertex_layout_for<Vertex>();
    auto& gp = ctx.pipelines.get_graphics("scene_basic", rp, layout);

    // 4. Build per-object UBOs (mvp, model) — one buffer + dynamic offsets,
    //    OR (simpler) one buffer per object for sub-project 2.
    auto view = look_at(ctx.scene.camera.position, ctx.scene.camera.target, ctx.scene.camera.up);
    auto proj = perspective(ctx.scene.camera.fov_deg, float(ctx.width)/ctx.height,
                            ctx.scene.camera.near_z, ctx.scene.camera.far_z);

    // 5. Record one-shot command buffer:
    auto cmd = ctx.device.begin_single_command();
    VkClearValue clears[2] = { {.color = {{0,0,0,1}}}, {.depthStencil = {1.0f, 0}} };
    VkRenderPassBeginInfo rpi{...};   // pass, framebuffer, render area, 2 clears
    vkCmdBeginRenderPass(cmd, &rpi, VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, gp.pipeline);

    PushLight pc{normalize(ctx.scene.lights[0].direction), 0,
                  ctx.scene.lights[0].color * ctx.scene.lights[0].intensity, 0};
    vkCmdPushConstants(cmd, gp.layout, VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(pc), &pc);

    for (auto& obj : ctx.scene.objects) {
        // Upload geometry per-eval (free at end). Optimization later.
        auto vb = create_vertex_buffer(ctx.device, obj.mesh.vertices.data(),
                                        obj.mesh.vertices.size() * sizeof(Vertex));
        auto ib = create_index_buffer (ctx.device, obj.mesh.indices.data(),
                                        obj.mesh.indices.size() * sizeof(uint32_t));

        auto model = compose(obj.position, obj.rotation, obj.scale);
        auto mvp = proj * view * model;
        UBO u{mvp, model};
        auto ub = create_uniform_buffer(ctx.device, sizeof(UBO));
        update_uniform_buffer(ctx.device, ub, &u, sizeof(UBO));

        // Allocate descriptor set, write UBO, bind set, bind VB/IB, draw indexed
        // ...
        ctx.frame_buffers_to_free.push_back({vb, ib, ub});
    }
    vkCmdEndRenderPass(cmd);

    // 6. Transition color attachment to GENERAL for downstream compute / viewport
    image_barrier(cmd, albedo->image,
        VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, VK_IMAGE_LAYOUT_GENERAL,
        VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT, VK_ACCESS_SHADER_READ_BIT);

    ctx.device.end_single_command(cmd);

    // 7. Free per-frame buffers + framebuffer (real pooling is a follow-up)
    for (auto& f : ctx.frame_buffers_to_free) {
        destroy_buffer(ctx.device, f.vb);
        destroy_buffer(ctx.device, f.ib);
        destroy_buffer(ctx.device, f.ub);
    }
    ctx.frame_buffers_to_free.clear();
    vkDestroyFramebuffer(ctx.device.device, fb, nullptr);
}
```

`Interpreter::evaluate` change: after the existing topological walk, do a second pass over RENDER-tier nodes in topological order. (Or extend the single walk to handle them last by op-tier comparison.)

**Step 5: Run all tests, verify pass.**

**Step 6: Commit**
```bash
git commit -am "feat(joon): geometry pass executor renders scene to color+depth targets"
```

---

## Phase 6: Wire Compute Graph + GUI

### Task 9: Confirm pass output is consumable as a compute input

The second test in Task 8 already covers this end-to-end. If `levels` reads the geometry-pass output cleanly, no further IR plumbing is needed (since both write into `ResourcePool` keyed by node id). If the test fails because the compute path expects `STORAGE_IMAGE` usage but the render target was allocated with only `COLOR_ATTACHMENT_BIT`, fix `alloc_render_target` to also include `STORAGE_BIT | SAMPLED_BIT`.

**Step 1-3:** Iterate on test until it passes — the failure mode here is informative and shouldn't be guessed at; trust the test output.

**Step 4: Commit any fix as `fix(joon): render targets need STORAGE_BIT for compute reads` (only if needed).**

---

### Task 10: Update gui default DSL to a 3D scene

**Files:**
- Modify: `projects/joon/gui/app.cpp`

```cpp
dsl_source = R"(; Joon - 3D scene
(cube :scale 1.0 :position [0 0 0])
(camera :fov 60 :position [0 1 4] :target [0 0 0])
(light :type directional :direction [-0.5 -1 -0.5] :color [1 1 1] :intensity 1.0)
(def gbuf (pass scene :outputs [albedo depth]))
(param contrast float 1.0 :min 0.0 :max 3.0)
(def final (levels gbuf :contrast contrast))
(output final)
)";
```

**Verify manually:** build joon-gui, run it, confirm a shaded cube appears in the viewport. Drag the contrast slider and confirm real-time updates. Check log.txt — no Vulkan validation errors.

**Step: Commit**
```bash
git commit -am "feat(joon): default GUI DSL renders a 3D cube via geometry pass"
```

---

## Phase 7: Final Verification

### Task 11: Run the full test plan, then open PR

- [ ] Clean build: `rm -rf build && /d/prg/premake5.exe vs2022`
- [ ] Build all 4 projects in Debug
- [ ] Run `joon-tests` — all tests pass (38 + new tests for scene/render)
- [ ] Run `joon-gui` — visual confirmation of cube rendering
- [ ] CI on PR shows all 4 checks green

Push the branch and open a PR titled **"feat(joon): scene graph and hardcoded geometry pass (sub-project 2)"** linking back to this plan and the design spec.

---

## Open Questions (resolve before implementing)

1. **Vec/matrix math.** Does joon already have a vec3/mat4 library? The architecture map didn't surface one explicitly. **Check `include/joon/types.h`** — if it has only the scalar `Type` enum, we need either a tiny inline math header OR adopt one of the deps already pulled in (VMA's internal types are not public). A simple `joon/math.h` with `vec2/vec3/vec4/mat4` plus `look_at`, `perspective`, multiplication is ~200 lines and worth keeping in-tree.

2. **Per-evaluate buffer allocation.** Sub-project 2 creates vertex/index/uniform buffers fresh every `evaluate()` call. This is fine for correctness but means the GUI slider re-uploads geometry on every frame. Is that acceptable for this sub-project? (Yes, per design — pooling is a follow-up if profiling shows it's needed.)

3. **Multiple light support.** The fragment shader hardcodes `lights[0]`. Multiple lights via push-constant array or UBO array can wait for sub-project 3.

Before starting Task 1, surface these to the user if uncertain.
