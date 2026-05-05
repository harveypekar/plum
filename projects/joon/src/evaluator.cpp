#include <joon/evaluator.h>
#include <joon/context.h>
#include <joon/graph.h>
#include <joon/scene.h>
#include "ir/ir_graph.h"
#include "interpreter/interpreter.h"
#include "nodes/node_registry.h"
#include "scene/texture_cache.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include "vulkan/pipeline_cache.h"

#include "util/exe_dir.h"

#include <stb/stb_image_write.h>

#include <algorithm>
#include <filesystem>

namespace joon {

// --- Result implementation ---

Result::Result(ResourcePool& pool, uint32_t node_id)
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
    if (m_nodeId == UINT32_MAX) return *this;
    auto& ir = m_graph.ir();
    if (m_nodeId >= ir.nodes.size()) return *this;
    for (auto& p : ir.params) {
        if (p.node_id == m_nodeId) {
            p.default_value = value;
            ir.nodes[m_nodeId].constant_value = value;
            break;
        }
    }
    return *this;
}

template<>
Param<float>::operator float() const {
    auto& ir = m_graph.ir();
    if (m_nodeId >= ir.nodes.size()) return 0.0f;
    return value_as_float(ir.nodes[m_nodeId].constant_value);
}

static std::string resolve_shader_dir() {
    namespace fs = std::filesystem;
    if (fs::is_directory("shaders")) return "shaders";
    auto from_exe = fs::path(joon::exe_dir()) / ".." / ".." / ".." / "shaders";
    if (fs::is_directory(from_exe)) return from_exe.string();
    return "shaders";
}

// --- Evaluator implementation ---

struct Evaluator::Impl {
    Context& ctx;
    Graph graph;
    NodeRegistry registry;
    std::unique_ptr<PipelineCache> pipelines;
    std::unique_ptr<TextureCache> textures;
    VkDescriptorPool desc_pool = VK_NULL_HANDLE;
    SceneCollection scene;
    Camera camera_override_storage;
    bool has_camera_override = false;

    Impl(Context& ctx, const Graph& source_graph)
        : ctx(ctx),
          registry(NodeRegistry::create_default()),
          pipelines(std::make_unique<PipelineCache>(ctx.device(), resolve_shader_dir())),
          textures(std::make_unique<TextureCache>(ctx.device())) {

        graph = ctx.parse_string("");
        graph.ir() = source_graph.ir();

        VkDescriptorPoolSize pool_sizes[4]{};
        pool_sizes[0].type = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        pool_sizes[0].descriptorCount = 256;
        pool_sizes[1].type = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
        pool_sizes[1].descriptorCount = 512;
        pool_sizes[2].type = VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE;
        pool_sizes[2].descriptorCount = 512;
        pool_sizes[3].type = VK_DESCRIPTOR_TYPE_SAMPLER;
        pool_sizes[3].descriptorCount = 512;

        VkDescriptorPoolCreateInfo pool_info{};
        pool_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
        pool_info.maxSets = 512;
        pool_info.poolSizeCount = 4;
        pool_info.pPoolSizes = pool_sizes;
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
    vkResetDescriptorPool(m_impl->ctx.device().device, m_impl->desc_pool, 0);

    m_impl->scene.clear();

    EvalContext eval_ctx{
        m_impl->ctx.device(),
        m_impl->ctx.pool(),
        *m_impl->pipelines,
        512, 512,
        m_impl->desc_pool,
        m_impl->scene,
        &m_impl->graph.ir().shader_defs,
        {},
        {},
        m_impl->has_camera_override ? &m_impl->camera_override_storage : nullptr,
        m_impl->textures.get()
    };

    Interpreter interp(eval_ctx, m_impl->registry);
    interp.evaluate(m_impl->graph.ir());
}

void Evaluator::re_render() {
    vkResetDescriptorPool(m_impl->ctx.device().device, m_impl->desc_pool, 0);

    if (m_impl->has_camera_override)
        m_impl->scene.set_camera(m_impl->camera_override_storage);

    EvalContext eval_ctx{
        m_impl->ctx.device(),
        m_impl->ctx.pool(),
        *m_impl->pipelines,
        512, 512,
        m_impl->desc_pool,
        m_impl->scene,
        &m_impl->graph.ir().shader_defs,
        {},
        {},
        nullptr,
        m_impl->textures.get()
    };

    Interpreter interp(eval_ctx, m_impl->registry);
    interp.re_render(m_impl->graph.ir());
}

template<>
Param<float> Evaluator::param(const std::string& name) {
    auto& ir = m_impl->graph.ir();
    for (auto& p : ir.params) {
        if (p.name == name) {
            return Param<float>(p.node_id, m_impl->graph);
        }
    }
    return Param<float>(UINT32_MAX, m_impl->graph);
}

Result Evaluator::result(const std::string& name) {
    auto& ir = m_impl->graph.ir();
    for (auto& out : ir.outputs) {
        auto* node = ir.find_node(out.node_id);
        if (node && node->name == name)
            return Result(m_impl->ctx.pool(), out.node_id);
    }
    if (!ir.outputs.empty())
        return Result(m_impl->ctx.pool(), ir.outputs[0].node_id);
    return Result(m_impl->ctx.pool(), UINT32_MAX);
}

Result Evaluator::node_result(const std::string& name) {
    auto* node = m_impl->graph.ir().find_node_by_name(name);
    if (node) return Result(m_impl->ctx.pool(), node->id);
    return Result(m_impl->ctx.pool(), UINT32_MAX);
}

const std::vector<Diagnostic>& Evaluator::diagnostics() const {
    return m_impl->graph.ir().diagnostics;
}

void Evaluator::set_camera(const Camera& cam) {
    m_impl->camera_override_storage = cam;
    m_impl->has_camera_override = true;
}

void Evaluator::clear_camera_override() {
    m_impl->has_camera_override = false;
}

const SceneCollection& Evaluator::scene_for_test() const {
    return m_impl->scene;
}

} // namespace joon
