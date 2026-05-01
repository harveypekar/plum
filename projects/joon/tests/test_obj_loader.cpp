#include "catch_amalgamated.hpp"
#include "scene/obj_loader.h"
#include <cmath>

using namespace joon;

static const char* CUBE_OBJ = R"(
v -0.5 -0.5 -0.5
v  0.5 -0.5 -0.5
v  0.5  0.5 -0.5
v -0.5  0.5 -0.5
v -0.5 -0.5  0.5
v  0.5 -0.5  0.5
v  0.5  0.5  0.5
v -0.5  0.5  0.5
vn 0 0 -1
vn 0 0  1
f 1//1 2//1 3//1
f 1//1 3//1 4//1
f 5//2 6//2 7//2
f 5//2 7//2 8//2
)";

TEST_CASE("OBJ loader parses positions and indices", "[obj]") {
    auto mesh = load_obj_string(CUBE_OBJ);
    CHECK(mesh.vertices.size() >= 12);   // 4 verts/face × 2 faces with split normals
    CHECK(mesh.indices.size() == 12);    // 2 tris × 3 indices × 2 faces

    // Positions are within ±0.5
    for (auto& v : mesh.vertices) {
        CHECK(std::abs(v.position.x) <= 0.5f + 1e-5f);
        CHECK(std::abs(v.position.y) <= 0.5f + 1e-5f);
        CHECK(std::abs(v.position.z) <= 0.5f + 1e-5f);
    }
}

TEST_CASE("OBJ loader handles invalid input gracefully", "[obj]") {
    // tinyobjloader returns false on garbage and our wrapper throws.
    // Check the error path exists (don't be too strict about the wording).
    REQUIRE_THROWS(load_obj_string("not a real obj file\nnonsense\n"));
}
