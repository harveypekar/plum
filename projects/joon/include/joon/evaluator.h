#pragma once

#include <joon/types.h>
#include <memory>
#include <string>
#include <vector>

namespace joon {

class Context;
class Graph;
namespace ir { struct Diagnostic; }
namespace vk { class ResourcePool; struct GpuImage; }

template<typename T>
class Param {
public:
    Param(uint32_t node_id, Graph& graph) : m_nodeId(node_id), m_graph(graph) {}
    Param& operator=(const T& value);
    operator T() const;

private:
    uint32_t m_nodeId;
    Graph& m_graph;
};

class Result {
public:
    Result(vk::ResourcePool& pool, uint32_t node_id);

    uint32_t width() const;
    uint32_t height() const;
    void save_image(const char* path);
    std::vector<float> read_pixels();

    // For GUI: direct Vulkan handles
    void* vk_image_view() const;

private:
    vk::ResourcePool& m_pool;
    uint32_t m_nodeId;
};

class Evaluator {
public:
    ~Evaluator();

    void evaluate();

    template<typename T>
    Param<T> param(const std::string& name);

    Result result(const std::string& name);
    Result node_result(const std::string& name);

    const std::vector<ir::Diagnostic>& diagnostics() const;

private:
    friend class Context;
    Evaluator(Context& ctx, const Graph& graph);
    struct Impl;
    std::unique_ptr<Impl> m_impl;
};

} // namespace joon
