#include "app.h"
#include <imgui.h>
#include <algorithm>
#include <cstring>

void App::draw_code() {
    ImGui::Begin("Code Editor");

    if (ImGui::IsWindowHovered() && ImGui::GetIO().KeyCtrl) {
        float wheel = ImGui::GetIO().MouseWheel;
        if (wheel != 0.0f) {
            codeFontScale = std::clamp(codeFontScale + wheel * 0.1f, 0.5f, 3.0f);
        }
    }

    ImGui::SetWindowFontScale(codeFontScale);

    static char buf[8192];
    if (dsl_source.size() < sizeof(buf)) {
        strncpy(buf, dsl_source.c_str(), sizeof(buf) - 1);
        buf[sizeof(buf) - 1] = '\0';
    }

    ImGui::PushItemWidth(-1);
    if (ImGui::InputTextMultiline("##code", buf, sizeof(buf),
                                   ImVec2(-1, -1),
                                   ImGuiInputTextFlags_AllowTabInput)) {
        dsl_source = buf;
        source_dirty = true;
    }
    ImGui::PopItemWidth();

    ImGui::SetWindowFontScale(1.0f);
    ImGui::End();
}
