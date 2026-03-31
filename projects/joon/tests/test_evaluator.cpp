#include "catch_amalgamated.hpp"
#include "evaluator.h"
#include "context.h"

using namespace joon;

TEST_CASE("Evaluator evaluates simple arithmetic", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Evaluate expression "(+ 1 2)" and verify result equals 3.0
    // Pattern: Parse source string → Create evaluator → Evaluate AST → Check result
    CHECK(false); // TODO: Implement after determining evaluator.evaluate() API
}

TEST_CASE("Evaluator evaluates nested expressions", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Evaluate nested expression "(+ (* 2 3) 4)" and verify result equals 10.0
    // Pattern: Verify operator precedence is preserved and results are correct
    CHECK(false); // TODO: Implement after determining evaluator.evaluate() API
}

TEST_CASE("Evaluator handles variable bindings", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Bind variable "x" to 5.0, reference it, verify lookup returns 5.0
    // Pattern: ctx->define("x", 5.0); auto result = ctx->lookup("x"); CHECK(result == 5.0)
    CHECK(false); // TODO: Implement after determining context.define() and lookup() API
}

TEST_CASE("Evaluator evaluates function calls", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Call built-in function "(abs -42)" and verify result equals 42.0
    // Pattern: Evaluate function call expression → Verify result matches expected value
    CHECK(false); // TODO: Implement after determining evaluator.evaluate() API for function calls
}

TEST_CASE("Evaluator type-checks values", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test: Attempt to pass wrong type to function (e.g., string to numeric function)
    // Pattern: Verify that type mismatch throws exception or returns error
    CHECK(false); // TODO: Implement error checking once API is determined
}
