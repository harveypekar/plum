#pragma once

#include <joon/joon.h>
#include "ir/ir_graph.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include <string>
#include <memory>
#include <vector>
#include <vulkan/vulkan.h>

// Forward declare Zep types to avoid header-only implementation duplication
namespace Zep {
    class ZepEditor_ImGui;
}

struct GraphTab {
    std::string path;
    std::string name;
    joon::Graph graph;
    std::unique_ptr<joon::Evaluator> eval;
    bool dirty = false;
    uint64_t saved_update_count = 0;
};

struct App {
    std::unique_ptr<joon::Context> ctx;
    std::vector<GraphTab> tabs;
    int active_tab = -1;

    uint32_t selected_node_id = UINT32_MAX;
    int untitled_count = 0;

    // Debounce timer for reparse (avoid GPU stall every keystroke)
    float reparse_cooldown = 0.0f;
    static constexpr float REPARSE_DELAY = 0.3f; // seconds
    int pending_reparse_tab = -1;

    VkDescriptorSet viewport_desc = VK_NULL_HANDLE;
    VkDescriptorSet preview_desc = VK_NULL_HANDLE;
    VkSampler sampler = VK_NULL_HANDLE;
    bool imgui_ready = false;

    std::unique_ptr<Zep::ZepEditor_ImGui> zep;

    App();
    ~App();

    void init();
    void init_editor();
    void destroy_editor();
    void render_zep_editor();
    void new_graph();
    void open_graph(const std::string& path);
    void close_tab(int idx);
    void rename_tab(int idx, const std::string& new_name);
    void reparse(int idx);
    void update();
    void update_viewport_desc();

    void draw_tree();
    void draw_hierarchy();
    void draw_properties();
    void draw_code();
    void draw_viewport();
    void draw_preview();
    void draw_log();
};
