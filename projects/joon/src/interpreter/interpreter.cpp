#include "interpreter/interpreter.h"

namespace joon {

Interpreter::Interpreter(nodes::EvalContext& ctx, const nodes::NodeRegistry& registry)
    : ctx_(ctx), registry_(registry) {}

void Interpreter::evaluate(const ir::IRGraph& graph) {
    auto order = graph.topological_order();

    for (uint32_t id : order) {
        auto& node = graph.nodes[id];

        // Skip nodes that don't produce GPU resources
        if (node.op == "constant" || node.op == "string_constant" ||
            node.op == "param" || node.op == "error") {
            // For constant float nodes that feed into GPU ops,
            // we need to create a constant image so math ops can consume them
            if ((node.op == "constant" || node.op == "param") && node.is_constant) {
                float val = std::get<float>(node.constant_value);
                auto* img = ctx_.pool.alloc_image(node.id,
                                                   ctx_.default_width,
                                                   ctx_.default_height);
                std::vector<float> data(ctx_.default_width * ctx_.default_height * 4);
                for (size_t i = 0; i < data.size(); i += 4) {
                    data[i] = val; data[i+1] = val; data[i+2] = val; data[i+3] = 1.0f;
                }
                ctx_.pool.upload(img, data.data(), data.size() * sizeof(float));
            }
            continue;
        }

        auto* executor = registry_.find(node.op);
        if (executor) {
            (*executor)(node, ctx_);
        }
    }
}

} // namespace joon
