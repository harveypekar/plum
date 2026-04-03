#include "ir/ir_graph.h"
#include <algorithm>
#include <queue>

namespace joon::ir {

IRGraph IRGraph::from_ast(const dsl::Program& program) {
    IRGraph graph;
    graph.add_builtins();
    graph.resolve_ast(program);
    return graph;
}

void IRGraph::add_builtins() {
    // viewport_uv: RG = normalized pixel coordinates, B=0, A=1
    uint32_t id = add_node("builtin_viewport_uv", Tier::CPU);
    nodes[id].name = "viewport_uv";
    nodes[id].output_type = Type::IMAGE;
    m_nameToNode["viewport_uv"] = id;
}

uint32_t IRGraph::add_node(const std::string& op, Tier tier) {
    uint32_t id = static_cast<uint32_t>(nodes.size());
    Node node{};
    node.id = id;
    node.op = op;
    node.tier = tier;
    node.output_type = Type::FLOAT;
    nodes.push_back(std::move(node));
    return id;
}

void IRGraph::resolve_ast(const dsl::Program& program) {
    for (auto& stmt : program.statements) {
        if (auto* def = std::get_if<dsl::DefNode>(&stmt->data)) {
            uint32_t node_id = resolve_expr(*def->value);
            nodes[node_id].name = def->name;
            m_nameToNode[def->name] = node_id;

        } else if (auto* param = std::get_if<dsl::ParamNode>(&stmt->data)) {
            uint32_t id = add_node("param", Tier::CPU);
            nodes[id].name = param->name;
            nodes[id].is_constant = true;

            auto* num = std::get_if<dsl::NumberNode>(&param->default_value->data);
            if (num) {
                nodes[id].constant_value = static_cast<float>(num->value);
            }

            ParamInfo pi{};
            pi.name = param->name;
            pi.default_value = nodes[id].constant_value;
            pi.node_id = id;

            if (param->type_name == "float")      pi.type = Type::FLOAT;
            else if (param->type_name == "int")    pi.type = Type::INT;
            else if (param->type_name == "bool")   pi.type = Type::BOOL;
            else if (param->type_name == "vec2")   pi.type = Type::VEC2;
            else if (param->type_name == "vec3")   pi.type = Type::VEC3;
            else if (param->type_name == "vec4")   pi.type = Type::VEC4;
            else pi.type = Type::FLOAT;

            nodes[id].output_type = pi.type;

            for (auto& c : param->constraints) {
                auto* cnum = std::get_if<dsl::NumberNode>(&c.value->data);
                if (cnum) pi.constraints[c.name] = static_cast<float>(cnum->value);
            }

            params.push_back(std::move(pi));
            m_nameToNode[param->name] = id;

        } else if (auto* output = std::get_if<dsl::OutputNode>(&stmt->data)) {
            uint32_t node_id = resolve_expr(*output->value);
            outputs.push_back({ node_id });
        }
    }
}

uint32_t IRGraph::resolve_expr(const dsl::AstNode& expr) {
    if (auto* num = std::get_if<dsl::NumberNode>(&expr.data)) {
        uint32_t id = add_node("constant", Tier::CPU);
        nodes[id].is_constant = true;
        nodes[id].constant_value = static_cast<float>(num->value);
        return id;
    }

    if (auto* str = std::get_if<dsl::StringNode>(&expr.data)) {
        uint32_t id = add_node("string_constant", Tier::CPU);
        nodes[id].string_arg = str->value;
        return id;
    }

    if (auto* sym = std::get_if<dsl::SymbolNode>(&expr.data)) {
        auto it = m_nameToNode.find(sym->name);
        if (it == m_nameToNode.end()) {
            diagnostics.push_back({
                Diagnostic::Level::ERROR,
                "Undefined symbol: " + sym->name,
                expr.line, expr.col
            });
            return add_node("error", Tier::CPU);
        }
        return it->second;
    }

    if (auto* call = std::get_if<dsl::CallNode>(&expr.data)) {
        Tier tier = Tier::GPU;
        if (call->op == "image" || call->op == "color" || call->op == "save") {
            tier = Tier::CPU;
        }

        uint32_t id = add_node(call->op, tier);

        for (auto& arg : call->args) {
            uint32_t input_id = resolve_expr(*arg);
            uint32_t input_slot = static_cast<uint32_t>(nodes[id].inputs.size());
            nodes[id].inputs.push_back(input_id);
            edges.push_back({ input_id, id, input_slot });
        }

        for (auto& kw : call->kwargs) {
            if (auto* knum = std::get_if<dsl::NumberNode>(&kw.value->data)) {
                nodes[id].kwargs.push_back({ kw.name, static_cast<float>(knum->value) });
            } else if (auto* kstr = std::get_if<dsl::StringNode>(&kw.value->data)) {
                nodes[id].string_arg = kstr->value;
            } else if (auto* ksym = std::get_if<dsl::SymbolNode>(&kw.value->data)) {
                // Keyword value is a symbol reference (e.g., :mode multiply)
                // Store as string for now — node implementations interpret it
                nodes[id].kwargs.push_back({ kw.name, 0.0f });
                nodes[id].string_arg = ksym->name; // overloaded, but works for single-kwarg case
            }
        }

        return id;
    }

    diagnostics.push_back({
        Diagnostic::Level::ERROR,
        "Unexpected expression",
        expr.line, expr.col
    });
    return add_node("error", Tier::CPU);
}

std::vector<uint32_t> IRGraph::topological_order() const {
    std::vector<uint32_t> in_degree(nodes.size(), 0);
    std::vector<std::vector<uint32_t>> dependents(nodes.size());

    for (auto& edge : edges) {
        in_degree[edge.to_node]++;
        dependents[edge.from_node].push_back(edge.to_node);
    }

    std::queue<uint32_t> queue;
    for (uint32_t i = 0; i < nodes.size(); i++) {
        if (in_degree[i] == 0) queue.push(i);
    }

    std::vector<uint32_t> order;
    while (!queue.empty()) {
        uint32_t n = queue.front();
        queue.pop();
        order.push_back(n);
        for (uint32_t dep : dependents[n]) {
            if (--in_degree[dep] == 0) queue.push(dep);
        }
    }

    return order;
}

const Node* IRGraph::find_node(uint32_t id) const {
    if (id < nodes.size()) return &nodes[id];
    return nullptr;
}

const Node* IRGraph::find_node_by_name(const std::string& name) const {
    auto it = m_nameToNode.find(name);
    if (it != m_nameToNode.end()) return &nodes[it->second];
    return nullptr;
}

} // namespace joon::ir
