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
