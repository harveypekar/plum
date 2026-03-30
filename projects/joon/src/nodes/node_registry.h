#pragma once

#include "ir/node.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include "vulkan/pipeline_cache.h"
#include <functional>
#include <string>
#include <unordered_map>

namespace joon::nodes {

struct EvalContext {
    vk::Device& device;
    vk::ResourcePool& pool;
    vk::PipelineCache& pipelines;
    uint32_t default_width;
    uint32_t default_height;
    VkDescriptorPool desc_pool;
};

using NodeExecutor = std::function<void(const ir::Node& node, EvalContext& ctx)>;

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

} // namespace joon::nodes
