#include "app.h"
#include <imgui.h>

void App::draw_log() {
    ImGui::Begin("Output Log");

    if (!eval_error.empty()) {
        ImGui::TextColored(ImVec4(1.0f, 0.3f, 0.3f, 1.0f),
                           "[EVAL] %s", eval_error.c_str());
    }

    if (graph.diagnostics().empty() && eval_error.empty()) {
        ImGui::TextDisabled("No messages");
    }

    for (auto& d : graph.diagnostics()) {
        ImVec4 color;
        const char* prefix;
        if (d.level == joon::Diagnostic::Level::ERROR) {
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
