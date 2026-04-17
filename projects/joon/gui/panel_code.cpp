#include "app.h"
#include <imgui.h>
#include <misc/cpp/imgui_stdlib.h>
#include <algorithm>

void App::draw_code() {
    ImGui::Begin("Code Editor");

    if (ImGui::IsWindowHovered() && ImGui::GetIO().KeyCtrl) {
        float wheel = ImGui::GetIO().MouseWheel;
        if (wheel != 0.0f) {
            codeFontScale = std::clamp(codeFontScale + wheel * 0.1f, 0.5f, 3.0f);
        }
    }

    ImGui::SetWindowFontScale(codeFontScale);

    ImGui::PushItemWidth(-1);
    if (ImGui::InputTextMultiline("##code", &dsl_source,
                                   ImVec2(-1, -1),
                                   ImGuiInputTextFlags_AllowTabInput)) {
        source_dirty = true;
    }
    ImGui::PopItemWidth();

    ImGui::SetWindowFontScale(1.0f);
    ImGui::End();
}
