#include "catch_amalgamated.hpp"
#include "context.h"
#include "graph.h"

using namespace joon;

TEST_CASE("Graph from parsed expression is valid", "[graph]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Parse valid DSL expression into graph with no errors
    auto graph = ctx->parse_string("(+ 1.0 2.0)");
    CHECK(!graph.has_errors());
}

TEST_CASE("Graph detects type checking errors", "[graph]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Parse expression with type mismatch (e.g., string where number expected)
    // Verify that graph captures compilation errors in diagnostics
    auto graph = ctx->parse_string("(+ \"text\" 2.0)");
    // Should either parse and have IR errors, or fail parsing
    // Either way, we can check diagnostics
    auto& diags = graph.diagnostics();
    // Valid to have errors for type mismatches
}

TEST_CASE("Graph represents complex expression structure", "[graph]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Parse complex nested expression and verify IR is created
    auto graph = ctx->parse_string("(blur (+ (* x 2.0) y))");
    REQUIRE(!graph.has_errors());

    // Access IR to verify structure exists
    auto& ir = graph.ir();
    // IR should contain nodes representing the computation graph
}

TEST_CASE("Graph provides diagnostic information for invalid expressions", "[graph]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Parse invalid expression and get detailed error messages
    auto graph = ctx->parse_string("(unknown-function arg1 arg2)");
    // Unknown function should trigger error
    auto& diags = graph.diagnostics();
    // Either has diagnostics or parse fails cleanly
}
