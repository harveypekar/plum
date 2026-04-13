#include "catch_amalgamated.hpp"
#include "nodes/node_registry.h"

using namespace joon;

TEST_CASE("NodeRegistry registers and retrieves nodes", "[nodes]") {
    NodeRegistry registry;
    bool called = false;
    registry.register_node("test_op", [&](const Node&, EvalContext&) { called = true; });

    auto* fn = registry.find("test_op");
    REQUIRE(fn != nullptr);
}

TEST_CASE("NodeRegistry returns null for unknown node", "[nodes]") {
    NodeRegistry registry;
    CHECK(registry.find("nonexistent") == nullptr);
}

TEST_CASE("Default registry has noise node", "[nodes]") {
    auto registry = NodeRegistry::create_default();
    CHECK(registry.find("noise") != nullptr);
    CHECK(registry.find("invert") != nullptr);
    CHECK(registry.find("levels") != nullptr);
    CHECK(registry.find("blur") != nullptr);
    CHECK(registry.find("blend") != nullptr);
}
