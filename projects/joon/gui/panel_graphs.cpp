#include "app.h"
#include <imgui.h>

void App::draw_graphs() {
    ImGui::Begin("Graphs", &show_graphs);

    for (size_t i = 0; i < graph_entries.size(); i++) {
        bool selected = (i == active_graph_index);
        if (ImGui::Selectable(graph_entries[i].name.c_str(), selected)) {
            active_graph_index = i;
            dsl_source = graph_entries[i].source;
            source_dirty = true;
        }
    }

    ImGui::End();
}
