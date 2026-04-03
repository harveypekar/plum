RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

[[vk::push_constant]]
struct {
    float threshold;
} params;

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint w, h;
    output_img.GetDimensions(w, h);
    if (id.x >= w || id.y >= h) return;

    float4 c = input_img[id.xy];
    float lum = dot(c.rgb, float3(0.299, 0.587, 0.114));
    float v = step(params.threshold, lum);
    output_img[id.xy] = float4(v, v, v, c.a);
}
