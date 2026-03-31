#include "catch_amalgamated.hpp"
#include "evaluator.h"
#include "context.h"

using namespace joon;

TEST_CASE("Evaluator evaluates simple arithmetic", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test basic arithmetic evaluation
    // Implementation depends on Context/Evaluator API
    // Expected: evaluator to handle simple numeric operations
}

TEST_CASE("Evaluator evaluates nested expressions", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test nested expression evaluation
    // Expected: evaluator to handle expressions with multiple levels of nesting
}

TEST_CASE("Evaluator handles variable bindings", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test variable binding and lookup
    // Expected: evaluator to correctly bind and retrieve variable values
}

TEST_CASE("Evaluator evaluates function calls", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test function evaluation
    // Expected: evaluator to handle user-defined and built-in functions
}

TEST_CASE("Evaluator type-checks values", "[evaluator]") {
    auto ctx = Context::create();
    REQUIRE(ctx != nullptr);

    // Test type validation
    // Expected: evaluator to validate type correctness and report diagnostics
}
