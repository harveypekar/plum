#include "interpreter/interpreter.h"

namespace joon {

Interpreter::Interpreter(EvalContext& ctx, const NodeRegistry& registry)
    : m_ctx(ctx), m_registry(registry) {}

void Interpreter::evaluate(IRGraph& graph) {
    auto order = graph.topological_order();

    // RENDER nodes (e.g. `pass`) must run AFTER all SCENE collection and GPU
    // compute is done — the geometry pass needs the populated SceneCollection
    // and any compute-produced textures it samples. Defer them.
    std::vector<uint32_t> deferred_render;

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

        for (auto& kw : node.kwargs) {
            if (kw.source_node != UINT32_MAX && kw.source_node < graph.nodes.size())
                kw.value = graph.nodes[kw.source_node].constant_value;
        }

        if (node.tier == Tier::RENDER) {
            deferred_render.push_back(id);
            continue;
        }

        auto* executor = m_registry.find(node.op);
        if (executor) {
            (*executor)(node, m_ctx);
        }
    }

    // Deferred RENDER pass — no executors registered for these in sub-project 2's
    // Task 5; Task 8 wires up `pass`. Nodes without executors are skipped harmlessly.
    for (uint32_t id : deferred_render) {
        auto& node = graph.nodes[id];
        auto* executor = m_registry.find(node.op);
        if (executor) (*executor)(node, m_ctx);
    }
}

} // namespace joon
