RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

[[vk::push_constant]]
struct {
    float radius;
} params;

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint w, h;
    output_img.GetDimensions(w, h);
    if (id.x >= w || id.y >= h) return;

    int r = (int)ceil(params.radius);
    float4 sum = float4(0, 0, 0, 0);
    float weight_sum = 0.0;

    for (int dy = -r; dy <= r; dy++) {
        for (int dx = -r; dx <= r; dx++) {
            int2 sample_pos = clamp(int2(id.xy) + int2(dx, dy), int2(0, 0), int2(w - 1, h - 1));
            float dist = length(float2(dx, dy));
            float wt = exp(-dist * dist / (2.0 * params.radius * params.radius));
            sum += wt * input_img[sample_pos];
            weight_sum += wt;
        }
    }

    output_img[id.xy] = sum / weight_sum;
}
