#include "catch_amalgamated.hpp"
#include <joon/joon.h>

using namespace joon;

TEST_CASE("Geometry pass renders non-clear pixels", "[render][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def c (cube :scale 1.5))
        (def cam (camera :fov 60))
        (def l (light :intensity 1.0))
        (def gbuf (pass))
        (output gbuf)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);

    // Expect at least some lit pixels (not all clear color {0,0,0,1}).
    int lit = 0;
    for (size_t i = 0; i < px.size(); i += 4) {
        if (px[i + 0] > 0.05f || px[i + 1] > 0.05f || px[i + 2] > 0.05f) ++lit;
    }
    CHECK(lit > 100);
}

TEST_CASE("Compute can read geometry-pass output", "[render][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def c (cube))
        (def cam (camera))
        (def l (light))
        (def gbuf (pass))
        (def adjusted (levels gbuf :contrast 1.5))
        (output adjusted)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);
}
