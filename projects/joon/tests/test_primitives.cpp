#include "catch_amalgamated.hpp"
#include "scene/primitives.h"
#include <algorithm>
#include <cmath>

using namespace joon;

TEST_CASE("Cube has 24 vertices / 36 indices, axis-aligned bounds, per-face normals", "[primitives]") {
    auto m = gen_cube(1.0f);
    CHECK(m.vertices.size() == 24);   // 4 verts/face × 6 faces
    CHECK(m.indices.size() == 36);    // 2 tris/face × 3 indices × 6 faces

    float minc = 999.f, maxc = -999.f;
    for (auto& v : m.vertices) {
        minc = std::min({minc, v.position.x, v.position.y, v.position.z});
        maxc = std::max({maxc, v.position.x, v.position.y, v.position.z});
    }
    CHECK(minc == Catch::Approx(-0.5f));
    CHECK(maxc == Catch::Approx( 0.5f));

    // Per-face normals: every group of 4 verts shares one normal.
    for (size_t f = 0; f < 6; ++f) {
        auto n = m.vertices[f * 4].normal;
        for (size_t i = 1; i < 4; ++i) {
            CHECK(m.vertices[f * 4 + i].normal.x == Catch::Approx(n.x));
            CHECK(m.vertices[f * 4 + i].normal.y == Catch::Approx(n.y));
            CHECK(m.vertices[f * 4 + i].normal.z == Catch::Approx(n.z));
        }
    }
}

TEST_CASE("Sphere has consistent vertex/index counts for given segments", "[primitives]") {
    auto m = gen_sphere(0.5f, /*lat=*/16, /*lon=*/32);
    // (lat+1) * (lon+1) verts, lat * lon * 6 indices
    CHECK(m.vertices.size() == 17 * 33);
    CHECK(m.indices.size()  == 16 * 32 * 6);

    // Every vertex is on the sphere of radius 0.5
    for (auto& v : m.vertices) {
        float r = std::sqrt(v.position.x*v.position.x
                          + v.position.y*v.position.y
                          + v.position.z*v.position.z);
        CHECK(r == Catch::Approx(0.5f).margin(1e-4f));
    }
}

TEST_CASE("Plane is 4 verts / 6 indices, lies in XZ at y=0, normal +Y", "[primitives]") {
    auto m = gen_plane(2.0f, 2.0f);
    CHECK(m.vertices.size() == 4);
    CHECK(m.indices.size() == 6);
    for (auto& v : m.vertices) {
        CHECK(v.position.y == Catch::Approx(0.f));
        CHECK(v.normal.y == Catch::Approx(1.f));
    }
}

TEST_CASE("Cylinder is closed (top + bottom caps + side strip)", "[primitives]") {
    int seg = 32;
    auto m = gen_cylinder(0.5f, 1.0f, seg);
    // Side strip: 2 verts per segment * (seg+1) (or seg*2 verts split per segment).
    // Caps: seg + 1 vert each (center + ring).
    // Index count: 6 * seg (side) + 3 * seg (top) + 3 * seg (bottom) = 12 * seg
    CHECK(m.indices.size() == size_t(12 * seg));
    // y bounds: [-0.5, 0.5]
    float ymin = 999.f, ymax = -999.f;
    for (auto& v : m.vertices) {
        ymin = std::min(ymin, v.position.y);
        ymax = std::max(ymax, v.position.y);
    }
    CHECK(ymin == Catch::Approx(-0.5f));
    CHECK(ymax == Catch::Approx( 0.5f));
}
