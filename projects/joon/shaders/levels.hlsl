RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

[[vk::push_constant]]
struct {
    float contrast;
    float brightness;
} params;

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint w, h;
    output_img.GetDimensions(w, h);
    if (id.x >= w || id.y >= h) return;

    float4 c = input_img[id.xy];
    float3 adjusted = (c.rgb - 0.5) * params.contrast + 0.5 + params.brightness;
    output_img[id.xy] = float4(saturate(adjusted), c.a);
}
