#include "app.h"
#include <imgui.h>

void App::draw_viewport() {
    ImGui::Begin("Viewport");

    if (eval && !graph.has_errors() && !graph.ir().outputs.empty()) {
        auto result = eval->result("output");
        if (result.width() > 0) {
            // Update ImGui texture descriptor for the output image
            // viewport_desc is set up by the main loop when it binds VkImageView to ImGui
            ImVec2 avail = ImGui::GetContentRegionAvail();
            if (viewport_desc) {
                // Maintain aspect ratio
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
        }
    } else {
        ImGui::TextDisabled("No output");
    }

    ImGui::End();
}
