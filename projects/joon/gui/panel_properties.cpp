#include "app.h"
#include <imgui.h>

void App::draw_properties() {
    ImGui::Begin("Properties");

    if (eval && !graph.has_errors()) {
        for (auto& p : graph.ir().params) {
            if (!std::holds_alternative<float>(p.default_value)) continue;
            float val = std::get<float>(p.default_value);
            float min_v = 0.0f, max_v = 1.0f;

            auto it = p.constraints.find("min");
            if (it != p.constraints.end()) min_v = it->second;
            it = p.constraints.find("max");
            if (it != p.constraints.end()) max_v = it->second;

            if (ImGui::SliderFloat(p.name.c_str(), &val, min_v, max_v)) {
                p.default_value = val;
                auto param = eval->param<float>(p.name);
                param = val;
                eval->evaluate();
                viewport_dirty = true;
            }
        }
    } else {
        ImGui::TextDisabled("No active graph");
    }

    ImGui::End();
}
