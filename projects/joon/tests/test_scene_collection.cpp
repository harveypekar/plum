#include "catch_amalgamated.hpp"
#include <joon/scene.h>

using namespace joon;

TEST_CASE("SceneCollection clear/add roundtrip", "[scene]") {
    SceneCollection s;
    Mesh m;
    m.vertices.push_back({{0,0,0},{0,1,0},{0,0}});
    s.add_object(SceneObject{m, {1,0,0}, {0,0,0}, {1,1,1}, 0});
    s.add_light(Light{LightType::Directional, {0,-1,0}, {0,0,0}, {1,1,1}, 1.0f, 30.0f});
    s.set_camera(Camera{60.f, {0,0,5}, {0,0,0}, {0,1,0}, 0.1f, 100.f});

    CHECK(s.objects.size() == 1);
    CHECK(s.lights.size() == 1);
    CHECK(s.camera.fov_deg == Catch::Approx(60.f));
    CHECK(s.objects[0].position.x == Catch::Approx(1.f));

    s.clear();
    CHECK(s.objects.empty());
    CHECK(s.lights.empty());
    CHECK(s.camera.fov_deg == Catch::Approx(60.f));   // default-constructed Camera has 60 fov per scene.h
}
