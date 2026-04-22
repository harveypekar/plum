RWTexture2D<float4> input_a : register(u0);
RWTexture2D<float4> input_b : register(u1);
RWTexture2D<float4> output_img : register(u2);

struct Params {
    float opacity;
    int mode; // 0=normal, 1=multiply, 2=screen, 3=overlay
};
[[vk::push_constant]] ConstantBuffer<Params> pc;

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 a = input_a[id.xy];
    float4 b = input_b[id.xy];

    float3 result;
    if (pc.mode == 0)      result = b.rgb;
    else if (pc.mode == 1) result = a.rgb * b.rgb;
    else if (pc.mode == 2) result = 1.0 - (1.0 - a.rgb) * (1.0 - b.rgb);
    else                   result = lerp(2.0 * a.rgb * b.rgb,
                                         1.0 - 2.0 * (1.0 - a.rgb) * (1.0 - b.rgb),
                                         step(0.5, a.rgb));

    result = lerp(a.rgb, result, pc.opacity);
    output_img[id.xy] = float4(result, max(a.a, b.a));
}
