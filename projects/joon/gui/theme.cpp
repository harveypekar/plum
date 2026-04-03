#include "theme.h"
#include <imgui.h>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <filesystem>
#include <cstring>

static AppColors s_appColors;

AppColors& app_colors() { return s_appColors; }

// Map ImGuiCol_ enum to JSON key names
static const char* color_name(int idx) {
    switch (idx) {
    case ImGuiCol_Text:                    return "Text";
    case ImGuiCol_TextDisabled:            return "TextDisabled";
    case ImGuiCol_WindowBg:                return "WindowBg";
    case ImGuiCol_ChildBg:                 return "ChildBg";
    case ImGuiCol_PopupBg:                 return "PopupBg";
    case ImGuiCol_Border:                  return "Border";
    case ImGuiCol_BorderShadow:            return "BorderShadow";
    case ImGuiCol_FrameBg:                 return "FrameBg";
    case ImGuiCol_FrameBgHovered:          return "FrameBgHovered";
    case ImGuiCol_FrameBgActive:           return "FrameBgActive";
    case ImGuiCol_TitleBg:                 return "TitleBg";
    case ImGuiCol_TitleBgActive:           return "TitleBgActive";
    case ImGuiCol_TitleBgCollapsed:        return "TitleBgCollapsed";
    case ImGuiCol_MenuBarBg:               return "MenuBarBg";
    case ImGuiCol_ScrollbarBg:             return "ScrollbarBg";
    case ImGuiCol_ScrollbarGrab:           return "ScrollbarGrab";
    case ImGuiCol_ScrollbarGrabHovered:    return "ScrollbarGrabHovered";
    case ImGuiCol_ScrollbarGrabActive:     return "ScrollbarGrabActive";
    case ImGuiCol_CheckMark:               return "CheckMark";
    case ImGuiCol_SliderGrab:              return "SliderGrab";
    case ImGuiCol_SliderGrabActive:        return "SliderGrabActive";
    case ImGuiCol_Button:                  return "Button";
    case ImGuiCol_ButtonHovered:           return "ButtonHovered";
    case ImGuiCol_ButtonActive:            return "ButtonActive";
    case ImGuiCol_Header:                  return "Header";
    case ImGuiCol_HeaderHovered:           return "HeaderHovered";
    case ImGuiCol_HeaderActive:            return "HeaderActive";
    case ImGuiCol_Separator:               return "Separator";
    case ImGuiCol_SeparatorHovered:        return "SeparatorHovered";
    case ImGuiCol_SeparatorActive:         return "SeparatorActive";
    case ImGuiCol_ResizeGrip:              return "ResizeGrip";
    case ImGuiCol_ResizeGripHovered:       return "ResizeGripHovered";
    case ImGuiCol_ResizeGripActive:        return "ResizeGripActive";
    case ImGuiCol_InputTextCursor:         return "InputTextCursor";
    case ImGuiCol_TabHovered:              return "TabHovered";
    case ImGuiCol_Tab:                     return "Tab";
    case ImGuiCol_TabSelected:             return "TabSelected";
    case ImGuiCol_TabSelectedOverline:     return "TabSelectedOverline";
    case ImGuiCol_TabDimmed:               return "TabDimmed";
    case ImGuiCol_TabDimmedSelected:       return "TabDimmedSelected";
    case ImGuiCol_TabDimmedSelectedOverline: return "TabDimmedSelectedOverline";
    case ImGuiCol_DockingPreview:          return "DockingPreview";
    case ImGuiCol_DockingEmptyBg:          return "DockingEmptyBg";
    case ImGuiCol_PlotLines:               return "PlotLines";
    case ImGuiCol_PlotLinesHovered:        return "PlotLinesHovered";
    case ImGuiCol_PlotHistogram:           return "PlotHistogram";
    case ImGuiCol_PlotHistogramHovered:    return "PlotHistogramHovered";
    case ImGuiCol_TableHeaderBg:           return "TableHeaderBg";
    case ImGuiCol_TableBorderStrong:       return "TableBorderStrong";
    case ImGuiCol_TableBorderLight:        return "TableBorderLight";
    case ImGuiCol_TableRowBg:              return "TableRowBg";
    case ImGuiCol_TableRowBgAlt:           return "TableRowBgAlt";
    case ImGuiCol_TextLink:                return "TextLink";
    case ImGuiCol_TextSelectedBg:          return "TextSelectedBg";
    case ImGuiCol_TreeLines:               return "TreeLines";
    case ImGuiCol_DragDropTarget:          return "DragDropTarget";
    case ImGuiCol_DragDropTargetBg:        return "DragDropTargetBg";
    case ImGuiCol_UnsavedMarker:           return "UnsavedMarker";
    case ImGuiCol_NavCursor:               return "NavCursor";
    case ImGuiCol_NavWindowingHighlight:   return "NavWindowingHighlight";
    case ImGuiCol_NavWindowingDimBg:       return "NavWindowingDimBg";
    case ImGuiCol_ModalWindowDimBg:        return "ModalWindowDimBg";
    default:                               return nullptr;
    }
}

static int color_index(const std::string& name) {
    for (int i = 0; i < ImGuiCol_COUNT; i++) {
        const char* n = color_name(i);
        if (n && name == n) return i;
    }
    return -1;
}

// Minimal JSON writing: "key": [r, g, b, a]
static void write_color(std::ofstream& f, const char* key, const float* c, bool last = false) {
    char buf[128];
    snprintf(buf, sizeof(buf), "    \"%s\": [%.2f, %.2f, %.2f, %.2f]%s\n",
             key, c[0], c[1], c[2], c[3], last ? "" : ",");
    f << buf;
}

void save_theme(const std::string& path) {
    std::ofstream f(path);
    if (!f.is_open()) return;

    f << "{\n";

    ImVec4* colors = ImGui::GetStyle().Colors;
    for (int i = 0; i < ImGuiCol_COUNT; i++) {
        const char* name = color_name(i);
        if (!name) continue;
        float c[4] = { colors[i].x, colors[i].y, colors[i].z, colors[i].w };
        write_color(f, name, c);
    }

    // App-specific colors
    write_color(f, "App_LogError",   s_appColors.log_error);
    write_color(f, "App_LogWarning", s_appColors.log_warning);
    write_color(f, "App_ViewportBg", s_appColors.viewport_bg, true);

    f << "}\n";
}

// Minimal JSON parser: reads { "key": [f, f, f, f], ... }
static bool parse_color(const std::string& value, float out[4]) {
    // value looks like "[0.26, 0.59, 0.98, 1.00]"
    float r, g, b, a;
    if (sscanf(value.c_str(), " [ %f , %f , %f , %f ]", &r, &g, &b, &a) == 4) {
        out[0] = r; out[1] = g; out[2] = b; out[3] = a;
        return true;
    }
    return false;
}

void load_theme(const std::string& path) {
    // Apply dark theme as baseline, then override backgrounds to pure black
    ImGui::StyleColorsDark();
    ImVec4 black(0.0f, 0.0f, 0.0f, 1.0f);
    ImVec4* c = ImGui::GetStyle().Colors;
    c[ImGuiCol_WindowBg]        = black;
    c[ImGuiCol_ChildBg]         = black;
    c[ImGuiCol_PopupBg]         = black;
    c[ImGuiCol_FrameBg]         = ImVec4(0.10f, 0.10f, 0.10f, 1.0f);
    c[ImGuiCol_TitleBg]         = black;
    c[ImGuiCol_TitleBgActive]   = ImVec4(0.10f, 0.10f, 0.10f, 1.0f);
    c[ImGuiCol_TitleBgCollapsed]= black;
    c[ImGuiCol_MenuBarBg]       = black;
    c[ImGuiCol_ScrollbarBg]     = black;
    c[ImGuiCol_TableHeaderBg]   = ImVec4(0.10f, 0.10f, 0.10f, 1.0f);
    c[ImGuiCol_TableRowBg]      = black;
    c[ImGuiCol_DockingEmptyBg]  = black;
    s_appColors.viewport_bg[0] = 0.0f;
    s_appColors.viewport_bg[1] = 0.0f;
    s_appColors.viewport_bg[2] = 0.0f;
    s_appColors.viewport_bg[3] = 1.0f;

    if (!std::filesystem::exists(path)) {
        // Write default theme so user can edit it
        save_theme(path);
        return;
    }

    std::ifstream f(path);
    if (!f.is_open()) return;

    std::string line;
    ImVec4* colors = ImGui::GetStyle().Colors;

    while (std::getline(f, line)) {
        // Find "key": [...]
        auto quote1 = line.find('"');
        if (quote1 == std::string::npos) continue;
        auto quote2 = line.find('"', quote1 + 1);
        if (quote2 == std::string::npos) continue;

        std::string key = line.substr(quote1 + 1, quote2 - quote1 - 1);

        auto bracket = line.find('[', quote2);
        if (bracket == std::string::npos) continue;
        auto bracket_end = line.find(']', bracket);
        if (bracket_end == std::string::npos) continue;

        std::string value = line.substr(bracket, bracket_end - bracket + 1);
        float c[4];
        if (!parse_color(value, c)) continue;

        // ImGui colors
        int idx = color_index(key);
        if (idx >= 0) {
            colors[idx] = ImVec4(c[0], c[1], c[2], c[3]);
            continue;
        }

        // App colors
        if (key == "App_LogError")        memcpy(s_appColors.log_error,   c, sizeof(c));
        else if (key == "App_LogWarning") memcpy(s_appColors.log_warning, c, sizeof(c));
        else if (key == "App_ViewportBg") memcpy(s_appColors.viewport_bg, c, sizeof(c));
    }
}
