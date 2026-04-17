#pragma once

#include <vulkan/vulkan.h>
#include <vk_mem_alloc.h>
#include <memory>

namespace joon {

struct Device {
    VkInstance instance = VK_NULL_HANDLE;
    VkPhysicalDevice physical_device = VK_NULL_HANDLE;
    VkDevice device = VK_NULL_HANDLE;
    VkQueue compute_queue = VK_NULL_HANDLE;
    VkQueue graphics_queue = VK_NULL_HANDLE;
    uint32_t compute_family = UINT32_MAX;
    uint32_t graphics_family = UINT32_MAX;
    VkCommandPool command_pool = VK_NULL_HANDLE;
    VmaAllocator allocator = VK_NULL_HANDLE;

    Device() = default;
    ~Device();

    Device(const Device&) = delete;
    Device& operator=(const Device&) = delete;

    static std::unique_ptr<Device> create(bool enable_validation = true);

    VkCommandBuffer begin_single_command() const;
    void end_single_command(VkCommandBuffer cmd) const;
};

} // namespace joon
