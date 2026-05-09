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

TEST_CASE("Dot access on pass output resolves to aliased image", "[shader][ir][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [1 0 0 1]))))
        (def c (cube :material mat))
        (def cam (camera))
        (def l (light))
        (def gbuf (pass))
        (def result (levels gbuf.albedo :contrast 1.5))
        (output result)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);
    int nonzero = 0;
    for (size_t i = 0; i < px.size(); i += 4)
        if (px[i] > 0.01f) ++nonzero;
    CHECK(nonzero > 50);
}

TEST_CASE("Custom toon BRDF produces stepped lighting", "[shader][brdf][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def toon_mat (shader
          :brdf (fn [normal light_dir view_dir albedo]
            (* albedo (step 0.3 (dot normal light_dir))))
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [0.3 0.8 0.2 1]))))
        (def c (cube :material toon_mat))
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
    int bright = 0;
    for (size_t i = 0; i < px.size(); i += 4) {
        if (px[i+1] > 0.5f) ++bright;
    }
    CHECK(bright > 50);
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

TEST_CASE("PBR Cook-Torrance BRDF compiles and produces lit output", "[shader][brdf][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def pbr (shader
          :brdf (fn [normal light_dir view_dir albedo]
            (set n_dot_l (max (dot normal light_dir) 0.0))
            (set h (normalize (+ light_dir view_dir)))
            (set n_dot_h (max (dot normal h) 0.0))
            (set n_dot_v (max (dot normal view_dir) 0.001))
            (set a2 (* roughness roughness))
            (set denom_inner (+ (* (* n_dot_h n_dot_h) (- a2 1.0)) 1.0))
            (set d (/ a2 (* 3.14159 (* denom_inner denom_inner))))
            (set f0 (lerp [0.04 0.04 0.04] albedo metallic))
            (set h_dot_v (max (dot h view_dir) 0.0))
            (set f (+ f0 (* (- 1.0 f0) (pow (- 1.0 h_dot_v) 5.0))))
            (set r1 (+ roughness 1.0))
            (set k (/ (* r1 r1) 8.0))
            (set g1 (/ n_dot_v (+ (* n_dot_v (- 1.0 k)) k)))
            (set g2 (/ n_dot_l (+ (* n_dot_l (- 1.0 k)) k)))
            (set spec (/ (* (* d f) (* g1 g2)) (+ (* (* 4.0 n_dot_v) n_dot_l) 0.001)))
            (set kd (* (- 1.0 metallic) (/ (- 1.0 f) 3.14159)))
            (set diffuse (* kd albedo))
            (* (+ diffuse spec) n_dot_l))
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [0.5 0.5 0.5 1]))))
        (def c (cube :material pbr))
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
    int lit = 0;
    for (size_t i = 0; i < px.size(); i += 4)
        if (px[i] > 0.01f) ++lit;
    CHECK(lit > 50);
}
