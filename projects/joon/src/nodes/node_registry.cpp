#include "nodes/node_registry.h"

namespace joon::nodes {

void NodeRegistry::register_node(const std::string& op, NodeExecutor executor) {
    m_executors[op] = std::move(executor);
}

const NodeExecutor* NodeRegistry::find(const std::string& op) const {
    auto it = m_executors.find(op);
    if (it == m_executors.end()) return nullptr;
    return &it->second;
}

NodeRegistry NodeRegistry::create_default() {
    NodeRegistry reg;
    register_image_load(reg);
    register_noise(reg);
    register_color(reg);
    register_math_ops(reg);
    register_image_ops(reg);
    register_save(reg);
    return reg;
}

} // namespace joon::nodes
