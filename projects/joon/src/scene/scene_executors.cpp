#include "scene/scene_executors.h"
#include "scene/primitives.h"
#include "scene/obj_loader.h"
#include "nodes/node_registry.h"
#include "ir/node.h"
#include <joon/scene.h>

namespace joon {

namespace {

// Look up a kwarg by name on a Node. Returns the float value or fallback.
// The DSL parser stores numeric kwargs as `float` in the variant; symbol kwargs
// that resolve to a constant node have `value` patched by the interpreter to the
// source's constant_value. value_as_float handles both.
float kwarg_float(const Node& n, const char* name, float fallback) {
    for (const auto& k : n.kwargs)
        if (k.name == name) return value_as_float(k.value, fallback);
    return fallback;
}

// vec3 kwargs aren't supported by the parser yet (no [x y z] vector literal
// tokens). This helper exists so the executor signature is forward-compatible
// when vector literals are added — for now it always returns the fallback.
vec3 kwarg_vec3(const Node& /*n*/, const char* /*name*/, vec3 fallback) {
    return fallback;
}

uint32_t kwarg_source_node(const Node& n, const char* name) {
    for (const auto& k : n.kwargs)
        if (k.name == name) return k.source_node;
    return UINT32_MAX;
}

void exec_cube(const Node& n, EvalContext& ctx) {
    SceneObject o;
    o.mesh = gen_cube(kwarg_float(n, "scale", 1.0f));
    o.position = kwarg_vec3(n, "position", {0, 0, 0});
    o.rotation = kwarg_vec3(n, "rotation", {0, 0, 0});
    o.material_node_id = kwarg_source_node(n, "material");
    ctx.scene.add_object(std::move(o));
}

void exec_sphere(const Node& n, EvalContext& ctx) {
    SceneObject o;
    o.mesh = gen_sphere(kwarg_float(n, "radius", 0.5f));
    o.position = kwarg_vec3(n, "position", {0, 0, 0});
    o.rotation = kwarg_vec3(n, "rotation", {0, 0, 0});
    o.material_node_id = kwarg_source_node(n, "material");
    ctx.scene.add_object(std::move(o));
}

void exec_plane(const Node& n, EvalContext& ctx) {
    SceneObject o;
    o.mesh = gen_plane(kwarg_float(n, "width", 1.0f),
                       kwarg_float(n, "height", 1.0f));
    o.position = kwarg_vec3(n, "position", {0, 0, 0});
    o.rotation = kwarg_vec3(n, "rotation", {0, 0, 0});
    o.material_node_id = kwarg_source_node(n, "material");
    ctx.scene.add_object(std::move(o));
}

void exec_cylinder(const Node& n, EvalContext& ctx) {
    SceneObject o;
    o.mesh = gen_cylinder(kwarg_float(n, "radius", 0.5f),
                          kwarg_float(n, "height", 1.0f),
                          static_cast<int>(kwarg_float(n, "segments", 32.0f)));
    o.position = kwarg_vec3(n, "position", {0, 0, 0});
    o.rotation = kwarg_vec3(n, "rotation", {0, 0, 0});
    o.material_node_id = kwarg_source_node(n, "material");
    ctx.scene.add_object(std::move(o));
}

void exec_mesh(const Node& n, EvalContext& ctx) {
    SceneObject o;
    if (!n.string_arg.empty()) o.mesh = load_obj_file(n.string_arg);
    o.position = kwarg_vec3(n, "position", {0, 0, 0});
    o.rotation = kwarg_vec3(n, "rotation", {0, 0, 0});
    o.material_node_id = kwarg_source_node(n, "material");
    ctx.scene.add_object(std::move(o));
}

void exec_light(const Node& n, EvalContext& ctx) {
    Light l;
    // type kwarg requires symbol-as-string parsing (not yet wired); default to
    // Directional for sub-project 2's single-light fragment shader.
    l.type = LightType::Directional;
    l.direction = kwarg_vec3(n, "direction", {0, -1, 0});
    l.position  = kwarg_vec3(n, "position",  {0, 0, 0});
    l.color     = kwarg_vec3(n, "color",     {1, 1, 1});
    l.intensity = kwarg_float(n, "intensity", 1.0f);
    l.spot_angle_deg = kwarg_float(n, "angle", 30.0f);
    ctx.scene.add_light(l);
}

void exec_camera(const Node& n, EvalContext& ctx) {
    if (ctx.camera_override) {
        ctx.scene.set_camera(*ctx.camera_override);
        return;
    }
    Camera c;
    c.fov_deg  = kwarg_float(n, "fov", 60.0f);
    c.position = kwarg_vec3(n, "position", {0, 0, 5});
    c.target   = kwarg_vec3(n, "target",   {0, 0, 0});
    c.up       = kwarg_vec3(n, "up",       {0, 1, 0});
    c.near_z   = kwarg_float(n, "near", 0.1f);
    c.far_z    = kwarg_float(n, "far", 100.0f);
    ctx.scene.set_camera(c);
}

} // namespace

void register_scene_nodes(NodeRegistry& reg) {
    reg.register_node("cube",     exec_cube);
    reg.register_node("sphere",   exec_sphere);
    reg.register_node("plane",    exec_plane);
    reg.register_node("cylinder", exec_cylinder);
    reg.register_node("mesh",     exec_mesh);
    reg.register_node("light",    exec_light);
    reg.register_node("camera",   exec_camera);
}

} // namespace joon
