#include "nodes/node_registry.h"
#include "nodes/gpu_dispatch.h"

namespace joon {

static void register_binary_op(NodeRegistry& reg, const std::string& op,
                                const std::string& shader_name) {
    reg.register_node(op, [shader_name](const Node& node, EvalContext& ctx) {
        if (node.inputs.size() != 2) return;

        auto* a = ctx.pool.get_image(node.inputs[0]);
        auto* b = ctx.pool.get_image(node.inputs[1]);
        if (!a || !b) return;

        uint32_t w = a->width, h = a->height;
        auto* out = ctx.pool.alloc_image(node.id, w, h);

        gpu_dispatch(ctx, shader_name, {a, b, out}, w, h);
    });
}

void register_math_ops(NodeRegistry& reg) {
    register_binary_op(reg, "+", "add");
    register_binary_op(reg, "-", "sub");
    register_binary_op(reg, "*", "mul");
    register_binary_op(reg, "/", "div");
}

} // namespace joon
