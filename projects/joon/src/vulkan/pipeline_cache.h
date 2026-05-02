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

struct GraphicsPipeline {
    VkShaderModule vert_module = VK_NULL_HANDLE;
    VkShaderModule frag_module = VK_NULL_HANDLE;
    VkDescriptorSetLayout desc_layout = VK_NULL_HANDLE;
    VkPipelineLayout layout = VK_NULL_HANDLE;
    VkPipeline pipeline = VK_NULL_HANDLE;
};

class PipelineCache {
public:
    explicit PipelineCache(Device& device, const std::string& shader_dir);
    ~PipelineCache();

    const ComputePipeline& get(const std::string& name,
                                uint32_t num_images,
                                uint32_t push_constant_size = 0);

    // Get-or-create a graphics pipeline keyed by name + render-pass handle.
    // Compiles `<name>.vert.hlsl` and `<name>.frag.hlsl` via DXC at first use.
    // Vertex input is hardcoded for joon::Vertex {position, normal, uv}.
    // Descriptor set 0 binding 0 = UBO (vertex stage).
    // Push constants in `push_constant_size` bytes go to the FRAGMENT stage.
    const GraphicsPipeline& get_graphics(const std::string& name,
                                          VkRenderPass render_pass,
                                          uint32_t push_constant_size = 0);

    const GraphicsPipeline& get_graphics_from_source(
        const std::string& key,
        const std::string& vert_hlsl_source,
        const std::string& frag_hlsl_source,
        VkRenderPass render_pass,
        uint32_t push_constant_size = 0,
        uint32_t num_color_attachments = 1);

    // Fullscreen triangle pipeline — uses fullscreen.vert.hlsl + frag_name.frag.hlsl.
    // No vertex input, no depth test, no backface culling.
    // Descriptor layout: binding 0 = SAMPLED_IMAGE, binding 1 = SAMPLER, binding 2 = UNIFORM_BUFFER.
    const GraphicsPipeline& get_fullscreen(const std::string& frag_name,
                                            VkRenderPass render_pass);

private:
    Device& m_device;
    std::string m_shaderDir;
    std::unordered_map<std::string, ComputePipeline> m_pipelines;
    std::unordered_map<std::string, GraphicsPipeline> m_graphics_pipelines;

    std::vector<uint8_t> load_or_compile(const std::string& name);
    bool needs_recompile(const std::string& hlsl_path, const std::string& spv_path);
    std::vector<uint8_t> compile_hlsl(const std::string& hlsl_path,
                                       const std::string& spv_path,
                                       const std::string& target_profile = "cs_6_0");
    std::vector<uint8_t> load_or_compile_stage(const std::string& base_name,
                                                const std::string& stage,
                                                const std::string& target_profile);
    std::vector<uint8_t> read_file(const std::string& path);

    VkPipeline build_graphics_pipeline(VkShaderModule vert_module,
                                        VkShaderModule frag_module,
                                        VkPipelineLayout layout,
                                        VkRenderPass render_pass,
                                        uint32_t num_color_attachments);
};

} // namespace joon
