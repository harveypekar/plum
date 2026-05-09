[[vk::binding(1, 0)]] Texture2D albedo_tex;
[[vk::binding(2, 0)]] SamplerState samp;
[[vk::binding(3, 0)]] Texture2D normal_tex;

[[vk::push_constant]]
struct PushConstants {
    float roughness;
    float metallic;
} pc;

struct PSIn {
    float4 sv        : SV_POSITION;
    float3 normal    : NORMAL;
    float2 uv        : TEXCOORD0;
    float3 world_pos : TEXCOORD1;
};

struct PSOut {
    float4 albedo     : SV_TARGET0;
    float4 normal_out : SV_TARGET1;
};

PSOut main(PSIn i) {
    PSOut o;
    float4 tex_color = albedo_tex.Sample(samp, i.uv);
    o.albedo = float4(tex_color.rgb, pc.roughness);

    float3 N = normalize(i.normal);

    float3 dp1 = ddx(i.world_pos);
    float3 dp2 = ddy(i.world_pos);
    float2 duv1 = ddx(i.uv);
    float2 duv2 = ddy(i.uv);

    float det = duv1.x * duv2.y - duv1.y * duv2.x;
    float3 T = normalize((dp1 * duv2.y - dp2 * duv1.y) * sign(det));
    float3 B = normalize(cross(N, T)) * sign(det);

    float3 ts = normal_tex.Sample(samp, i.uv).xyz * 2.0 - 1.0;
    float3 mapped = normalize(T * ts.x + B * ts.y + N * ts.z);

    o.normal_out = float4(mapped * 0.5 + 0.5, pc.metallic);
    return o;
}
