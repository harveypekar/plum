#define TINYOBJLOADER_IMPLEMENTATION
#include "tinyobjloader/tiny_obj_loader.h"

#include "scene/obj_loader.h"

#include <sstream>
#include <stdexcept>

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

} // namespace joon
