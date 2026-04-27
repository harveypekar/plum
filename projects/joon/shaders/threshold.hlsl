RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

struct Params {
    float threshold;
};

[[vk::push_constant]] ConstantBuffer<Params> pc;

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 c = input_img[id.xy];
    float lum = dot(c.rgb, float3(0.299, 0.587, 0.114));
    float v = step(pc.threshold, lum);
    output_img[id.xy] = float4(v, v, v, c.a);
}
