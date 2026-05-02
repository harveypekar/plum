#include "shader/brdf_emitter.h"
#include "shader/hlsl_emitter.h"
#include <sstream>

namespace joon {

std::string BrdfEmitter::emit_lighting_shader(const ShaderFnIR& brdf) {
    HlslEmitter hlsl;
    std::ostringstream ss;

    ss << "[[vk::binding(0, 0)]] Texture2D gbuf_albedo;\n";
    ss << "[[vk::binding(1, 0)]] SamplerState samp;\n\n";

    ss << "struct LightData { float4 position_type; float4 color_intensity; float4 spot_params; };\n";
    ss << "struct LightUBO { LightData lights[16]; int light_count; float3 camera_pos; float4x4 inv_view_proj; };\n";
    ss << "[[vk::binding(2, 0)]] ConstantBuffer<LightUBO> light_ubo;\n\n";

    ss << "struct PSIn { float4 sv : SV_POSITION; float2 uv : TEXCOORD0; };\n\n";

    ss << "float4 main(PSIn i) : SV_TARGET {\n";
    ss << "    float4 albedo = gbuf_albedo.Sample(samp, i.uv);\n";
    ss << "    if (albedo.a < 0.01) discard;\n\n";

    ss << "    float3 normal = float3(0, 1, 0);\n";
    ss << "    float3 view_dir = normalize(light_ubo.camera_pos);\n";
    ss << "    float3 result = float3(0, 0, 0);\n\n";

    ss << "    for (int li = 0; li < light_ubo.light_count; li++) {\n";
    ss << "        float3 light_dir = -normalize(light_ubo.lights[li].position_type.xyz);\n";
    ss << "        float3 light_color = light_ubo.lights[li].color_intensity.xyz;\n";

    // The BRDF body uses params: normal, light_dir, view_dir, albedo
    // Emit each statement in the BRDF body
    for (auto& stmt : brdf.body) {
        std::string expr_str = hlsl.emit_expr(*stmt);
        // If it's a bare expression (not an assignment), accumulate as contribution
        if (auto* assign = std::get_if<ShaderAssign>(stmt.get())) {
            ss << "        " << expr_str << ";\n";
        } else {
            ss << "        result += (" << expr_str << ").xyz * light_color;\n";
        }
    }

    ss << "    }\n\n";
    ss << "    return float4(result, 1.0);\n";
    ss << "}\n";

    return ss.str();
}

} // namespace joon
