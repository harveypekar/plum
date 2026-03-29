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
    std::unique_ptr<vk::Device> device;
    std::unique_ptr<vk::ResourcePool> pool;
};

Context::Context() : impl_(std::make_unique<Impl>()) {}
Context::~Context() = default;

std::unique_ptr<Context> Context::create() {
    auto ctx = std::unique_ptr<Context>(new Context());
    ctx->impl_->device = vk::Device::create();
    ctx->impl_->pool = std::make_unique<vk::ResourcePool>(*ctx->impl_->device);
    return ctx;
}

vk::Device& Context::device() const { return *impl_->device; }
vk::ResourcePool& Context::pool() const { return *impl_->pool; }

Graph Context::parse_string(const char* source) {
    Graph g;
    dsl::Parser parser(source);
    auto program = parser.parse();
    g.ir() = ir::IRGraph::from_ast(program);
    ir::type_check(g.ir());
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
