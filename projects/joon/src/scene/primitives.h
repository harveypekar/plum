#pragma once
#include <joon/scene.h>

namespace joon {

// Axis-aligned cube centered at origin, side length = `size`.
// 24 vertices (4 per face for per-face flat normals), 36 indices.
Mesh gen_cube(float size = 1.0f);

// UV sphere centered at origin, radius = `radius`.
// (lat+1) * (lon+1) vertices, lat * lon * 6 indices. Smooth normals.
Mesh gen_sphere(float radius = 0.5f, int lat = 16, int lon = 32);

// Quad in the XZ plane at y=0, centered, with normal pointing +Y.
// 4 vertices, 6 indices.
Mesh gen_plane(float w = 1.0f, float h = 1.0f);

// Cylinder along Y-axis, centered at origin, total height = `height`.
// Top and bottom caps + side strip. `segments` divides the circle.
Mesh gen_cylinder(float radius = 0.5f, float height = 1.0f, int segments = 32);

} // namespace joon
