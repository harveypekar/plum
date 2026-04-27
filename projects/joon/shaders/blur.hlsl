RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

struct Params {
    float radius;
};
[[vk::push_constant]] ConstantBuffer<Params> pc;

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    int2 pos = int2(id.xy);
    int r = int(ceil(pc.radius));
    float4 sum = float4(0.0, 0.0, 0.0, 0.0);
    float weight_sum = 0.0;

    for (int dy = -r; dy <= r; dy++) {
        for (int dx = -r; dx <= r; dx++) {
            int2 sample_pos = clamp(pos + int2(dx, dy), int2(0, 0), int2(size) - int2(1, 1));
            float dist = length(float2(dx, dy));
            float w = exp(-dist * dist / (2.0 * pc.radius * pc.radius));
            sum += w * input_img[sample_pos];
            weight_sum += w;
        }
    }

    output_img[id.xy] = sum / weight_sum;
}
