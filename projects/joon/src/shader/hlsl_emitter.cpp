#include "shader/hlsl_emitter.h"
#include "shader/noise_hlsl.h"
#include <sstream>
#include <cstdio>

namespace joon {

const std::unordered_map<std::string, std::string> HlslEmitter::OP_RENAMES = {
    {"mix", "lerp"}, {"fract", "frac"}, {"mod", "fmod"},
};

const std::unordered_set<std::string> HlslEmitter::BINARY_OPS = {
    "+", "-", "*", "/"
};

std::string HlslEmitter::emit_expr(const ShaderExpr& expr) {
    if (auto* lit = std::get_if<ShaderLiteral>(&expr)) {
        char buf[32];
        snprintf(buf, sizeof(buf), "%f", lit->value);
        return buf;
    }
    if (auto* var = std::get_if<ShaderVar>(&expr))
        return var->name;
    if (auto* call = std::get_if<ShaderCall>(&expr))
        return emit_call(*call);
    if (auto* assign = std::get_if<ShaderAssign>(&expr))
        return emit_assign(*assign, true);
    if (auto* vc = std::get_if<ShaderVecConstruct>(&expr))
        return emit_vec(*vc);
    if (auto* da = std::get_if<ShaderDotAccess>(&expr))
        return emit_dot(*da);
    if (auto* ps = std::get_if<ShaderPrepassSample>(&expr)) {
        std::ostringstream ss;
        ss << "__prepass_" << ps->prepass_index
           << ".Sample(__sampler_" << ps->prepass_index << ", uv)";
        return ss.str();
    }
    return "0.0";
}

std::string HlslEmitter::emit_call(const ShaderCall& call) {
    if (call.op == "encode" && call.args.size() == 1) {
        return "float4(" + emit_expr(*call.args[0]) + " * 0.5 + 0.5, 1.0)";
    }
    if (call.op == "decode" && call.args.size() == 1) {
        return "(" + emit_expr(*call.args[0]) + ".xyz * 2.0 - 1.0)";
    }
    if (call.op == "noise") {
        float scale = 1.0f;
        int octaves = 4;
        for (auto& kw : call.kwargs) {
            if (kw.first == "scale") scale = kw.second;
            if (kw.first == "octaves") octaves = static_cast<int>(kw.second);
        }
        std::ostringstream ss;
        ss << "fbm(world_pos * " << scale << ", " << octaves << ")";
        return ss.str();
    }

    if (BINARY_OPS.count(call.op) && call.args.size() == 2) {
        return "(" + emit_expr(*call.args[0]) + " " + call.op + " " + emit_expr(*call.args[1]) + ")";
    }

    std::string name = call.op;
    auto rename = OP_RENAMES.find(call.op);
    if (rename != OP_RENAMES.end()) name = rename->second;

    std::ostringstream ss;
    ss << name << "(";
    for (size_t i = 0; i < call.args.size(); i++) {
        if (i > 0) ss << ", ";
        ss << emit_expr(*call.args[i]);
    }
    ss << ")";
    return ss.str();
}

std::string HlslEmitter::emit_assign(const ShaderAssign& assign, bool is_fragment) {
    std::string prefix = is_fragment ? "o." : "";
    return prefix + assign.target + " = " + emit_expr(*assign.value);
}

std::string HlslEmitter::emit_vec(const ShaderVecConstruct& vc) {
    std::ostringstream ss;
    ss << "float" << vc.elements.size() << "(";
    for (size_t i = 0; i < vc.elements.size(); i++) {
        if (i > 0) ss << ", ";
        ss << emit_expr(*vc.elements[i]);
    }
    ss << ")";
    return ss.str();
}

std::string HlslEmitter::emit_dot(const ShaderDotAccess& da) {
    return emit_expr(*da.object) + "." + da.field;
}

std::string HlslEmitter::emit_fragment(const ShaderFnIR& fn, uint32_t prepass_count) {
    std::ostringstream ss;

    ss << "struct PSOut {\n";
    for (size_t i = 0; i < fn.outputs.size(); i++) {
        std::string hlsl_type = (fn.outputs[i].type_name == "vec4") ? "float4" :
                                 (fn.outputs[i].type_name == "vec3") ? "float3" :
                                 (fn.outputs[i].type_name == "vec2") ? "float2" : "float";
        ss << "    " << hlsl_type << " " << fn.outputs[i].name
           << " : SV_TARGET" << i << ";\n";
    }
    ss << "};\n\n";

    ss << "struct PSIn {\n"
       << "    float4 sv : SV_POSITION;\n"
       << "    float3 normal : NORMAL;\n"
       << "    float2 uv : TEXCOORD0;\n"
       << "    float3 world_pos : TEXCOORD1;\n"
       << "};\n\n";

    ss << "struct FragUBO { float time; float3 pad; };\n"
       << "[[vk::binding(0, 1)]] ConstantBuffer<FragUBO> frag_ubo;\n\n";

    for (uint32_t i = 0; i < prepass_count; i++) {
        uint32_t binding = 1 + i * 2;
        ss << "[[vk::binding(" << binding << ", 1)]] Texture2D __prepass_" << i << ";\n";
        ss << "[[vk::binding(" << (binding + 1) << ", 1)]] SamplerState __sampler_" << i << ";\n";
    }
    if (prepass_count > 0) ss << "\n";

    ss << NOISE_HLSL_FUNCTIONS << "\n";

    ss << "PSOut main(PSIn i) {\n";
    ss << "    float3 normal = normalize(i.normal);\n";
    ss << "    float2 uv = i.uv;\n";
    ss << "    float3 world_pos = i.world_pos;\n";
    ss << "    float time = frag_ubo.time;\n";
    ss << "    PSOut o;\n";

    for (auto& stmt : fn.body) {
        ss << "    " << emit_expr(*stmt) << ";\n";
    }

    ss << "    return o;\n";
    ss << "}\n";
    return ss.str();
}

std::string HlslEmitter::emit_vertex(const ShaderFnIR& fn) {
    std::ostringstream ss;

    ss << "struct UBO { float4x4 mvp; float4x4 model; float time; float3 pad; };\n";
    ss << "[[vk::binding(0, 0)]] ConstantBuffer<UBO> ubo;\n\n";

    ss << "struct VSIn  { float3 pos : POSITION; float3 nrm : NORMAL; float2 uv : TEXCOORD0; };\n";
    ss << "struct VSOut { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; float3 world_pos : TEXCOORD1; };\n\n";

    ss << "VSOut main(VSIn v) {\n";
    ss << "    float3 pos = v.pos;\n";
    ss << "    float3 normal = v.nrm;\n";
    ss << "    float2 uv = v.uv;\n";
    ss << "    float time = ubo.time;\n";

    for (auto& stmt : fn.body) {
        ss << "    " << emit_expr(*stmt) << ";\n";
    }

    ss << "    VSOut o;\n";
    ss << "    o.sv = mul(ubo.mvp, float4(pos, 1.0));\n";
    ss << "    o.normal = normalize(mul((float3x3)ubo.model, normal));\n";
    ss << "    o.uv = uv;\n";
    ss << "    o.world_pos = mul(ubo.model, float4(pos, 1.0)).xyz;\n";
    ss << "    return o;\n";
    ss << "}\n";
    return ss.str();
}

} // namespace joon
