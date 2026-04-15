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
