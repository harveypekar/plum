#pragma once

#include <joon/joon.h>
#include "ir/ir_graph.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include <string>
#include <memory>
#include <vulkan/vulkan.h>

struct App {
    std::unique_ptr<joon::Context> ctx;
    joon::Graph graph;
    std::unique_ptr<joon::Evaluator> eval;

    std::string dsl_source;
    bool source_dirty = true;
    float codeFontScale = 1.0f;
    uint32_t selected_node_id = UINT32_MAX;

    VkDescriptorSet viewport_desc = VK_NULL_HANDLE;
    VkDescriptorSet preview_desc = VK_NULL_HANDLE;
    VkSampler sampler = VK_NULL_HANDLE;
    VkDescriptorPool imgui_desc_pool = VK_NULL_HANDLE;

    void init();
    void reparse();
    void update();

    void draw_tree();
    void draw_properties();
    void draw_code();
    void draw_viewport();
    void draw_preview();
    void draw_log();
};
