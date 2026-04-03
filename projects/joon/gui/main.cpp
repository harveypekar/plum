#define NOMINMAX

#include "app.h"

#define GLFW_INCLUDE_VULKAN
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_internal.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_vulkan.h>

#include "vulkan/device.h"
#include "theme.h"
#include "log.h"

#include <thread>
#include <chrono>
#include <windows.h>
#include <dbghelp.h>
#include <ctime>
#include <sstream>
#include <iomanip>
#include <iostream>
#include <csignal>
#include <cstdlib>

#pragma comment(lib, "dbghelp.lib")

// Minidump generation for crash diagnostics.
// Works for SEH exceptions (access violations, asserts), C++ exceptions, and abort().

static std::string GenerateMiniDump(EXCEPTION_POINTERS* pExceptionPointers = nullptr) {
    auto now = std::time(nullptr);
    auto tm = *std::localtime(&now);

    std::ostringstream oss;
    oss << "joon_crash_" << std::put_time(&tm, "%Y%m%d_%H%M%S") << ".dmp";
    std::string filename = oss.str();

    HANDLE hFile = CreateFileA(
        filename.c_str(), GENERIC_WRITE, 0, nullptr,
        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);

    if (hFile == INVALID_HANDLE_VALUE)
        return "Failed to create minidump file";

    MINIDUMP_EXCEPTION_INFORMATION mdei;
    MINIDUMP_EXCEPTION_INFORMATION* pMdei = nullptr;
    if (pExceptionPointers) {
        mdei.ThreadId = GetCurrentThreadId();
        mdei.ExceptionPointers = pExceptionPointers;
        mdei.ClientPointers = FALSE;
        pMdei = &mdei;
    }

    // MiniDumpWithDataSegs captures global variables for better debugging
    BOOL success = MiniDumpWriteDump(
        GetCurrentProcess(), GetCurrentProcessId(), hFile,
        static_cast<MINIDUMP_TYPE>(MiniDumpNormal | MiniDumpWithDataSegs),
        pMdei, nullptr, nullptr);

    CloseHandle(hFile);
    return success ? ("Minidump written to: " + filename) : "Failed to write minidump";
}

// Single crash entry point: write minidump, log message, break into debugger.
// Every crash path funnels through here.
static void Crash(const char* reason, EXCEPTION_POINTERS* ep = nullptr) {
    static bool already_crashing = false;
    if (already_crashing) return; // prevent recursion
    already_crashing = true;

    jlog("CRASH: %s", reason);
    jlog("%s", GenerateMiniDump(ep).c_str());
    __debugbreak();
}

static LONG WINAPI UnhandledExceptionHandler(EXCEPTION_POINTERS* ep) {
    std::ostringstream msg;
    msg << "Unhandled SEH exception 0x" << std::hex << ep->ExceptionRecord->ExceptionCode;
    Crash(msg.str().c_str(), ep);
    return EXCEPTION_EXECUTE_HANDLER;
}

static void AbortHandler(int) {
    Crash("abort() called");
}

void JoonImGuiAssertHandler(const char* expr, const char* file, int line) {
    std::ostringstream msg;
    msg << "ImGui assert failed: " << expr << " at " << file << ":" << line;
    Crash(msg.str().c_str());
}

static void InstallCrashHandlers() {
    SetUnhandledExceptionFilter(UnhandledExceptionHandler);
    signal(SIGABRT, AbortHandler);
    _set_abort_behavior(0, _WRITE_ABORT_MSG | _CALL_REPORTFAULT);
}

// Minimal Vulkan swapchain for ImGui rendering.
// The joon::Context owns the compute device; this adds presentation support.

struct SwapchainFrame {
    VkImage image;
    VkImageView view;
    VkFramebuffer framebuffer;
};

static constexpr uint32_t MAX_FRAMES_IN_FLIGHT = 2;

struct GuiVulkan {
    VkSurfaceKHR surface = VK_NULL_HANDLE;
    VkSwapchainKHR swapchain = VK_NULL_HANDLE;
    VkRenderPass render_pass = VK_NULL_HANDLE;
    VkDescriptorPool desc_pool = VK_NULL_HANDLE;
    VkCommandPool command_pool = VK_NULL_HANDLE;

    // Per-frame-in-flight resources
    VkCommandBuffer command_buffers[MAX_FRAMES_IN_FLIGHT]{};
    VkFence fences[MAX_FRAMES_IN_FLIGHT]{};
    VkSemaphore image_available[MAX_FRAMES_IN_FLIGHT]{};
    VkSemaphore render_finished[MAX_FRAMES_IN_FLIGHT]{};
    uint32_t current_frame = 0;

    std::vector<SwapchainFrame> frames;
    VkFormat format = VK_FORMAT_B8G8R8A8_UNORM;
    VkExtent2D extent{};
    bool framebuffer_resized = false;
};

static void check_vk(VkResult err) {
    if (err != VK_SUCCESS) {
        std::cerr << "Vulkan error: " << err << std::endl;
    }
}

static int app_main(); // forward declare

// SEH filter — writes minidump with full exception context
static LONG WINAPI SehFilter(EXCEPTION_POINTERS* ep) {
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    // Skip first-chance C++ exceptions (0xE06D7363 = MSVC C++ throw)
    if (code == 0xE06D7363)
        return EXCEPTION_CONTINUE_SEARCH;

    std::ostringstream msg;
    msg << "SEH exception 0x" << std::hex << code;
    Crash(msg.str().c_str(), ep);
    return EXCEPTION_EXECUTE_HANDLER;
}

int main() {
    InstallCrashHandlers();

    __try {
        return app_main();
    }
    __except (SehFilter(GetExceptionInformation())) {
        return 1;
    }
}

static int app_main() {
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
    swapchain_info.minImageCount = (std::max)(2u, capabilities.minImageCount);
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
    cmd_alloc_info.commandBufferCount = MAX_FRAMES_IN_FLIGHT;

    check_vk(vkAllocateCommandBuffers(dev.device, &cmd_alloc_info, gui.command_buffers));

    // Create per-frame synchronization primitives
    VkSemaphoreCreateInfo sem_info{};
    sem_info.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;

    VkFenceCreateInfo fence_info{};
    fence_info.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
    fence_info.flags = VK_FENCE_CREATE_SIGNALED_BIT;

    for (uint32_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
        check_vk(vkCreateSemaphore(dev.device, &sem_info, nullptr, &gui.image_available[i]));
        check_vk(vkCreateSemaphore(dev.device, &sem_info, nullptr, &gui.render_finished[i]));
        check_vk(vkCreateFence(dev.device, &fence_info, nullptr, &gui.fences[i]));
    }

    // Create ImGui descriptor pool
    VkDescriptorPoolSize pool_size = { VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 64 };
    VkDescriptorPoolCreateInfo desc_pool_info{};
    desc_pool_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    desc_pool_info.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;
    desc_pool_info.maxSets = 64;
    desc_pool_info.poolSizeCount = 1;
    desc_pool_info.pPoolSizes = &pool_size;

    check_vk(vkCreateDescriptorPool(dev.device, &desc_pool_info, nullptr, &gui.desc_pool));

    // Initialize ImGui
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.DisplaySize = ImVec2(static_cast<float>(display_w), static_cast<float>(display_h));

    load_theme("settings.json");

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
    app.imgui_ready = true;
    app.update_viewport_desc();

    // Resize callback
    glfwSetWindowUserPointer(window, &gui);
    glfwSetFramebufferSizeCallback(window, [](GLFWwindow* w, int, int) {
        auto* g = static_cast<GuiVulkan*>(glfwGetWindowUserPointer(w));
        g->framebuffer_resized = true;
    });

    // Lambda to recreate swapchain on resize
    auto recreate_swapchain = [&]() {
        int w = 0, h = 0;
        glfwGetFramebufferSize(window, &w, &h);
        while (w == 0 || h == 0) {
            glfwGetFramebufferSize(window, &w, &h);
            glfwWaitEvents();
        }
        vkDeviceWaitIdle(dev.device);

        // Destroy old framebuffers and image views
        for (auto& frame : gui.frames) {
            vkDestroyFramebuffer(dev.device, frame.framebuffer, nullptr);
            vkDestroyImageView(dev.device, frame.view, nullptr);
        }
        gui.frames.clear();

        // Query new surface capabilities
        VkSurfaceCapabilitiesKHR caps;
        vkGetPhysicalDeviceSurfaceCapabilitiesKHR(dev.physical_device, gui.surface, &caps);
        gui.extent = { static_cast<uint32_t>(w), static_cast<uint32_t>(h) };

        VkSwapchainKHR old_swapchain = gui.swapchain;

        VkSwapchainCreateInfoKHR sci{};
        sci.sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR;
        sci.surface = gui.surface;
        sci.minImageCount = (std::max)(2u, caps.minImageCount);
        sci.imageFormat = gui.format;
        sci.imageColorSpace = VK_COLOR_SPACE_SRGB_NONLINEAR_KHR;
        sci.imageExtent = gui.extent;
        sci.imageArrayLayers = 1;
        sci.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
        sci.imageSharingMode = VK_SHARING_MODE_EXCLUSIVE;
        sci.preTransform = VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
        sci.compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
        sci.presentMode = VK_PRESENT_MODE_FIFO_KHR;
        sci.clipped = VK_TRUE;
        sci.oldSwapchain = old_swapchain;

        check_vk(vkCreateSwapchainKHR(dev.device, &sci, nullptr, &gui.swapchain));
        vkDestroySwapchainKHR(dev.device, old_swapchain, nullptr);

        // Get new images
        uint32_t ic = 0;
        vkGetSwapchainImagesKHR(dev.device, gui.swapchain, &ic, nullptr);
        std::vector<VkImage> imgs(ic);
        vkGetSwapchainImagesKHR(dev.device, gui.swapchain, &ic, imgs.data());

        VkImageViewCreateInfo vi{};
        vi.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
        vi.viewType = VK_IMAGE_VIEW_TYPE_2D;
        vi.format = gui.format;
        vi.components = { VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY,
                          VK_COMPONENT_SWIZZLE_IDENTITY, VK_COMPONENT_SWIZZLE_IDENTITY };
        vi.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };

        for (auto img : imgs) {
            vi.image = img;
            VkImageView view;
            check_vk(vkCreateImageView(dev.device, &vi, nullptr, &view));

            VkFramebufferCreateInfo fbi{};
            fbi.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
            fbi.renderPass = gui.render_pass;
            fbi.attachmentCount = 1;
            fbi.pAttachments = &view;
            fbi.width = gui.extent.width;
            fbi.height = gui.extent.height;
            fbi.layers = 1;

            VkFramebuffer fb;
            check_vk(vkCreateFramebuffer(dev.device, &fbi, nullptr, &fb));
            gui.frames.push_back({ img, view, fb });
        }

        gui.framebuffer_resized = false;
    };

    // Main loop
    static bool load_layout_requested = false;

    while (!glfwWindowShouldClose(window)) {
        try {
            glfwPollEvents();

            // Skip rendering if minimized
            int fb_w = 0, fb_h = 0;
            glfwGetFramebufferSize(window, &fb_w, &fb_h);
            if (fb_w == 0 || fb_h == 0) continue;

            uint32_t frame_idx = gui.current_frame;
            VkCommandBuffer cmd = gui.command_buffers[frame_idx];

            vkWaitForFences(dev.device, 1, &gui.fences[frame_idx], VK_TRUE, UINT64_MAX);

            uint32_t image_index = 0;
            VkResult acquire_result = vkAcquireNextImageKHR(
                dev.device, gui.swapchain, UINT64_MAX,
                gui.image_available[frame_idx], VK_NULL_HANDLE, &image_index);

            if (acquire_result == VK_ERROR_OUT_OF_DATE_KHR) {
                recreate_swapchain();
                continue;
            }

            // Reset fence only after successful acquire (prevents deadlock)
            vkResetFences(dev.device, 1, &gui.fences[frame_idx]);

            vkResetCommandBuffer(cmd, 0);

            VkCommandBufferBeginInfo begin_info{};
            begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
            begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;

            vkBeginCommandBuffer(cmd, &begin_info);

            auto& vp = app_colors().viewport_bg;
            VkClearValue clear_value = { { { vp[0], vp[1], vp[2], vp[3] } } };

            VkRenderPassBeginInfo render_pass_begin{};
            render_pass_begin.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
            render_pass_begin.renderPass = gui.render_pass;
            render_pass_begin.framebuffer = gui.frames[image_index].framebuffer;
            render_pass_begin.renderArea.extent = gui.extent;
            render_pass_begin.clearValueCount = 1;
            render_pass_begin.pClearValues = &clear_value;

            vkCmdBeginRenderPass(cmd, &render_pass_begin, VK_SUBPASS_CONTENTS_INLINE);

            // ImGui frame
            ImGui_ImplVulkan_NewFrame();
            ImGui_ImplGlfw_NewFrame();
            ImGui::NewFrame();

            // Menu bar
            if (ImGui::BeginMainMenuBar()) {
                if (ImGui::BeginMenu("File")) {
                    if (ImGui::MenuItem("New Graph"))
                        app.new_graph();
                    ImGui::EndMenu();
                }
                if (ImGui::BeginMenu("Layout")) {
                    if (ImGui::MenuItem("Save Layout"))
                        ImGui::SaveIniSettingsToDisk("joon_layout.ini");
                    if (ImGui::MenuItem("Load Layout"))
                        load_layout_requested = true;
                    ImGui::EndMenu();
                }
                ImGui::EndMainMenuBar();
            }

            if (load_layout_requested) {
                ImGui::LoadIniSettingsFromDisk("joon_layout.ini");
                load_layout_requested = false;
            }

            ImGuiID dockspace_id = ImGui::GetID("MainDockSpace");
            ImGui::DockSpaceOverViewport(dockspace_id, ImGui::GetMainViewport());

            app.update();
            app.draw_hierarchy();
            app.draw_code();
            app.draw_properties();
            app.draw_viewport();
            app.draw_log();

            ImGui::Render();
            ImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), cmd);

            vkCmdEndRenderPass(cmd);
            vkEndCommandBuffer(cmd);

            VkPipelineStageFlags wait_stage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
            VkSubmitInfo submit_info{};
            submit_info.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
            submit_info.waitSemaphoreCount = 1;
            submit_info.pWaitSemaphores = &gui.image_available[frame_idx];
            submit_info.pWaitDstStageMask = &wait_stage;
            submit_info.commandBufferCount = 1;
            submit_info.pCommandBuffers = &cmd;
            submit_info.signalSemaphoreCount = 1;
            submit_info.pSignalSemaphores = &gui.render_finished[frame_idx];

            vkQueueSubmit(dev.graphics_queue, 1, &submit_info, gui.fences[frame_idx]);

            VkPresentInfoKHR present_info{};
            present_info.sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
            present_info.waitSemaphoreCount = 1;
            present_info.pWaitSemaphores = &gui.render_finished[frame_idx];
            present_info.swapchainCount = 1;
            present_info.pSwapchains = &gui.swapchain;
            present_info.pImageIndices = &image_index;

            VkResult present_result = vkQueuePresentKHR(dev.graphics_queue, &present_info);
            if (present_result == VK_ERROR_OUT_OF_DATE_KHR ||
                present_result == VK_SUBOPTIMAL_KHR || gui.framebuffer_resized) {
                recreate_swapchain();
            }

            gui.current_frame = (gui.current_frame + 1) % MAX_FRAMES_IN_FLIGHT;
        } catch (const std::exception& e) {
            Crash(e.what());
            break;
        } catch (...) {
            Crash("Unknown C++ exception");
            break;
        }
    }

    // Cleanup
    vkDeviceWaitIdle(dev.device);

    ImGui_ImplVulkan_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();

    for (uint32_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
        vkDestroyFence(dev.device, gui.fences[i], nullptr);
        vkDestroySemaphore(dev.device, gui.image_available[i], nullptr);
        vkDestroySemaphore(dev.device, gui.render_finished[i], nullptr);
    }

    vkFreeCommandBuffers(dev.device, gui.command_pool, MAX_FRAMES_IN_FLIGHT, gui.command_buffers);
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
