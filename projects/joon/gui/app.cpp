#include "app.h"
#include "log.h"
#include <imgui.h>
#include <imgui_impl_vulkan.h>
#include <zep.h>
#include <zep/imgui/editor_imgui.h>
#include <zep/theme.h>
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

void App::init() {
    ctx = joon::Context::create();

    VkSamplerCreateInfo sampler_info{};
    sampler_info.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    sampler_info.magFilter = VK_FILTER_LINEAR;
    sampler_info.minFilter = VK_FILTER_LINEAR;
    sampler_info.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    sampler_info.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    vkCreateSampler(ctx->device().device, &sampler_info, nullptr, &sampler);

    init_editor();

    // Scan graphs/ directory and open any .jn files
    fs::path graphs_dir = fs::absolute("../../../graphs");
    if (fs::exists(graphs_dir)) {
        for (auto& entry : fs::directory_iterator(graphs_dir)) {
            if (entry.path().extension() == ".jn") {
                open_graph(entry.path().string());
            }
        }
    }
}

void App::new_graph() {
    std::string name = "Untitled " + std::to_string(++untitled_count);

    GraphTab tab;
    tab.path = "";  // No path yet - unsaved
    tab.name = name;

    // Parse default template
    std::string source = "(output (constant 0.5))";
    try {
        tab.graph = ctx->parse_string(source.c_str());
        if (!tab.graph.has_errors()) {
            tab.eval = ctx->create_evaluator(tab.graph);
            tab.eval->evaluate();
        }
    } catch (const std::exception&) {
        // Empty/error graph
    }

    tabs.push_back(std::move(tab));
    active_tab = tabs.size() - 1;
    update_viewport_desc();

    // Create Zep buffer (don't use InitWithText — it also adds a window,
    // which causes splits/crashes when called after initial setup)
    if (zep) {
        try {
            auto* buf = zep->GetEmptyBuffer(name);
            buf->SetText(source);
        } catch (const std::exception&) {
            // Zep buffer creation failed, but tab is still created
        }
    }
}

void App::open_graph(const std::string& path) {
    // Resolve to absolute path
    fs::path abs_path = fs::absolute(path);

    // Check if already open
    for (size_t i = 0; i < tabs.size(); i++) {
        if (!tabs[i].path.empty() && fs::absolute(tabs[i].path) == abs_path) {
            active_tab = static_cast<int>(i);
            return;
        }
    }

    // Create new tab
    GraphTab tab;
    tab.path = abs_path.string();
    tab.name = abs_path.stem().string();

    try {
        tab.graph = ctx->parse_file(abs_path.string().c_str());
        auto& ir = tab.graph.ir();
        jlog("open_graph: %s nodes=%d outputs=%d errors=%d",
             tab.name.c_str(), (int)ir.nodes.size(), (int)ir.outputs.size(), tab.graph.has_errors());
        for (size_t i = 0; i < ir.nodes.size(); i++) {
            jlog("  node[%d] op=%s const=%d", (int)i, ir.nodes[i].op.c_str(), ir.nodes[i].is_constant);
        }
        if (!tab.graph.has_errors()) {
            tab.eval = ctx->create_evaluator(tab.graph);
            tab.eval->evaluate();
        }
    } catch (const std::exception& e) {
        jlog("open_graph: exception %s", e.what());
    }

    // Open in Zep (just load the file buffer, ImGui tabs manage visibility)
    if (zep) {
        zep->GetFileBuffer(abs_path);
    }

    tabs.push_back(std::move(tab));
    active_tab = tabs.size() - 1;
    update_viewport_desc();
}

void App::close_tab(int idx) {
    if (idx < 0 || idx >= (int)tabs.size()) return;

    // TODO: warn on unsaved changes

    // Remove from Zep
    if (zep) {
        Zep::ZepBuffer* buf = nullptr;

        if (tabs[idx].path.empty()) {
            // Unsaved graph - find by display name
            for (auto& b : zep->GetBuffers()) {
                if (b->GetDisplayName() == tabs[idx].name) {
                    buf = b.get();
                    break;
                }
            }
        } else {
            // File graph
            buf = zep->GetFileBuffer(tabs[idx].path);
        }

        if (buf) {
            try {
                zep->RemoveBuffer(buf);
            } catch (const std::exception&) {}
        }
    }

    tabs.erase(tabs.begin() + idx);
    active_tab = (std::max)(-1, (std::min)(active_tab, (int)tabs.size() - 1));
}

void App::rename_tab(int idx, const std::string& new_name) {
    if (idx < 0 || idx >= (int)tabs.size()) return;
    if (new_name.empty()) return;

    std::string source = "(output (constant 0.5))";

    // Get source from Zep buffer if available
    if (zep) {
        Zep::ZepBuffer* buf = nullptr;

        if (tabs[idx].path.empty()) {
            // Unsaved graph - find by display name
            for (auto& b : zep->GetBuffers()) {
                if (b->GetDisplayName() == tabs[idx].name) {
                    buf = b.get();
                    break;
                }
            }
        } else {
            // File graph
            buf = zep->GetFileBuffer(tabs[idx].path);
        }

        if (buf) {
            source = buf->GetBufferText(buf->Begin(), buf->End());
            // Remove the old buffer before renaming
            try {
                zep->RemoveBuffer(buf);
            } catch (const std::exception&) {}
        }
    }

    // Resolve graphs directory
    fs::path graphs_dir = fs::absolute("../../../graphs");
    fs::create_directories(graphs_dir);

    // Write to new file
    fs::path new_path = graphs_dir / (new_name + ".jn");
    try {
        std::ofstream file(new_path);
        if (!file.is_open()) return;
        file << source;
        file.close();

        // Update tab
        tabs[idx].path = new_path.string();
        tabs[idx].name = new_name;
    } catch (const std::exception&) {
        // Failed to write
    }
}

void App::reparse(int idx) {
    if (idx < 0 || idx >= (int)tabs.size()) return;

    try {
        Zep::ZepBuffer* buf = nullptr;

        if (zep) {
            if (tabs[idx].path.empty()) {
                // Unsaved graph - find by display name
                for (auto& b : zep->GetBuffers()) {
                    if (b->GetDisplayName() == tabs[idx].name) {
                        buf = b.get();
                        break;
                    }
                }
            } else {
                // File graph
                buf = zep->GetFileBuffer(tabs[idx].path);
            }

            if (buf) {
                std::string source = buf->GetBufferText(buf->Begin(), buf->End());
                tabs[idx].graph = ctx->parse_string(source.c_str());
                tabs[idx].saved_update_count = buf->GetUpdateCount();
            }
        } else if (!tabs[idx].path.empty()) {
            tabs[idx].graph = ctx->parse_file(tabs[idx].path.c_str());
        }

        if (!tabs[idx].graph.has_errors()) {
            tabs[idx].eval = ctx->create_evaluator(tabs[idx].graph);
            tabs[idx].eval->evaluate();
        } else {
            tabs[idx].eval.reset();
        }
        tabs[idx].dirty = false;
        if (idx == active_tab) update_viewport_desc();
    } catch (const std::exception&) {
        tabs[idx].eval.reset();
    }
}

void App::update() {
    // Re-evaluate and refresh viewport when active tab changes
    static int last_viewport_tab = -1;
    if (active_tab != last_viewport_tab) {
        last_viewport_tab = active_tab;
        if (active_tab >= 0 && active_tab < (int)tabs.size()) {
            auto& tab = tabs[active_tab];
            jlog("tab switch: tab=%d eval=%p errors=%d", active_tab, (void*)tab.eval.get(), tab.graph.has_errors());
            if (tab.eval && !tab.graph.has_errors()) {
                tab.eval->evaluate();
                jlog("tab switch: evaluate done, pool_img[0]=%p", (void*)ctx->pool().get_image(0));
            }
        }
        update_viewport_desc();
    }

    // Poll buffers for changes — mark dirty but defer reparse
    for (int i = 0; i < (int)tabs.size(); i++) {
        if (!zep) continue;
        Zep::ZepBuffer* buf = nullptr;

        if (tabs[i].path.empty()) {
            for (auto& b : zep->GetBuffers()) {
                if (b->GetDisplayName() == tabs[i].name) {
                    buf = b.get();
                    break;
                }
            }
        } else {
            buf = zep->GetFileBuffer(tabs[i].path);
        }

        if (buf && buf->GetUpdateCount() != tabs[i].saved_update_count) {
            tabs[i].dirty = true;
            tabs[i].saved_update_count = buf->GetUpdateCount();
            pending_reparse_tab = i;
            reparse_cooldown = REPARSE_DELAY;
        }
    }

    // Debounced reparse — only fire after user stops typing
    if (pending_reparse_tab >= 0 && reparse_cooldown > 0.0f) {
        reparse_cooldown -= 1.0f / 60.0f; // approximate frame time
        if (reparse_cooldown <= 0.0f) {
            reparse(pending_reparse_tab);
            pending_reparse_tab = -1;
        }
    }
}

void App::update_viewport_desc() {
    if (!imgui_ready) return;
    if (active_tab < 0 || active_tab >= (int)tabs.size()) return;
    auto& tab = tabs[active_tab];
    if (!tab.eval || tab.graph.has_errors() || tab.graph.ir().outputs.empty()) return;

    auto result = tab.eval->result("output");
    VkImageView view = (VkImageView)result.vk_image_view();
    // Log from tab's graph AND from evaluator's result
    auto& ir = tab.graph.ir();
    // Also check pool directly
    auto* pool_img = ctx->pool().get_image(ir.outputs[0].node_id);
    jlog("viewport: tab=%d nodes=%d out_node=%u result=%ux%u pool_img=%p view=%p",
         active_tab, (int)ir.nodes.size(), ir.outputs[0].node_id,
         result.width(), result.height(), (void*)pool_img, (void*)view);
    if (!view) return;

    // Remove old descriptor before creating new one
    if (viewport_desc) {
        ImGui_ImplVulkan_RemoveTexture(viewport_desc);
        viewport_desc = VK_NULL_HANDLE;
    }

    viewport_desc = ImGui_ImplVulkan_AddTexture(sampler, view, VK_IMAGE_LAYOUT_GENERAL);
}

void App::init_editor() {
    if (!zep) {
        zep = std::make_unique<Zep::ZepEditor_ImGui>(
            "",
            Zep::NVec2f(1.0f, 1.0f)
        );
        auto black = Zep::NVec4f(0.0f, 0.0f, 0.0f, 1.0f);
        zep->GetTheme().SetColor(Zep::ThemeColor::Background, black);
        zep->GetTheme().SetColor(Zep::ThemeColor::LineNumberBackground, black);
        zep->GetTheme().SetColor(Zep::ThemeColor::CursorLineBackground, black);
        zep->GetTheme().SetColor(Zep::ThemeColor::AirlineBackground, black);
        zep->GetTheme().SetColor(Zep::ThemeColor::WidgetBackground, black);
    }
}

void App::destroy_editor() {
    zep.reset();
}

void App::render_zep_editor() {
    if (!zep || active_tab < 0 || active_tab >= (int)tabs.size()) return;

    // Only switch the active buffer when the tab changes.
    static int last_rendered_tab = -1;
    if (last_rendered_tab != active_tab) {
        last_rendered_tab = active_tab;

        Zep::ZepBuffer* buf = nullptr;
        if (tabs[active_tab].path.empty()) {
            for (auto& b : zep->GetBuffers()) {
                if (b->GetDisplayName() == tabs[active_tab].name) {
                    buf = b.get();
                    break;
                }
            }
        } else {
            buf = zep->GetFileBuffer(tabs[active_tab].path);
        }

        if (buf) {
            auto* tw = zep->GetTabWindows().empty()
                ? zep->AddTabWindow()
                : zep->GetTabWindows()[0];

            if (tw->GetWindows().empty()) {
                // No window exists yet — create one
                tw->AddWindow(buf, nullptr, Zep::RegionLayoutType::HBox);
            } else {
                // Window exists — just swap the buffer (no destroy/recreate)
                zep->GetTabWindows()[0]->GetWindows()[0]->SetBuffer(buf);
            }
        }
    }

    auto size = ImGui::GetContentRegionAvail();
    ImVec2 cursor_pos = ImGui::GetCursorScreenPos();

    zep->SetDisplayRegion(
        Zep::NVec2f(cursor_pos.x, cursor_pos.y),
        Zep::NVec2f(cursor_pos.x + size.x, cursor_pos.y + size.y)
    );

    // Zep's HandleInput uses deprecated ImGui key indices (raw ASCII)
    // which triggers asserts in modern ImGui. Only pass text input, not
    // raw keyboard events, until Zep is updated.
    if (ImGui::IsWindowFocused(ImGuiFocusedFlags_RootAndChildWindows)) {
        auto& io = ImGui::GetIO();
        if (!io.KeyCtrl && !io.KeyAlt) {
            zep->HandleInput();
        }
    }
    zep->Display();
}

App::App() = default;

App::~App() {
    destroy_editor();
    if (viewport_desc) {
        ImGui_ImplVulkan_RemoveTexture(viewport_desc);
        viewport_desc = VK_NULL_HANDLE;
    }
    if (preview_desc) {
        ImGui_ImplVulkan_RemoveTexture(preview_desc);
        preview_desc = VK_NULL_HANDLE;
    }
    if (ctx && sampler) {
        vkDestroySampler(ctx->device().device, sampler, nullptr);
        sampler = VK_NULL_HANDLE;
    }
}
