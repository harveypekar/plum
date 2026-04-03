RWTexture2D<float4> output_img : register(u0);

[[vk::push_constant]]
struct {
    float scale;
    float octaves;
    float width;
    float height;
} params;

float2 hash(float2 p) {
    p = float2(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)));
    return -1.0 + 2.0 * frac(sin(p) * 43758.5453123);
}

float simplex_noise(float2 p) {
    const float K1 = 0.366025404; // (sqrt(3)-1)/2
    const float K2 = 0.211324865; // (3-sqrt(3))/6
    float2 i = floor(p + (p.x + p.y) * K1);
    float2 a = p - i + (i.x + i.y) * K2;
    float m = step(a.y, a.x);
    float2 o = float2(m, 1.0 - m);
    float2 b = a - o + K2;
    float2 c = a - 1.0 + 2.0 * K2;
    float3 h = max(0.5 - float3(dot(a, a), dot(b, b), dot(c, c)), 0.0);
    float3 n = h * h * h * h * float3(dot(a, hash(i)), dot(b, hash(i + o)), dot(c, hash(i + 1.0)));
    return dot(n, float3(70.0, 70.0, 70.0));
}

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    uint w, h;
    output_img.GetDimensions(w, h);
    if (id.x >= w || id.y >= h) return;

    float2 uv = float2(id.xy) / float2(params.width, params.height);

    float value = 0.0;
    float amplitude = 1.0;
    float frequency = params.scale;
    int oct = (int)params.octaves;

    for (int i = 0; i < oct; i++) {
        value += amplitude * simplex_noise(uv * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
    }

    value = value * 0.5 + 0.5;
    output_img[id.xy] = float4(value, value, value, 1.0);
}
