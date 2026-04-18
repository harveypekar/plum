#define NOMINMAX

#include "app.h"

#define GLFW_INCLUDE_VULKAN
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_vulkan.h>

#include "vulkan/device.h"
#include "util/exe_dir.h"
#include "log.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <vector>

// Minimal Vulkan presentation stack for ImGui. The joon::Context owns the
// compute device; this adds the swapchain, render pass, and per-frame
// synchronization needed to actually show pixels on screen.

static constexpr uint32_t MAX_FRAMES_IN_FLIGHT = 2;

struct SwapchainFrame {
    VkImage image = VK_NULL_HANDLE;
    VkImageView view = VK_NULL_HANDLE;
    VkFramebuffer framebuffer = VK_NULL_HANDLE;
};

struct GuiVulkan {
    VkSurfaceKHR surface = VK_NULL_HANDLE;
    VkSwapchainKHR swapchain = VK_NULL_HANDLE;
    VkRenderPass render_pass = VK_NULL_HANDLE;
    VkDescriptorPool desc_pool = VK_NULL_HANDLE;
    VkCommandPool command_pool = VK_NULL_HANDLE;

    VkCommandBuffer command_buffers[MAX_FRAMES_IN_FLIGHT]{};
    VkFence fences[MAX_FRAMES_IN_FLIGHT]{};
    VkSemaphore image_available[MAX_FRAMES_IN_FLIGHT]{};
    // Per-swapchain-image (not per frame-in-flight). The present op waits on
    // this semaphore, so it must not be re-signaled while present is pending.
    std::vector<VkSemaphore> render_finished;
    uint32_t current_frame = 0;

    std::vector<SwapchainFrame> frames;
    VkFormat format = VK_FORMAT_B8G8R8A8_UNORM;
    VkColorSpaceKHR color_space = VK_COLOR_SPACE_SRGB_NONLINEAR_KHR;
    VkExtent2D extent{};
    uint32_t min_image_count = 2;
    bool framebuffer_resized = false;
};

static void check_vk(VkResult err, const char* where) {
    if (err != VK_SUCCESS) {
        joon_log::write("Vulkan error (%d) at %s\n", err, where);
    }
}

// Build swapchain + image views + framebuffers. Destroys the old swapchain
// if one was passed in. Also refreshes gui.extent from the current surface.
static void create_swapchain(const joon::Device& dev, GuiVulkan& gui, GLFWwindow* window, VkSwapchainKHR old_swapchain) {
    int w = 0, h = 0;
    glfwGetFramebufferSize(window, &w, &h);
    gui.extent = { static_cast<uint32_t>(w), static_cast<uint32_t>(h) };

    VkSurfaceCapabilitiesKHR caps{};
    vkGetPhysicalDeviceSurfaceCapabilitiesKHR(dev.physical_device, gui.surface, &caps);

    // currentExtent (0xFFFFFFFF) means the surface defers to us; otherwise clamp.
    if (caps.currentExtent.width != 0xFFFFFFFFu) {
        gui.extent = caps.currentExtent;
    } else {
        gui.extent.width  = std::clamp(gui.extent.width,  caps.minImageExtent.width,  caps.maxImageExtent.width);
        gui.extent.height = std::clamp(gui.extent.height, caps.minImageExtent.height, caps.maxImageExtent.height);
    }

    gui.min_image_count = std::max(2u, caps.minImageCount);
    if (caps.maxImageCount > 0 && gui.min_image_count > caps.maxImageCount) {
        gui.min_image_count = caps.maxImageCount;
    }

    VkSwapchainCreateInfoKHR sci{};
    sci.sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR;
    sci.surface = gui.surface;
    sci.minImageCount = gui.min_image_count;
    sci.imageFormat = gui.format;
    sci.imageColorSpace = gui.color_space;
    sci.imageExtent = gui.extent;
    sci.imageArrayLayers = 1;
    sci.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    sci.imageSharingMode = VK_SHARING_MODE_EXCLUSIVE;
    sci.preTransform = caps.currentTransform;
    sci.compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
    sci.presentMode = VK_PRESENT_MODE_FIFO_KHR;
    sci.clipped = VK_TRUE;
    sci.oldSwapchain = old_swapchain;

    check_vk(vkCreateSwapchainKHR(dev.device, &sci, nullptr, &gui.swapchain), "vkCreateSwapchainKHR");

    if (old_swapchain != VK_NULL_HANDLE) {
        vkDestroySwapchainKHR(dev.device, old_swapchain, nullptr);
    }

    // Retrieve images and build views + framebuffers
    uint32_t image_count = 0;
    vkGetSwapchainImagesKHR(dev.device, gui.swapchain, &image_count, nullptr);
    std::vector<VkImage> images(image_count);
    vkGetSwapchainImagesKHR(dev.device, gui.swapchain, &image_count, images.data());

    // Tear down any previous per-image resources
    for (auto& f : gui.frames) {
        if (f.framebuffer) vkDestroyFramebuffer(dev.device, f.framebuffer, nullptr);
        if (f.view) vkDestroyImageView(dev.device, f.view, nullptr);
    }
    gui.frames.clear();
    gui.frames.reserve(image_count);

    // Per-image render_finished semaphores. Size may change on recreate.
    for (VkSemaphore s : gui.render_finished) {
        if (s) vkDestroySemaphore(dev.device, s, nullptr);
    }
    gui.render_finished.assign(image_count, VK_NULL_HANDLE);
    {
        VkSemaphoreCreateInfo sem_ci{};
        sem_ci.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;
        for (uint32_t i = 0; i < image_count; i++) {
            check_vk(vkCreateSemaphore(dev.device, &sem_ci, nullptr, &gui.render_finished[i]),
                     "vkCreateSemaphore(render_finished)");
        }
    }

    for (VkImage img : images) {
        VkImageViewCreateInfo vi{};
        vi.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
        vi.image = img;
        vi.viewType = VK_IMAGE_VIEW_TYPE_2D;
        vi.format = gui.format;
        vi.components = { VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY,
                          VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY };
        vi.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };

        VkImageView view = VK_NULL_HANDLE;
        check_vk(vkCreateImageView(dev.device, &vi, nullptr, &view), "vkCreateImageView");

        VkFramebufferCreateInfo fbi{};
        fbi.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
        fbi.renderPass = gui.render_pass;
        fbi.attachmentCount = 1;
        fbi.pAttachments = &view;
        fbi.width = gui.extent.width;
        fbi.height = gui.extent.height;
        fbi.layers = 1;

        VkFramebuffer fb = VK_NULL_HANDLE;
        check_vk(vkCreateFramebuffer(dev.device, &fbi, nullptr, &fb), "vkCreateFramebuffer");

        gui.frames.push_back({ img, view, fb });
    }

    gui.framebuffer_resized = false;
}

static void recreate_swapchain(const joon::Device& dev, GuiVulkan& gui, GLFWwindow* window) {
    int w = 0, h = 0;
    glfwGetFramebufferSize(window, &w, &h);
    while (w == 0 || h == 0) {
        glfwGetFramebufferSize(window, &w, &h);
        glfwWaitEvents();
    }
    vkDeviceWaitIdle(dev.device);

    VkSwapchainKHR old = gui.swapchain;
    gui.swapchain = VK_NULL_HANDLE;
    create_swapchain(dev, gui, window, old);
}

int main() {
    auto log_path = joon::exe_dir() + "/joon-gui.log";
    joon_log::init(log_path.c_str());

    if (!glfwInit()) {
        joon_log::write("glfwInit failed\n");
        joon_log::close();
        return 1;
    }
    glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API);
    GLFWwindow* window = glfwCreateWindow(1280, 720, "Joon", nullptr, nullptr);
    if (!window) {
        joon_log::write("glfwCreateWindow failed\n");
        glfwTerminate();
        return 1;
    }

    App app;
    app.init();
    auto& dev = app.ctx->device();

    GuiVulkan gui;

    // Surface from GLFW
    check_vk(glfwCreateWindowSurface(dev.instance, window, nullptr, &gui.surface),
             "glfwCreateWindowSurface");

    // Spec: VUID-VkSwapchainCreateInfoKHR-surface-01270. We also present via
    // the graphics queue so it must actually support this surface.
    {
        VkBool32 present_supported = VK_FALSE;
        vkGetPhysicalDeviceSurfaceSupportKHR(dev.physical_device, dev.graphics_family,
                                             gui.surface, &present_supported);
        if (!present_supported) {
            joon_log::write("graphics queue family %u does not support presentation\n",
                           dev.graphics_family);
            vkDestroySurfaceKHR(dev.instance, gui.surface, nullptr);
            app.shutdown();
            glfwDestroyWindow(window);
            glfwTerminate();
            return 1;
        }
    }

    // Pick a reasonable swapchain format
    {
        uint32_t fmt_count = 0;
        vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical_device, gui.surface, &fmt_count, nullptr);
        std::vector<VkSurfaceFormatKHR> formats(fmt_count);
        vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical_device, gui.surface, &fmt_count, formats.data());
        if (!formats.empty()) {
            gui.format = formats[0].format;
            gui.color_space = formats[0].colorSpace;
            for (const auto& f : formats) {
                if (f.format == VK_FORMAT_B8G8R8A8_UNORM &&
                    f.colorSpace == VK_COLOR_SPACE_SRGB_NONLINEAR_KHR) {
                    gui.format = f.format;
                    gui.color_space = f.colorSpace;
                    break;
                }
            }
        }
    }

    // Render pass (single color attachment cleared at start, presented at end)
    {
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

        VkSubpassDependency dep{};
        dep.srcSubpass = VK_SUBPASS_EXTERNAL;
        dep.dstSubpass = 0;
        dep.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        dep.dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        dep.srcAccessMask = 0;
        dep.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;

        VkRenderPassCreateInfo rpi{};
        rpi.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
        rpi.attachmentCount = 1;
        rpi.pAttachments = &attachment;
        rpi.subpassCount = 1;
        rpi.pSubpasses = &subpass;
        rpi.dependencyCount = 1;
        rpi.pDependencies = &dep;

        check_vk(vkCreateRenderPass(dev.device, &rpi, nullptr, &gui.render_pass), "vkCreateRenderPass");
    }

    // Build the initial swapchain + framebuffers
    create_swapchain(dev, gui, window, VK_NULL_HANDLE);

    // Command pool + command buffers (graphics queue)
    {
        VkCommandPoolCreateInfo cpi{};
        cpi.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
        cpi.queueFamilyIndex = dev.graphics_family;
        cpi.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
        check_vk(vkCreateCommandPool(dev.device, &cpi, nullptr, &gui.command_pool), "vkCreateCommandPool");

        VkCommandBufferAllocateInfo cbai{};
        cbai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
        cbai.commandPool = gui.command_pool;
        cbai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        cbai.commandBufferCount = MAX_FRAMES_IN_FLIGHT;
        check_vk(vkAllocateCommandBuffers(dev.device, &cbai, gui.command_buffers), "vkAllocateCommandBuffers");
    }

    // Sync primitives — fences start signaled so the first frame can proceed.
    // render_finished is per-swapchain-image and lives in create_swapchain.
    {
        VkSemaphoreCreateInfo sci{};
        sci.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;

        VkFenceCreateInfo fci{};
        fci.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        fci.flags = VK_FENCE_CREATE_SIGNALED_BIT;

        for (uint32_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
            check_vk(vkCreateSemaphore(dev.device, &sci, nullptr, &gui.image_available[i]), "vkCreateSemaphore");
            check_vk(vkCreateFence(dev.device, &fci, nullptr, &gui.fences[i]), "vkCreateFence");
        }
    }

    // Descriptor pool for ImGui's font texture + any image bindings the panels use.
    {
        VkDescriptorPoolSize pool_size{};
        pool_size.type = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
        pool_size.descriptorCount = 64;

        VkDescriptorPoolCreateInfo dpi{};
        dpi.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
        dpi.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;
        dpi.maxSets = 64;
        dpi.poolSizeCount = 1;
        dpi.pPoolSizes = &pool_size;

        check_vk(vkCreateDescriptorPool(dev.device, &dpi, nullptr, &gui.desc_pool), "vkCreateDescriptorPool");
        app.imgui_desc_pool = gui.desc_pool;
    }

    // ImGui context + backends
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    ImGui::StyleColorsDark();

    ImGui_ImplGlfw_InitForVulkan(window, true);

    ImGui_ImplVulkan_InitInfo init_info{};
    init_info.Instance = dev.instance;
    init_info.PhysicalDevice = dev.physical_device;
    init_info.Device = dev.device;
    init_info.QueueFamily = dev.graphics_family;
    init_info.Queue = dev.graphics_queue;
    init_info.DescriptorPool = gui.desc_pool;
    init_info.MinImageCount = gui.min_image_count;
    init_info.ImageCount = static_cast<uint32_t>(gui.frames.size());

    ImGui_ImplVulkan_PipelineInfo pipeline_info{};
    pipeline_info.RenderPass = gui.render_pass;
    pipeline_info.Subpass = 0;
    pipeline_info.MSAASamples = VK_SAMPLE_COUNT_1_BIT;
    init_info.PipelineInfoMain = pipeline_info;

    ImGui_ImplVulkan_Init(&init_info);

    // Framebuffer resize callback
    glfwSetWindowUserPointer(window, &gui);
    glfwSetFramebufferSizeCallback(window, [](GLFWwindow* w, int, int) {
        auto* g = static_cast<GuiVulkan*>(glfwGetWindowUserPointer(w));
        g->framebuffer_resized = true;
    });

    // Main loop
    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();

        // Skip frame when minimized
        int fb_w = 0, fb_h = 0;
        glfwGetFramebufferSize(window, &fb_w, &fb_h);
        if (fb_w == 0 || fb_h == 0) continue;

        uint32_t frame_idx = gui.current_frame;

        vkWaitForFences(dev.device, 1, &gui.fences[frame_idx], VK_TRUE, UINT64_MAX);

        uint32_t image_index = 0;
        VkResult acquire = vkAcquireNextImageKHR(
            dev.device, gui.swapchain, UINT64_MAX,
            gui.image_available[frame_idx], VK_NULL_HANDLE, &image_index);

        if (acquire == VK_ERROR_OUT_OF_DATE_KHR) {
            recreate_swapchain(dev, gui, window);
            continue;
        }
        // VK_SUBOPTIMAL_KHR is acceptable — handled after present.

        vkResetFences(dev.device, 1, &gui.fences[frame_idx]);

        VkCommandBuffer cmd = gui.command_buffers[frame_idx];
        vkResetCommandBuffer(cmd, 0);

        VkCommandBufferBeginInfo bi{};
        bi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        vkBeginCommandBuffer(cmd, &bi);

        VkClearValue clear_value{};
        clear_value.color = { { 0.10f, 0.10f, 0.12f, 1.0f } };

        VkRenderPassBeginInfo rpbi{};
        rpbi.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
        rpbi.renderPass = gui.render_pass;
        rpbi.framebuffer = gui.frames[image_index].framebuffer;
        rpbi.renderArea.extent = gui.extent;
        rpbi.clearValueCount = 1;
        rpbi.pClearValues = &clear_value;
        vkCmdBeginRenderPass(cmd, &rpbi, VK_SUBPASS_CONTENTS_INLINE);

        // ImGui frame
        ImGui_ImplVulkan_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        // Menu bar
        if (ImGui::BeginMainMenuBar()) {
            if (ImGui::BeginMenu("Layout")) {
                if (ImGui::MenuItem("Save Layout"))
                    ImGui::SaveIniSettingsToDisk("joon_layout.ini");
                if (ImGui::MenuItem("Load Layout"))
                    ImGui::LoadIniSettingsFromDisk("joon_layout.ini");
                ImGui::EndMenu();
            }
            ImGui::EndMainMenuBar();
        }

        ImGui::DockSpaceOverViewport();

        app.update();
        app.draw_tree();
        app.draw_properties();
        app.draw_code();
        app.draw_viewport();
        app.draw_preview();
        app.draw_log();

        ImGui::Render();
        ImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), cmd);

        vkCmdEndRenderPass(cmd);
        vkEndCommandBuffer(cmd);

        VkPipelineStageFlags wait_stage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        VkSubmitInfo submit{};
        submit.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
        submit.waitSemaphoreCount = 1;
        submit.pWaitSemaphores = &gui.image_available[frame_idx];
        submit.pWaitDstStageMask = &wait_stage;
        submit.commandBufferCount = 1;
        submit.pCommandBuffers = &cmd;
        submit.signalSemaphoreCount = 1;
        submit.pSignalSemaphores = &gui.render_finished[image_index];
        vkQueueSubmit(dev.graphics_queue, 1, &submit, gui.fences[frame_idx]);

        VkPresentInfoKHR present{};
        present.sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
        present.waitSemaphoreCount = 1;
        present.pWaitSemaphores = &gui.render_finished[image_index];
        present.swapchainCount = 1;
        present.pSwapchains = &gui.swapchain;
        present.pImageIndices = &image_index;

        VkResult pr = vkQueuePresentKHR(dev.graphics_queue, &present);
        if (pr == VK_ERROR_OUT_OF_DATE_KHR || pr == VK_SUBOPTIMAL_KHR || gui.framebuffer_resized) {
            recreate_swapchain(dev, gui, window);
        }

        gui.current_frame = (gui.current_frame + 1) % MAX_FRAMES_IN_FLIGHT;
    }

    // Cleanup
    vkDeviceWaitIdle(dev.device);

    app.shutdown();

    ImGui_ImplVulkan_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();

    for (uint32_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
        vkDestroyFence(dev.device, gui.fences[i], nullptr);
        vkDestroySemaphore(dev.device, gui.image_available[i], nullptr);
    }
    for (VkSemaphore s : gui.render_finished) {
        if (s) vkDestroySemaphore(dev.device, s, nullptr);
    }

    vkFreeCommandBuffers(dev.device, gui.command_pool, MAX_FRAMES_IN_FLIGHT, gui.command_buffers);
    vkDestroyCommandPool(dev.device, gui.command_pool, nullptr);

    for (auto& f : gui.frames) {
        if (f.framebuffer) vkDestroyFramebuffer(dev.device, f.framebuffer, nullptr);
        if (f.view) vkDestroyImageView(dev.device, f.view, nullptr);
    }

    vkDestroyRenderPass(dev.device, gui.render_pass, nullptr);
    vkDestroySwapchainKHR(dev.device, gui.swapchain, nullptr);
    vkDestroyDescriptorPool(dev.device, gui.desc_pool, nullptr);
    vkDestroySurfaceKHR(dev.instance, gui.surface, nullptr);

    glfwDestroyWindow(window);
    glfwTerminate();
    joon_log::close();
    return 0;
}
