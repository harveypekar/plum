#define TINYOBJLOADER_IMPLEMENTATION
#include "tinyobjloader/tiny_obj_loader.h"

#include "scene/obj_loader.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

namespace joon {

static Mesh build_mesh(const tinyobj::attrib_t& attrib,
                       const std::vector<tinyobj::shape_t>& shapes) {
    Mesh out;
    for (const auto& shape : shapes) {
        for (const auto& idx : shape.mesh.indices) {
            // Bounds-check before indexing — tinyobjloader uses negative indices
            // as "absent" sentinels and doesn't validate index ranges itself.
            if (idx.vertex_index < 0 ||
                static_cast<size_t>(3 * idx.vertex_index + 2) >= attrib.vertices.size()) {
                throw std::runtime_error("OBJ has invalid vertex index");
            }
            Vertex v{};
            v.position = {
                attrib.vertices[3 * idx.vertex_index + 0],
                attrib.vertices[3 * idx.vertex_index + 1],
                attrib.vertices[3 * idx.vertex_index + 2],
            };
            if (idx.normal_index >= 0 &&
                static_cast<size_t>(3 * idx.normal_index + 2) < attrib.normals.size()) {
                v.normal = {
                    attrib.normals[3 * idx.normal_index + 0],
                    attrib.normals[3 * idx.normal_index + 1],
                    attrib.normals[3 * idx.normal_index + 2],
                };
            }
            if (idx.texcoord_index >= 0 &&
                static_cast<size_t>(2 * idx.texcoord_index + 1) < attrib.texcoords.size()) {
                v.uv = {
                    attrib.texcoords[2 * idx.texcoord_index + 0],
                    attrib.texcoords[2 * idx.texcoord_index + 1],
                };
            }
            out.vertices.push_back(v);
            out.indices.push_back(static_cast<uint32_t>(out.indices.size()));
        }
    }
    return out;
}

Mesh load_obj_string(const std::string& obj_text) {
    tinyobj::attrib_t attrib;
    std::vector<tinyobj::shape_t> shapes;
    std::vector<tinyobj::material_t> materials;
    std::string warn, err;
    std::istringstream iss(obj_text);
    if (!tinyobj::LoadObj(&attrib, &shapes, &materials, &warn, &err, &iss)) {
        throw std::runtime_error("OBJ parse failed: " + err);
    }
    if (shapes.empty()) {
        throw std::runtime_error("OBJ parse produced no shapes");
    }
    return build_mesh(attrib, shapes);
}

Mesh load_obj_file(const std::string& path) {
    tinyobj::attrib_t attrib;
    std::vector<tinyobj::shape_t> shapes;
    std::vector<tinyobj::material_t> materials;
    std::string warn, err;
    if (!tinyobj::LoadObj(&attrib, &shapes, &materials, &warn, &err, path.c_str())) {
        throw std::runtime_error("OBJ load failed: " + err);
    }
    if (shapes.empty()) {
        throw std::runtime_error("OBJ load produced no shapes from: " + path);
    }
    return build_mesh(attrib, shapes);
}

static Vertex build_vertex(const tinyobj::attrib_t& attrib,
                           const tinyobj::index_t& idx) {
    Vertex v{};
    if (idx.vertex_index >= 0 &&
        static_cast<size_t>(3 * idx.vertex_index + 2) < attrib.vertices.size()) {
        v.position = {
            attrib.vertices[3 * idx.vertex_index + 0],
            attrib.vertices[3 * idx.vertex_index + 1],
            attrib.vertices[3 * idx.vertex_index + 2],
        };
    }
    if (idx.normal_index >= 0 &&
        static_cast<size_t>(3 * idx.normal_index + 2) < attrib.normals.size()) {
        v.normal = {
            attrib.normals[3 * idx.normal_index + 0],
            attrib.normals[3 * idx.normal_index + 1],
            attrib.normals[3 * idx.normal_index + 2],
        };
    }
    if (idx.texcoord_index >= 0 &&
        static_cast<size_t>(2 * idx.texcoord_index + 1) < attrib.texcoords.size()) {
        v.uv = {
            attrib.texcoords[2 * idx.texcoord_index + 0],
            attrib.texcoords[2 * idx.texcoord_index + 1],
        };
    }
    return v;
}

std::vector<SubMesh> load_obj_with_materials(const std::string& path) {
    namespace fs = std::filesystem;
    std::string mtl_dir = fs::path(path).parent_path().string();
    if (!mtl_dir.empty()) mtl_dir += "/";

    tinyobj::attrib_t attrib;
    std::vector<tinyobj::shape_t> shapes;
    std::vector<tinyobj::material_t> materials;
    std::string warn, err;
    if (!tinyobj::LoadObj(&attrib, &shapes, &materials, &warn, &err,
                          path.c_str(), mtl_dir.c_str()))
        throw std::runtime_error("OBJ load failed: " + err);
    if (shapes.empty())
        throw std::runtime_error("OBJ load produced no shapes from: " + path);

    // Group faces by material_id across all shapes.
    std::unordered_map<int, Mesh> meshes_by_mat;

    for (const auto& shape : shapes) {
        size_t index_offset = 0;
        for (size_t f = 0; f < shape.mesh.num_face_vertices.size(); f++) {
            int mat_id = -1;
            if (f < shape.mesh.material_ids.size())
                mat_id = shape.mesh.material_ids[f];

            int fv = shape.mesh.num_face_vertices[f];
            auto& mesh = meshes_by_mat[mat_id];
            for (int vi = 0; vi < fv; vi++) {
                auto v = build_vertex(attrib, shape.mesh.indices[index_offset + vi]);
                mesh.indices.push_back(
                    static_cast<uint32_t>(mesh.vertices.size()));
                mesh.vertices.push_back(v);
            }
            index_offset += fv;
        }
    }

    std::vector<SubMesh> result;
    result.reserve(meshes_by_mat.size());
    for (auto& [mat_id, mesh] : meshes_by_mat) {
        SubMesh sm;
        sm.mesh = std::move(mesh);
        if (mat_id >= 0 && mat_id < static_cast<int>(materials.size())) {
            auto& m = materials[mat_id];
            if (!m.diffuse_texname.empty())
                sm.material.diffuse_tex = mtl_dir + m.diffuse_texname;
            if (!m.displacement_texname.empty())
                sm.material.normal_tex = mtl_dir + m.displacement_texname;
            else if (!m.bump_texname.empty())
                sm.material.normal_tex = mtl_dir + m.bump_texname;

            float ns = std::clamp(m.shininess, 0.0f, 1000.0f);
            sm.material.roughness = std::clamp(
                1.0f - std::sqrt(ns / 1000.0f), 0.04f, 1.0f);
            float ks_lum = 0.2126f * m.specular[0]
                         + 0.7152f * m.specular[1]
                         + 0.0722f * m.specular[2];
            sm.material.metallic = ks_lum > 0.5f ? 1.0f : 0.0f;
        }
        result.push_back(std::move(sm));
    }
    return result;
}

} // namespace joon
