#include "ir/type_checker.h"

namespace joon::ir {

// Promotion lattice: FLOAT < INT < BOOL < VEC2 < VEC3 < VEC4 < IMAGE
// FLOAT promotes into everything. IMAGE is the widest.
static Type promote(Type a, Type b) {
    if (a == b) return a;
    if (a == Type::FLOAT) return b;
    if (b == Type::FLOAT) return a;
    if (a == Type::IMAGE || b == Type::IMAGE) return Type::IMAGE;
    if (a == Type::VEC4 || b == Type::VEC4) return Type::VEC4;
    if (a == Type::VEC3 || b == Type::VEC3) return Type::VEC3;
    if (a == Type::VEC2 || b == Type::VEC2) return Type::VEC2;
    return a;
}

static bool is_math_op(const std::string& op) {
    return op == "+" || op == "-" || op == "*" || op == "/";
}

void type_check(IRGraph& graph) {
    auto order = graph.topological_order();

    for (uint32_t id : order) {
        auto& node = graph.nodes[id];

        if (node.op == "constant" || node.op == "param" ||
            node.op == "string_constant" || node.op == "error") {
            continue;
        }

        if (node.op == "image") {
            node.output_type = Type::IMAGE;
            continue;
        }

        if (node.op == "color") {
            node.output_type = Type::VEC3;
            continue;
        }

        if (node.op == "noise") {
            node.output_type = Type::FLOAT;
            continue;
        }

        if (is_math_op(node.op)) {
            if (node.inputs.size() != 2) {
                graph.diagnostics.push_back({
                    Diagnostic::Level::ERROR,
                    "Operator " + node.op + " expects 2 arguments, got " +
                        std::to_string(node.inputs.size()),
                    0, 0
                });
                continue;
            }
            Type a = graph.nodes[node.inputs[0]].output_type;
            Type b = graph.nodes[node.inputs[1]].output_type;
            node.output_type = promote(a, b);
            continue;
        }

        // Unary image ops: output type matches input
        if (node.op == "invert" || node.op == "threshold" ||
            node.op == "blur" || node.op == "levels") {
            if (!node.inputs.empty()) {
                node.output_type = graph.nodes[node.inputs[0]].output_type;
            }
            continue;
        }

        // Binary image ops
        if (node.op == "blend") {
            if (node.inputs.size() >= 2) {
                Type a = graph.nodes[node.inputs[0]].output_type;
                Type b = graph.nodes[node.inputs[1]].output_type;
                node.output_type = promote(a, b);
            }
            continue;
        }

        if (node.op == "save") {
            if (!node.inputs.empty()) {
                node.output_type = graph.nodes[node.inputs[0]].output_type;
            }
            continue;
        }

        graph.diagnostics.push_back({
            Diagnostic::Level::ERROR,
            "Unknown node type: " + node.op,
            0, 0
        });
    }
}

} // namespace joon::ir
