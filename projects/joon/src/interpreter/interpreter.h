#pragma once

#include "ir/ir_graph.h"
#include "nodes/node_registry.h"

namespace joon {

class Interpreter {
public:
    Interpreter(nodes::EvalContext& ctx, const nodes::NodeRegistry& registry);

    void evaluate(const ir::IRGraph& graph);

private:
    nodes::EvalContext& m_ctx;
    const nodes::NodeRegistry& m_registry;
};

} // namespace joon
