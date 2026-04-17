#pragma once

#include "ir/node.h"
#include "dsl/ast.h"
#include <vector>
#include <unordered_map>
#include <string>

namespace joon {

struct Diagnostic {
    enum class Level { ERROR, WARNING };
    Level level;
    std::string message;
    uint32_t line, col;
};

class IRGraph {
public:
    std::vector<Node> nodes;
    std::vector<Edge> edges;
    std::vector<ParamInfo> params;
    std::vector<OutputInfo> outputs;
    std::vector<Diagnostic> diagnostics;

    static IRGraph from_ast(const Program& program);

    std::vector<uint32_t> topological_order();

    const Node* find_node(uint32_t id) const;
    const Node* find_node_by_name(const std::string& name) const;

private:
    std::unordered_map<std::string, uint32_t> m_nameToNode;

    uint32_t add_node(const std::string& op, Tier tier);
    void resolve_ast(const Program& program);
    uint32_t resolve_expr(const AstNode& expr);
};

} // namespace joon
