#pragma once
#include "vulkan/device.h"
#include "vulkan/pipeline_cache.h"
#include "vulkan/resource_pool.h"
#include "shader/shader_ir.h"
#include <joon/scene.h>
#include <joon/math.h>

namespace joon {

struct LightingPassConfig {
    Device& device;
    PipelineCache& pipelines;
    ResourcePool& pool;
    VkDescriptorPool desc_pool;
    const SceneCollection& scene;
    uint32_t width, height;
    GpuImage* albedo_target;
    GpuImage* normal_target;
    uint32_t output_node_id;
    const ShaderFnIR* brdf = nullptr;
};

void dispatch_lighting_pass(const LightingPassConfig& cfg);

} // namespace joon
