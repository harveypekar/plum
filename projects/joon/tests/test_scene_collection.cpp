#include "catch_amalgamated.hpp"
#include <joon/scene.h>

using namespace joon;

TEST_CASE("SceneCollection clear/add roundtrip", "[scene]") {
    SceneCollection s;
    Mesh m;
    m.vertices.push_back({{0,0,0},{0,1,0},{0,0}});
    s.add_object(SceneObject{m, {1,0,0}, {0,0,0}, {1,1,1}, UINT32_MAX});
    s.add_light(Light{LightType::Directional, {0,-1,0}, {0,0,0}, {1,1,1}, 1.0f, 30.0f});
    // Set camera to a NON-default fov so clear-preserves-camera is actually exercised
    // (vs trivially passing because both "preserve" and "reset to default" land on 60).
    s.set_camera(Camera{75.f, {1,2,3}, {0,0,0}, {0,1,0}, 0.1f, 100.f});

    CHECK(s.objects.size() == 1);
    CHECK(s.lights.size() == 1);
    CHECK(s.camera.fov_deg == Catch::Approx(75.f));
    CHECK(s.objects[0].position.x == Catch::Approx(1.f));

    s.clear();
    CHECK(s.objects.empty());
    CHECK(s.lights.empty());
    CHECK(s.camera.fov_deg == Catch::Approx(75.f));   // clear preserves the camera that was set
    CHECK(s.camera.position.x == Catch::Approx(1.f));
}
