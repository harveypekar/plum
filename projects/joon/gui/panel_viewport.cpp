#include "app.h"
#include <joon/math.h>
#include <imgui.h>
#include <algorithm>
#include <cmath>

void App::draw_viewport() {
    ImGui::Begin("Viewport", &show_viewport);

    bool hovered = ImGui::IsWindowHovered(ImGuiHoveredFlags_None);
    bool wants_kb = ImGui::GetIO().WantCaptureKeyboard;

    if (eval && hovered && !wants_kb) {
        using namespace joon;
        float dt = ImGui::GetIO().DeltaTime;

        mat4 rot = mul(rotate_y(cam_yaw), mul(rotate_x(cam_pitch), rotate_z(cam_roll)));
        vec3 forward{-rot.m[8], -rot.m[9], -rot.m[10]};
        vec3 right{rot.m[0], rot.m[1], rot.m[2]};

        bool moved = false;
        float speed = cam_speed * dt;

        if (ImGui::IsKeyDown(ImGuiKey_W)) { cam_pos = cam_pos + forward * speed; moved = true; }
        if (ImGui::IsKeyDown(ImGuiKey_R)) { cam_pos = cam_pos - forward * speed; moved = true; }
        if (ImGui::IsKeyDown(ImGuiKey_A)) { cam_pos = cam_pos - right * speed; moved = true; }
        if (ImGui::IsKeyDown(ImGuiKey_S)) { cam_pos = cam_pos + right * speed; moved = true; }
        if (ImGui::IsKeyDown(ImGuiKey_P)) { cam_pos.y += speed; moved = true; }
        if (ImGui::IsKeyDown(ImGuiKey_T)) { cam_pos.y -= speed; moved = true; }
        if (ImGui::IsKeyDown(ImGuiKey_Q)) { cam_roll -= 1.5f * dt; moved = true; }
        if (ImGui::IsKeyDown(ImGuiKey_F)) { cam_roll += 1.5f * dt; moved = true; }

        if (ImGui::IsMouseDown(ImGuiMouseButton_Right) && hovered) {
            ImVec2 delta = ImGui::GetIO().MouseDelta;
            if (delta.x != 0 || delta.y != 0) {
                cam_yaw += delta.x * cam_mouse_sens;
                cam_pitch -= delta.y * cam_mouse_sens;
                cam_pitch = std::clamp(cam_pitch, -1.5f, 1.5f);
                moved = true;
            }
        }

        if (moved) {
            cam_active = true;
            apply_camera();
        }
    }

    if (eval && !graph.has_errors() && !graph.ir().outputs.empty()) {
        auto result = eval->result("output");
        if (result.width() > 0) {
            ImVec2 avail = ImGui::GetContentRegionAvail();
            if (viewport_desc) {
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
