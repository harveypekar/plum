#include "app.h"

#define GLFW_INCLUDE_VULKAN
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_vulkan.h>

#include "vulkan/device.h"

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

    // The full swapchain + ImGui Vulkan backend initialization would go here.
    // This is the integration point where:
    // 1. Create VkSurfaceKHR from GLFW window
    // 2. Create swapchain
    // 3. Create render pass for ImGui
    // 4. Initialize ImGui backends
    // 5. Each frame: acquire image, record ImGui commands, present
    //
    // For the vertical slice, this is a working skeleton.
    // The full implementation will be fleshed out when we first build and test on Windows.

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;

    ImGui::StyleColorsDark();

    // TODO: Initialize ImGui GLFW and Vulkan backends once swapchain is set up
    // ImGui_ImplGlfw_InitForVulkan(window, true);
    // ImGui_ImplVulkan_Init(&init_info);

    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();

        // ImGui_ImplVulkan_NewFrame();
        // ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();
        ImGui::DockSpaceOverViewport();

        app.update();
        app.draw_tree();
        app.draw_properties();
        app.draw_code();
        app.draw_viewport();
        app.draw_preview();
        app.draw_log();

        ImGui::Render();
        // Submit ImGui draw data to Vulkan
    }

    vkDeviceWaitIdle(dev.device);

    // ImGui_ImplVulkan_Shutdown();
    // ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();
    return 0;
}
