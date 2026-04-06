#include <joon/context.h>
#include <joon/graph.h>
#include <joon/evaluator.h>
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include "dsl/parser.h"
#include "ir/ir_graph.h"
#include "ir/type_checker.h"
#include <fstream>
#include <sstream>

namespace joon {

struct Context::Impl {
    std::unique_ptr<Device> device;
    std::unique_ptr<ResourcePool> pool;
};

Context::Context() : m_impl(std::make_unique<Impl>()) {}
Context::~Context() = default;

std::unique_ptr<Context> Context::create() {
    auto ctx = std::unique_ptr<Context>(new Context());
    ctx->m_impl->device = Device::create();
    ctx->m_impl->pool = std::make_unique<ResourcePool>(*ctx->m_impl->device);
    return ctx;
}

Device& Context::device() const { return *m_impl->device; }
ResourcePool& Context::pool() const { return *m_impl->pool; }

Graph Context::parse_string(const char* source) {
    Graph g;
    Parser parser(source);
    auto program = parser.parse();
    g.ir() = IRGraph::from_ast(program);
    type_check(g.ir());
    return g;
}

Graph Context::parse_file(const char* path) {
    std::ifstream file(path);
    std::stringstream buf;
    buf << file.rdbuf();
    return parse_string(buf.str().c_str());
}

std::unique_ptr<Evaluator> Context::create_evaluator(const Graph& graph) {
    return std::unique_ptr<Evaluator>(new Evaluator(*this, graph));
}

} // namespace joon
