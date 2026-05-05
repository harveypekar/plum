#include "scene/texture_cache.h"
#include <stb/stb_image.h>
#include <cstring>
#include <stdexcept>

namespace joon {

TextureCache::TextureCache(Device& device) : m_device(device) {
    VkSamplerCreateInfo si{};
    si.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    si.magFilter = VK_FILTER_LINEAR;
    si.minFilter = VK_FILTER_LINEAR;
    si.mipmapMode = VK_SAMPLER_MIPMAP_MODE_LINEAR;
    si.addressModeU = VK_SAMPLER_ADDRESS_MODE_REPEAT;
    si.addressModeV = VK_SAMPLER_ADDRESS_MODE_REPEAT;
    si.addressModeW = VK_SAMPLER_ADDRESS_MODE_REPEAT;
    si.maxAnisotropy = 1.0f;
    vkCreateSampler(device.device, &si, nullptr, &m_sampler);
}

TextureCache::~TextureCache() {
    for (auto& [path, img] : m_textures) {
        vkDestroyImageView(m_device.device, img->view, nullptr);
        vmaDestroyImage(m_device.allocator, img->image, img->allocation);
    }
    if (m_defaults_created) {
        vkDestroyImageView(m_device.device, m_default_albedo.view, nullptr);
        vmaDestroyImage(m_device.allocator, m_default_albedo.image,
                        m_default_albedo.allocation);
        vkDestroyImageView(m_device.device, m_default_normal.view, nullptr);
        vmaDestroyImage(m_device.allocator, m_default_normal.image,
                        m_default_normal.allocation);
    }
    if (m_sampler)
        vkDestroySampler(m_device.device, m_sampler, nullptr);
}

GpuImage TextureCache::upload_rgba8(const uint8_t* data, uint32_t w, uint32_t h,
                                    VkFormat format) {
    GpuImage img{};
    img.width = w;
    img.height = h;
    img.format = format;

    VkImageCreateInfo img_info{};
    img_info.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    img_info.imageType = VK_IMAGE_TYPE_2D;
    img_info.format = format;
    img_info.extent = {w, h, 1};
    img_info.mipLevels = 1;
    img_info.arrayLayers = 1;
    img_info.samples = VK_SAMPLE_COUNT_1_BIT;
    img_info.tiling = VK_IMAGE_TILING_OPTIMAL;
    img_info.usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;

    VmaAllocationCreateInfo alloc_info{};
    alloc_info.usage = VMA_MEMORY_USAGE_GPU_ONLY;

    if (vmaCreateImage(m_device.allocator, &img_info, &alloc_info,
                       &img.image, &img.allocation, nullptr) != VK_SUCCESS)
        throw std::runtime_error("TextureCache: failed to allocate image");

    VkImageViewCreateInfo view_info{};
    view_info.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    view_info.image = img.image;
    view_info.viewType = VK_IMAGE_VIEW_TYPE_2D;
    view_info.format = format;
    view_info.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    view_info.subresourceRange.levelCount = 1;
    view_info.subresourceRange.layerCount = 1;
    if (vkCreateImageView(m_device.device, &view_info, nullptr, &img.view) !=
        VK_SUCCESS)
        throw std::runtime_error("TextureCache: failed to create image view");

    size_t byte_size = w * h * 4;

    VkBufferCreateInfo buf_info{};
    buf_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    buf_info.size = byte_size;
    buf_info.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT;

    VmaAllocationCreateInfo staging_alloc{};
    staging_alloc.usage = VMA_MEMORY_USAGE_CPU_ONLY;

    VkBuffer staging;
    VmaAllocation staging_mem;
    vmaCreateBuffer(m_device.allocator, &buf_info, &staging_alloc, &staging,
                    &staging_mem, nullptr);

    void* mapped;
    vmaMapMemory(m_device.allocator, staging_mem, &mapped);
    memcpy(mapped, data, byte_size);
    vmaUnmapMemory(m_device.allocator, staging_mem);

    auto cmd = m_device.begin_single_command();

    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.image = img.image;
    barrier.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                         VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, nullptr, 0,
                         nullptr, 1, &barrier);

    VkBufferImageCopy region{};
    region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    region.imageSubresource.layerCount = 1;
    region.imageExtent = {w, h, 1};
    vkCmdCopyBufferToImage(cmd, staging, img.image,
                           VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

    barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, 0, 0, nullptr,
                         0, nullptr, 1, &barrier);

    m_device.end_single_command(cmd);
    vmaDestroyBuffer(m_device.allocator, staging, staging_mem);

    return img;
}

void TextureCache::create_defaults() {
    if (m_defaults_created) return;
    uint8_t white[4] = {255, 255, 255, 255};
    m_default_albedo = upload_rgba8(white, 1, 1, VK_FORMAT_R8G8B8A8_UNORM);

    // Tangent-space "flat" normal: (0.5, 0.5, 1.0) encoded as 8-bit
    uint8_t flat_normal[4] = {128, 128, 255, 255};
    m_default_normal = upload_rgba8(flat_normal, 1, 1, VK_FORMAT_R8G8B8A8_UNORM);

    m_defaults_created = true;
}

GpuImage* TextureCache::load(const std::string& path) {
    auto it = m_textures.find(path);
    if (it != m_textures.end()) return it->second.get();

    int w, h, channels;
    uint8_t* data = stbi_load(path.c_str(), &w, &h, &channels, 4);
    if (!data) return nullptr;

    auto img = upload_rgba8(data, static_cast<uint32_t>(w),
                            static_cast<uint32_t>(h), VK_FORMAT_R8G8B8A8_UNORM);
    stbi_image_free(data);

    auto ptr = std::make_unique<GpuImage>(img);
    GpuImage* raw = ptr.get();
    m_textures[path] = std::move(ptr);
    return raw;
}

GpuImage* TextureCache::default_albedo() {
    create_defaults();
    return &m_default_albedo;
}

GpuImage* TextureCache::default_normal() {
    create_defaults();
    return &m_default_normal;
}

} // namespace joon
