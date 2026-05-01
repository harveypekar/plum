#pragma once

#include <joon/types.h>
#include <cmath>

namespace joon {

// Column-major mat4 (matches Vulkan/HLSL convention: matrix * column-vector).
// `m[col*4 + row]` indexing — OR helpers below for readability.

constexpr float PI = 3.14159265358979323846f;

inline float radians(float deg) { return deg * (PI / 180.0f); }

inline mat4 identity_mat4() {
    mat4 r{};
    r.m[0] = 1; r.m[5] = 1; r.m[10] = 1; r.m[15] = 1;
    return r;
}

inline mat4 mul(const mat4& a, const mat4& b) {
    mat4 r{};
    for (int c = 0; c < 4; ++c)
        for (int row = 0; row < 4; ++row) {
            float s = 0;
            for (int k = 0; k < 4; ++k)
                s += a.m[k * 4 + row] * b.m[c * 4 + k];
            r.m[c * 4 + row] = s;
        }
    return r;
}

inline vec3 vec3_sub(vec3 a, vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline vec3 vec3_cross(vec3 a, vec3 b) {
    return {a.y * b.z - a.z * b.y,
            a.z * b.x - a.x * b.z,
            a.x * b.y - a.y * b.x};
}
inline float vec3_dot(vec3 a, vec3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
inline float vec3_len(vec3 a) { return std::sqrt(vec3_dot(a, a)); }
inline vec3  vec3_normalize(vec3 a) {
    float l = vec3_len(a);
    return l > 0 ? vec3{a.x / l, a.y / l, a.z / l} : vec3{0, 0, 0};
}

// Translation matrix.
inline mat4 translate(vec3 t) {
    mat4 r = identity_mat4();
    r.m[12] = t.x; r.m[13] = t.y; r.m[14] = t.z;
    return r;
}

// Scale matrix.
inline mat4 scale(vec3 s) {
    mat4 r{};
    r.m[0] = s.x; r.m[5] = s.y; r.m[10] = s.z; r.m[15] = 1;
    return r;
}

// Rotation matrices (Euler XYZ in radians).
inline mat4 rotate_x(float r) {
    mat4 m = identity_mat4();
    float c = std::cos(r), s = std::sin(r);
    m.m[5] =  c; m.m[6]  = s;
    m.m[9] = -s; m.m[10] = c;
    return m;
}
inline mat4 rotate_y(float r) {
    mat4 m = identity_mat4();
    float c = std::cos(r), s = std::sin(r);
    m.m[0]  = c; m.m[2]  = -s;
    m.m[8]  = s; m.m[10] =  c;
    return m;
}
inline mat4 rotate_z(float r) {
    mat4 m = identity_mat4();
    float c = std::cos(r), s = std::sin(r);
    m.m[0] =  c; m.m[1] = s;
    m.m[4] = -s; m.m[5] = c;
    return m;
}

// Compose TRS — translate * rotateZ * rotateY * rotateX * scale (XYZ Euler).
inline mat4 compose_trs(vec3 position, vec3 rotation, vec3 sc) {
    return mul(translate(position),
               mul(rotate_z(rotation.z),
                   mul(rotate_y(rotation.y),
                       mul(rotate_x(rotation.x),
                           scale(sc)))));
}

// Right-handed look-at — Vulkan-friendly view matrix.
inline mat4 look_at(vec3 eye, vec3 target, vec3 up_hint) {
    vec3 f = vec3_normalize(vec3_sub(target, eye));   // forward
    vec3 s = vec3_normalize(vec3_cross(f, up_hint));  // right
    vec3 u = vec3_cross(s, f);                         // true up

    mat4 r{};
    r.m[0] = s.x;   r.m[4] = s.y;   r.m[8]  = s.z;   r.m[12] = -vec3_dot(s, eye);
    r.m[1] = u.x;   r.m[5] = u.y;   r.m[9]  = u.z;   r.m[13] = -vec3_dot(u, eye);
    r.m[2] = -f.x;  r.m[6] = -f.y;  r.m[10] = -f.z;  r.m[14] =  vec3_dot(f, eye);
    r.m[15] = 1.0f;
    return r;
}

// Right-handed perspective with Vulkan clip space (depth in [0, 1], Y-down by
// flipping m[5] sign). fov_deg is the vertical field of view.
inline mat4 perspective_vk(float fov_deg, float aspect, float near_z, float far_z) {
    float f = 1.0f / std::tan(radians(fov_deg) * 0.5f);
    mat4 r{};
    r.m[0]  = f / aspect;
    r.m[5]  = -f;                          // negate to flip Y for Vulkan clip space
    r.m[10] = far_z / (near_z - far_z);
    r.m[11] = -1.0f;
    r.m[14] = (near_z * far_z) / (near_z - far_z);
    return r;
}

} // namespace joon
