#include "catch_amalgamated.hpp"
#include "shader/hlsl_emitter.h"
#include "shader/shader_ir.h"
using namespace joon;

TEST_CASE("Emit literal", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderExpr e = ShaderLiteral{1.5f};
    auto code = emitter.emit_expr(e);
    CHECK(code == "1.500000");
}

TEST_CASE("Emit binary op", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderCall sc;
    sc.op = "+";
    sc.args.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    sc.args.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{2.0f}));
    ShaderExpr e = std::move(sc);
    auto code = emitter.emit_expr(e);
    CHECK(code == "(1.000000 + 2.000000)");
}

TEST_CASE("Emit function call", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderCall sc;
    sc.op = "sin";
    sc.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"x"}));
    ShaderExpr e = std::move(sc);
    auto code = emitter.emit_expr(e);
    CHECK(code == "sin(x)");
}

TEST_CASE("Emit mix maps to lerp", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderCall sc;
    sc.op = "mix";
    sc.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"a"}));
    sc.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"b"}));
    sc.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"t"}));
    ShaderExpr e = std::move(sc);
    auto code = emitter.emit_expr(e);
    CHECK(code == "lerp(a, b, t)");
}

TEST_CASE("Emit vector constructor", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderVecConstruct vc;
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    ShaderExpr e = std::move(vc);
    auto code = emitter.emit_expr(e);
    CHECK(code == "float3(1.000000, 0.000000, 0.000000)");
}

TEST_CASE("Emit encode normal", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderCall sc;
    sc.op = "encode";
    sc.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"normal"}));
    ShaderExpr e = std::move(sc);
    auto code = emitter.emit_expr(e);
    CHECK(code == "float4(normal * 0.5 + 0.5, 1.0)");
}

TEST_CASE("Emit complete fragment shader", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderFnIR frag;
    frag.params = {"normal", "uv"};
    frag.outputs = {{"albedo", "vec4"}, {"normal_out", "vec4"}};

    ShaderVecConstruct vc;
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    ShaderAssign sa;
    sa.target = "albedo";
    sa.value = std::make_unique<ShaderExpr>(std::move(vc));
    frag.body.push_back(std::make_unique<ShaderExpr>(std::move(sa)));

    auto hlsl = emitter.emit_fragment(frag, 0);
    CHECK(hlsl.find("struct PSOut") != std::string::npos);
    CHECK(hlsl.find("SV_TARGET0") != std::string::npos);
    CHECK(hlsl.find("SV_TARGET1") != std::string::npos);
    CHECK(hlsl.find("o.albedo") != std::string::npos);
}

TEST_CASE("Emit vertex shader", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderFnIR vert;
    vert.params = {"pos", "normal", "uv"};

    auto hlsl = emitter.emit_vertex(vert);
    CHECK(hlsl.find("struct UBO") != std::string::npos);
    CHECK(hlsl.find("VSOut main") != std::string::npos);
    CHECK(hlsl.find("o.world_pos") != std::string::npos);
}

TEST_CASE("Emit dot access", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderDotAccess da;
    da.object = std::make_unique<ShaderExpr>(ShaderVar{"pos"});
    da.field = "y";
    ShaderExpr e = std::move(da);
    CHECK(emitter.emit_expr(e) == "pos.y");
}

TEST_CASE("Emit prepass sample", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderExpr e = ShaderPrepassSample{0};
    CHECK(emitter.emit_expr(e) == "__prepass_0.Sample(__sampler_0, uv)");
}
