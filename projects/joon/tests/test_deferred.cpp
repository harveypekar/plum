#include "catch_amalgamated.hpp"
#include <joon/context.h>
#include "vulkan/resource_pool.h"
using namespace joon;

TEST_CASE("alloc_depth_sampled creates depth with SAMPLED_BIT", "[shader][gpu]") {
    auto ctx = Context::create();
    auto& pool = ctx->pool();
    auto* depth = pool.alloc_depth_sampled(999, 512, 512);
    REQUIRE(depth != nullptr);
    CHECK(depth->view != VK_NULL_HANDLE);
    CHECK(depth->format == VK_FORMAT_D32_SFLOAT);
}
