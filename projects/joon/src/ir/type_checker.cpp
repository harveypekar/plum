#include "ir/type_checker.h"

namespace joon::ir {

// Promotion lattice: Float < Int < Bool < Vec2 < Vec3 < Vec4 < Image
// Float promotes into everything. Image is the widest.
static Type promote(Type a, Type b) {
    if (a == b) return a;
    if (a == Type::Float) return b;
    if (b == Type::Float) return a;
    if (a == Type::Image || b == Type::Image) return Type::Image;
    if (a == Type::Vec4 || b == Type::Vec4) return Type::Vec4;
    if (a == Type::Vec3 || b == Type::Vec3) return Type::Vec3;
    if (a == Type::Vec2 || b == Type::Vec2) return Type::Vec2;
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
            node.output_type = Type::Image;
            continue;
        }

        if (node.op == "color") {
            node.output_type = Type::Vec3;
            continue;
        }

        if (node.op == "noise") {
            node.output_type = Type::Float;
            continue;
        }

        if (is_math_op(node.op)) {
            if (node.inputs.size() != 2) {
                graph.diagnostics.push_back({
                    Diagnostic::Level::Error,
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
            Diagnostic::Level::Error,
            "Unknown node type: " + node.op,
            0, 0
        });
    }
}

} // namespace joon::ir
