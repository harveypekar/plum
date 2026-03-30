#include "app.h"
#include <imgui.h>

void App::draw_log() {
    ImGui::Begin("Output Log");

    if (graph.diagnostics().empty()) {
        ImGui::TextDisabled("No messages");
    }

    for (auto& d : graph.diagnostics()) {
        ImVec4 color;
        const char* prefix;
        if (d.level == joon::ir::Diagnostic::Level::Error) {
            color = ImVec4(1.0f, 0.3f, 0.3f, 1.0f);
            prefix = "ERROR";
        } else {
            color = ImVec4(1.0f, 0.8f, 0.3f, 1.0f);
            prefix = "WARN";
        }
        ImGui::TextColored(color, "[%s] %u:%u: %s",
                           prefix, d.line, d.col, d.message.c_str());
    }

    ImGui::End();
}
