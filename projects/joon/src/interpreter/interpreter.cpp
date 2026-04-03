#include "interpreter/interpreter.h"

namespace joon {

Interpreter::Interpreter(nodes::EvalContext& ctx, const nodes::NodeRegistry& registry)
    : m_ctx(ctx), m_registry(registry) {}

void Interpreter::evaluate(const ir::IRGraph& graph) {
    auto order = graph.topological_order();

    for (uint32_t id : order) {
        auto& node = graph.nodes[id];

        // Built-in global inputs
        if (node.op == "builtin_viewport_uv") {
            uint32_t w = m_ctx.default_width, h = m_ctx.default_height;
            auto* img = m_ctx.pool.alloc_image(node.id, w, h);
            std::vector<float> data(w * h * 4);
            for (uint32_t y = 0; y < h; y++) {
                for (uint32_t x = 0; x < w; x++) {
                    size_t i = (y * w + x) * 4;
                    data[i + 0] = static_cast<float>(x) / static_cast<float>(w - 1);
                    data[i + 1] = static_cast<float>(y) / static_cast<float>(h - 1);
                    data[i + 2] = 0.0f;
                    data[i + 3] = 1.0f;
                }
            }
            m_ctx.pool.upload(img, data.data(), data.size() * sizeof(float));
            continue;
        }

        // Skip nodes that don't produce GPU resources
        if (node.op == "constant" || node.op == "string_constant" ||
            node.op == "param" || node.op == "error") {
            if ((node.op == "constant" || node.op == "param") && node.is_constant) {
                // Literal constant — fill a uniform image with the scalar value
                auto* fval = std::get_if<float>(&node.constant_value);
                float val = fval ? *fval : 0.0f;
                auto* img = m_ctx.pool.alloc_image(node.id,
                                                   m_ctx.default_width,
                                                   m_ctx.default_height);
                std::vector<float> data(m_ctx.default_width * m_ctx.default_height * 4);
                for (size_t i = 0; i < data.size(); i += 4) {
                    data[i] = val; data[i+1] = val; data[i+2] = val; data[i+3] = 1.0f;
                }
                m_ctx.pool.upload(img, data.data(), data.size() * sizeof(float));
            } else if (node.op == "constant" && !node.inputs.empty()) {
                // (constant <expr>) call — alias to the input's image
                auto* src = m_ctx.pool.get_image(node.inputs[0]);
                if (src) {
                    auto* img = m_ctx.pool.alloc_image(node.id, src->width, src->height);
                    std::vector<float> data(src->width * src->height * 4);
                    m_ctx.pool.download(src, data.data(), data.size() * sizeof(float));
                    m_ctx.pool.upload(img, data.data(), data.size() * sizeof(float));
                }
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
