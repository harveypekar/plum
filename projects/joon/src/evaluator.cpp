#include <joon/evaluator.h>
#include <joon/context.h>
#include <joon/graph.h>
#include "ir/ir_graph.h"
#include "interpreter/interpreter.h"
#include "nodes/node_registry.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include "vulkan/pipeline_cache.h"

#include <stb/stb_image_write.h>

#include <algorithm>
#include <cstdio>

namespace joon {

// --- Result implementation ---

Result::Result(vk::ResourcePool& pool, uint32_t node_id)
    : m_pool(pool), m_nodeId(node_id) {}

uint32_t Result::width() const {
    auto* img = m_pool.get_image(m_nodeId);
    return img ? img->width : 0;
}

uint32_t Result::height() const {
    auto* img = m_pool.get_image(m_nodeId);
    return img ? img->height : 0;
}

void* Result::vk_image_view() const {
    auto* img = m_pool.get_image(m_nodeId);
    return img ? (void*)img->view : nullptr;
}

std::vector<float> Result::read_pixels() {
    auto* img = m_pool.get_image(m_nodeId);
    if (!img) return {};

    size_t pixel_count = img->width * img->height;
    std::vector<float> data(pixel_count * 4);
    m_pool.download(img, data.data(), data.size() * sizeof(float));
    return data;
}

void Result::save_image(const char* path) {
    auto* img = m_pool.get_image(m_nodeId);
    if (!img) return;

    auto float_data = read_pixels();
    std::vector<uint8_t> byte_data(float_data.size());
    for (size_t i = 0; i < float_data.size(); i++) {
        byte_data[i] = static_cast<uint8_t>(
            std::clamp(float_data[i] * 255.0f, 0.0f, 255.0f));
    }

    stbi_write_png(path, img->width, img->height, 4,
                   byte_data.data(), img->width * 4);
}

// --- Param<float> specialization ---

template<>
Param<float>& Param<float>::operator=(const float& value) {
    auto& ir = m_graph.ir();
    for (auto& p : ir.params) {
        if (p.node_id == m_nodeId) {
            p.default_value = value;
            if (m_nodeId < ir.nodes.size()) {
                ir.nodes[m_nodeId].constant_value = value;
            }
            break;
        }
    }
    return *this;
}

template<>
Param<float>::operator float() const {
    auto& ir = m_graph.ir();
    if (m_nodeId < ir.nodes.size()) {
        auto* val = std::get_if<float>(&ir.nodes[m_nodeId].constant_value);
        if (val) return *val;
    }
    return 0.0f;
}

// --- Evaluator implementation ---

struct Evaluator::Impl {
    Context& ctx;
    Graph graph; // mutable copy for param updates
    nodes::NodeRegistry registry;
    std::unique_ptr<vk::PipelineCache> pipelines;
    VkDescriptorPool desc_pool = VK_NULL_HANDLE;

    Impl(Context& ctx, const Graph& source_graph)
        : ctx(ctx),
          registry(nodes::NodeRegistry::create_default()),
          pipelines(std::make_unique<vk::PipelineCache>(ctx.device(), "shaders")) {

        // Copy the IR so we can mutate params during evaluation.
        // Graph default-constructs with a valid empty impl.
        graph.ir() = source_graph.ir();

        VkDescriptorPoolSize pool_size{};
        pool_size.type = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        pool_size.descriptorCount = 256;

        VkDescriptorPoolCreateInfo pool_info{};
        pool_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
        pool_info.maxSets = 128;
        pool_info.poolSizeCount = 1;
        pool_info.pPoolSizes = &pool_size;
        pool_info.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;
        vkCreateDescriptorPool(ctx.device().device, &pool_info, nullptr, &desc_pool);
    }

    ~Impl() {
        if (desc_pool) {
            vkDestroyDescriptorPool(ctx.device().device, desc_pool, nullptr);
        }
    }
};

Evaluator::Evaluator(Context& ctx, const Graph& graph)
    : m_impl(std::make_unique<Impl>(ctx, graph)) {}

Evaluator::~Evaluator() = default;

void Evaluator::evaluate() {
    vkDeviceWaitIdle(m_impl->ctx.device().device);
    vkResetDescriptorPool(m_impl->ctx.device().device, m_impl->desc_pool, 0);

    auto& ir = m_impl->graph.ir();
    {
        FILE* f = fopen("joon.log", "a");
        if (f) {
            fprintf(f, "[eval] nodes=%d edges=%d outputs=%d\n",
                    (int)ir.nodes.size(), (int)ir.edges.size(), (int)ir.outputs.size());
            for (size_t i = 0; i < ir.nodes.size(); i++) {
                fprintf(f, "[eval]   node[%d] op=%s const=%d\n",
                        (int)i, ir.nodes[i].op.c_str(), ir.nodes[i].is_constant);
            }
            fclose(f);
        }
    }

    nodes::EvalContext eval_ctx{
        m_impl->ctx.device(),
        m_impl->ctx.pool(),
        *m_impl->pipelines,
        512, 512,
        m_impl->desc_pool
    };

    Interpreter interp(eval_ctx, m_impl->registry);
    interp.evaluate(ir);

    {
        FILE* f = fopen("joon.log", "a");
        if (f) {
            for (size_t i = 0; i < ir.nodes.size(); i++) {
                auto* img = m_impl->ctx.pool().get_image((uint32_t)i);
                fprintf(f, "[eval]   pool[%d]=%p\n", (int)i, (void*)img);
            }
            fclose(f);
        }
    }
}

template<>
Param<float> Evaluator::param(const std::string& name) {
    auto& ir = m_impl->graph.ir();
    for (auto& p : ir.params) {
        if (p.name == name) {
            return Param<float>(p.node_id, m_impl->graph);
        }
    }
    // Not found — return a dummy param pointing at node 0
    return Param<float>(0, m_impl->graph);
}

Result Evaluator::result(const std::string& name) {
    auto& ir = m_impl->graph.ir();
    if (!ir.outputs.empty()) {
        return Result(m_impl->ctx.pool(), ir.outputs[0].node_id);
    }
    return Result(m_impl->ctx.pool(), 0);
}

Result Evaluator::node_result(const std::string& name) {
    auto* node = m_impl->graph.ir().find_node_by_name(name);
    if (node) return Result(m_impl->ctx.pool(), node->id);
    return Result(m_impl->ctx.pool(), 0);
}

const std::vector<ir::Diagnostic>& Evaluator::diagnostics() const {
    return m_impl->graph.ir().diagnostics;
}

} // namespace joon
