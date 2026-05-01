#include "vulkan/pipeline_cache.h"
#include <joon/scene.h>
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
    for (auto& [name, p] : m_graphics_pipelines) {
        vkDestroyPipeline(m_device.device, p.pipeline, nullptr);
        vkDestroyPipelineLayout(m_device.device, p.layout, nullptr);
        vkDestroyDescriptorSetLayout(m_device.device, p.desc_layout, nullptr);
        vkDestroyShaderModule(m_device.device, p.vert_module, nullptr);
        vkDestroyShaderModule(m_device.device, p.frag_module, nullptr);
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
                                                   const std::string& spv_path,
                                                   const std::string& target_profile) {
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
        + " -T " + target_profile + " -E main -spirv -fspv-target-env=vulkan1.1"
        + " \"" + hlsl_path + "\""
        + " -Fo \"" + spv_path + "\""
        + " 2>&1";

#ifdef _WIN32
    // cmd.exe /c strips the outer quotes around an argv[0] when the entire
    // command starts and ends with a quote, mangling our path. Wrap the whole
    // command in an extra pair so the inner quoting survives.
    cmd = "\"" + cmd + "\"";
#endif

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
            return compile_hlsl(hlsl_path, spv_path, "cs_6_0");
        return read_file(spv_path);
    }

    if (fs::exists(spv_path))
        return read_file(spv_path);

    throw std::runtime_error("No shader source found: " + name);
}

std::vector<uint8_t> PipelineCache::load_or_compile_stage(const std::string& base_name,
                                                            const std::string& stage,
                                                            const std::string& target_profile) {
    // e.g. base_name="scene_basic", stage="vert" → "scene_basic.vert.hlsl" / ".vert.spv"
    std::string hlsl_path = m_shaderDir + "/" + base_name + "." + stage + ".hlsl";
    std::string spv_path  = m_shaderDir + "/" + base_name + "." + stage + ".spv";

    if (!fs::exists(hlsl_path))
        throw std::runtime_error("Graphics shader source missing: " + hlsl_path);
    if (needs_recompile(hlsl_path, spv_path))
        return compile_hlsl(hlsl_path, spv_path, target_profile);
    return read_file(spv_path);
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

const GraphicsPipeline& PipelineCache::get_graphics(const std::string& name,
                                                     VkRenderPass render_pass,
                                                     uint32_t push_constant_size) {
    std::string key = name + ":" + std::to_string(reinterpret_cast<uintptr_t>(render_pass))
                    + ":" + std::to_string(push_constant_size);
    auto it = m_graphics_pipelines.find(key);
    if (it != m_graphics_pipelines.end()) return it->second;

    GraphicsPipeline p{};

    // Compile both stages.
    auto vs_spirv = load_or_compile_stage(name, "vert", "vs_6_0");
    auto fs_spirv = load_or_compile_stage(name, "frag", "ps_6_0");

    auto make_module = [&](const std::vector<uint8_t>& spirv, const char* what) {
        if (spirv.size() % 4 != 0)
            throw std::runtime_error(std::string("SPIR-V size not multiple of 4: ") + what);
        VkShaderModuleCreateInfo info{};
        info.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
        info.codeSize = spirv.size();
        info.pCode = reinterpret_cast<const uint32_t*>(spirv.data());
        VkShaderModule mod = VK_NULL_HANDLE;
        if (vkCreateShaderModule(m_device.device, &info, nullptr, &mod) != VK_SUCCESS)
            throw std::runtime_error(std::string("vkCreateShaderModule failed: ") + what);
        return mod;
    };
    p.vert_module = make_module(vs_spirv, (name + ".vert").c_str());
    p.frag_module = make_module(fs_spirv, (name + ".frag").c_str());

    // Descriptor set layout — single UBO at binding 0, vertex stage.
    VkDescriptorSetLayoutBinding ubo_binding{};
    ubo_binding.binding = 0;
    ubo_binding.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    ubo_binding.descriptorCount = 1;
    ubo_binding.stageFlags = VK_SHADER_STAGE_VERTEX_BIT;

    VkDescriptorSetLayoutCreateInfo desc_info{};
    desc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    desc_info.bindingCount = 1;
    desc_info.pBindings = &ubo_binding;
    if (vkCreateDescriptorSetLayout(m_device.device, &desc_info, nullptr, &p.desc_layout) != VK_SUCCESS)
        throw std::runtime_error("graphics: vkCreateDescriptorSetLayout failed");

    // Pipeline layout — descriptor set + optional push constants (fragment stage).
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
    if (vkCreatePipelineLayout(m_device.device, &layout_info, nullptr, &p.layout) != VK_SUCCESS)
        throw std::runtime_error("graphics: vkCreatePipelineLayout failed");

    // Vertex input — matches joon::Vertex {position, normal, uv}.
    VkVertexInputBindingDescription vb_desc{};
    vb_desc.binding = 0;
    vb_desc.stride = sizeof(Vertex);
    vb_desc.inputRate = VK_VERTEX_INPUT_RATE_VERTEX;

    VkVertexInputAttributeDescription va_desc[3]{};
    va_desc[0].binding = 0;
    va_desc[0].location = 0;
    va_desc[0].format = VK_FORMAT_R32G32B32_SFLOAT;
    va_desc[0].offset = offsetof(Vertex, position);
    va_desc[1].binding = 0;
    va_desc[1].location = 1;
    va_desc[1].format = VK_FORMAT_R32G32B32_SFLOAT;
    va_desc[1].offset = offsetof(Vertex, normal);
    va_desc[2].binding = 0;
    va_desc[2].location = 2;
    va_desc[2].format = VK_FORMAT_R32G32_SFLOAT;
    va_desc[2].offset = offsetof(Vertex, uv);

    VkPipelineVertexInputStateCreateInfo vi{};
    vi.sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO;
    vi.vertexBindingDescriptionCount = 1;
    vi.pVertexBindingDescriptions = &vb_desc;
    vi.vertexAttributeDescriptionCount = 3;
    vi.pVertexAttributeDescriptions = va_desc;

    VkPipelineInputAssemblyStateCreateInfo ia{};
    ia.sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO;
    ia.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;

    VkPipelineViewportStateCreateInfo vp{};
    vp.sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO;
    vp.viewportCount = 1;
    vp.scissorCount = 1;

    VkPipelineRasterizationStateCreateInfo rs{};
    rs.sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO;
    rs.polygonMode = VK_POLYGON_MODE_FILL;
    rs.cullMode = VK_CULL_MODE_BACK_BIT;
    rs.frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE;
    rs.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo ms{};
    ms.sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO;
    ms.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;

    VkPipelineDepthStencilStateCreateInfo ds{};
    ds.sType = VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO;
    ds.depthTestEnable = VK_TRUE;
    ds.depthWriteEnable = VK_TRUE;
    ds.depthCompareOp = VK_COMPARE_OP_LESS;

    VkPipelineColorBlendAttachmentState cba{};
    cba.colorWriteMask = VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT
                       | VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT;
    cba.blendEnable = VK_FALSE;

    VkPipelineColorBlendStateCreateInfo cb{};
    cb.sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO;
    cb.attachmentCount = 1;
    cb.pAttachments = &cba;

    // Dynamic viewport+scissor — set per draw via vkCmdSetViewport/Scissor.
    VkDynamicState dyn_states[2] = { VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR };
    VkPipelineDynamicStateCreateInfo dyn{};
    dyn.sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO;
    dyn.dynamicStateCount = 2;
    dyn.pDynamicStates = dyn_states;

    VkPipelineShaderStageCreateInfo stages[2]{};
    stages[0].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[0].stage = VK_SHADER_STAGE_VERTEX_BIT;
    stages[0].module = p.vert_module;
    stages[0].pName = "main";
    stages[1].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[1].stage = VK_SHADER_STAGE_FRAGMENT_BIT;
    stages[1].module = p.frag_module;
    stages[1].pName = "main";

    VkGraphicsPipelineCreateInfo gp_info{};
    gp_info.sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO;
    gp_info.stageCount = 2;
    gp_info.pStages = stages;
    gp_info.pVertexInputState = &vi;
    gp_info.pInputAssemblyState = &ia;
    gp_info.pViewportState = &vp;
    gp_info.pRasterizationState = &rs;
    gp_info.pMultisampleState = &ms;
    gp_info.pDepthStencilState = &ds;
    gp_info.pColorBlendState = &cb;
    gp_info.pDynamicState = &dyn;
    gp_info.layout = p.layout;
    gp_info.renderPass = render_pass;
    gp_info.subpass = 0;

    if (vkCreateGraphicsPipelines(m_device.device, VK_NULL_HANDLE, 1, &gp_info, nullptr,
                                   &p.pipeline) != VK_SUCCESS)
        throw std::runtime_error("vkCreateGraphicsPipelines failed: " + name);

    m_graphics_pipelines[key] = p;
    return m_graphics_pipelines[key];
}

} // namespace joon
