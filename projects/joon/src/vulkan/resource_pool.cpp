#include "vulkan/resource_pool.h"
#include <cstring>
#include <stdexcept>

namespace joon::vk {

ResourcePool::ResourcePool(Device& device) : device_(device) {}

ResourcePool::~ResourcePool() { clear(); }

GpuImage* ResourcePool::alloc_image(uint32_t node_id, uint32_t width, uint32_t height,
                                     VkFormat format) {
    auto it = images_.find(node_id);
    if (it != images_.end()) {
        auto& old = it->second;
        if (old.width == width && old.height == height && old.format == format) {
            return &it->second; // reuse if same dimensions
        }
        vkDestroyImageView(device_.device, old.view, nullptr);
        vmaDestroyImage(device_.allocator, old.image, old.allocation);
        images_.erase(it);
    }

    GpuImage img{};
    img.width = width;
    img.height = height;
    img.format = format;

    VkImageCreateInfo img_info{};
    img_info.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    img_info.imageType = VK_IMAGE_TYPE_2D;
    img_info.format = format;
    img_info.extent = { width, height, 1 };
    img_info.mipLevels = 1;
    img_info.arrayLayers = 1;
    img_info.samples = VK_SAMPLE_COUNT_1_BIT;
    img_info.tiling = VK_IMAGE_TILING_OPTIMAL;
    img_info.usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
                     VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;

    VmaAllocationCreateInfo alloc_info{};
    alloc_info.usage = VMA_MEMORY_USAGE_GPU_ONLY;

    if (vmaCreateImage(device_.allocator, &img_info, &alloc_info,
                       &img.image, &img.allocation, nullptr) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate GPU image");
    }

    VkImageViewCreateInfo view_info{};
    view_info.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    view_info.image = img.image;
    view_info.viewType = VK_IMAGE_VIEW_TYPE_2D;
    view_info.format = format;
    view_info.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    view_info.subresourceRange.levelCount = 1;
    view_info.subresourceRange.layerCount = 1;

    vkCreateImageView(device_.device, &view_info, nullptr, &img.view);

    images_[node_id] = img;
    return &images_[node_id];
}

GpuImage* ResourcePool::get_image(uint32_t node_id) {
    auto it = images_.find(node_id);
    if (it == images_.end()) return nullptr;
    return &it->second;
}

void ResourcePool::upload(GpuImage* img, const void* data, size_t size) {
    VkBufferCreateInfo buf_info{};
    buf_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    buf_info.size = size;
    buf_info.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT;

    VmaAllocationCreateInfo alloc_info{};
    alloc_info.usage = VMA_MEMORY_USAGE_CPU_ONLY;

    VkBuffer staging;
    VmaAllocation staging_alloc;
    vmaCreateBuffer(device_.allocator, &buf_info, &alloc_info, &staging, &staging_alloc, nullptr);

    void* mapped;
    vmaMapMemory(device_.allocator, staging_alloc, &mapped);
    memcpy(mapped, data, size);
    vmaUnmapMemory(device_.allocator, staging_alloc);

    auto cmd = device_.begin_single_command();

    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.image = img->image;
    barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                         VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &barrier);

    VkBufferImageCopy region{};
    region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    region.imageSubresource.layerCount = 1;
    region.imageExtent = { img->width, img->height, 1 };
    vkCmdCopyBufferToImage(cmd, staging, img->image,
                           VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

    barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &barrier);

    device_.end_single_command(cmd);
    vmaDestroyBuffer(device_.allocator, staging, staging_alloc);
}

void ResourcePool::download(GpuImage* img, void* data, size_t size) {
    VkBufferCreateInfo buf_info{};
    buf_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    buf_info.size = size;
    buf_info.usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT;

    VmaAllocationCreateInfo alloc_info{};
    alloc_info.usage = VMA_MEMORY_USAGE_CPU_ONLY;

    VkBuffer staging;
    VmaAllocation staging_alloc;
    vmaCreateBuffer(device_.allocator, &buf_info, &alloc_info, &staging, &staging_alloc, nullptr);

    auto cmd = device_.begin_single_command();

    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.oldLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    barrier.image = img->image;
    barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
    barrier.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &barrier);

    VkBufferImageCopy region{};
    region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    region.imageSubresource.layerCount = 1;
    region.imageExtent = { img->width, img->height, 1 };
    vkCmdCopyImageToBuffer(cmd, img->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           staging, 1, &region);

    device_.end_single_command(cmd);

    void* mapped;
    vmaMapMemory(device_.allocator, staging_alloc, &mapped);
    memcpy(data, mapped, size);
    vmaUnmapMemory(device_.allocator, staging_alloc);

    vmaDestroyBuffer(device_.allocator, staging, staging_alloc);
}

void ResourcePool::clear() {
    for (auto& [id, img] : images_) {
        vkDestroyImageView(device_.device, img.view, nullptr);
        vmaDestroyImage(device_.allocator, img.image, img.allocation);
    }
    images_.clear();
}

} // namespace joon::vk
