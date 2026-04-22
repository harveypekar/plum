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

class PipelineCache {
public:
    explicit PipelineCache(Device& device, const std::string& shader_dir);
    ~PipelineCache();

    const ComputePipeline& get(const std::string& name,
                                uint32_t num_images,
                                uint32_t push_constant_size = 0);

private:
    Device& m_device;
    std::string m_shaderDir;
    std::unordered_map<std::string, ComputePipeline> m_pipelines;

    std::vector<uint8_t> load_or_compile(const std::string& name);
    bool needs_recompile(const std::string& hlsl_path, const std::string& spv_path);
    std::vector<uint8_t> compile_hlsl(const std::string& hlsl_path, const std::string& spv_path);
    std::vector<uint8_t> read_file(const std::string& path);
};

} // namespace joon
