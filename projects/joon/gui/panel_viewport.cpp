#include "app.h"
#include <imgui.h>

void App::draw_viewport() {
    ImGui::Begin("Viewport");

    if (active_tab < 0 || active_tab >= (int)tabs.size()) {
        ImGui::TextDisabled("No graph open");
        ImGui::End();
        return;
    }

    auto& tab = tabs[active_tab];
    if (tab.eval && !tab.graph.has_errors() && !tab.graph.ir().outputs.empty()) {
        auto result = tab.eval->result("output");
        if (result.width() > 0 && viewport_desc) {
            ImVec2 avail = ImGui::GetContentRegionAvail();
            float aspect = static_cast<float>(result.width()) / result.height();
            float display_w = avail.x;
            float display_h = avail.x / aspect;
            if (display_h > avail.y) {
                display_h = avail.y;
                display_w = avail.y * aspect;
            }
            ImGui::Image((ImTextureID)viewport_desc, ImVec2(display_w, display_h));
        } else {
            ImGui::Text("Output: %dx%d", result.width(), result.height());
        }
    } else {
        ImGui::TextDisabled("No output");
    }

    ImGui::End();
}
