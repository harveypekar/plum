#include "app.h"
#include <imgui.h>
#include <string>
#include <variant>
#include <filesystem>
#include <algorithm>
#include <cstring>

namespace fs = std::filesystem;

void App::draw_hierarchy() {
    ImGui::Begin("Hierarchy");

    // Graphs section - flat file list
    if (ImGui::CollapsingHeader("Graphs", ImGuiTreeNodeFlags_DefaultOpen)) {
        static std::vector<std::string> graph_files;
        static bool scanned = false;
        static int renaming_tab_idx = -1;
        static char rename_buffer[256];

        if (!scanned) {
            graph_files.clear();
            fs::path graphs_dir = fs::absolute("../../../graphs");
            if (fs::exists(graphs_dir)) {
                for (auto& entry : fs::directory_iterator(graphs_dir)) {
                    if (entry.path().extension() == ".jn") {
                        graph_files.push_back(entry.path().string());
                    }
                }
                std::sort(graph_files.begin(), graph_files.end());
            }
            scanned = true;
        }

        // Show unsaved graphs and disk files
        std::vector<int> unsaved_tabs;
        for (int i = 0; i < (int)tabs.size(); i++) {
            if (tabs[i].path.empty()) unsaved_tabs.push_back(i);
        }

        // Draw unsaved graphs first
        for (int tab_idx : unsaved_tabs) {
            if (renaming_tab_idx == tab_idx) {
                // Edit mode for rename
                ImGui::SetKeyboardFocusHere();
                if (ImGui::InputText("##rename", rename_buffer, sizeof(rename_buffer), ImGuiInputTextFlags_EnterReturnsTrue)) {
                    // Save with new name
                    std::string new_name(rename_buffer);
                    if (!new_name.empty()) {
                        rename_tab(tab_idx, new_name);
                        graph_files.clear();
                        scanned = false;  // Rescan
                    }
                    renaming_tab_idx = -1;
                }
                if (ImGui::IsKeyPressed(ImGuiKey_Escape)) {
                    renaming_tab_idx = -1;
                }
            } else {
                bool selected = (active_tab == tab_idx);
                if (ImGui::Selectable(tabs[tab_idx].name.c_str(), selected)) {
                    active_tab = tab_idx;
                }
                if (ImGui::IsItemHovered() && ImGui::IsKeyPressed(ImGuiKey_F2)) {
                    renaming_tab_idx = tab_idx;
                    strncpy_s(rename_buffer, sizeof(rename_buffer), tabs[tab_idx].name.c_str(), sizeof(rename_buffer) - 1);
                }
            }
        }

        // Draw files from disk
        for (auto& path : graph_files) {
            std::string name = fs::path(path).stem().string();
            bool selected = (active_tab >= 0 && tabs[active_tab].path == path);
            if (ImGui::Selectable(name.c_str(), selected)) {
                // Selection only
            }
            if (ImGui::IsItemHovered() && ImGui::IsMouseDoubleClicked(0)) {
                open_graph(path);
            }
        }
    }

    // Assets section (placeholder)
    if (ImGui::CollapsingHeader("Assets")) {
        ImGui::TextDisabled("(empty)");
    }

    // Parameters section
    if (ImGui::CollapsingHeader("Parameters", ImGuiTreeNodeFlags_DefaultOpen)) {
        if (active_tab >= 0 && active_tab < (int)tabs.size() && !tabs[active_tab].graph.has_errors()) {
            for (auto& p : tabs[active_tab].graph.ir().params) {
                auto* float_ptr = std::get_if<float>(&p.default_value);
                if (float_ptr) {
                    float val = *float_ptr;
                    auto min_it = p.constraints.find("min");
                    auto max_it = p.constraints.find("max");
                    if (min_it != p.constraints.end() && max_it != p.constraints.end()) {
                        ImGui::Text("%-16s  %.3f  [%.1f..%.1f]",
                            p.name.c_str(), val, min_it->second, max_it->second);
                    } else {
                        ImGui::Text("%-16s  %.3f", p.name.c_str(), val);
                    }
                } else {
                    ImGui::Text("%s", p.name.c_str());
                }
            }
        } else {
            ImGui::TextDisabled("No active graph");
        }
    }

    ImGui::End();
}
