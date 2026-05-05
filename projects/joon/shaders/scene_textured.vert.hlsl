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
    float4 sv        : SV_POSITION;
    float3 normal    : NORMAL;
    float2 uv        : TEXCOORD0;
    float3 world_pos : TEXCOORD1;
};

VSOut main(VSIn v) {
    VSOut o;
    o.sv = mul(ubo.mvp, float4(v.pos, 1.0));
    o.normal = normalize(mul((float3x3)ubo.model, v.normal));
    o.uv = v.uv;
    o.world_pos = mul(ubo.model, float4(v.pos, 1.0)).xyz;
    return o;
}
