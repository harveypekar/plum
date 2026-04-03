RWTexture2D<float4> input_a : register(u0);
RWTexture2D<float4> input_b : register(u1);
RWTexture2D<float4> output_img : register(u2);

[[vk::push_constant]]
struct {
    float opacity;
    int mode; // 0=normal, 1=multiply, 2=screen, 3=overlay
} params;

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint w, h;
    output_img.GetDimensions(w, h);
    if (id.x >= w || id.y >= h) return;

    float4 a = input_a[id.xy];
    float4 b = input_b[id.xy];

    float3 result;
    if (params.mode == 0)      result = b.rgb;
    else if (params.mode == 1) result = a.rgb * b.rgb;
    else if (params.mode == 2) result = 1.0 - (1.0 - a.rgb) * (1.0 - b.rgb);
    else                       result = lerp(2.0 * a.rgb * b.rgb,
                                             1.0 - 2.0 * (1.0 - a.rgb) * (1.0 - b.rgb),
                                             step(0.5, a.rgb));

    result = lerp(a.rgb, result, params.opacity);
    output_img[id.xy] = float4(result, max(a.a, b.a));
}
