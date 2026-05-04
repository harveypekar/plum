#include "interpreter/interpreter.h"

namespace joon {

Interpreter::Interpreter(EvalContext& ctx, const NodeRegistry& registry)
    : m_ctx(ctx), m_registry(registry) {}

void Interpreter::evaluate(IRGraph& graph) {
    auto order = graph.topological_order();

    // Phase 1: SCENE-tier executors. Scene nodes carry no inter-edges in the
    // current DSL, so their topo position relative to RENDER/GPU consumers is
    // arbitrary; doing them as a separate pre-pass guarantees the
    // SceneCollection is fully populated before any pass executor runs.
    for (uint32_t id : order) {
        auto& node = graph.nodes[id];
        if (node.tier != Tier::SCENE) continue;

        for (auto& kw : node.kwargs) {
            if (kw.source_node != UINT32_MAX && kw.source_node < graph.nodes.size())
                kw.value = graph.nodes[kw.source_node].constant_value;
        }

        auto* executor = m_registry.find(node.op);
        if (executor) (*executor)(node, m_ctx);
    }

    // Phase 2: MATERIAL tier — compile shaders, cache pipelines.
    for (uint32_t id : order) {
        auto& node = graph.nodes[id];
        if (node.tier != Tier::MATERIAL) continue;

        for (auto& kw : node.kwargs) {
            if (kw.source_node != UINT32_MAX && kw.source_node < graph.nodes.size())
                kw.value = graph.nodes[kw.source_node].constant_value;
        }

        auto* executor = m_registry.find(node.op);
        if (executor) (*executor)(node, m_ctx);
    }

    // Phase 3: CPU constants + GPU compute + RENDER passes in topological
    // order so producer-consumer chains (e.g. pass → levels) execute correctly.
    for (uint32_t id : order) {
        auto& node = graph.nodes[id];
        if (node.tier == Tier::SCENE || node.tier == Tier::MATERIAL) continue;

        // Skip nodes that don't produce GPU resources via an executor
        if (node.op == "constant" || node.op == "string_constant" ||
            node.op == "param" || node.op == "error") {
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

        auto* executor = m_registry.find(node.op);
        if (executor) (*executor)(node, m_ctx);
    }
}

void Interpreter::render(IRGraph& graph) {
    auto order = graph.topological_order();

    for (uint32_t id : order) {
        auto& node = graph.nodes[id];
        if (node.tier == Tier::SCENE || node.tier == Tier::MATERIAL) continue;

        if (node.op == "constant" || node.op == "string_constant" ||
            node.op == "param" || node.op == "error") {
            continue;
        }

        for (auto& kw : node.kwargs) {
            if (kw.source_node != UINT32_MAX && kw.source_node < graph.nodes.size())
                kw.value = graph.nodes[kw.source_node].constant_value;
        }

        auto* executor = m_registry.find(node.op);
        if (executor) (*executor)(node, m_ctx);
    }
}

} // namespace joon
