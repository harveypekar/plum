#include "catch_amalgamated.hpp"
#include <joon/joon.h>
#include "vulkan/resource_pool.h"
using namespace joon;

TEST_CASE("alloc_depth_sampled creates depth with SAMPLED_BIT", "[shader][gpu]") {
    auto ctx = Context::create();
    auto& pool = ctx->pool();
    auto* depth = pool.alloc_depth_sampled(999, 512, 512);
    REQUIRE(depth != nullptr);
    CHECK(depth->view != VK_NULL_HANDLE);
    CHECK(depth->format == VK_FORMAT_D32_SFLOAT);
}

TEST_CASE("Material executor compiles shader and stores pipeline", "[shader][material][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [1 0 0 1]))))
        (def c (cube :material mat))
        (def cam (camera))
        (def l (light))
        (def gbuf (pass))
        (output gbuf)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);
    int red_pixels = 0;
    for (size_t i = 0; i < px.size(); i += 4)
        if (px[i] > 0.5f && px[i+1] < 0.2f && px[i+2] < 0.2f) ++red_pixels;
    CHECK(red_pixels > 50);
}
