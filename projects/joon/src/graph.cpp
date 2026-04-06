#include <joon/graph.h>
#include "ir/ir_graph.h"

namespace joon {

struct Graph::Impl {
    IRGraph ir;
};

Graph::Graph() : m_impl(std::make_unique<Impl>()) {}
Graph::~Graph() = default;
Graph::Graph(Graph&&) noexcept = default;
Graph& Graph::operator=(Graph&&) noexcept = default;

bool Graph::has_errors() const {
    for (auto& d : m_impl->ir.diagnostics) {
        if (d.level == Diagnostic::Level::ERROR) return true;
    }
    return false;
}

const std::vector<Diagnostic>& Graph::diagnostics() const {
    return m_impl->ir.diagnostics;
}

IRGraph& Graph::ir() { return m_impl->ir; }
const IRGraph& Graph::ir() const { return m_impl->ir; }

} // namespace joon
