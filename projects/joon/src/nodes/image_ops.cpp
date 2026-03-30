#include "nodes/node_registry.h"
#include "nodes/gpu_dispatch.h"

namespace joon::nodes {

void register_image_ops(NodeRegistry& reg) {
    // Invert: no push constants
    reg.register_node("invert", [](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.empty()) return;
        auto* input = ctx.pool.get_image(node.inputs[0]);
        if (!input) return;

        auto* out = ctx.pool.alloc_image(node.id, input->width, input->height);
        gpu_dispatch(ctx, "invert", {input, out}, input->width, input->height);
    });

    // Threshold: push constant float
    reg.register_node("threshold", [](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.empty()) return;
        auto* input = ctx.pool.get_image(node.inputs[0]);
        if (!input) return;

        float threshold = 0.5f;
        for (auto& kw : node.kwargs) {
            if (kw.name == "threshold") threshold = std::get<float>(kw.value);
        }

        auto* out = ctx.pool.alloc_image(node.id, input->width, input->height);
        gpu_dispatch(ctx, "threshold", {input, out}, input->width, input->height,
                     &threshold, sizeof(float));
    });

    // Levels: push constants (contrast, brightness)
    reg.register_node("levels", [](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.empty()) return;
        auto* input = ctx.pool.get_image(node.inputs[0]);
        if (!input) return;

        struct { float contrast, brightness; } pc{ 1.0f, 0.0f };
        for (auto& kw : node.kwargs) {
            if (kw.name == "contrast") pc.contrast = std::get<float>(kw.value);
            else if (kw.name == "brightness") pc.brightness = std::get<float>(kw.value);
        }

        auto* out = ctx.pool.alloc_image(node.id, input->width, input->height);
        gpu_dispatch(ctx, "levels", {input, out}, input->width, input->height,
                     &pc, sizeof(pc));
    });

    // Blur: push constant (radius)
    reg.register_node("blur", [](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.empty()) return;
        auto* input = ctx.pool.get_image(node.inputs[0]);
        if (!input) return;

        float radius = 1.0f;
        for (auto& kw : node.kwargs) {
            if (kw.name == "radius") radius = std::get<float>(kw.value);
        }

        auto* out = ctx.pool.alloc_image(node.id, input->width, input->height);
        gpu_dispatch(ctx, "blur", {input, out}, input->width, input->height,
                     &radius, sizeof(float));
    });

    // Blend: push constants (opacity, mode)
    reg.register_node("blend", [](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.size() < 2) return;
        auto* a = ctx.pool.get_image(node.inputs[0]);
        auto* b = ctx.pool.get_image(node.inputs[1]);
        if (!a || !b) return;

        struct { float opacity; int mode; } pc{ 1.0f, 0 };
        for (auto& kw : node.kwargs) {
            if (kw.name == "opacity") pc.opacity = std::get<float>(kw.value);
            else if (kw.name == "mode") pc.mode = static_cast<int>(std::get<float>(kw.value));
        }

        uint32_t w = a->width, h = a->height;
        auto* out = ctx.pool.alloc_image(node.id, w, h);
        gpu_dispatch(ctx, "blend", {a, b, out}, w, h, &pc, sizeof(pc));
    });
}

} // namespace joon::nodes
