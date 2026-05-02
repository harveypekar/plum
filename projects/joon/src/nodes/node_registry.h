#pragma once

#include "ir/node.h"
#include "ir/ir_graph.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include "vulkan/pipeline_cache.h"
#include <functional>
#include <string>
#include <unordered_map>

namespace joon {

struct SceneCollection;

struct EvalContext {
    Device& device;
    ResourcePool& pool;
    PipelineCache& pipelines;
    uint32_t default_width;
    uint32_t default_height;
    VkDescriptorPool desc_pool;
    SceneCollection& scene;
    std::unordered_map<uint32_t, ShaderDef>* shader_defs = nullptr;
    std::unordered_map<uint32_t, const GraphicsPipeline*> material_pipelines;
};

using NodeExecutor = std::function<void(const Node& node, EvalContext& ctx)>;

class NodeRegistry {
public:
    void register_node(const std::string& op, NodeExecutor executor);
    const NodeExecutor* find(const std::string& op) const;

    static NodeRegistry create_default();

private:
    std::unordered_map<std::string, NodeExecutor> m_executors;
};

void register_image_load(NodeRegistry& reg);
void register_noise(NodeRegistry& reg);
void register_color(NodeRegistry& reg);
void register_math_ops(NodeRegistry& reg);
void register_image_ops(NodeRegistry& reg);
void register_save(NodeRegistry& reg);
void register_scene_nodes(NodeRegistry& reg);
void register_geometry_pass(NodeRegistry& reg);
void register_material_nodes(NodeRegistry& reg);

} // namespace joon
