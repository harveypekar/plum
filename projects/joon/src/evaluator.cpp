#include <joon/evaluator.h>
#include <joon/context.h>
#include <joon/graph.h>
#include "ir/ir_graph.h"
#include "interpreter/interpreter.h"
#include "nodes/node_registry.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include "vulkan/pipeline_cache.h"

#define STB_IMAGE_WRITE_STATIC
#include <stb/stb_image_write.h>

#include <algorithm>

namespace joon {

// --- Result implementation ---

Result::Result(vk::ResourcePool& pool, uint32_t node_id)
    : pool_(pool), node_id_(node_id) {}

uint32_t Result::width() const {
    auto* img = pool_.get_image(node_id_);
    return img ? img->width : 0;
}

uint32_t Result::height() const {
    auto* img = pool_.get_image(node_id_);
    return img ? img->height : 0;
}

void* Result::vk_image_view() const {
    auto* img = pool_.get_image(node_id_);
    return img ? (void*)img->view : nullptr;
}

std::vector<float> Result::read_pixels() {
    auto* img = pool_.get_image(node_id_);
    if (!img) return {};

    size_t pixel_count = img->width * img->height;
    std::vector<float> data(pixel_count * 4);
    pool_.download(img, data.data(), data.size() * sizeof(float));
    return data;
}

void Result::save_image(const char* path) {
    auto* img = pool_.get_image(node_id_);
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
    auto& ir = graph_.ir();
    for (auto& p : ir.params) {
        if (p.node_id == node_id_) {
            p.default_value = value;
            ir.nodes[node_id_].constant_value = value;
            break;
        }
    }
    return *this;
}

template<>
Param<float>::operator float() const {
    auto& ir = graph_.ir();
    return std::get<float>(ir.nodes[node_id_].constant_value);
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

        // Copy the graph so we can mutate params
        graph = ctx.parse_string(""); // placeholder
        graph.ir() = source_graph.ir(); // copy IR

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
    : impl_(std::make_unique<Impl>(ctx, graph)) {}

Evaluator::~Evaluator() = default;

void Evaluator::evaluate() {
    vkResetDescriptorPool(impl_->ctx.device().device, impl_->desc_pool, 0);

    nodes::EvalContext eval_ctx{
        impl_->ctx.device(),
        impl_->ctx.pool(),
        *impl_->pipelines,
        512, 512,
        impl_->desc_pool
    };

    Interpreter interp(eval_ctx, impl_->registry);
    interp.evaluate(impl_->graph.ir());
}

template<>
Param<float> Evaluator::param(const std::string& name) {
    auto& ir = impl_->graph.ir();
    for (auto& p : ir.params) {
        if (p.name == name) {
            return Param<float>(p.node_id, impl_->graph);
        }
    }
    // Not found — return a dummy param pointing at node 0
    return Param<float>(0, impl_->graph);
}

Result Evaluator::result(const std::string& name) {
    auto& ir = impl_->graph.ir();
    if (!ir.outputs.empty()) {
        return Result(impl_->ctx.pool(), ir.outputs[0].node_id);
    }
    return Result(impl_->ctx.pool(), 0);
}

Result Evaluator::node_result(const std::string& name) {
    auto* node = impl_->graph.ir().find_node_by_name(name);
    if (node) return Result(impl_->ctx.pool(), node->id);
    return Result(impl_->ctx.pool(), 0);
}

const std::vector<ir::Diagnostic>& Evaluator::diagnostics() const {
    return impl_->graph.ir().diagnostics;
}

} // namespace joon
