#include <joon/graph.h>
#include "ir/ir_graph.h"

namespace joon {

struct Graph::Impl {
    ir::IRGraph ir;
};

Graph::Graph() : impl_(std::make_unique<Impl>()) {}
Graph::~Graph() = default;
Graph::Graph(Graph&&) noexcept = default;
Graph& Graph::operator=(Graph&&) noexcept = default;

bool Graph::has_errors() const {
    for (auto& d : impl_->ir.diagnostics) {
        if (d.level == ir::Diagnostic::Level::Error) return true;
    }
    return false;
}

const std::vector<ir::Diagnostic>& Graph::diagnostics() const {
    return impl_->ir.diagnostics;
}

ir::IRGraph& Graph::ir() { return impl_->ir; }
const ir::IRGraph& Graph::ir() const { return impl_->ir; }

} // namespace joon
