#include "nodes/node_registry.h"
#include "nodes/gpu_dispatch.h"

namespace joon::nodes {

void register_noise(NodeRegistry& reg) {
    reg.register_node("noise", [](const ir::Node& node, EvalContext& ctx) {
        // Inherit dimensions from first input if available, else use default
        uint32_t w = ctx.default_width, h = ctx.default_height;
        if (!node.inputs.empty()) {
            auto* in = ctx.pool.get_image(node.inputs[0]);
            if (in) { w = in->width; h = in->height; }
        }

        auto* img = ctx.pool.alloc_image(node.id, w, h);

        float scale = 4.0f, octaves = 1.0f;
        for (auto& kw : node.kwargs) {
            if (kw.name == "scale") scale = std::get<float>(kw.value);
            else if (kw.name == "octaves") octaves = std::get<float>(kw.value);
        }

        struct { float scale, octaves, width, height; } pc{
            scale, octaves, static_cast<float>(w), static_cast<float>(h)
        };

        gpu_dispatch(ctx, "noise", {img}, w, h, &pc, sizeof(pc));
    });
}

} // namespace joon::nodes
