#pragma once

#include "vulkan/device.h"
#include <cstddef>

namespace joon {

// Thin wrappers over VMA-allocated VkBuffer. Sub-project 2 creates fresh
// vertex/index/uniform buffers each evaluate() and frees them at the end.
// Pooling can come later if profiling shows it's worth the complexity.

struct GpuBuffer {
    VkBuffer buffer = VK_NULL_HANDLE;
    VmaAllocation alloc = VK_NULL_HANDLE;
    size_t size = 0;
};

// DEVICE_LOCAL vertex/index buffers — uploaded via a one-shot staging buffer.
GpuBuffer create_vertex_buffer(Device& dev, const void* data, size_t size_bytes);
GpuBuffer create_index_buffer (Device& dev, const void* data, size_t size_bytes);

// CPU_TO_GPU mapped uniform buffer — call update_uniform_buffer to refill.
GpuBuffer create_uniform_buffer(Device& dev, size_t size_bytes);
void      update_uniform_buffer(Device& dev, GpuBuffer& buf,
                                 const void* data, size_t size_bytes);

void destroy_buffer(Device& dev, GpuBuffer& buf);

} // namespace joon
