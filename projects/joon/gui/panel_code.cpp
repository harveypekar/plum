#include "app.h"
#include <imgui.h>

void App::draw_code() {
    ImGui::Begin("Code Editor");

    if (tabs.empty()) {
        ImGui::TextDisabled("No graphs open");
        ImGui::End();
        return;
    }

    // Tab bar — only force-select when active_tab changed externally
    static int last_code_tab = -1;
    bool tab_changed_externally = (active_tab != last_code_tab);

    if (ImGui::BeginTabBar("##tabs", ImGuiTabBarFlags_Reorderable)) {
        for (int i = 0; i < (int)tabs.size(); i++) {
            ImGuiTabItemFlags flags = 0;
            if (tab_changed_externally && active_tab == i)
                flags = ImGuiTabItemFlags_SetSelected;

            if (ImGui::BeginTabItem(tabs[i].name.c_str(), nullptr, flags)) {
                active_tab = i;
                ImGui::EndTabItem();
            }
        }
        ImGui::EndTabBar();
    }
    last_code_tab = active_tab;

    // Render active tab's editor
    if (active_tab >= 0 && active_tab < (int)tabs.size() && zep) {
        render_zep_editor();
    }

    ImGui::End();
}
