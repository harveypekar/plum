#pragma once

#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include <memory>
#include <string>
#include <unordered_map>

namespace joon {

class TextureCache {
public:
    explicit TextureCache(Device& device);
    ~TextureCache();

    GpuImage* load(const std::string& path);
    GpuImage* default_albedo();
    GpuImage* default_normal();
    VkSampler sampler() const { return m_sampler; }

private:
    Device& m_device;
    VkSampler m_sampler = VK_NULL_HANDLE;
    std::unordered_map<std::string, std::unique_ptr<GpuImage>> m_textures;

    GpuImage upload_rgba8(const uint8_t* data, uint32_t w, uint32_t h,
                          VkFormat format);
    void create_defaults();
    bool m_defaults_created = false;
    GpuImage m_default_albedo{};
    GpuImage m_default_normal{};
};

} // namespace joon
