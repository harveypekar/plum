#include "app.h"
#include <imgui.h>

void App::draw_preview() {
    ImGui::Begin("Node Preview");

    if (active_tab < 0 || active_tab >= (int)tabs.size()) {
        ImGui::TextDisabled("No graph open");
        ImGui::End();
        return;
    }

    auto& tab = tabs[active_tab];
    if (tab.eval && selected_node_id != UINT32_MAX) {
        auto* node = tab.graph.ir().find_node(selected_node_id);
        if (node) {
            std::string label = node->name.empty() ? node->op : node->name;
            ImGui::Text("Node: %s (#%u)", label.c_str(), node->id);
            ImGui::Separator();

            ImVec2 avail = ImGui::GetContentRegionAvail();
            if (preview_desc) {
                ImGui::Image((ImTextureID)preview_desc, avail);
            } else {
                ImGui::TextDisabled("No preview available");
            }
        }
    } else {
        ImGui::TextDisabled("Select a node in the tree");
    }

    ImGui::End();
}
