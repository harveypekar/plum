RWTexture2D<float4> input_img : register(u0);
RWTexture2D<float4> output_img : register(u1);

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint2 size;
    output_img.GetDimensions(size.x, size.y);
    if (id.x >= size.x || id.y >= size.y) return;

    float4 c = input_img[id.xy];
    output_img[id.xy] = float4(1.0 - c.rgb, c.a);
}
