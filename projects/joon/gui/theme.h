#pragma once

#include <string>

// Load color theme from a JSON file and apply to ImGui.
// If the file doesn't exist, writes the current (default) theme to it.
void load_theme(const std::string& path);

// Write the current ImGui theme + app colors to a JSON file.
void save_theme(const std::string& path);

// App-specific colors (not part of ImGui style)
struct AppColors {
    float log_error[4]   = { 1.0f, 0.3f, 0.3f, 1.0f };
    float log_warning[4] = { 1.0f, 0.8f, 0.3f, 1.0f };
    float viewport_bg[4] = { 0.45f, 0.55f, 0.60f, 1.0f };
};

AppColors& app_colors();
