#pragma once

namespace joon {

inline const char* NOISE_HLSL_FUNCTIONS = R"(
float hash31(float3 p) {
    p = frac(p * float3(443.8975, 397.2973, 491.1871));
    p += dot(p, p.yzx + 19.19);
    return frac((p.x + p.y) * p.z);
}

float noise3d(float3 p) {
    float3 i = floor(p);
    float3 f = frac(p);
    f = f * f * (3.0 - 2.0 * f);
    return lerp(
        lerp(lerp(hash31(i), hash31(i + float3(1,0,0)), f.x),
             lerp(hash31(i + float3(0,1,0)), hash31(i + float3(1,1,0)), f.x), f.y),
        lerp(lerp(hash31(i + float3(0,0,1)), hash31(i + float3(1,0,1)), f.x),
             lerp(hash31(i + float3(0,1,1)), hash31(i + float3(1,1,1)), f.x), f.y),
        f.z);
}

float fbm(float3 p, int octaves) {
    float val = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i = 0; i < octaves; i++) {
        val += amp * noise3d(p * freq);
        freq *= 2.0;
        amp *= 0.5;
    }
    return val;
}
)";

} // namespace joon
