#include "catch_amalgamated.hpp"
#include "shader/hlsl_emitter.h"
#include "shader/brdf_emitter.h"
#include "shader/shader_ir.h"
#include "vulkan/pipeline_cache.h"
#include "vulkan/render_pass.h"
#include <joon/context.h>
#include <filesystem>
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

TEST_CASE("PipelineCache compiles generated HLSL source", "[shader][pipeline][gpu]") {
    auto ctx = Context::create();
    auto tmp_dir = std::filesystem::temp_directory_path().string();
    PipelineCache cache(ctx->device(), tmp_dir);

    std::string vert_src = R"(
struct UBO { float4x4 mvp; float4x4 model; float time; float3 pad; };
[[vk::binding(0, 0)]] ConstantBuffer<UBO> ubo;
struct VSIn  { float3 pos : POSITION; float3 nrm : NORMAL; float2 uv : TEXCOORD0; };
struct VSOut { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; float3 world_pos : TEXCOORD1; };
VSOut main(VSIn v) {
    VSOut o;
    o.sv = mul(ubo.mvp, float4(v.pos, 1.0));
    o.normal = normalize(mul((float3x3)ubo.model, v.nrm));
    o.uv = v.uv;
    o.world_pos = mul(ubo.model, float4(v.pos, 1.0)).xyz;
    return o;
}
)";

    std::string frag_src = R"(
struct PSOut { float4 albedo : SV_TARGET0; };
struct PSIn { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; float3 world_pos : TEXCOORD1; };
PSOut main(PSIn i) {
    PSOut o;
    o.albedo = float4(1, 0, 0, 1);
    return o;
}
)";

    auto rp = create_color_depth_renderpass(ctx->device(), {VK_FORMAT_R8G8B8A8_UNORM});
    auto& gp = cache.get_graphics_from_source("test_gen", vert_src, frag_src, rp.pass, 0);
    CHECK(gp.pipeline != VK_NULL_HANDLE);
    destroy_renderpass(ctx->device(), rp);
}

TEST_CASE("BRDF emitter injects roughness and metallic", "[shader][brdf]") {
    BrdfEmitter emitter;

    ShaderFnIR brdf;
    brdf.params = {"normal", "light_dir", "view_dir", "albedo"};

    ShaderCall mul_call;
    mul_call.op = "*";
    mul_call.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"roughness"}));
    mul_call.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"metallic"}));
    brdf.body.push_back(std::make_unique<ShaderExpr>(std::move(mul_call)));

    auto hlsl = emitter.emit_lighting_shader(brdf);

    CHECK(hlsl.find("float roughness") != std::string::npos);
    CHECK(hlsl.find("float metallic") != std::string::npos);
    CHECK(hlsl.find("float3 albedo") != std::string::npos);
}
