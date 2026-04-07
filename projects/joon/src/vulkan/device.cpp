#define VMA_IMPLEMENTATION
#include "vulkan/device.h"
#include <stdexcept>
#include <vector>

namespace joon {

std::unique_ptr<Device> Device::create(bool enable_validation) {
    auto dev = std::make_unique<Device>();

    // Instance
    VkApplicationInfo app_info{};
    app_info.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app_info.pApplicationName = "Joon";
    app_info.applicationVersion = VK_MAKE_VERSION(0, 1, 0);
    app_info.pEngineName = "Joon Engine";
    app_info.engineVersion = VK_MAKE_VERSION(0, 1, 0);
    app_info.apiVersion = VK_API_VERSION_1_2;

    // Instance extensions required for window-system presentation.
    // Enabled unconditionally so the CLI and GUI share one Device::create path.
    std::vector<const char*> instance_extensions = {
        "VK_KHR_surface",
#ifdef _WIN32
        "VK_KHR_win32_surface",
#elif defined(__APPLE__)
        "VK_EXT_metal_surface",
#else
        "VK_KHR_xlib_surface",
#endif
    };

    VkInstanceCreateInfo create_info{};
    create_info.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    create_info.pApplicationInfo = &app_info;
    create_info.enabledExtensionCount = static_cast<uint32_t>(instance_extensions.size());
    create_info.ppEnabledExtensionNames = instance_extensions.data();

    std::vector<const char*> layers;
    if (enable_validation) {
        layers.push_back("VK_LAYER_KHRONOS_validation");
    }
    create_info.enabledLayerCount = static_cast<uint32_t>(layers.size());
    create_info.ppEnabledLayerNames = layers.data();

    if (vkCreateInstance(&create_info, nullptr, &dev->instance) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create Vulkan instance");
    }

    // Physical device — prefer discrete GPU
    uint32_t device_count = 0;
    vkEnumeratePhysicalDevices(dev->instance, &device_count, nullptr);
    if (device_count == 0) {
        throw std::runtime_error("No Vulkan-capable GPU found");
    }
    std::vector<VkPhysicalDevice> devices(device_count);
    vkEnumeratePhysicalDevices(dev->instance, &device_count, devices.data());

    dev->physical_device = devices[0];
    for (auto& pd : devices) {
        VkPhysicalDeviceProperties props;
        vkGetPhysicalDeviceProperties(pd, &props);
        if (props.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) {
            dev->physical_device = pd;
            break;
        }
    }

    // Queue families
    uint32_t family_count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(dev->physical_device, &family_count, nullptr);
    std::vector<VkQueueFamilyProperties> families(family_count);
    vkGetPhysicalDeviceQueueFamilyProperties(dev->physical_device, &family_count, families.data());

    for (uint32_t i = 0; i < family_count; i++) {
        if (families[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) {
            dev->graphics_family = i;
        }
        if (families[i].queueFlags & VK_QUEUE_COMPUTE_BIT) {
            dev->compute_family = i;
        }
    }

    // Logical device
    float priority = 1.0f;
    std::vector<VkDeviceQueueCreateInfo> queue_infos;

    VkDeviceQueueCreateInfo qi{};
    qi.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    qi.queueFamilyIndex = dev->graphics_family;
    qi.queueCount = 1;
    qi.pQueuePriorities = &priority;
    queue_infos.push_back(qi);

    if (dev->compute_family != dev->graphics_family) {
        qi.queueFamilyIndex = dev->compute_family;
        queue_infos.push_back(qi);
    }

    // Device extensions — swapchain is needed by the GUI; harmless for the CLI.
    std::vector<const char*> device_extensions = {
        "VK_KHR_swapchain",
    };

    VkDeviceCreateInfo device_info{};
    device_info.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    device_info.queueCreateInfoCount = static_cast<uint32_t>(queue_infos.size());
    device_info.pQueueCreateInfos = queue_infos.data();
    device_info.enabledExtensionCount = static_cast<uint32_t>(device_extensions.size());
    device_info.ppEnabledExtensionNames = device_extensions.data();

    if (vkCreateDevice(dev->physical_device, &device_info, nullptr, &dev->device) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create Vulkan device");
    }

    vkGetDeviceQueue(dev->device, dev->graphics_family, 0, &dev->graphics_queue);
    vkGetDeviceQueue(dev->device, dev->compute_family, 0, &dev->compute_queue);

    // Command pool
    VkCommandPoolCreateInfo pool_info{};
    pool_info.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    pool_info.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    pool_info.queueFamilyIndex = dev->compute_family;
    vkCreateCommandPool(dev->device, &pool_info, nullptr, &dev->command_pool);

    // VMA allocator
    VmaAllocatorCreateInfo alloc_info{};
    alloc_info.physicalDevice = dev->physical_device;
    alloc_info.device = dev->device;
    alloc_info.instance = dev->instance;
    alloc_info.vulkanApiVersion = VK_API_VERSION_1_2;
    vmaCreateAllocator(&alloc_info, &dev->allocator);

    return dev;
}

Device::~Device() {
    if (device) vkDeviceWaitIdle(device);
    if (allocator) vmaDestroyAllocator(allocator);
    if (command_pool) vkDestroyCommandPool(device, command_pool, nullptr);
    if (device) vkDestroyDevice(device, nullptr);
    if (instance) vkDestroyInstance(instance, nullptr);
}

VkCommandBuffer Device::begin_single_command() const {
    VkCommandBufferAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    alloc_info.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    alloc_info.commandPool = command_pool;
    alloc_info.commandBufferCount = 1;

    VkCommandBuffer cmd;
    vkAllocateCommandBuffers(device, &alloc_info, &cmd);

    VkCommandBufferBeginInfo begin_info{};
    begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vkBeginCommandBuffer(cmd, &begin_info);
    return cmd;
}

void Device::end_single_command(VkCommandBuffer cmd) const {
    vkEndCommandBuffer(cmd);
    VkSubmitInfo submit{};
    submit.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit.commandBufferCount = 1;
    submit.pCommandBuffers = &cmd;
    vkQueueSubmit(compute_queue, 1, &submit, VK_NULL_HANDLE);
    vkQueueWaitIdle(compute_queue);
    vkFreeCommandBuffers(device, command_pool, 1, &cmd);
}

} // namespace joon
