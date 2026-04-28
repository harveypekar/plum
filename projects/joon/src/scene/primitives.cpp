#include "scene/primitives.h"
#include <cmath>

namespace joon {

namespace {
constexpr float PI = 3.14159265358979323846f;
} // namespace

Mesh gen_cube(float size) {
    const float h = size * 0.5f;
    // 6 faces × 4 unique verts each (so normals are flat per-face).
    const vec3 normals[6] = {
        { 0, 0, 1}, { 0, 0,-1},   // +Z, -Z
        { 1, 0, 0}, {-1, 0, 0},   // +X, -X
        { 0, 1, 0}, { 0,-1, 0},   // +Y, -Y
    };
    // Each face's 4 corners in CCW order when viewed from outside.
    const vec3 corners[6][4] = {
        {{-h,-h, h},{ h,-h, h},{ h, h, h},{-h, h, h}},  // +Z
        {{ h,-h,-h},{-h,-h,-h},{-h, h,-h},{ h, h,-h}},  // -Z
        {{ h,-h, h},{ h,-h,-h},{ h, h,-h},{ h, h, h}},  // +X
        {{-h,-h,-h},{-h,-h, h},{-h, h, h},{-h, h,-h}},  // -X
        {{-h, h, h},{ h, h, h},{ h, h,-h},{-h, h,-h}},  // +Y
        {{-h,-h,-h},{ h,-h,-h},{ h,-h, h},{-h,-h, h}},  // -Y
    };
    const vec2 uvs[4] = { {0,0}, {1,0}, {1,1}, {0,1} };

    Mesh m;
    m.vertices.reserve(24);
    m.indices.reserve(36);

    for (uint32_t f = 0; f < 6; ++f) {
        const uint32_t base = f * 4;
        for (uint32_t i = 0; i < 4; ++i) {
            m.vertices.push_back({ corners[f][i], normals[f], uvs[i] });
        }
        // Two triangles (0,1,2) and (0,2,3) — CCW from outside.
        m.indices.push_back(base + 0);
        m.indices.push_back(base + 1);
        m.indices.push_back(base + 2);
        m.indices.push_back(base + 0);
        m.indices.push_back(base + 2);
        m.indices.push_back(base + 3);
    }

    return m;
}

Mesh gen_sphere(float radius, int lat, int lon) {
    Mesh m;
    m.vertices.reserve(static_cast<size_t>(lat + 1) * static_cast<size_t>(lon + 1));
    m.indices.reserve(static_cast<size_t>(lat) * static_cast<size_t>(lon) * 6);

    const float inv_r = (radius != 0.0f) ? (1.0f / radius) : 0.0f;

    for (int i = 0; i <= lat; ++i) {
        const float v = static_cast<float>(i) / static_cast<float>(lat);   // 0..1, top to bottom
        const float theta = v * PI;                                        // pole-to-pole
        const float sin_t = std::sin(theta);
        const float cos_t = std::cos(theta);
        for (int j = 0; j <= lon; ++j) {
            const float u = static_cast<float>(j) / static_cast<float>(lon);   // 0..1, around
            const float phi = u * 2.0f * PI;
            const float sin_p = std::sin(phi);
            const float cos_p = std::cos(phi);

            vec3 pos = { radius * sin_t * cos_p,
                         radius * cos_t,
                         radius * sin_t * sin_p };
            vec3 normal = pos * inv_r;   // outward unit (zero-radius edge case yields {0,0,0})
            m.vertices.push_back({ pos, normal, { u, v } });
        }
    }

    const uint32_t stride = static_cast<uint32_t>(lon + 1);
    for (int i = 0; i < lat; ++i) {
        for (int j = 0; j < lon; ++j) {
            const uint32_t a = static_cast<uint32_t>(i) * stride + static_cast<uint32_t>(j);
            const uint32_t b = a + 1;
            const uint32_t c = a + stride;
            const uint32_t d = c + 1;
            // Quad (a,b,d,c) → two CCW triangles. Degenerate triangles at the poles
            // are kept on purpose to match the lat*lon*6 index-count contract.
            m.indices.push_back(a);
            m.indices.push_back(c);
            m.indices.push_back(b);

            m.indices.push_back(b);
            m.indices.push_back(c);
            m.indices.push_back(d);
        }
    }

    return m;
}

Mesh gen_plane(float w, float h) {
    const float hw = w * 0.5f;
    const float hh = h * 0.5f;

    Mesh m;
    m.vertices.reserve(4);
    m.indices.reserve(6);

    const vec3 n = { 0.0f, 1.0f, 0.0f };
    // 4 corners in CCW order when viewed from +Y (looking down -Y).
    m.vertices.push_back({ {-hw, 0.0f, -hh}, n, {0.0f, 0.0f} });
    m.vertices.push_back({ { hw, 0.0f, -hh}, n, {1.0f, 0.0f} });
    m.vertices.push_back({ { hw, 0.0f,  hh}, n, {1.0f, 1.0f} });
    m.vertices.push_back({ {-hw, 0.0f,  hh}, n, {0.0f, 1.0f} });

    m.indices.push_back(0);
    m.indices.push_back(1);
    m.indices.push_back(2);
    m.indices.push_back(0);
    m.indices.push_back(2);
    m.indices.push_back(3);

    return m;
}

Mesh gen_cylinder(float radius, float height, int segments) {
    const float hh = height * 0.5f;

    Mesh m;
    // Side strip: 2 * (segments + 1)
    // Top cap: 1 center + segments ring
    // Bottom cap: 1 center + segments ring
    m.vertices.reserve(static_cast<size_t>(2 * (segments + 1) + 2 * (segments + 1)));
    // Indices: 6*segments (side) + 3*segments (top) + 3*segments (bottom) = 12*segments
    m.indices.reserve(static_cast<size_t>(12 * segments));

    // ------------- Side strip -------------
    // 2 * (segments + 1) vertices: bottom and top for each ring index 0..segments.
    // Last ring index duplicates the first position but with UV.x = 1 to allow seam.
    const uint32_t side_base = 0;
    for (int s = 0; s <= segments; ++s) {
        const float u = static_cast<float>(s) / static_cast<float>(segments);
        const float angle = u * 2.0f * PI;
        const float cs = std::cos(angle);
        const float sn = std::sin(angle);
        const vec3 normal = { cs, 0.0f, sn };
        const vec3 bottom = { radius * cs, -hh, radius * sn };
        const vec3 top    = { radius * cs,  hh, radius * sn };
        m.vertices.push_back({ bottom, normal, { u, 0.0f } });
        m.vertices.push_back({ top,    normal, { u, 1.0f } });
    }
    // Two triangles per segment forming the quad: (b, t, b+1) and (b+1, t, t+1)
    // where b = 2*s (bottom), t = 2*s+1 (top), b+1 = 2*s+2 next bottom (wraps via duplicated ring).
    for (int s = 0; s < segments; ++s) {
        const uint32_t b0 = side_base + static_cast<uint32_t>(s) * 2;
        const uint32_t t0 = b0 + 1;
        const uint32_t b1 = b0 + 2;
        const uint32_t t1 = b0 + 3;
        // CCW from outside (normal pointing +outward).
        m.indices.push_back(b0);
        m.indices.push_back(t0);
        m.indices.push_back(t1);

        m.indices.push_back(b0);
        m.indices.push_back(t1);
        m.indices.push_back(b1);
    }

    // ------------- Top cap -------------
    // Center vertex + `segments` ring vertices (no seam needed: triangle fan, last triangle wraps).
    const uint32_t top_center = static_cast<uint32_t>(m.vertices.size());
    {
        const vec3 n_up = { 0.0f, 1.0f, 0.0f };
        m.vertices.push_back({ { 0.0f, hh, 0.0f }, n_up, { 0.5f, 0.5f } });
        for (int s = 0; s < segments; ++s) {
            const float u = static_cast<float>(s) / static_cast<float>(segments);
            const float angle = u * 2.0f * PI;
            const float cs = std::cos(angle);
            const float sn = std::sin(angle);
            const vec3 pos = { radius * cs, hh, radius * sn };
            const vec2 uv  = { 0.5f + 0.5f * cs, 0.5f + 0.5f * sn };
            m.vertices.push_back({ pos, n_up, uv });
        }
    }
    const uint32_t top_ring = top_center + 1;
    for (int s = 0; s < segments; ++s) {
        const uint32_t a = top_ring + static_cast<uint32_t>(s);
        const uint32_t b = top_ring + static_cast<uint32_t>((s + 1) % segments);
        // CCW when viewed from +Y (above).
        m.indices.push_back(top_center);
        m.indices.push_back(a);
        m.indices.push_back(b);
    }

    // ------------- Bottom cap -------------
    const uint32_t bot_center = static_cast<uint32_t>(m.vertices.size());
    {
        const vec3 n_dn = { 0.0f, -1.0f, 0.0f };
        m.vertices.push_back({ { 0.0f, -hh, 0.0f }, n_dn, { 0.5f, 0.5f } });
        for (int s = 0; s < segments; ++s) {
            const float u = static_cast<float>(s) / static_cast<float>(segments);
            const float angle = u * 2.0f * PI;
            const float cs = std::cos(angle);
            const float sn = std::sin(angle);
            const vec3 pos = { radius * cs, -hh, radius * sn };
            const vec2 uv  = { 0.5f + 0.5f * cs, 0.5f - 0.5f * sn };
            m.vertices.push_back({ pos, n_dn, uv });
        }
    }
    const uint32_t bot_ring = bot_center + 1;
    for (int s = 0; s < segments; ++s) {
        const uint32_t a = bot_ring + static_cast<uint32_t>(s);
        const uint32_t b = bot_ring + static_cast<uint32_t>((s + 1) % segments);
        // Reversed winding so it's CCW when viewed from -Y (below).
        m.indices.push_back(bot_center);
        m.indices.push_back(b);
        m.indices.push_back(a);
    }

    return m;
}

} // namespace joon
