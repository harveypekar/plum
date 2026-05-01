#include "catch_amalgamated.hpp"
#include "dsl/parser.h"
#include <joon/context.h>
#include <joon/graph.h>
#include "ir/ir_graph.h"
using namespace joon;

TEST_CASE("Parse vector literal", "[shader][parser]") {
    Parser p("[1.0 2.0 3.0]");
    auto expr = p.parse_expression();
    auto* vec = std::get_if<VectorNode>(&expr->data);
    REQUIRE(vec != nullptr);
    CHECK(vec->elements.size() == 3);
    auto* e0 = std::get_if<NumberNode>(&vec->elements[0]->data);
    REQUIRE(e0);
    CHECK(e0->value == Catch::Approx(1.0));
}

TEST_CASE("Parse fn with body", "[shader][parser]") {
    Parser p("(fn [pos normal uv] (set pos.y (* pos.x 2.0)))");
    auto expr = p.parse_expression();
    auto* fn = std::get_if<FnNode>(&expr->data);
    REQUIRE(fn != nullptr);
    CHECK(fn->params.size() == 3);
    CHECK(fn->params[0] == "pos");
    CHECK(fn->params[1] == "normal");
    CHECK(fn->params[2] == "uv");
    CHECK(fn->body.size() == 1);
}

TEST_CASE("Parse fn with arrow outputs", "[shader][parser]") {
    Parser p("(fn [normal uv] -> [albedo vec4, normal vec4] (set albedo [1 0 0 1]))");
    auto expr = p.parse_expression();
    auto* fn = std::get_if<FnNode>(&expr->data);
    REQUIRE(fn != nullptr);
    CHECK(fn->params.size() == 2);
    CHECK(fn->outputs.size() == 2);
    CHECK(fn->outputs[0].name == "albedo");
    CHECK(fn->outputs[0].type_name == "vec4");
    CHECK(fn->outputs[1].name == "normal");
    CHECK(fn->body.size() == 1);
}

TEST_CASE("Parse shader call with fn kwargs", "[shader][parser]") {
    Parser p(R"(
        (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [1 0 0 1])))
    )");
    auto expr = p.parse_expression();
    auto* call = std::get_if<CallNode>(&expr->data);
    REQUIRE(call != nullptr);
    CHECK(call->op == "shader");
    CHECK(call->kwargs.size() == 1);
    CHECK(call->kwargs[0].name == "fragment");
    auto* fn = std::get_if<FnNode>(&call->kwargs[0].value->data);
    REQUIRE(fn != nullptr);
    CHECK(fn->outputs.size() == 1);
}

TEST_CASE("Vector literal with expressions", "[shader][parser]") {
    Parser p("[(+ 1 2) 3.0 x]");
    auto expr = p.parse_expression();
    auto* vec = std::get_if<VectorNode>(&expr->data);
    REQUIRE(vec != nullptr);
    CHECK(vec->elements.size() == 3);
    CHECK(std::get_if<CallNode>(&vec->elements[0]->data) != nullptr);
    CHECK(std::get_if<NumberNode>(&vec->elements[1]->data) != nullptr);
    CHECK(std::get_if<SymbolNode>(&vec->elements[2]->data) != nullptr);
}

TEST_CASE("Parse dot access", "[shader][parser]") {
    Parser p("gbuf.albedo");
    auto expr = p.parse_expression();
    auto* dot = std::get_if<DotAccessNode>(&expr->data);
    REQUIRE(dot != nullptr);
    CHECK(dot->field == "albedo");
    auto* obj = std::get_if<SymbolNode>(&dot->object->data);
    REQUIRE(obj != nullptr);
    CHECK(obj->name == "gbuf");
}

TEST_CASE("Parse chained dot access", "[shader][parser]") {
    Parser p("a.b.c");
    auto expr = p.parse_expression();
    auto* dot = std::get_if<DotAccessNode>(&expr->data);
    REQUIRE(dot != nullptr);
    CHECK(dot->field == "c");
    auto* inner = std::get_if<DotAccessNode>(&dot->object->data);
    REQUIRE(inner != nullptr);
    CHECK(inner->field == "b");
}

TEST_CASE("shader op lowers to MATERIAL tier", "[shader][ir]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [1 0 0 1]))))
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto& ir = graph.ir();
    bool found_material = false;
    for (auto& n : ir.nodes) {
        if (n.tier == Tier::MATERIAL) {
            found_material = true;
            CHECK(n.op == "shader");
            CHECK(n.output_type == Type::MATERIAL);
            auto sd_it = ir.shader_defs.find(n.id);
            REQUIRE(sd_it != ir.shader_defs.end());
            auto& sd = sd_it->second;
            REQUIRE(sd.fragment.has_value());
            CHECK(sd.fragment->params.size() == 2);
            CHECK(sd.fragment->outputs.size() == 1);
            CHECK(sd.fragment->outputs[0].name == "albedo");
            CHECK(sd.fragment->body.size() == 1);
        }
    }
    CHECK(found_material);
}

TEST_CASE("shader with all three clauses", "[shader][ir]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :vertex (fn [pos normal uv] (set pos.y (* pos.x 2.0)))
          :brdf (fn [normal light_dir view_dir albedo]
            (* albedo (dot normal light_dir)))
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [1 0 0 1]))))
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto& ir = graph.ir();
    auto* mat = ir.find_node_by_name("mat");
    REQUIRE(mat);
    auto sd_it = ir.shader_defs.find(mat->id);
    REQUIRE(sd_it != ir.shader_defs.end());
    auto& sd = sd_it->second;
    CHECK(sd.vertex.has_value());
    CHECK(sd.fragment.has_value());
    CHECK(sd.brdf.has_value());
    CHECK(sd.vertex->params.size() == 3);
    CHECK(sd.brdf->params.size() == 4);
}
