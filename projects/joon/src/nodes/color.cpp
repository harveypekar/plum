#include "nodes/node_registry.h"

namespace joon::nodes {

void register_color(NodeRegistry& reg) {
    reg.register_node("color", [](const ir::Node& node, EvalContext& ctx) {
        float r = 0, g = 0, b = 0;

        // Read constant values from kwargs (e.g., :r 0.5 :g 0.3 :b 0.8)
        for (auto& kw : node.kwargs) {
            if (kw.name == "r") r = std::get<float>(kw.value);
            else if (kw.name == "g") g = std::get<float>(kw.value);
            else if (kw.name == "b") b = std::get<float>(kw.value);
        }

        // Also support positional args — read the constant image's first pixel
        // The interpreter fills constant images with the scalar value in all channels
        if (node.inputs.size() >= 1) {
            auto* ri = ctx.pool.get_image(node.inputs[0]);
            if (ri) {
                float px[4];
                ctx.pool.download(ri, px, sizeof(px));
                r = px[0];
            }
        }
        if (node.inputs.size() >= 2) {
            auto* gi = ctx.pool.get_image(node.inputs[1]);
            if (gi) {
                float px[4];
                ctx.pool.download(gi, px, sizeof(px));
                g = px[0];
            }
        }
        if (node.inputs.size() >= 3) {
            auto* bi = ctx.pool.get_image(node.inputs[2]);
            if (bi) {
                float px[4];
                ctx.pool.download(bi, px, sizeof(px));
                b = px[0];
            }
        }

        auto* img = ctx.pool.alloc_image(node.id, ctx.default_width, ctx.default_height);
        std::vector<float> data(ctx.default_width * ctx.default_height * 4);
        for (size_t i = 0; i < data.size(); i += 4) {
            data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = 1.0f;
        }
        ctx.pool.upload(img, data.data(), data.size() * sizeof(float));
    });
}

} // namespace joon::nodes
