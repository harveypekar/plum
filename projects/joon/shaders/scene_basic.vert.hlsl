// Hardcoded vertex shader for the sub-project 2 geometry pass.
// Reads UBO {mvp, model} from descriptor set 0 binding 0, transforms position
// and normal into clip / world space, passes UV through.

struct UBO {
    float4x4 mvp;
    float4x4 model;
};

[[vk::binding(0, 0)]] ConstantBuffer<UBO> ubo;

struct VSIn {
    [[vk::location(0)]] float3 pos    : POSITION;
    [[vk::location(1)]] float3 normal : NORMAL;
    [[vk::location(2)]] float2 uv     : TEXCOORD0;
};

struct VSOut {
    float4 sv     : SV_POSITION;
    float3 normal : NORMAL;
    float2 uv     : TEXCOORD0;
};

VSOut main(VSIn v) {
    VSOut o;
    o.sv = mul(ubo.mvp, float4(v.pos, 1.0));
    // World-space normal — transpose-of-inverse omitted; for uniform scale this is fine.
    o.normal = normalize(mul((float3x3)ubo.model, v.normal));
    o.uv = v.uv;
    return o;
}
