#pragma once

#include <memory>
#include <string>
#include <vector>

namespace joon {

class IRGraph;
struct Diagnostic;

class Graph {
public:
    Graph();
    ~Graph();
    Graph(Graph&&) noexcept;
    Graph& operator=(Graph&&) noexcept;

    bool has_errors() const;
    const std::vector<Diagnostic>& diagnostics() const;

    IRGraph& ir();
    const IRGraph& ir() const;

private:
    friend class Context;
    struct Impl;
    std::unique_ptr<Impl> m_impl;
};

} // namespace joon
