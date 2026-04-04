#include "app.h"
#include <imgui.h>
#include <cstring>

void App::draw_code() {
    ImGui::Begin("Code Editor");

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

    ImGui::End();
}
