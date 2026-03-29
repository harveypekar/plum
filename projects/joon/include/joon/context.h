#pragma once

#include <memory>

namespace joon {

namespace vk { struct Device; class ResourcePool; }

class Graph;
class Evaluator;

class Context {
public:
    static std::unique_ptr<Context> create();
    ~Context();

    Graph parse_file(const char* path);
    Graph parse_string(const char* source);
    std::unique_ptr<Evaluator> create_evaluator(const Graph& graph);

    vk::Device& device() const;
    vk::ResourcePool& pool() const;

private:
    Context();
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace joon
