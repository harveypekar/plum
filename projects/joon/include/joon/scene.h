#pragma once
#include <joon/types.h>
#include <vector>
#include <cstdint>

namespace joon {

struct Vertex {
    vec3 position;
    vec3 normal;
    vec2 uv;
};

struct Mesh {
    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;
};

struct GpuImage;

struct SceneObject {
    Mesh mesh;
    vec3 position{0, 0, 0};
    vec3 rotation{0, 0, 0};   // Euler XYZ, radians
    vec3 scale{1, 1, 1};
    uint32_t material_node_id = UINT32_MAX;
    GpuImage* albedo_texture = nullptr;
    GpuImage* normal_texture = nullptr;
};

enum class LightType { Directional, Point, Spot };

struct Light {
    LightType type = LightType::Directional;
    vec3 direction{0, -1, 0};   // directional / spot
    vec3 position{0, 0, 0};     // point / spot
    vec3 color{1, 1, 1};
    float intensity = 1.0f;
    float spot_angle_deg = 30.0f;
};

struct Camera {
    float fov_deg = 60.0f;
    vec3 position{0, 0, 5};
    vec3 target{0, 0, 0};
    vec3 up{0, 1, 0};
    float near_z = 0.1f;
    float far_z = 100.0f;
};

struct LightData {
    float position_type[4];
    float color_intensity[4];
    float spot_params[4];
};

struct LightUBO {
    LightData lights[16];
    int light_count;
    float camera_pos[3];
    float inv_view_proj[16];
};

struct SceneCollection {
    std::vector<SceneObject> objects;
    std::vector<Light> lights;
    Camera camera;

    void clear();
    void add_object(SceneObject obj);
    void add_light(Light l);
    void set_camera(Camera c);
};

} // namespace joon
