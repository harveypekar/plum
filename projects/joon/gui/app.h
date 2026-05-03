#pragma once

#include <joon/joon.h>
#include <joon/math.h>
#include "ir/ir_graph.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include <string>
#include <vector>
#include <memory>
#include <vulkan/vulkan.h>

struct GraphEntry {
    std::string name;
    std::string source;
};

struct App {
    std::unique_ptr<joon::Context> ctx;
    joon::Graph graph;
    std::unique_ptr<joon::Evaluator> eval;

    std::string dsl_source;
    std::string eval_error;
    bool source_dirty = true;
    bool viewport_dirty = true;
    float codeFontScale = 1.0f;
    uint32_t selected_node_id = UINT32_MAX;

    VkDescriptorSet viewport_desc = VK_NULL_HANDLE;
    VkDescriptorSet preview_desc = VK_NULL_HANDLE;
    VkSampler sampler = VK_NULL_HANDLE;
    VkDescriptorPool imgui_desc_pool = VK_NULL_HANDLE;

    bool show_code = true;
    bool show_tree = true;
    bool show_properties = true;
    bool show_viewport = true;
    bool show_preview = true;
    bool show_log = true;
    bool show_graphs = true;

    std::vector<GraphEntry> graph_entries;
    size_t active_graph_index = 0;

    joon::vec3 cam_pos{0, 0, 5};
    float cam_yaw = 0;
    float cam_pitch = 0;
    float cam_roll = 0;
    float cam_speed = 200.0f;
    float cam_mouse_sens = 0.003f;
    float cam_fov = 60.0f;
    float cam_near = 0.1f;
    float cam_far = 100.0f;
    bool cam_active = false;

    void init();
    void shutdown();
    void reparse();
    void bind_viewport();
    void update();
    void init_camera_from_scene();
    void apply_camera();

    void draw_tree();
    void draw_properties();
    void draw_code();
    void draw_viewport();
    void draw_preview();
    void draw_log();
    void draw_graphs();
};
