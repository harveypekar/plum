#pragma once

#include "vulkan/device.h"
#include <joon/types.h>
#include <unordered_map>

namespace joon {

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

    // Like alloc_image but adds COLOR_ATTACHMENT_BIT for use as a render target.
    // Same format default keeps the existing read_pixels() / compute pipeline
    // contract — render targets are sampleable and compute-writeable.
    GpuImage* alloc_render_target(uint32_t node_id, uint32_t width, uint32_t height,
                                   VkFormat format = VK_FORMAT_R32G32B32A32_SFLOAT);

    // Depth attachment with DEPTH_STENCIL_ATTACHMENT_BIT and depth-aspect view.
    GpuImage* alloc_depth(uint32_t node_id, uint32_t width, uint32_t height,
                           VkFormat format = VK_FORMAT_D32_SFLOAT);

    // Like alloc_depth but adds SAMPLED_BIT so the depth can be read in shaders.
    GpuImage* alloc_depth_sampled(uint32_t node_id, uint32_t width, uint32_t height,
                                   VkFormat format = VK_FORMAT_D32_SFLOAT);

    GpuImage* get_image(uint32_t node_id);

    void upload(GpuImage* img, const void* data, size_t size);
    void download(GpuImage* img, void* data, size_t size);

    void clear();

private:
    Device& m_device;
    std::unordered_map<uint32_t, GpuImage> m_images;
};

} // namespace joon
