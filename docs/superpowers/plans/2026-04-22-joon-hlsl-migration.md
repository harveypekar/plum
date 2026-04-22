# HLSL Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all GLSL compute shaders with HLSL equivalents compiled via DXC, removing the GLSL toolchain entirely.

**Architecture:** The PipelineCache gains a `compile_hlsl()` method that shells out to `dxc.exe` (shipped with the Vulkan SDK) to compile `.hlsl` → SPIR-V at runtime on first use. This replaces the prebuild `glslc` step. The shader directory switches from `.comp` (GLSL) to `.hlsl` files. All downstream code (gpu_dispatch, node executors, tests) is unchanged — they never see the shader source, only the Vulkan pipeline objects.

**Tech Stack:** HLSL, DXC (from Vulkan SDK), Vulkan compute pipelines, Premake

**Worktree:** `/mnt/d/prg/plum-joon-3d-design` (branch `joon-3d-design`)

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `shaders/add.hlsl` | HLSL port of add.comp |
| Create | `shaders/sub.hlsl` | HLSL port of sub.comp |
| Create | `shaders/mul.hlsl` | HLSL port of mul.comp |
| Create | `shaders/div.hlsl` | HLSL port of div.comp |
| Create | `shaders/invert.hlsl` | HLSL port of invert.comp |
| Create | `shaders/threshold.hlsl` | HLSL port of threshold.comp |
| Create | `shaders/levels.hlsl` | HLSL port of levels.comp |
| Create | `shaders/blur.hlsl` | HLSL port of blur.comp |
| Create | `shaders/blend.hlsl` | HLSL port of blend.comp |
| Create | `shaders/noise.hlsl` | HLSL port of noise.comp |
| Modify | `src/vulkan/pipeline_cache.h` | Add `compile_hlsl()` method |
| Modify | `src/vulkan/pipeline_cache.cpp` | Implement DXC compilation, replace `read_spirv()` |
| Modify | `premake5.lua` | Remove prebuild shader compilation commands |
| Delete | `shaders/add.comp` | Replaced by .hlsl |
| Delete | `shaders/sub.comp` | Replaced by .hlsl |
| Delete | `shaders/mul.comp` | Replaced by .hlsl |
| Delete | `shaders/div.comp` | Replaced by .hlsl |
| Delete | `shaders/invert.comp` | Replaced by .hlsl |
| Delete | `shaders/threshold.comp` | Replaced by .hlsl |
| Delete | `shaders/levels.comp` | Replaced by .hlsl |
| Delete | `shaders/blur.comp` | Replaced by .hlsl |
| Delete | `shaders/blend.comp` | Replaced by .hlsl |
| Delete | `shaders/noise.comp` | Replaced by .hlsl |
| Delete | `shaders/compile.bat` | No longer needed (runtime compilation) |
| Delete | `shaders/compile_if_changed.bat` | No longer needed (runtime compilation) |
| Delete | `shaders/*.spv` | Generated at runtime now |

---

### Task 1: Port Math Op Shaders (add, sub, mul, div)

These four shaders share the same structure: two inputs, one output, no push constants.

**Files:**
- Create: `projects/joon/shaders/add.hlsl`
- Create: `projects/joon/shaders/sub.hlsl`
- Create: `projects/joon/shaders/mul.hlsl`
- Create: `projects/joon/shaders/div.hlsl`

- [ ] **Step 1: Write `add.hlsl`**

```hlsl
RWTexture2D<float4> input_a : register(u0);
RWTexture2D<float4> input_b : register(u1);
RWTexture2D<float4> output_img : register(u2);

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 a = input_a[id.xy];
    float4 b = input_b[id.xy];
    output_img[id.xy] = a + b;
}
```

- [ ] **Step 2: Write `sub.hlsl`**

Same structure as add.hlsl but with `a - b`:

```hlsl
RWTexture2D<float4> input_a : register(u0);
RWTexture2D<float4> input_b : register(u1);
RWTexture2D<float4> output_img : register(u2);

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 a = input_a[id.xy];
    float4 b = input_b[id.xy];
    output_img[id.xy] = a - b;
}
```

- [ ] **Step 3: Write `mul.hlsl`**

```hlsl
RWTexture2D<float4> input_a : register(u0);
RWTexture2D<float4> input_b : register(u1);
RWTexture2D<float4> output_img : register(u2);

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 a = input_a[id.xy];
    float4 b = input_b[id.xy];
    output_img[id.xy] = a * b;
}
```

- [ ] **Step 4: Write `div.hlsl`**

```hlsl
RWTexture2D<float4> input_a : register(u0);
RWTexture2D<float4> input_b : register(u1);
RWTexture2D<float4> output_img : register(u2);

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 a = input_a[id.xy];
    float4 b = input_b[id.xy];
    output_img[id.xy] = a / max(b, float4(0.0001, 0.0001, 0.0001, 0.0001));
}
```

- [ ] **Step 5: Verify DXC compiles all four**

Run from the `shaders/` directory:

```bat
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 add.hlsl -Fo add.spv
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 sub.hlsl -Fo sub.spv
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 mul.hlsl -Fo mul.spv
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 div.hlsl -Fo div.spv
```

Expected: all four compile with no errors. Each produces a `.spv` file.

- [ ] **Step 6: Commit**

```bash
git add shaders/add.hlsl shaders/sub.hlsl shaders/mul.hlsl shaders/div.hlsl
git commit -m "feat(joon): port math op compute shaders to HLSL"
```

---

### Task 2: Port Single-Input Shaders (invert, threshold, levels)

Single input image, single output. Threshold and levels use push constants.

**Files:**
- Create: `projects/joon/shaders/invert.hlsl`
- Create: `projects/joon/shaders/threshold.hlsl`
- Create: `projects/joon/shaders/levels.hlsl`

- [ ] **Step 1: Write `invert.hlsl`**

```hlsl
RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 c = input_img[id.xy];
    output_img[id.xy] = float4(1.0 - c.rgb, c.a);
}
```

- [ ] **Step 2: Write `threshold.hlsl`**

Push constants use `[[vk::push_constant]]`:

```hlsl
RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

[[vk::push_constant]]
struct Params {
    float threshold;
};

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 c = input_img[id.xy];
    float lum = dot(c.rgb, float3(0.299, 0.587, 0.114));
    float v = step(threshold, lum);
    output_img[id.xy] = float4(v, v, v, c.a);
}
```

- [ ] **Step 3: Write `levels.hlsl`**

```hlsl
RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

[[vk::push_constant]]
struct Params {
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

- [ ] **Step 4: Verify DXC compiles all three**

```bat
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 invert.hlsl -Fo invert.spv
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 threshold.hlsl -Fo threshold.spv
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 levels.hlsl -Fo levels.spv
```

Expected: all three compile with no errors.

- [ ] **Step 5: Commit**

```bash
git add shaders/invert.hlsl shaders/threshold.hlsl shaders/levels.hlsl
git commit -m "feat(joon): port invert, threshold, levels shaders to HLSL"
```

---

### Task 3: Port Complex Shaders (blur, blend, noise)

These have more logic: blur has a nested loop, blend has branching blend modes, noise has helper functions.

**Files:**
- Create: `projects/joon/shaders/blur.hlsl`
- Create: `projects/joon/shaders/blend.hlsl`
- Create: `projects/joon/shaders/noise.hlsl`

- [ ] **Step 1: Write `blur.hlsl`**

```hlsl
RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

[[vk::push_constant]]
struct Params {
    float radius;
};

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    int2 pos = int2(id.xy);
    int r = int(ceil(radius));
    float4 sum = float4(0.0, 0.0, 0.0, 0.0);
    float weight_sum = 0.0;

    for (int dy = -r; dy <= r; dy++) {
        for (int dx = -r; dx <= r; dx++) {
            int2 sample_pos = clamp(pos + int2(dx, dy), int2(0, 0), int2(size) - int2(1, 1));
            float dist = length(float2(dx, dy));
            float w = exp(-dist * dist / (2.0 * radius * radius));
            sum += w * input_img[sample_pos];
            weight_sum += w;
        }
    }

    output_img[id.xy] = sum / weight_sum;
}
```

- [ ] **Step 2: Write `blend.hlsl`**

```hlsl
RWTexture2D<float4> input_a : register(u0);
RWTexture2D<float4> input_b : register(u1);
RWTexture2D<float4> output_img : register(u2);

[[vk::push_constant]]
struct Params {
    float opacity;
    int mode; // 0=normal, 1=multiply, 2=screen, 3=overlay
};

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 a = input_a[id.xy];
    float4 b = input_b[id.xy];

    float3 result;
    if (mode == 0)      result = b.rgb;
    else if (mode == 1) result = a.rgb * b.rgb;
    else if (mode == 2) result = 1.0 - (1.0 - a.rgb) * (1.0 - b.rgb);
    else                result = lerp(2.0 * a.rgb * b.rgb,
                                      1.0 - 2.0 * (1.0 - a.rgb) * (1.0 - b.rgb),
                                      step(0.5, a.rgb));

    result = lerp(a.rgb, result, opacity);
    output_img[id.xy] = float4(result, max(a.a, b.a));
}
```

Note: GLSL `mix` → HLSL `lerp`.

- [ ] **Step 3: Write `noise.hlsl`**

The simplex noise helper functions port directly. GLSL `fract` → HLSL `frac`. GLSL `vec2/vec3` → HLSL `float2/float3`.

```hlsl
RWTexture2D<float4> output_img : register(u0);

[[vk::push_constant]]
struct Params {
    float scale;
    float octaves;
    float width;
    float height;
};

float2 hash(float2 p) {
    p = float2(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)));
    return -1.0 + 2.0 * frac(sin(p) * 43758.5453123);
}

float simplex_noise(float2 p) {
    const float K1 = 0.366025404; // (sqrt(3)-1)/2
    const float K2 = 0.211324865; // (3-sqrt(3))/6
    float2 i = floor(p + (p.x + p.y) * K1);
    float2 a = p - i + (i.x + i.y) * K2;
    float m = step(a.y, a.x);
    float2 o = float2(m, 1.0 - m);
    float2 b = a - o + K2;
    float2 c = a - 1.0 + 2.0 * K2;
    float3 h = max(0.5 - float3(dot(a, a), dot(b, b), dot(c, c)), 0.0);
    float3 n = h * h * h * h * float3(dot(a, hash(i)), dot(b, hash(i + o)), dot(c, hash(i + 1.0)));
    return dot(n, float3(70.0, 70.0, 70.0));
}

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float2 uv = float2(id.xy) / float2(width, height);

    float value = 0.0;
    float amplitude = 1.0;
    float frequency = scale;
    int oct = int(octaves);

    for (int i = 0; i < oct; i++) {
        value += amplitude * simplex_noise(uv * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
    }

    value = value * 0.5 + 0.5;
    output_img[id.xy] = float4(value, value, value, 1.0);
}
```

- [ ] **Step 4: Verify DXC compiles all three**

```bat
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 blur.hlsl -Fo blur.spv
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 blend.hlsl -Fo blend.spv
%VULKAN_SDK%\Bin\dxc.exe -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1 noise.hlsl -Fo noise.spv
```

Expected: all three compile with no errors. If DXC reports warnings about HLSL → SPIR-V mapping, they are acceptable as long as compilation succeeds.

- [ ] **Step 5: Commit**

```bash
git add shaders/blur.hlsl shaders/blend.hlsl shaders/noise.hlsl
git commit -m "feat(joon): port blur, blend, noise shaders to HLSL"
```

---

### Task 4: Update PipelineCache for DXC Runtime Compilation

Replace the `read_spirv` method (which loads pre-compiled `.spv` files) with a `compile_hlsl` method that shells out to `dxc.exe` and returns SPIR-V bytes. Compilation results are cached as `.spv` files next to the `.hlsl` source — recompiled only when the source is newer.

**Files:**
- Modify: `projects/joon/src/vulkan/pipeline_cache.h`
- Modify: `projects/joon/src/vulkan/pipeline_cache.cpp`

- [ ] **Step 1: Run existing tests to establish baseline**

Build and run `joon-tests` in Visual Studio (Debug config). All tests should pass with the current GLSL `.spv` files still present.

- [ ] **Step 2: Update `pipeline_cache.h`**

Replace `read_spirv` with `load_or_compile`:

```cpp
#pragma once

#include "vulkan/device.h"
#include <string>
#include <unordered_map>
#include <vector>

namespace joon {

struct ComputePipeline {
    VkShaderModule shader_module = VK_NULL_HANDLE;
    VkPipelineLayout layout = VK_NULL_HANDLE;
    VkPipeline pipeline = VK_NULL_HANDLE;
    VkDescriptorSetLayout desc_layout = VK_NULL_HANDLE;
};

class PipelineCache {
public:
    explicit PipelineCache(Device& device, const std::string& shader_dir);
    ~PipelineCache();

    const ComputePipeline& get(const std::string& name,
                                uint32_t num_images,
                                uint32_t push_constant_size = 0);

private:
    Device& m_device;
    std::string m_shaderDir;
    std::unordered_map<std::string, ComputePipeline> m_pipelines;

    std::vector<uint8_t> load_or_compile(const std::string& name);
    bool needs_recompile(const std::string& hlsl_path, const std::string& spv_path);
    std::vector<uint8_t> compile_hlsl(const std::string& hlsl_path, const std::string& spv_path);
    std::vector<uint8_t> read_file(const std::string& path);
};

} // namespace joon
```

- [ ] **Step 3: Implement `pipeline_cache.cpp`**

```cpp
#include "vulkan/pipeline_cache.h"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <stdexcept>

namespace joon {
namespace fs = std::filesystem;

PipelineCache::PipelineCache(Device& device, const std::string& shader_dir)
    : m_device(device), m_shaderDir(shader_dir) {}

PipelineCache::~PipelineCache() {
    for (auto& [name, p] : m_pipelines) {
        vkDestroyPipeline(m_device.device, p.pipeline, nullptr);
        vkDestroyPipelineLayout(m_device.device, p.layout, nullptr);
        vkDestroyDescriptorSetLayout(m_device.device, p.desc_layout, nullptr);
        vkDestroyShaderModule(m_device.device, p.shader_module, nullptr);
    }
}

std::vector<uint8_t> PipelineCache::read_file(const std::string& path) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file.is_open()) throw std::runtime_error("Cannot open file: " + path);
    size_t size = file.tellg();
    std::vector<uint8_t> data(size);
    file.seekg(0);
    file.read(reinterpret_cast<char*>(data.data()), size);
    return data;
}

bool PipelineCache::needs_recompile(const std::string& hlsl_path,
                                     const std::string& spv_path) {
    if (!fs::exists(spv_path)) return true;
    auto hlsl_time = fs::last_write_time(hlsl_path);
    auto spv_time = fs::last_write_time(spv_path);
    return hlsl_time > spv_time;
}

std::vector<uint8_t> PipelineCache::compile_hlsl(const std::string& hlsl_path,
                                                   const std::string& spv_path) {
    std::string dxc;
    const char* vulkan_sdk = std::getenv("VULKAN_SDK");
    if (vulkan_sdk) {
        dxc = std::string(vulkan_sdk) + "/Bin/dxc.exe";
        if (!fs::exists(dxc))
            dxc = std::string(vulkan_sdk) + "/bin/dxc";
    }
    if (dxc.empty() || !fs::exists(dxc))
        throw std::runtime_error("DXC not found. Set VULKAN_SDK environment variable.");

    std::string cmd = "\"" + dxc + "\""
        + " -T cs_6_0 -E main -spirv -fspv-target-env=vulkan1.1"
        + " \"" + hlsl_path + "\""
        + " -Fo \"" + spv_path + "\""
        + " 2>&1";

    int result = std::system(cmd.c_str());
    if (result != 0)
        throw std::runtime_error("DXC compilation failed for: " + hlsl_path);

    return read_file(spv_path);
}

std::vector<uint8_t> PipelineCache::load_or_compile(const std::string& name) {
    std::string hlsl_path = m_shaderDir + "/" + name + ".hlsl";
    std::string spv_path = m_shaderDir + "/" + name + ".spv";

    if (fs::exists(hlsl_path)) {
        if (needs_recompile(hlsl_path, spv_path))
            return compile_hlsl(hlsl_path, spv_path);
        return read_file(spv_path);
    }

    if (fs::exists(spv_path))
        return read_file(spv_path);

    throw std::runtime_error("No shader source found: " + name);
}

const ComputePipeline& PipelineCache::get(const std::string& name,
                                           uint32_t num_images,
                                           uint32_t push_constant_size) {
    std::string key = name + ":" + std::to_string(num_images) + ":" + std::to_string(push_constant_size);
    auto it = m_pipelines.find(key);
    if (it != m_pipelines.end()) return it->second;

    ComputePipeline p{};

    auto spirv = load_or_compile(name);
    if (spirv.size() % 4 != 0)
        throw std::runtime_error("SPIR-V size not a multiple of 4: " + name);

    VkShaderModuleCreateInfo shader_info{};
    shader_info.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
    shader_info.codeSize = spirv.size();
    shader_info.pCode = reinterpret_cast<const uint32_t*>(spirv.data());
    if (vkCreateShaderModule(m_device.device, &shader_info, nullptr, &p.shader_module) != VK_SUCCESS)
        throw std::runtime_error("Failed to create shader module: " + name);

    std::vector<VkDescriptorSetLayoutBinding> bindings(num_images);
    for (uint32_t i = 0; i < num_images; i++) {
        bindings[i].binding = i;
        bindings[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        bindings[i].descriptorCount = 1;
        bindings[i].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
    }

    VkDescriptorSetLayoutCreateInfo desc_info{};
    desc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    desc_info.bindingCount = num_images;
    desc_info.pBindings = bindings.data();
    if (vkCreateDescriptorSetLayout(m_device.device, &desc_info, nullptr, &p.desc_layout) != VK_SUCCESS) {
        vkDestroyShaderModule(m_device.device, p.shader_module, nullptr);
        throw std::runtime_error("Failed to create descriptor set layout: " + name);
    }

    VkPipelineLayoutCreateInfo layout_info{};
    layout_info.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    layout_info.setLayoutCount = 1;
    layout_info.pSetLayouts = &p.desc_layout;

    VkPushConstantRange push_range{};
    if (push_constant_size > 0) {
        push_range.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
        push_range.offset = 0;
        push_range.size = push_constant_size;
        layout_info.pushConstantRangeCount = 1;
        layout_info.pPushConstantRanges = &push_range;
    }

    if (vkCreatePipelineLayout(m_device.device, &layout_info, nullptr, &p.layout) != VK_SUCCESS) {
        vkDestroyDescriptorSetLayout(m_device.device, p.desc_layout, nullptr);
        vkDestroyShaderModule(m_device.device, p.shader_module, nullptr);
        throw std::runtime_error("Failed to create pipeline layout: " + name);
    }

    VkComputePipelineCreateInfo pipeline_info{};
    pipeline_info.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
    pipeline_info.stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    pipeline_info.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
    pipeline_info.stage.module = p.shader_module;
    pipeline_info.stage.pName = "main";
    pipeline_info.layout = p.layout;

    if (vkCreateComputePipelines(m_device.device, VK_NULL_HANDLE, 1, &pipeline_info, nullptr,
                                 &p.pipeline) != VK_SUCCESS) {
        vkDestroyPipelineLayout(m_device.device, p.layout, nullptr);
        vkDestroyDescriptorSetLayout(m_device.device, p.desc_layout, nullptr);
        vkDestroyShaderModule(m_device.device, p.shader_module, nullptr);
        throw std::runtime_error("Failed to create compute pipeline: " + name);
    }

    m_pipelines[key] = p;
    return m_pipelines[key];
}

} // namespace joon
```

- [ ] **Step 4: Run tests with HLSL shaders**

Delete existing `.spv` files from the shaders directory so the new `load_or_compile` path is exercised. Build and run `joon-tests`.

```bat
cd projects\joon\shaders
del *.spv
```

Then build and run tests in Visual Studio. Expected: all tests pass. DXC compiles `.hlsl` → `.spv` on demand during the test run.

- [ ] **Step 5: Run GUI and verify viewport**

Build and run `joon-gui`. Expected: the viewport renders the same noise+levels output as before. Dragging the contrast slider updates the viewport.

- [ ] **Step 6: Commit**

```bash
git add src/vulkan/pipeline_cache.h src/vulkan/pipeline_cache.cpp
git commit -m "feat(joon): runtime HLSL compilation via DXC in PipelineCache"
```

---

### Task 5: Remove GLSL Infrastructure

Delete all GLSL source files, compile scripts, and prebuild commands from premake.

**Files:**
- Delete: `projects/joon/shaders/*.comp` (10 files)
- Delete: `projects/joon/shaders/compile.bat`
- Delete: `projects/joon/shaders/compile_if_changed.bat`
- Modify: `projects/joon/premake5.lua` (remove prebuild commands)

- [ ] **Step 1: Delete GLSL source files**

```bash
cd projects/joon
git rm shaders/add.comp shaders/sub.comp shaders/mul.comp shaders/div.comp
git rm shaders/invert.comp shaders/threshold.comp shaders/levels.comp
git rm shaders/blur.comp shaders/blend.comp shaders/noise.comp
```

- [ ] **Step 2: Delete compile scripts**

```bash
git rm shaders/compile.bat shaders/compile_if_changed.bat
```

- [ ] **Step 3: Remove prebuild commands from `premake5.lua`**

Remove the `prebuildcommands` blocks from both the `joon-cli` and `joon-gui` projects.

In `joon-cli` (around line 153-158), remove:

```lua
    filter "system:windows"
        prebuildcommands {
            "{CHDIR} %{wks.location}/../shaders",
            "call .\\compile_if_changed.bat"
        }
    filter {}
```

In `joon-gui` (around line 191-196), remove:

```lua
        prebuildcommands {
            "{CHDIR} %{wks.location}/../shaders",
            "call .\\compile_if_changed.bat"
        }
```

Keep the `filter "system:windows"` in the gui project since it still has the `links` line.

- [ ] **Step 4: Add `.spv` to `.gitignore`**

`.spv` files are now generated at runtime and should not be committed. Append to `projects/joon/.gitignore` (create if it doesn't exist):

```
*.spv
```

- [ ] **Step 5: Regenerate project files and verify**

```bash
cd projects/joon
premake5 vs2022
```

Build and run `joon-tests` — all tests pass. Build and run `joon-gui` — viewport renders correctly.

- [ ] **Step 6: Commit**

```bash
git add -A shaders/ premake5.lua .gitignore
git commit -m "chore(joon): remove GLSL shaders, compile scripts, and prebuild steps"
```

---

### Task 6: Final Verification & PR

End-to-end verification that everything works identically to the GLSL version.

- [ ] **Step 1: Clean build from scratch**

Delete the `build/` directory and all `.spv` files:

```bat
cd projects\joon
rmdir /s /q build
del shaders\*.spv
premake5 vs2022
```

Build all four projects (joon-lib, joon-cli, joon-gui, joon-tests) in Debug config.

- [ ] **Step 2: Run tests**

Run `joon-tests`. Expected: all tests pass, including:
- "Evaluator runs a constant-output graph"
- "Param change produces different output after re-evaluate"
- "Param kwarg updates propagate through levels node"

- [ ] **Step 3: Run GUI**

Run `joon-gui`. Verify:
- Viewport shows noise texture on launch
- Dragging contrast slider updates viewport in real-time
- Check `joon-gui.log` for `[SLIDER]` and `[BIND]` messages
- No Vulkan validation errors in the log

- [ ] **Step 4: Verify DXC caching**

After the first run, `.spv` files should exist in `shaders/`. Kill and restart `joon-gui` — it should start faster (no recompilation). Verify by checking that no DXC process spawns (or check file timestamps).

- [ ] **Step 5: Push and create PR**

```bash
git push -u origin joon-3d-design
gh pr create --title "feat(joon): migrate compute shaders from GLSL to HLSL" --body "$(cat <<'EOF'
## Summary

- Ported all 10 compute shaders from GLSL to HLSL
- PipelineCache now compiles HLSL → SPIR-V via DXC at runtime (cached)
- Removed GLSL source files, compile scripts, and premake prebuild steps
- All existing tests pass identically

## Test plan

```bash
cd projects/joon
rmdir /s /q build
del shaders\*.spv
premake5 vs2022
# Build all in Visual Studio (Debug)
# Run joon-tests — all pass
# Run joon-gui — viewport renders, slider works, no validation errors
# Restart joon-gui — starts faster (cached .spv files)
```

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
