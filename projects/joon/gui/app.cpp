#include "app.h"
#include "log.h"
#include <joon/math.h>
#include <imgui.h>
#include <imgui_impl_vulkan.h>
#include <algorithm>
#include <cmath>

void App::init() {
    ctx = joon::Context::create();
    ctx->device().log_fn = joon_log::write;

    graph_entries = {
        {"3D Scene", R"(; Joon - 3D scene with materials
(def red_mat (shader
  :fragment (fn [normal uv] -> [albedo vec4]
    (set albedo [0.8 0.2 0.1 1]))))

(def c (cube :scale 1.0 :material red_mat))
(def cam (camera :fov 60))
(def l (light :intensity 1.0))
(def gbuf (pass))
(param contrast float 1.0 :min 0.0 :max 3.0)
(def final (levels gbuf :contrast contrast))
(output final)
)"},
        {"Noise + Invert", R"(; Simple noise pipeline
(def a (noise :scale 4.0 :octaves 3))
(def b (invert a))
(output b)
)"},
        {"Levels", R"(; Parameterized levels
(def base (noise :scale 4.0 :octaves 3))
(param contrast float 1.0 :min 0.0 :max 3.0)
(def result (levels base :contrast contrast))
(output result)
)"},
        {"Constant", R"(; Constant output
(output 0.5)
)"},
        {"Sponza", R"(; Sponza atrium
(def mat (shader
  :fragment (fn [normal uv] -> [albedo vec4]
    (set albedo [0.5 0.45 0.4 1]))))

(def sponza (mesh "assets/scenes/sponza/sponza.obj" :material mat))
(def cam (camera :fov 75 :position [-500 400 0] :target [500 400 0] :near 1 :far 5000))
(def sun (light :direction [-0.5 -1 -0.3] :intensity 0.7))
(def gbuf (pass))
(output gbuf)
)"},
    };

    active_graph_index = 0;
    dsl_source = graph_entries[0].source;

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
    if (!eval || graph.has_errors() || graph.ir().outputs.empty()) {
        joon_log::write("[BIND] skip: eval=%p errors=%d outputs=%zu\n",
                        eval.get(), graph.has_errors(), graph.ir().outputs.size());
        if (viewport_desc) {
            ImGui_ImplVulkan_RemoveTexture(viewport_desc);
            viewport_desc = VK_NULL_HANDLE;
        }
        return;
    }

    auto result = eval->result("");
    auto* view = static_cast<VkImageView>(result.vk_image_view());
    joon_log::write("[BIND] view=%p sampler=%p w=%u h=%u\n",
                    view, sampler, result.width(), result.height());
    if (!view || !sampler) return;

    if (viewport_desc) {
        vkDeviceWaitIdle(ctx->device().device);
        ImGui_ImplVulkan_RemoveTexture(viewport_desc);
    }
    viewport_desc = ImGui_ImplVulkan_AddTexture(sampler, view, VK_IMAGE_LAYOUT_GENERAL);
    joon_log::write("[BIND] new descriptor=%p\n", viewport_desc);
}

void App::reparse() {
    eval_error.clear();
    eval.reset();
    if (viewport_desc) {
        vkDeviceWaitIdle(ctx->device().device);
        ImGui_ImplVulkan_RemoveTexture(viewport_desc);
        viewport_desc = VK_NULL_HANDLE;
    }
    if (preview_desc) {
        vkDeviceWaitIdle(ctx->device().device);
        ImGui_ImplVulkan_RemoveTexture(preview_desc);
        preview_desc = VK_NULL_HANDLE;
    }
    ctx->pool().clear();
    try {
        graph = ctx->parse_string(dsl_source.c_str());
        for (auto& d : graph.diagnostics()) {
            const char* lvl = d.level == joon::Diagnostic::Level::ERROR ? "ERROR" : "WARN";
            joon_log::write("[%s] %u:%u: %s\n", lvl, d.line, d.col, d.message.c_str());
        }
        if (!graph.has_errors()) {
            eval = ctx->create_evaluator(graph);
            eval->evaluate();
            init_camera_from_scene();
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

void App::init_camera_from_scene() {
    if (!eval) return;
    const auto& cam = eval->scene_for_test().camera;
    cam_pos = cam.position;
    cam_fov = cam.fov_deg;
    cam_near = cam.near_z;
    cam_far = cam.far_z;
    cam_roll = 0;
    cam_active = false;

    joon::vec3 dir = joon::vec3_normalize(cam.target - cam.position);
    cam_pitch = std::asin(std::clamp(dir.y, -1.0f, 1.0f));
    cam_yaw = std::atan2(dir.x, -dir.z);
}

void App::apply_camera() {
    if (!eval) return;
    using namespace joon;
    mat4 rot = mul(rotate_y(cam_yaw), mul(rotate_x(cam_pitch), rotate_z(cam_roll)));
    vec3 forward{-rot.m[8], -rot.m[9], -rot.m[10]};
    vec3 up{rot.m[4], rot.m[5], rot.m[6]};

    Camera cam;
    cam.position = cam_pos;
    cam.target = cam_pos + forward;
    cam.up = up;
    cam.fov_deg = cam_fov;
    cam.near_z = cam_near;
    cam.far_z = cam_far;

    eval->set_camera(cam);
    eval->render();
    viewport_dirty = true;
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
