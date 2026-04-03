#include "app.h"
#include "theme.h"
#include <imgui.h>

void App::draw_log() {
    ImGui::Begin("Output Log");

    if (active_tab < 0 || active_tab >= (int)tabs.size()) {
        ImGui::TextDisabled("No graph open");
        ImGui::End();
        return;
    }

    auto& tab = tabs[active_tab];
    if (tab.graph.diagnostics().empty()) {
        ImGui::TextDisabled("No messages");
    }

    auto& ac = app_colors();
    for (auto& d : tab.graph.diagnostics()) {
        ImVec4 color;
        const char* prefix;
        if (d.level == joon::ir::Diagnostic::Level::ERROR) {
            color = ImVec4(ac.log_error[0], ac.log_error[1], ac.log_error[2], ac.log_error[3]);
            prefix = "ERROR";
        } else {
            color = ImVec4(ac.log_warning[0], ac.log_warning[1], ac.log_warning[2], ac.log_warning[3]);
            prefix = "WARN";
        }
        ImGui::TextColored(color, "[%s] %u:%u: %s",
                           prefix, d.line, d.col, d.message.c_str());
    }

    ImGui::End();
}
