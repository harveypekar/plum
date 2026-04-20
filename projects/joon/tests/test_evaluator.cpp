#include "catch_amalgamated.hpp"
#include <joon/joon.h>

#include <cmath>

using namespace joon;

TEST_CASE("Evaluator runs a constant-output graph", "[evaluator][gpu]") {
    // Full integration: parse → type-check → build IRGraph →
    // create Vulkan device/pipeline cache → dispatch the `noise` shader
    // for the param indirection? No — a bare `(output 0.5)` takes the
    // constant path in Interpreter::evaluate which allocates an image and
    // uploads a solid-color buffer. No compute shader required.
    auto ctx = Context::create();
    auto graph = ctx->parse_string("(output 0.5)");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto result = eval->result("");
    REQUIRE(result.width() > 0);
    REQUIRE(result.height() > 0);

    auto pixels = result.read_pixels();
    REQUIRE(pixels.size() == result.width() * result.height() * 4);

    // Every RGB channel should be 0.5; alpha should be 1.0.
    // Sample a few points rather than checking all — the upload path is
    // a simple memcpy so a handful of samples is sufficient coverage.
    const size_t w = result.width(), h = result.height();
    const size_t samples[][2] = {
        {0, 0}, {w / 2, h / 2}, {w - 1, h - 1}, {0, h - 1}, {w - 1, 0}
    };
    for (auto& [x, y] : samples) {
        size_t i = (y * w + x) * 4;
        CHECK(std::abs(pixels[i + 0] - 0.5f) < 1e-5f);
        CHECK(std::abs(pixels[i + 1] - 0.5f) < 1e-5f);
        CHECK(std::abs(pixels[i + 2] - 0.5f) < 1e-5f);
        CHECK(std::abs(pixels[i + 3] - 1.0f) < 1e-5f);
    }
}

TEST_CASE("Param change produces different output after re-evaluate", "[evaluator][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def base (noise :scale 4.0 :octaves 3))
        (param contrast float 1.0 :min 0.0 :max 3.0)
        (def result (levels base :contrast contrast))
        (output result)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto r0 = eval->result("");
    REQUIRE(r0.width() > 0);
    auto pixels_before = r0.read_pixels();

    auto param = eval->param<float>("contrast");
    param = 0.0f;
    eval->evaluate();

    auto pixels_after = eval->result("").read_pixels();
    REQUIRE(pixels_before.size() == pixels_after.size());

    double diff = 0.0;
    for (size_t i = 0; i < pixels_before.size(); i++)
        diff += std::abs(pixels_before[i] - pixels_after[i]);
    diff /= static_cast<double>(pixels_before.size());

    CHECK(diff > 0.01);
}

TEST_CASE("Param kwarg updates propagate through levels node", "[evaluator][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (param val float 0.5 :min 0.0 :max 1.0)
        (def result (levels val :contrast 1.0))
        (output result)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);

    float values[] = { 0.0f, 0.25f, 0.5f, 0.75f, 1.0f };
    std::vector<float> prev_pixels;

    for (float v : values) {
        auto param = eval->param<float>("val");
        param = v;
        eval->evaluate();

        auto pixels = eval->result("").read_pixels();
        REQUIRE(pixels.size() > 0);

        if (!prev_pixels.empty()) {
            double diff = 0.0;
            for (size_t i = 0; i < pixels.size(); i++)
                diff += std::abs(pixels[i] - prev_pixels[i]);
            diff /= static_cast<double>(pixels.size());
            CHECK(diff > 0.001);
        }
        prev_pixels = pixels;
    }
}
