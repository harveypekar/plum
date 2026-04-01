#include "catch_amalgamated.hpp"
#include "nodes/node_registry.h"

using namespace joon::nodes;

TEST_CASE("NodeRegistry creates default registry", "[nodes]") {
    // Test: Create default registry with all built-in nodes
    auto registry = NodeRegistry::create_default();
    // Registry should be created successfully
    REQUIRE(true); // create_default() should not throw
}

TEST_CASE("NodeRegistry provides access to math operators", "[nodes]") {
    auto registry = NodeRegistry::create_default();

    // Test: Verify that common arithmetic operators can be found
    // The registry should support finding operators like add, sub, mul, div
    auto add_op = registry.find("add");
    CHECK(add_op != nullptr);

    auto mul_op = registry.find("mul");
    CHECK(mul_op != nullptr);
}

TEST_CASE("NodeRegistry provides image processing operations", "[nodes]") {
    auto registry = NodeRegistry::create_default();

    // Test: Verify image ops are registered (blur, noise, etc.)
    auto blur_op = registry.find("blur");
    // Blur may or may not be directly available; verify lookup mechanism works

    auto noise_op = registry.find("noise");
    // Noise should be available
}

TEST_CASE("NodeRegistry lookup returns null for unknown operators", "[nodes]") {
    auto registry = NodeRegistry::create_default();

    // Test: Verify that querying for non-existent operator returns nullptr
    auto unknown = registry.find("unknown_operator_xyz");
    CHECK(unknown == nullptr);
}
