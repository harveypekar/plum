#include "catch_amalgamated.hpp"
#include "dsl/parser.h"
#include "ir/ir_graph.h"
#include "ir/type_checker.h"

using namespace joon;

static ir::IRGraph build(const char* src) {
    dsl::Parser parser(src);
    auto program = parser.parse();
    auto graph = ir::IRGraph::from_ast(program);
    ir::type_check(graph);
    return graph;
}

TEST_CASE("Type: noise is float", "[types]") {
    auto g = build("(def n (noise :scale 4.0)) (output n)");
    auto* n = g.find_node_by_name("n");
    REQUIRE(n);
    CHECK(n->output_type == Type::FLOAT);
}

TEST_CASE("Type: image load is image", "[types]") {
    auto g = build(R"((def b (image "t.png")) (output b))");
    auto* b = g.find_node_by_name("b");
    REQUIRE(b);
    CHECK(b->output_type == Type::IMAGE);
}

TEST_CASE("Type: float * image promotes to image", "[types]") {
    auto g = build(R"(
        (def b (image "t.png"))
        (def n (noise :scale 1.0))
        (def r (* b n))
        (output r)
    )");
    auto* r = g.find_node_by_name("r");
    REQUIRE(r);
    CHECK(r->output_type == Type::IMAGE);
}

TEST_CASE("Type: float + float stays float", "[types]") {
    auto g = build("(def r (+ 1.0 2.0)) (output r)");
    auto* r = g.find_node_by_name("r");
    REQUIRE(r);
    CHECK(r->output_type == Type::FLOAT);
}

TEST_CASE("Type: color is vec3", "[types]") {
    auto g = build("(def c (color 0.8 0.3 0.1)) (output c)");
    auto* c = g.find_node_by_name("c");
    REQUIRE(c);
    CHECK(c->output_type == Type::VEC3);
}

TEST_CASE("Type: vec3 * image promotes to image", "[types]") {
    auto g = build(R"(
        (def b (image "t.png"))
        (def c (color 0.8 0.3 0.1))
        (def r (* b c))
        (output r)
    )");
    auto* r = g.find_node_by_name("r");
    REQUIRE(r);
    CHECK(r->output_type == Type::IMAGE);
}

TEST_CASE("Type: float * vec3 promotes to vec3", "[types]") {
    auto g = build("(def c (color 0.8 0.3 0.1)) (def r (* c 0.5)) (output r)");
    auto* r = g.find_node_by_name("r");
    REQUIRE(r);
    CHECK(r->output_type == Type::VEC3);
}

TEST_CASE("Type: undefined symbol produces error", "[types]") {
    auto g = build("(def r (* x 1.0)) (output r)");
    bool has_error = false;
    for (auto& d : g.diagnostics) {
        if (d.level == ir::Diagnostic::Level::ERROR &&
            d.message.find("Undefined symbol") != std::string::npos) {
            has_error = true;
        }
    }
    CHECK(has_error);
}

TEST_CASE("Type: topological order is valid", "[types]") {
    auto g = build(R"(
        (def b (image "t.png"))
        (def n (noise :scale 1.0))
        (def r (* b n))
        (output r)
    )");
    auto order = g.topological_order();
    REQUIRE(order.size() == g.nodes.size());
}

TEST_CASE("Diagnostics: no errors on valid graph", "[types]") {
    auto g = build(R"(
        (def b (image "t.png"))
        (def n (noise :scale 4.0))
        (def r (* b n))
        (output r)
    )");
    for (auto& d : g.diagnostics) {
        CHECK(d.level != ir::Diagnostic::Level::ERROR);
    }
}

TEST_CASE("Type: param type is respected", "[types]") {
    auto g = build("(param c float 1.0) (output c)");
    auto* c = g.find_node_by_name("c");
    REQUIRE(c);
    CHECK(c->output_type == Type::FLOAT);
}

TEST_CASE("Type: blur preserves input type", "[types]") {
    auto g = build(R"(
        (def b (image "t.png"))
        (def r (blur b :radius 3.0))
        (output r)
    )");
    auto* r = g.find_node_by_name("r");
    REQUIRE(r);
    CHECK(r->output_type == Type::IMAGE);
}

TEST_CASE("Type checker validates arithmetic operations", "[type_checker]") {
    // Test: Verify that +, -, *, / operations accept numeric types
    // Pattern: Create expression with arithmetic op → type_checker.check() → verify no type errors
    CHECK(false); // TODO: Implement once type_checker API is determined
}

TEST_CASE("Type checker rejects type mismatches", "[type_checker]") {
    // Test: Verify that operations on incompatible types produce type errors
    // Pattern: Create expression mixing string + number → type_checker.check() → verify error reported
    CHECK(false); // TODO: Implement once type_checker error reporting API is determined
}

TEST_CASE("Type checker infers types", "[type_checker]") {
    // Test: Verify that type inference works for expressions without explicit types
    // Pattern: Infer type from operation (e.g., (+ 1 2) should infer number type)
    CHECK(false); // TODO: Implement once type inference API is determined
}

TEST_CASE("Type checker handles polymorphic functions", "[type_checker]") {
    // Test: Verify polymorphic function dispatch based on input types
    // Pattern: Create polymorphic function → call with different types → verify correct overload chosen
    CHECK(false); // TODO: Implement once polymorphic type system API is determined
}

TEST_CASE("Type checker produces useful error messages", "[type_checker]") {
    // Test: Verify that type error messages are informative and helpful
    // Pattern: Trigger type error → check error message contains type info and location
    CHECK(false); // TODO: Implement once error message API is determined
}
