#include "catch_amalgamated.hpp"
#include <joon/joon.h>

#include <cmath>
#include <numeric>

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

static float avg_red(const std::vector<float>& pixels) {
    double sum = 0;
    size_t count = pixels.size() / 4;
    for (size_t i = 0; i < pixels.size(); i += 4)
        sum += pixels[i];
    return static_cast<float>(sum / count);
}

TEST_CASE("Param change produces different output after re-evaluate", "[evaluator][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string("(param val float 0.0 :min 0.0 :max 1.0) (output val)");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto r1 = eval->result("");
    auto px1 = r1.read_pixels();
    float avg1 = avg_red(px1);
    CHECK(avg1 < 0.01f);

    auto p = eval->param<float>("val");
    p = 1.0f;
    eval->evaluate();

    auto r2 = eval->result("");
    auto px2 = r2.read_pixels();
    float avg2 = avg_red(px2);
    CHECK(avg2 > 0.99f);

    REQUIRE(std::abs(avg2 - avg1) > 0.5f);
}

TEST_CASE("Multiple param re-evaluations produce correct values", "[evaluator][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string("(param x float 0.0 :min 0.0 :max 1.0) (output x)");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);

    float test_values[] = {0.0f, 0.25f, 0.5f, 0.75f, 1.0f};
    for (float val : test_values) {
        auto p = eval->param<float>("x");
        p = val;
        eval->evaluate();

        auto result = eval->result("");
        auto pixels = result.read_pixels();
        float avg = avg_red(pixels);
        CHECK(std::abs(avg - val) < 0.02f);
    }
}
