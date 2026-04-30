#include "catch_amalgamated.hpp"
#include <joon/joon.h>
#include <joon/scene.h>

using namespace joon;

TEST_CASE("Evaluating a scene populates SceneCollection", "[scene][executors][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def c (cube :scale 1.0))
        (def s (sphere :radius 0.5))
        (def l (light :type directional :intensity 0.8))
        (def cam (camera :fov 75))
        (output 0.5)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto& scene = eval->scene_for_test();
    CHECK(scene.objects.size() == 2);
    CHECK(scene.lights.size() == 1);
    CHECK(scene.lights[0].intensity == Catch::Approx(0.8f));
    CHECK(scene.camera.fov_deg == Catch::Approx(75.0f));
}

TEST_CASE("SceneCollection is cleared between evaluate() calls", "[scene][executors][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def c (cube))
        (output 0.5)
    )");
    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();
    CHECK(eval->scene_for_test().objects.size() == 1);

    // Re-evaluate; objects must not accumulate.
    eval->evaluate();
    CHECK(eval->scene_for_test().objects.size() == 1);
}
