#include "catch_amalgamated.hpp"
#include <joon/graph.h>
#include <joon/context.h>

using namespace joon;

TEST_CASE("Graph creates nodes from DSL", "[graph]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string("(def a (noise)) (def b (invert a)) (output b)");
    REQUIRE_FALSE(graph.has_errors());
    auto& ir = graph.ir();
    CHECK(ir.nodes.size() > 0);
    CHECK(ir.outputs.size() == 1);
}

TEST_CASE("Graph tracks edges between nodes", "[graph]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string("(def a (noise)) (def b (invert a)) (output b)");
    REQUIRE_FALSE(graph.has_errors());
    auto& ir = graph.ir();
    auto* b = ir.find_node_by_name("b");
    REQUIRE(b);
    REQUIRE(b->inputs.size() == 1);
}

TEST_CASE("Graph reports undefined symbol", "[graph]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string("(def b (invert nonexistent)) (output b)");
    CHECK(graph.has_errors());
}

TEST_CASE("Graph topological order covers all nodes", "[graph]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string("(def a (noise)) (def b (invert a)) (output b)");
    REQUIRE_FALSE(graph.has_errors());
    auto order = graph.ir().topological_order();
    CHECK(order.size() == graph.ir().nodes.size());
}
