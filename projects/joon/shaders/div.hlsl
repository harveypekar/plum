RWTexture2D<float4> input_a : register(u0);
RWTexture2D<float4> input_b : register(u1);
RWTexture2D<float4> output_img : register(u2);

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 a = input_a[id.xy];
    float4 b = input_b[id.xy];
    output_img[id.xy] = a / max(b, float4(0.0001, 0.0001, 0.0001, 0.0001));
}
