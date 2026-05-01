#include "vulkan/buffer.h"
#include <cstring>
#include <stdexcept>

namespace joon {

namespace {

GpuBuffer create_device_local_buffer(Device& dev, const void* data, size_t size_bytes,
                                      VkBufferUsageFlags usage) {
    if (size_bytes == 0) throw std::runtime_error("create_device_local_buffer: size_bytes == 0");

    // Staging buffer — host-visible, source for the copy.
    VkBufferCreateInfo staging_info{};
    staging_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    staging_info.size = size_bytes;
    staging_info.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT;
    staging_info.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    VmaAllocationCreateInfo staging_alloc_info{};
    staging_alloc_info.usage = VMA_MEMORY_USAGE_AUTO;
    staging_alloc_info.flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT
                             | VMA_ALLOCATION_CREATE_MAPPED_BIT;

    VkBuffer staging_buf;
    VmaAllocation staging_alloc;
    VmaAllocationInfo staging_alloc_meta{};
    if (vmaCreateBuffer(dev.allocator, &staging_info, &staging_alloc_info,
                         &staging_buf, &staging_alloc, &staging_alloc_meta) != VK_SUCCESS)
        throw std::runtime_error("vmaCreateBuffer (staging) failed");

    std::memcpy(staging_alloc_meta.pMappedData, data, size_bytes);

    // Destination buffer — device-local.
    VkBufferCreateInfo dst_info{};
    dst_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    dst_info.size = size_bytes;
    dst_info.usage = usage | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
    dst_info.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    VmaAllocationCreateInfo dst_alloc_info{};
    dst_alloc_info.usage = VMA_MEMORY_USAGE_AUTO;

    GpuBuffer out;
    out.size = size_bytes;
    if (vmaCreateBuffer(dev.allocator, &dst_info, &dst_alloc_info,
                         &out.buffer, &out.alloc, nullptr) != VK_SUCCESS) {
        vmaDestroyBuffer(dev.allocator, staging_buf, staging_alloc);
        throw std::runtime_error("vmaCreateBuffer (device-local) failed");
    }

    // Copy staging → device-local on the compute queue.
    VkCommandBuffer cmd = dev.begin_single_command();
    VkBufferCopy region{};
    region.size = size_bytes;
    vkCmdCopyBuffer(cmd, staging_buf, out.buffer, 1, &region);
    dev.end_single_command(cmd);

    vmaDestroyBuffer(dev.allocator, staging_buf, staging_alloc);
    return out;
}

} // namespace

GpuBuffer create_vertex_buffer(Device& dev, const void* data, size_t size_bytes) {
    return create_device_local_buffer(dev, data, size_bytes, VK_BUFFER_USAGE_VERTEX_BUFFER_BIT);
}

GpuBuffer create_index_buffer(Device& dev, const void* data, size_t size_bytes) {
    return create_device_local_buffer(dev, data, size_bytes, VK_BUFFER_USAGE_INDEX_BUFFER_BIT);
}

GpuBuffer create_uniform_buffer(Device& dev, size_t size_bytes) {
    if (size_bytes == 0) throw std::runtime_error("create_uniform_buffer: size_bytes == 0");

    VkBufferCreateInfo info{};
    info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    info.size = size_bytes;
    info.usage = VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT;
    info.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    VmaAllocationCreateInfo alloc_info{};
    alloc_info.usage = VMA_MEMORY_USAGE_AUTO;
    alloc_info.flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT
                     | VMA_ALLOCATION_CREATE_MAPPED_BIT;

    GpuBuffer out;
    out.size = size_bytes;
    if (vmaCreateBuffer(dev.allocator, &info, &alloc_info,
                         &out.buffer, &out.alloc, nullptr) != VK_SUCCESS)
        throw std::runtime_error("vmaCreateBuffer (uniform) failed");
    return out;
}

void update_uniform_buffer(Device& dev, GpuBuffer& buf, const void* data, size_t size_bytes) {
    if (size_bytes > buf.size) throw std::runtime_error("update_uniform_buffer: size > buf.size");
    void* mapped = nullptr;
    if (vmaMapMemory(dev.allocator, buf.alloc, &mapped) != VK_SUCCESS)
        throw std::runtime_error("vmaMapMemory failed");
    std::memcpy(mapped, data, size_bytes);
    vmaUnmapMemory(dev.allocator, buf.alloc);
}

void destroy_buffer(Device& dev, GpuBuffer& buf) {
    if (buf.buffer) vmaDestroyBuffer(dev.allocator, buf.buffer, buf.alloc);
    buf.buffer = VK_NULL_HANDLE;
    buf.alloc = VK_NULL_HANDLE;
    buf.size = 0;
}

} // namespace joon
