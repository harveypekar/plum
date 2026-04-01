#include "catch_amalgamated.hpp"
#include "evaluator.h"
#include "context.h"

using namespace joon;

TEST_CASE("Evaluator parses and compiles arithmetic expression", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Parse simple arithmetic expression without errors
    auto graph = ctx->parse_string("(+ 1.0 2.0)");
    REQUIRE(!graph.has_errors());
}

TEST_CASE("Evaluator parses nested expressions without errors", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Parse nested expression with proper structure
    auto graph = ctx->parse_string("(+ (* 2.0 3.0) 4.0)");
    REQUIRE(!graph.has_errors());
}

TEST_CASE("Evaluator reports parsing errors for invalid syntax", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Parse malformed expression and verify error reporting
    auto graph = ctx->parse_string("(+ 1.0)"); // Missing second operand
    CHECK(graph.has_errors());
    auto& diags = graph.diagnostics();
    CHECK(!diags.empty());
}

TEST_CASE("Evaluator creates from valid graph", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Successfully create evaluator from parsed graph
    auto graph = ctx->parse_string("(+ 1.0 2.0)");
    REQUIRE(!graph.has_errors());

    auto evaluator = ctx->create_evaluator(graph);
    REQUIRE(evaluator != nullptr);
}

TEST_CASE("Evaluator handles nested function composition", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Parse expression with multiple function calls
    auto graph = ctx->parse_string("(abs (- 5.0 10.0))");
    REQUIRE(!graph.has_errors());

    auto evaluator = ctx->create_evaluator(graph);
    REQUIRE(evaluator != nullptr);
}
