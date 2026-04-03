#include "app.h"
#include <imgui.h>

void App::draw_properties() {
    ImGui::Begin("Properties");

    if (active_tab < 0 || active_tab >= (int)tabs.size()) {
        ImGui::TextDisabled("No graph open");
        ImGui::End();
        return;
    }

    auto& tab = tabs[active_tab];
    if (tab.eval && !tab.graph.has_errors()) {
        for (auto& p : tab.graph.ir().params) {
            auto* float_val = std::get_if<float>(&p.default_value);
            if (!float_val) {
                ImGui::Text("%s (non-float)", p.name.c_str());
                continue;
            }
            float val = *float_val;
            float min_v = 0.0f, max_v = 1.0f;

            auto it = p.constraints.find("min");
            if (it != p.constraints.end()) min_v = it->second;
            it = p.constraints.find("max");
            if (it != p.constraints.end()) max_v = it->second;

            if (ImGui::SliderFloat(p.name.c_str(), &val, min_v, max_v)) {
                auto param = tab.eval->param<float>(p.name);
                param = val;
                tab.eval->evaluate();
                update_viewport_desc();
            }
        }
    } else {
        ImGui::TextDisabled("No active graph");
    }

    ImGui::End();
}
