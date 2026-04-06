#include "nodes/node_registry.h"

namespace joon {

void register_color(NodeRegistry& reg) {
    reg.register_node("color", [](const Node& node, EvalContext& ctx) {
        // Color args come as constant node inputs
        float r = 0, g = 0, b = 0;
        for (size_t i = 0; i < node.inputs.size() && i < 3; i++) {
            // Input nodes are constants — read their values from the pool's graph
            // For now we can't easily reach back to the IR from here,
            // so color values would need to come through kwargs or be resolved differently.
            // TODO: wire constant propagation through the interpreter
        }

        auto* img = ctx.pool.alloc_image(node.id, ctx.default_width, ctx.default_height);
        std::vector<float> data(ctx.default_width * ctx.default_height * 4);
        for (size_t i = 0; i < data.size(); i += 4) {
            data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = 1.0f;
        }
        ctx.pool.upload(img, data.data(), data.size() * sizeof(float));
    });
}

} // namespace joon
