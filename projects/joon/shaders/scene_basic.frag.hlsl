// Hardcoded fragment shader for the sub-project 2 geometry pass.
// Single directional light via push constants; ambient + lambert.

struct PushLight {
    float3 light_dir;
    float pad0;
    float3 light_color;
    float pad1;
};

[[vk::push_constant]] PushLight pc;

struct PSIn {
    float4 sv     : SV_POSITION;
    float3 normal : NORMAL;
    float2 uv     : TEXCOORD0;
};

float4 main(PSIn i) : SV_TARGET {
    float3 n = normalize(i.normal);
    float ndotl = saturate(dot(n, -normalize(pc.light_dir)));
    float3 col = pc.light_color * (0.1 + 0.9 * ndotl);   // ambient + diffuse
    return float4(col, 1.0);
}
