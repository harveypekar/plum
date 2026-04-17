#include "interpreter/interpreter.h"

namespace joon {

Interpreter::Interpreter(EvalContext& ctx, const NodeRegistry& registry)
    : m_ctx(ctx), m_registry(registry) {}

void Interpreter::evaluate(IRGraph& graph) {
    auto order = graph.topological_order();

    for (uint32_t id : order) {
        auto& node = graph.nodes[id];

        // Skip nodes that don't produce GPU resources
        if (node.op == "constant" || node.op == "string_constant" ||
            node.op == "param" || node.op == "error") {
            // For constant float nodes that feed into GPU ops,
            // we need to create a constant image so math ops can consume them
            if ((node.op == "constant" || node.op == "param") && node.is_constant) {
                float val = value_as_float(node.constant_value);
                auto* img = m_ctx.pool.alloc_image(node.id,
                                                   m_ctx.default_width,
                                                   m_ctx.default_height);
                std::vector<float> data(m_ctx.default_width * m_ctx.default_height * 4);
                for (size_t i = 0; i < data.size(); i += 4) {
                    data[i] = val; data[i+1] = val; data[i+2] = val; data[i+3] = 1.0f;
                }
                m_ctx.pool.upload(img, data.data(), data.size() * sizeof(float));
            }
            continue;
        }

        auto* executor = m_registry.find(node.op);
        if (executor) {
            (*executor)(node, m_ctx);
        }
    }
}

} // namespace joon
