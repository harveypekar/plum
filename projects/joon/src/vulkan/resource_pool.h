#pragma once

#include "vulkan/device.h"
#include <joon/types.h>
#include <unordered_map>

namespace joon::vk {

struct GpuImage {
    VkImage image = VK_NULL_HANDLE;
    VkImageView view = VK_NULL_HANDLE;
    VmaAllocation allocation = VK_NULL_HANDLE;
    uint32_t width, height;
    VkFormat format;
};

class ResourcePool {
public:
    explicit ResourcePool(Device& device);
    ~ResourcePool();

    GpuImage* alloc_image(uint32_t node_id, uint32_t width, uint32_t height,
                          VkFormat format = VK_FORMAT_R32G32B32A32_SFLOAT);

    GpuImage* get_image(uint32_t node_id);

    void upload(GpuImage* img, const void* data, size_t size);
    void download(GpuImage* img, void* data, size_t size);

    void clear();

private:
    Device& device_;
    std::unordered_map<uint32_t, GpuImage> images_;
};

} // namespace joon::vk
