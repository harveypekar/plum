#include "app.h"

#define GLFW_INCLUDE_VULKAN
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_vulkan.h>

#include "vulkan/device.h"

#include <thread>
#include <chrono>

// Minimal Vulkan swapchain for ImGui rendering.
// The joon::Context owns the compute device; this adds presentation support.

struct SwapchainFrame {
    VkImage image;
    VkImageView view;
    VkFramebuffer framebuffer;
};

struct GuiVulkan {
    VkSurfaceKHR surface = VK_NULL_HANDLE;
    VkSwapchainKHR swapchain = VK_NULL_HANDLE;
    VkRenderPass render_pass = VK_NULL_HANDLE;
    VkDescriptorPool desc_pool = VK_NULL_HANDLE;
    VkCommandPool command_pool = VK_NULL_HANDLE;
    VkCommandBuffer command_buffer = VK_NULL_HANDLE;
    VkFence fence = VK_NULL_HANDLE;
    VkSemaphore image_available = VK_NULL_HANDLE;
    VkSemaphore render_finished = VK_NULL_HANDLE;
    std::vector<SwapchainFrame> frames;
    VkFormat format = VK_FORMAT_B8G8R8A8_UNORM;
    VkExtent2D extent{};
};

static void check_vk(VkResult err) {
    if (err != VK_SUCCESS) {
        // In production this would be a proper error handler
    }
}

int main() {
    // GLFW
    if (!glfwInit()) return 1;
    glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API);
    GLFWwindow* window = glfwCreateWindow(1280, 720, "Joon", nullptr, nullptr);
    if (!window) return 1;

    // App + Vulkan context
    App app;
    app.init();
    auto& dev = app.ctx->device();

    GuiVulkan gui;

    // Create surface from GLFW window
    check_vk(glfwCreateWindowSurface(dev.instance, window, nullptr, &gui.surface));

    // Get window dimensions
    int display_w, display_h;
    glfwGetWindowSize(window, &display_w, &display_h);
    gui.extent = { static_cast<uint32_t>(display_w), static_cast<uint32_t>(display_h) };

    // Query surface capabilities and choose format
    VkSurfaceCapabilitiesKHR capabilities;
    vkGetPhysicalDeviceSurfaceCapabilitiesKHR(dev.physical_device, gui.surface, &capabilities);

    uint32_t format_count = 0;
    vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical_device, gui.surface, &format_count, nullptr);
    std::vector<VkSurfaceFormatKHR> formats(format_count);
    vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical_device, gui.surface, &format_count, formats.data());

    VkFormat chosen_format = formats.empty() ? VK_FORMAT_B8G8R8A8_UNORM : formats[0].format;
    gui.format = chosen_format;

    // Create swapchain
    VkSwapchainCreateInfoKHR swapchain_info{};
    swapchain_info.sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR;
    swapchain_info.surface = gui.surface;
    swapchain_info.minImageCount = std::max(2u, capabilities.minImageCount);
    swapchain_info.imageFormat = gui.format;
    swapchain_info.imageColorSpace = VK_COLOR_SPACE_SRGB_NONLINEAR_KHR;
    swapchain_info.imageExtent = gui.extent;
    swapchain_info.imageArrayLayers = 1;
    swapchain_info.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    swapchain_info.imageSharingMode = VK_SHARING_MODE_EXCLUSIVE;
    swapchain_info.preTransform = VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
    swapchain_info.compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
    swapchain_info.presentMode = VK_PRESENT_MODE_FIFO_KHR;
    swapchain_info.clipped = VK_TRUE;

    check_vk(vkCreateSwapchainKHR(dev.device, &swapchain_info, nullptr, &gui.swapchain));

    // Get swapchain images
    uint32_t image_count = 0;
    vkGetSwapchainImagesKHR(dev.device, gui.swapchain, &image_count, nullptr);
    std::vector<VkImage> swapchain_images(image_count);
    vkGetSwapchainImagesKHR(dev.device, gui.swapchain, &image_count, swapchain_images.data());

    // Create image views and framebuffers
    VkImageViewCreateInfo view_info{};
    view_info.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    view_info.viewType = VK_IMAGE_VIEW_TYPE_2D;
    view_info.format = gui.format;
    view_info.components.r = VK_COMPONENT_SWIZZLE_IDENTITY;
    view_info.components.g = VK_COMPONENT_SWIZZLE_IDENTITY;
    view_info.components.b = VK_COMPONENT_SWIZZLE_IDENTITY;
    view_info.components.a = VK_COMPONENT_SWIZZLE_IDENTITY;
    view_info.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    view_info.subresourceRange.baseMipLevel = 0;
    view_info.subresourceRange.levelCount = 1;
    view_info.subresourceRange.baseArrayLayer = 0;
    view_info.subresourceRange.layerCount = 1;

    // Create render pass
    VkAttachmentDescription attachment{};
    attachment.format = gui.format;
    attachment.samples = VK_SAMPLE_COUNT_1_BIT;
    attachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    attachment.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    attachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    attachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    attachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    attachment.finalLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;

    VkAttachmentReference color_ref{};
    color_ref.attachment = 0;
    color_ref.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

    VkSubpassDescription subpass{};
    subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    subpass.colorAttachmentCount = 1;
    subpass.pColorAttachments = &color_ref;

    VkRenderPassCreateInfo render_pass_info{};
    render_pass_info.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
    render_pass_info.attachmentCount = 1;
    render_pass_info.pAttachments = &attachment;
    render_pass_info.subpassCount = 1;
    render_pass_info.pSubpasses = &subpass;

    check_vk(vkCreateRenderPass(dev.device, &render_pass_info, nullptr, &gui.render_pass));

    for (auto image : swapchain_images) {
        view_info.image = image;
        VkImageView view;
        check_vk(vkCreateImageView(dev.device, &view_info, nullptr, &view));

        VkFramebufferCreateInfo fb_info{};
        fb_info.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
        fb_info.renderPass = gui.render_pass;
        fb_info.attachmentCount = 1;
        fb_info.pAttachments = &view;
        fb_info.width = gui.extent.width;
        fb_info.height = gui.extent.height;
        fb_info.layers = 1;

        VkFramebuffer framebuffer;
        check_vk(vkCreateFramebuffer(dev.device, &fb_info, nullptr, &framebuffer));

        gui.frames.push_back({ image, view, framebuffer });
    }

    // Create command pool and command buffer for rendering
    VkCommandPoolCreateInfo cmd_pool_info{};
    cmd_pool_info.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    cmd_pool_info.queueFamilyIndex = dev.graphics_family;
    cmd_pool_info.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;

    check_vk(vkCreateCommandPool(dev.device, &cmd_pool_info, nullptr, &gui.command_pool));

    VkCommandBufferAllocateInfo cmd_alloc_info{};
    cmd_alloc_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cmd_alloc_info.commandPool = gui.command_pool;
    cmd_alloc_info.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cmd_alloc_info.commandBufferCount = 1;

    check_vk(vkAllocateCommandBuffers(dev.device, &cmd_alloc_info, &gui.command_buffer));

    // Create synchronization primitives
    VkSemaphoreCreateInfo sem_info{};
    sem_info.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;

    VkFenceCreateInfo fence_info{};
    fence_info.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
    fence_info.flags = VK_FENCE_CREATE_SIGNALED_BIT;

    check_vk(vkCreateSemaphore(dev.device, &sem_info, nullptr, &gui.image_available));
    check_vk(vkCreateSemaphore(dev.device, &sem_info, nullptr, &gui.render_finished));
    check_vk(vkCreateFence(dev.device, &fence_info, nullptr, &gui.fence));

    // Create ImGui descriptor pool
    VkDescriptorPoolSize pool_size = { VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1 };
    VkDescriptorPoolCreateInfo desc_pool_info{};
    desc_pool_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    desc_pool_info.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;
    desc_pool_info.maxSets = 16;
    desc_pool_info.poolSizeCount = 1;
    desc_pool_info.pPoolSizes = &pool_size;

    check_vk(vkCreateDescriptorPool(dev.device, &desc_pool_info, nullptr, &gui.desc_pool));

    // Initialize ImGui
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.DisplaySize = ImVec2(static_cast<float>(display_w), static_cast<float>(display_h));

    ImGui::StyleColorsDark();

    ImGui_ImplGlfw_InitForVulkan(window, true);

    ImGui_ImplVulkan_InitInfo init_info{};
    init_info.Instance = dev.instance;
    init_info.PhysicalDevice = dev.physical_device;
    init_info.Device = dev.device;
    init_info.QueueFamily = dev.graphics_family;
    init_info.Queue = dev.graphics_queue;
    init_info.DescriptorPool = gui.desc_pool;
    init_info.MinImageCount = swapchain_info.minImageCount;
    init_info.ImageCount = image_count;
    init_info.Allocator = nullptr;

    ImGui_ImplVulkan_PipelineInfo pipeline_info{};
    pipeline_info.RenderPass = gui.render_pass;
    pipeline_info.Subpass = 0;
    pipeline_info.MSAASamples = VK_SAMPLE_COUNT_1_BIT;

    init_info.PipelineInfoMain = pipeline_info;

    ImGui_ImplVulkan_Init(&init_info);

    // Main loop
    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();

        vkWaitForFences(dev.device, 1, &gui.fence, VK_TRUE, UINT64_MAX);
        vkResetFences(dev.device, 1, &gui.fence);

        uint32_t image_index = 0;
        vkAcquireNextImageKHR(dev.device, gui.swapchain, UINT64_MAX, gui.image_available, VK_NULL_HANDLE, &image_index);

        vkResetCommandBuffer(gui.command_buffer, 0);

        VkCommandBufferBeginInfo begin_info{};
        begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;

        vkBeginCommandBuffer(gui.command_buffer, &begin_info);

        VkClearValue clear_value = { { { 0.45f, 0.55f, 0.60f, 1.00f } } };

        VkRenderPassBeginInfo render_pass_begin{};
        render_pass_begin.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
        render_pass_begin.renderPass = gui.render_pass;
        render_pass_begin.framebuffer = gui.frames[image_index].framebuffer;
        render_pass_begin.renderArea.extent = gui.extent;
        render_pass_begin.clearValueCount = 1;
        render_pass_begin.pClearValues = &clear_value;

        vkCmdBeginRenderPass(gui.command_buffer, &render_pass_begin, VK_SUBPASS_CONTENTS_INLINE);

        // ImGui frame
        ImGui_ImplVulkan_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        // Simple demo window
        ImGui::SetNextWindowPos(ImVec2(10, 10), ImGuiCond_FirstUseEver);
        ImGui::SetNextWindowSize(ImVec2(300, 200), ImGuiCond_FirstUseEver);
        ImGui::Begin("Joon");
        ImGui::Text("Graphics DSL System");
        ImGui::Separator();
        ImGui::Text("Application average %.3f ms/frame (%.1f FPS)", 1000.0f / io.Framerate, io.Framerate);
        ImGui::End();

        ImGui::Render();
        ImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), gui.command_buffer);

        vkCmdEndRenderPass(gui.command_buffer);
        vkEndCommandBuffer(gui.command_buffer);

        VkPipelineStageFlags wait_stage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        VkSubmitInfo submit_info{};
        submit_info.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
        submit_info.waitSemaphoreCount = 1;
        submit_info.pWaitSemaphores = &gui.image_available;
        submit_info.pWaitDstStageMask = &wait_stage;
        submit_info.commandBufferCount = 1;
        submit_info.pCommandBuffers = &gui.command_buffer;
        submit_info.signalSemaphoreCount = 1;
        submit_info.pSignalSemaphores = &gui.render_finished;

        vkQueueSubmit(dev.graphics_queue, 1, &submit_info, gui.fence);

        VkPresentInfoKHR present_info{};
        present_info.sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
        present_info.waitSemaphoreCount = 1;
        present_info.pWaitSemaphores = &gui.render_finished;
        present_info.swapchainCount = 1;
        present_info.pSwapchains = &gui.swapchain;
        present_info.pImageIndices = &image_index;

        vkQueuePresentKHR(dev.graphics_queue, &present_info);
    }

    // Cleanup
    vkDeviceWaitIdle(dev.device);

    ImGui_ImplVulkan_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();

    vkDestroyFence(dev.device, gui.fence, nullptr);
    vkDestroySemaphore(dev.device, gui.image_available, nullptr);
    vkDestroySemaphore(dev.device, gui.render_finished, nullptr);

    vkFreeCommandBuffers(dev.device, gui.command_pool, 1, &gui.command_buffer);
    vkDestroyCommandPool(dev.device, gui.command_pool, nullptr);

    for (auto& frame : gui.frames) {
        vkDestroyFramebuffer(dev.device, frame.framebuffer, nullptr);
        vkDestroyImageView(dev.device, frame.view, nullptr);
    }

    vkDestroyRenderPass(dev.device, gui.render_pass, nullptr);
    vkDestroySwapchainKHR(dev.device, gui.swapchain, nullptr);
    vkDestroyDescriptorPool(dev.device, gui.desc_pool, nullptr);
    vkDestroySurfaceKHR(dev.instance, gui.surface, nullptr);

    glfwDestroyWindow(window);
    glfwTerminate();
    return 0;
}
