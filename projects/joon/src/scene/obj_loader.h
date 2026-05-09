#pragma once
#include <joon/scene.h>
#include <string>
#include <vector>

namespace joon {

Mesh load_obj_string(const std::string& obj_text);
Mesh load_obj_file(const std::string& path);

struct MaterialInfo {
    std::string diffuse_tex;
    std::string normal_tex;
    float roughness = 0.5f;
    float metallic  = 0.0f;
};

struct SubMesh {
    Mesh mesh;
    MaterialInfo material;
};

std::vector<SubMesh> load_obj_with_materials(const std::string& path);

} // namespace joon
