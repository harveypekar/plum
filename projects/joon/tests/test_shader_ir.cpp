#include "catch_amalgamated.hpp"
#include "shader/shader_ir.h"
#include "shader/shader_analyzer.h"
#include "ir/node.h"
#include "dsl/ast.h"
using namespace joon;

// --- ShaderIR type tests (Task 4) ---

TEST_CASE("ShaderExpr: literal float", "[shader][ir]") {
    ShaderExpr e = ShaderLiteral{1.5f};
    CHECK(std::get<ShaderLiteral>(e).value == Catch::Approx(1.5f));
}

TEST_CASE("ShaderExpr: binary add", "[shader][ir]") {
    auto a = std::make_unique<ShaderExpr>(ShaderLiteral{1.0f});
    auto b = std::make_unique<ShaderExpr>(ShaderLiteral{2.0f});
    ShaderExpr e = ShaderCall{"+", {}, {}};
    auto& call = std::get<ShaderCall>(e);
    call.args.push_back(std::move(a));
    call.args.push_back(std::move(b));
    CHECK(call.op == "+");
    CHECK(call.args.size() == 2);
}

TEST_CASE("ShaderExpr: noise with kwargs", "[shader][ir]") {
    ShaderExpr e = ShaderCall{"noise", {}, {{"scale", 4.0f}, {"octaves", 3.0f}}};
    auto& call = std::get<ShaderCall>(e);
    CHECK(call.kwargs.size() == 2);
    CHECK(call.kwargs[0].first == "scale");
}

TEST_CASE("ShaderExpr: variable reference", "[shader][ir]") {
    ShaderExpr e = ShaderVar{"normal"};
    CHECK(std::get<ShaderVar>(e).name == "normal");
}

TEST_CASE("ShaderExpr: assignment", "[shader][ir]") {
    auto val = std::make_unique<ShaderExpr>(ShaderLiteral{1.0f});
    ShaderAssign sa;
    sa.target = "albedo";
    sa.value = std::move(val);
    ShaderExpr e = std::move(sa);
    CHECK(std::get<ShaderAssign>(e).target == "albedo");
}

TEST_CASE("ShaderExpr: vector constructor", "[shader][ir]") {
    ShaderVecConstruct vc;
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    ShaderExpr e = std::move(vc);
    CHECK(std::get<ShaderVecConstruct>(e).elements.size() == 3);
}

TEST_CASE("ShaderExpr: dot access", "[shader][ir]") {
    ShaderDotAccess da;
    da.object = std::make_unique<ShaderExpr>(ShaderVar{"pos"});
    da.field = "y";
    ShaderExpr e = std::move(da);
    CHECK(std::get<ShaderDotAccess>(e).field == "y");
}

TEST_CASE("ShaderExpr: prepass texture sample", "[shader][ir]") {
    ShaderExpr e = ShaderPrepassSample{0};
    CHECK(std::get<ShaderPrepassSample>(e).prepass_index == 0);
}

// --- ShaderAnalyzer tests (Task 5) ---

TEST_CASE("Analyzer builds ShaderIR from ShaderDef", "[shader][analyzer]") {
    ShaderDef sd;
    ShaderFnDef frag;
    frag.params = {"normal", "uv"};
    frag.outputs = {{"albedo", "vec4"}};

    // Build AST for (set albedo [1 0 0 1])
    auto vec = std::make_unique<AstNode>();
    VectorNode vn;
    for (float v : {1.0f, 0.0f, 0.0f, 1.0f}) {
        auto num = std::make_unique<AstNode>();
        num->data = NumberNode{v};
        vn.elements.push_back(std::move(num));
    }
    vec->data = std::move(vn);

    auto set_call = std::make_unique<AstNode>();
    CallNode cn;
    cn.op = "set";
    auto target = std::make_unique<AstNode>();
    target->data = SymbolNode{"albedo"};
    cn.args.push_back(std::move(target));
    cn.args.push_back(std::move(vec));
    set_call->data = std::move(cn);

    frag.body.push_back(std::shared_ptr<AstNode>(std::move(set_call)));
    sd.fragment = std::move(frag);

    ShaderAnalyzer analyzer;
    auto ir = analyzer.analyze(sd);

    REQUIRE(ir.fragment.has_value());
    CHECK(ir.fragment->params.size() == 2);
    CHECK(ir.fragment->outputs.size() == 1);
    CHECK(ir.fragment->body.size() == 1);

    auto* assign = std::get_if<ShaderAssign>(ir.fragment->body[0].get());
    REQUIRE(assign != nullptr);
    CHECK(assign->target == "albedo");
}

TEST_CASE("Op classification: inlineable ops", "[shader][analyzer]") {
    ShaderAnalyzer analyzer;
    CHECK(analyzer.classify("sin") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("dot") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("noise") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("+") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("mix") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("step") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("encode") == ShaderOpKind::INLINEABLE);
}

TEST_CASE("Op classification: prepass-required ops", "[shader][analyzer]") {
    ShaderAnalyzer analyzer;
    CHECK(analyzer.classify("blur") == ShaderOpKind::PREPASS_REQUIRED);
    CHECK(analyzer.classify("levels") == ShaderOpKind::PREPASS_REQUIRED);
    CHECK(analyzer.classify("blend") == ShaderOpKind::PREPASS_REQUIRED);
}

TEST_CASE("Op classification: unknown ops", "[shader][analyzer]") {
    ShaderAnalyzer analyzer;
    CHECK(analyzer.classify("foobar") == ShaderOpKind::UNKNOWN);
}
