#pragma once

#include <vulkan/vulkan.h>
#include <vk_mem_alloc.h>
#include <memory>

namespace joon::vk {

struct Device {
    VkInstance instance = VK_NULL_HANDLE;
    VkPhysicalDevice physical_device = VK_NULL_HANDLE;
    VkDevice device = VK_NULL_HANDLE;
    VkQueue compute_queue = VK_NULL_HANDLE;
    VkQueue graphics_queue = VK_NULL_HANDLE;
    uint32_t compute_family = 0;
    uint32_t graphics_family = 0;
    VkCommandPool command_pool = VK_NULL_HANDLE;
    VmaAllocator allocator = VK_NULL_HANDLE;

    static std::unique_ptr<Device> create(bool enable_validation = true);
    ~Device();

    Device(const Device&) = delete;
    Device& operator=(const Device&) = delete;

    VkCommandBuffer begin_single_command() const;
    void end_single_command(VkCommandBuffer cmd) const;
};

} // namespace joon::vk
