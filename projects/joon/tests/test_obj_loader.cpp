#include "catch_amalgamated.hpp"
#include "scene/obj_loader.h"
#include <cmath>
#include <fstream>
#include <filesystem>

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

TEST_CASE("MTL roughness/metallic extraction", "[obj]") {
    namespace fs = std::filesystem;
    auto dir = fs::temp_directory_path() / "joon_test_mtl";
    fs::create_directories(dir);

    {
        std::ofstream f(dir / "test.mtl");
        f << "newmtl shiny_metal\n"
          << "Ns 250.0\n"
          << "Ks 0.8 0.8 0.8\n"
          << "map_Kd dummy.tga\n";
    }
    {
        std::ofstream f(dir / "test.obj");
        f << "mtllib test.mtl\n"
          << "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
          << "vn 0 0 1\n"
          << "usemtl shiny_metal\n"
          << "f 1//1 2//1 3//1\n";
    }

    auto submeshes = load_obj_with_materials((dir / "test.obj").string());
    REQUIRE(submeshes.size() == 1);
    CHECK(submeshes[0].material.roughness == Catch::Approx(0.5f).margin(0.01f));
    CHECK(submeshes[0].material.metallic == Catch::Approx(1.0f));

    fs::remove_all(dir);
}

TEST_CASE("MTL defaults when no Ns/Ks", "[obj]") {
    namespace fs = std::filesystem;
    auto dir = fs::temp_directory_path() / "joon_test_mtl2";
    fs::create_directories(dir);

    {
        std::ofstream f(dir / "test.mtl");
        f << "newmtl plain\n";
    }
    {
        std::ofstream f(dir / "test.obj");
        f << "mtllib test.mtl\n"
          << "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
          << "vn 0 0 1\n"
          << "usemtl plain\n"
          << "f 1//1 2//1 3//1\n";
    }

    auto submeshes = load_obj_with_materials((dir / "test.obj").string());
    REQUIRE(submeshes.size() == 1);
    CHECK(submeshes[0].material.roughness == Catch::Approx(0.968f).margin(0.01f));
    CHECK(submeshes[0].material.metallic == Catch::Approx(0.0f));

    fs::remove_all(dir);
}
