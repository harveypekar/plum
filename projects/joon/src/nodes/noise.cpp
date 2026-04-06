#include "nodes/node_registry.h"
#include "nodes/gpu_dispatch.h"

namespace joon {

void register_noise(NodeRegistry& reg) {
    reg.register_node("noise", [](const Node& node, EvalContext& ctx) {
        auto* img = ctx.pool.alloc_image(node.id, ctx.default_width, ctx.default_height);

        float scale = 4.0f, octaves = 1.0f;
        for (auto& kw : node.kwargs) {
            if (kw.name == "scale") scale = std::get<float>(kw.value);
            else if (kw.name == "octaves") octaves = std::get<float>(kw.value);
        }

        struct { float scale, octaves, width, height; } pc{
            scale, octaves,
            static_cast<float>(ctx.default_width),
            static_cast<float>(ctx.default_height)
        };

        gpu_dispatch(ctx, "noise", {img}, ctx.default_width, ctx.default_height,
                     &pc, sizeof(pc));
    });
}

} // namespace joon
