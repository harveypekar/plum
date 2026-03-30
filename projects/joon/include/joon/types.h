#pragma once

#include <cstdint>
#include <string>
#include <variant>
#include <vector>

namespace joon {

struct vec2 {
    float x, y;
    vec2 operator+(const vec2& o) const { return {x + o.x, y + o.y}; }
    vec2 operator-(const vec2& o) const { return {x - o.x, y - o.y}; }
    vec2 operator*(float s) const { return {x * s, y * s}; }
};

struct vec3 {
    float x, y, z;
    vec3 operator+(const vec3& o) const { return {x + o.x, y + o.y, z + o.z}; }
    vec3 operator-(const vec3& o) const { return {x - o.x, y - o.y, z - o.z}; }
    vec3 operator*(float s) const { return {x * s, y * s, z * s}; }
    vec3 operator*(const vec3& o) const { return {x * o.x, y * o.y, z * o.z}; }
};

struct vec4 {
    float x, y, z, w;
    vec4 operator+(const vec4& o) const { return {x + o.x, y + o.y, z + o.z, w + o.w}; }
    vec4 operator-(const vec4& o) const { return {x - o.x, y - o.y, z - o.z, w - o.w}; }
    vec4 operator*(float s) const { return {x * s, y * s, z * s, w * s}; }
    vec4 operator*(const vec4& o) const { return {x * o.x, y * o.y, z * o.z, w * o.w}; }
};

struct mat3 { float m[9]; };
struct mat4 { float m[16]; };

enum class Type {
    FLOAT,
    INT,
    BOOL,
    VEC2,
    VEC3,
    VEC4,
    MAT3,
    MAT4,
    IMAGE
};

using Value = std::variant<
    float, int, bool,
    vec2, vec3, vec4,
    mat3, mat4
>;

struct ImageHandle {
    uint32_t id;
    uint32_t width;
    uint32_t height;
};

} // namespace joon
