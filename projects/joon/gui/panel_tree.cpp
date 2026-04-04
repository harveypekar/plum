#include "app.h"
#include <imgui.h>

void App::draw_tree() {
    ImGui::Begin("Graph Tree");

    if (!graph.has_errors()) {
        auto& ir = graph.ir();

        if (ImGui::TreeNodeEx("Params", ImGuiTreeNodeFlags_DefaultOpen)) {
            for (auto& p : ir.params) {
                bool selected = (selected_node_id == p.node_id);
                if (ImGui::Selectable(p.name.c_str(), selected)) {
                    selected_node_id = p.node_id;
                }
            }
            ImGui::TreePop();
        }

        if (ImGui::TreeNodeEx("Nodes", ImGuiTreeNodeFlags_DefaultOpen)) {
            for (auto& node : ir.nodes) {
                if (node.op == "constant" || node.op == "string_constant" || node.op == "param")
                    continue;
                bool selected = (selected_node_id == node.id);
                std::string label = node.name.empty()
                    ? node.op + "##" + std::to_string(node.id)
                    : node.name + " (" + node.op + ")##" + std::to_string(node.id);
                if (ImGui::Selectable(label.c_str(), selected)) {
                    selected_node_id = node.id;
                }
            }
            ImGui::TreePop();
        }

        if (ImGui::TreeNodeEx("Outputs", ImGuiTreeNodeFlags_DefaultOpen)) {
            for (size_t i = 0; i < ir.outputs.size(); i++) {
                std::string label = "output " + std::to_string(i);
                bool selected = (selected_node_id == ir.outputs[i].node_id);
                if (ImGui::Selectable(label.c_str(), selected)) {
                    selected_node_id = ir.outputs[i].node_id;
                }
            }
            ImGui::TreePop();
        }
    } else {
        ImGui::TextDisabled("Parse errors - see log");
    }

    ImGui::End();
}
