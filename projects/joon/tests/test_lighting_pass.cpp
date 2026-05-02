#include "catch_amalgamated.hpp"
#include <joon/joon.h>
using namespace joon;

TEST_CASE("Deferred lighting produces lit output", "[shader][lighting][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [0.8 0.2 0.1 1]))))
        (def c (cube :scale 1.5 :material mat))
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

    int lit = 0;
    for (size_t i = 0; i < px.size(); i += 4)
        if (px[i] > 0.05f) ++lit;
    CHECK(lit > 100);
}
