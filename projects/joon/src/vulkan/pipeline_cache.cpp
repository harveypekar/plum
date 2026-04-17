#include "vulkan/pipeline_cache.h"
#include <fstream>
#include <stdexcept>

namespace joon {

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

std::vector<uint8_t> PipelineCache::read_spirv(const std::string& name) {
    std::string path = m_shaderDir + "/" + name + ".spv";
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file.is_open()) throw std::runtime_error("Cannot open shader: " + path);
    size_t size = file.tellg();
    std::vector<uint8_t> data(size);
    file.seekg(0);
    file.read(reinterpret_cast<char*>(data.data()), size);
    return data;
}

const ComputePipeline& PipelineCache::get(const std::string& name,
                                           uint32_t num_images,
                                           uint32_t push_constant_size) {
    std::string key = name + ":" + std::to_string(num_images) + ":" + std::to_string(push_constant_size);
    auto it = m_pipelines.find(key);
    if (it != m_pipelines.end()) return it->second;

    ComputePipeline p{};

    auto spirv = read_spirv(name);
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
