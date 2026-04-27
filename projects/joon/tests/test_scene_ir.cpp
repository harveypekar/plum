#include "catch_amalgamated.hpp"
#include <joon/joon.h>
#include "ir/ir_graph.h"
using namespace joon;

TEST_CASE("Scene ops are tagged with SCENE tier", "[scene][ir]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def c (cube :scale 1.0))
        (def s (sphere :radius 0.5))
        (def l (light :type directional))
        (def cam (camera :fov 60))
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto& ir = graph.ir();
    int scene_count = 0;
    for (auto& n : ir.nodes)
        if (n.tier == Tier::SCENE) ++scene_count;
    CHECK(scene_count == 4);
}

TEST_CASE("pass op is tagged with RENDER tier", "[scene][ir]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def scene (cube))
        (def cam (camera :fov 60))
        (def out (pass scene))
        (output out)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto& ir = graph.ir();
    bool found_render = false;
    for (auto& n : ir.nodes)
        if (n.tier == Tier::RENDER) { found_render = true; break; }
    CHECK(found_render);
}
