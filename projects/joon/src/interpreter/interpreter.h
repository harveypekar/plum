#pragma once

#include "ir/ir_graph.h"
#include "nodes/node_registry.h"

namespace joon {

class Interpreter {
public:
    Interpreter(EvalContext& ctx, const NodeRegistry& registry);

    void evaluate(IRGraph& graph);

private:
    EvalContext& m_ctx;
    const NodeRegistry& m_registry;
};

} // namespace joon
