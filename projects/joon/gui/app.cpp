#include "app.h"
#include "log.h"
#include <imgui.h>
#include <imgui_impl_vulkan.h>

void App::init() {
    ctx = joon::Context::create();

    dsl_source = R"(; Joon - edit this code
(def base (noise :scale 4.0 :octaves 3))
(param contrast float 1.2 :min 0.0 :max 3.0)
(def result (levels base :contrast contrast))
(output result)
)";

    VkSamplerCreateInfo sampler_info{};
    sampler_info.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    sampler_info.magFilter = VK_FILTER_LINEAR;
    sampler_info.minFilter = VK_FILTER_LINEAR;
    sampler_info.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    sampler_info.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    vkCreateSampler(ctx->device().device, &sampler_info, nullptr, &sampler);

    reparse();
}

void App::shutdown() {
    if (viewport_desc) {
        ImGui_ImplVulkan_RemoveTexture(viewport_desc);
        viewport_desc = VK_NULL_HANDLE;
    }
    if (preview_desc) {
        ImGui_ImplVulkan_RemoveTexture(preview_desc);
        preview_desc = VK_NULL_HANDLE;
    }
    eval.reset();
    if (sampler && ctx) {
        vkDestroySampler(ctx->device().device, sampler, nullptr);
        sampler = VK_NULL_HANDLE;
    }
}

void App::bind_viewport() {
    if (viewport_desc) {
        ImGui_ImplVulkan_RemoveTexture(viewport_desc);
        viewport_desc = VK_NULL_HANDLE;
    }
    if (!eval || graph.has_errors() || graph.ir().outputs.empty()) return;

    auto result = eval->result("");
    auto* view = static_cast<VkImageView>(result.vk_image_view());
    if (!view || !sampler) return;

    viewport_desc = ImGui_ImplVulkan_AddTexture(sampler, view, VK_IMAGE_LAYOUT_GENERAL);
}

void App::reparse() {
    eval_error.clear();
    try {
        graph = ctx->parse_string(dsl_source.c_str());
        for (auto& d : graph.diagnostics()) {
            const char* lvl = d.level == joon::Diagnostic::Level::ERROR ? "ERROR" : "WARN";
            joon_log::write("[%s] %u:%u: %s\n", lvl, d.line, d.col, d.message.c_str());
        }
        if (!graph.has_errors()) {
            eval = ctx->create_evaluator(graph);
            eval->evaluate();
        } else {
            eval.reset();
        }
    } catch (const std::exception& e) {
        eval.reset();
        eval_error = e.what();
        joon_log::write("[EVAL] %s\n", eval_error.c_str());
    }
    source_dirty = false;
}

void App::update() {
    if (source_dirty) {
        reparse();
        viewport_dirty = true;
    }
    if (viewport_dirty && eval) {
        bind_viewport();
        viewport_dirty = false;
    }
}
