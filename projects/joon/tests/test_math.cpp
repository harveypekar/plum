#include "catch_amalgamated.hpp"
#include <joon/math.h>

using namespace joon;

TEST_CASE("identity_mat4 is the identity", "[math]") {
    auto i = identity_mat4();
    for (int c = 0; c < 4; ++c)
        for (int r = 0; r < 4; ++r) {
            float expected = (c == r) ? 1.0f : 0.0f;
            CHECK(i.m[c * 4 + r] == Catch::Approx(expected));
        }
}

TEST_CASE("mul(identity, M) == M and mul(M, identity) == M", "[math]") {
    mat4 m = translate({1, 2, 3});
    auto a = mul(identity_mat4(), m);
    auto b = mul(m, identity_mat4());
    for (int i = 0; i < 16; ++i) {
        CHECK(a.m[i] == Catch::Approx(m.m[i]));
        CHECK(b.m[i] == Catch::Approx(m.m[i]));
    }
}

TEST_CASE("translate puts the translation in the last column", "[math]") {
    auto t = translate({4, 5, 6});
    CHECK(t.m[12] == Catch::Approx(4.f));
    CHECK(t.m[13] == Catch::Approx(5.f));
    CHECK(t.m[14] == Catch::Approx(6.f));
    CHECK(t.m[15] == Catch::Approx(1.f));
}

TEST_CASE("vec3_normalize produces unit length", "[math]") {
    auto u = vec3_normalize({3, 0, 4});   // length 5
    CHECK(vec3_len(u) == Catch::Approx(1.f));
    auto z = vec3_normalize({0, 0, 0});
    CHECK(z.x == Catch::Approx(0.f));
    CHECK(z.y == Catch::Approx(0.f));
    CHECK(z.z == Catch::Approx(0.f));
}

TEST_CASE("look_at from {0,0,5} towards origin produces sane right/up/forward", "[math]") {
    auto v = look_at({0, 0, 5}, {0, 0, 0}, {0, 1, 0});
    // forward (-Z in view space) → world -Z → m[2]=-(-1)=+1? Layout per perspective.
    // Simpler: applying view to the eye position should give origin.
    // view * vec4(eye, 1) = (0, 0, 0, 1)
    float vx = v.m[0]*0 + v.m[4]*0 + v.m[8]*5  + v.m[12]*1;
    float vy = v.m[1]*0 + v.m[5]*0 + v.m[9]*5  + v.m[13]*1;
    float vz = v.m[2]*0 + v.m[6]*0 + v.m[10]*5 + v.m[14]*1;
    CHECK(vx == Catch::Approx(0.f).margin(1e-4f));
    CHECK(vy == Catch::Approx(0.f).margin(1e-4f));
    CHECK(vz == Catch::Approx(0.f).margin(1e-4f));
}

TEST_CASE("perspective_vk negates m[5] for Vulkan Y-down clip space", "[math]") {
    auto p = perspective_vk(60.f, 1.0f, 0.1f, 100.f);
    CHECK(p.m[5] < 0.f);
}
