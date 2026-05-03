#include "ir/ir_graph.h"
#include <algorithm>
#include <queue>
#include <unordered_set>

namespace joon {

IRGraph IRGraph::from_ast(const Program& program) {
    IRGraph graph;
    graph.resolve_ast(program);
    return graph;
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

void IRGraph::resolve_ast(const Program& program) {
    for (auto& stmt : program.statements) {
        if (auto* def = std::get_if<DefNode>(&stmt->data)) {
            uint32_t node_id = resolve_expr(*def->value);
            nodes[node_id].name = def->name;
            m_nameToNode[def->name] = node_id;

        } else if (auto* param = std::get_if<ParamNode>(&stmt->data)) {
            uint32_t id = add_node("param", Tier::CPU);
            nodes[id].name = param->name;
            nodes[id].is_constant = true;

            auto* num = std::get_if<NumberNode>(&param->default_value->data);
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
                auto* cnum = std::get_if<NumberNode>(&c.value->data);
                if (cnum) pi.constraints[c.name] = static_cast<float>(cnum->value);
            }

            params.push_back(std::move(pi));
            m_nameToNode[param->name] = id;

        } else if (auto* output = std::get_if<OutputNode>(&stmt->data)) {
            uint32_t node_id = resolve_expr(*output->value);
            outputs.push_back({ node_id });
        }
    }
}

uint32_t IRGraph::resolve_expr(const AstNode& expr) {
    if (auto* num = std::get_if<NumberNode>(&expr.data)) {
        uint32_t id = add_node("constant", Tier::CPU);
        nodes[id].is_constant = true;
        nodes[id].constant_value = static_cast<float>(num->value);
        return id;
    }

    if (auto* str = std::get_if<StringNode>(&expr.data)) {
        uint32_t id = add_node("string_constant", Tier::CPU);
        nodes[id].string_arg = str->value;
        return id;
    }

    if (auto* sym = std::get_if<SymbolNode>(&expr.data)) {
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

    if (auto* call = std::get_if<CallNode>(&expr.data)) {
        static const std::unordered_set<std::string> SCENE_OPS = {
            "cube", "sphere", "plane", "cylinder", "mesh", "light", "camera"
        };
        static const std::unordered_set<std::string> RENDER_OPS = { "pass" };
        static const std::unordered_set<std::string> CPU_OPS = {
            "image", "color", "save"
        };
        static const std::unordered_set<std::string> MATERIAL_OPS = { "shader" };

        Tier tier;
        Type output_type = Type::FLOAT;
        if (MATERIAL_OPS.count(call->op)) {
            tier = Tier::MATERIAL;
            output_type = Type::MATERIAL;
        } else if (SCENE_OPS.count(call->op)) {
            tier = Tier::SCENE;
            if (call->op == "light") output_type = Type::LIGHT;
            else if (call->op == "camera") output_type = Type::CAMERA;
            else output_type = Type::SCENE_OBJECT;
        } else if (RENDER_OPS.count(call->op)) {
            tier = Tier::RENDER;
            output_type = Type::RENDER_TARGET;
        } else if (CPU_OPS.count(call->op)) {
            tier = Tier::CPU;
        } else {
            tier = Tier::GPU;
        }

        uint32_t id = add_node(call->op, tier);
        nodes[id].output_type = output_type;

        for (auto& arg : call->args) {
            uint32_t input_id = resolve_expr(*arg);
            uint32_t input_slot = static_cast<uint32_t>(nodes[id].inputs.size());
            nodes[id].inputs.push_back(input_id);
            edges.push_back({ input_id, id, input_slot });
            if (nodes[input_id].op == "string_constant")
                nodes[id].string_arg = nodes[input_id].string_arg;
        }

        for (auto& kw : call->kwargs) {
            if (auto* knum = std::get_if<NumberNode>(&kw.value->data)) {
                nodes[id].kwargs.push_back({ kw.name, static_cast<float>(knum->value) });
            } else if (auto* kstr = std::get_if<StringNode>(&kw.value->data)) {
                nodes[id].string_arg = kstr->value;
            } else if (auto* ksym = std::get_if<SymbolNode>(&kw.value->data)) {
                auto sym_it = m_nameToNode.find(ksym->name);
                if (sym_it != m_nameToNode.end()) {
                    auto& src = nodes[sym_it->second];
                    nodes[id].kwargs.push_back({ kw.name, src.constant_value, sym_it->second });
                } else {
                    nodes[id].kwargs.push_back({ kw.name, 0.0f });
                    nodes[id].string_arg = ksym->name;
                }
            }
        }

        if (call->op == "shader") {
            ShaderDef sd;
            for (auto& kw : call->kwargs) {
                auto* fn = std::get_if<FnNode>(&kw.value->data);
                if (!fn) continue;
                ShaderFnDef fndef;
                fndef.params = fn->params;
                for (auto& o : fn->outputs)
                    fndef.outputs.push_back({o.name, o.type_name});
                for (auto& b : fn->body)
                    fndef.body.push_back(std::shared_ptr<AstNode>(std::move(b)));
                if (kw.name == "vertex") sd.vertex = std::move(fndef);
                else if (kw.name == "fragment") sd.fragment = std::move(fndef);
                else if (kw.name == "brdf") sd.brdf = std::move(fndef);
            }
            shader_defs[id] = std::move(sd);
        }

        return id;
    }

    if (auto* dot = std::get_if<DotAccessNode>(&expr.data)) {
        auto* obj_sym = std::get_if<SymbolNode>(&dot->object->data);
        if (obj_sym) {
            auto it = m_nameToNode.find(obj_sym->name);
            if (it != m_nameToNode.end()) {
                uint32_t parent_id = it->second;
                uint32_t id = add_node("channel_select", Tier::GPU);
                nodes[id].inputs.push_back(parent_id);
                edges.push_back({ parent_id, id, 0 });
                nodes[id].string_arg = dot->field;
                nodes[id].output_type = Type::IMAGE;
                return id;
            }
        }
        diagnostics.push_back({
            Diagnostic::Level::ERROR,
            "Invalid dot access",
            expr.line, expr.col
        });
        return add_node("error", Tier::CPU);
    }

    diagnostics.push_back({
        Diagnostic::Level::ERROR,
        "Unexpected expression",
        expr.line, expr.col
    });
    return add_node("error", Tier::CPU);
}

std::vector<uint32_t> IRGraph::topological_order() {
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

    if (order.size() != nodes.size()) {
        diagnostics.push_back({
            Diagnostic::Level::ERROR,
            "Cycle detected in compute graph",
            0, 0
        });
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

} // namespace joon
