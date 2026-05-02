struct LightData {
    float4 position_type;
    float4 color_intensity;
    float4 spot_params;
};

struct LightUBO {
    LightData lights[16];
    int light_count;
    float3 camera_pos;
    float4x4 inv_view_proj;
};

[[vk::binding(0, 0)]] Texture2D gbuf_albedo;
[[vk::binding(1, 0)]] SamplerState samp;
[[vk::binding(2, 0)]] ConstantBuffer<LightUBO> light_ubo;

struct PSIn {
    float4 sv : SV_POSITION;
    float2 uv : TEXCOORD0;
};

float4 main(PSIn i) : SV_TARGET {
    float4 albedo = gbuf_albedo.Sample(samp, i.uv);
    if (albedo.a < 0.01) discard;

    float3 result = albedo.rgb * 0.1;

    for (int li = 0; li < light_ubo.light_count; li++) {
        float3 light_dir;
        float3 light_color = light_ubo.lights[li].color_intensity.xyz;
        float type = light_ubo.lights[li].position_type.w;

        if (type < 0.5) {
            light_dir = -normalize(light_ubo.lights[li].position_type.xyz);
        } else {
            light_dir = normalize(light_ubo.lights[li].position_type.xyz);
        }

        float ndotl = saturate(dot(float3(0, 1, 0), light_dir));
        result += albedo.rgb * light_color * ndotl;
    }

    return float4(result, 1.0);
}
