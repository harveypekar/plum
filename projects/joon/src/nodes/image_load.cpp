#include "nodes/node_registry.h"

#define STB_IMAGE_IMPLEMENTATION
#include <stb/stb_image.h>

namespace joon::nodes {

void register_image_load(NodeRegistry& reg) {
    reg.register_node("image", [](const ir::Node& node, EvalContext& ctx) {
        // Get path from the string constant input node
        std::string path;
        if (!node.inputs.empty()) {
            // The input is a string_constant node — look it up in the pool's graph
            // For now, use string_arg if available on the node itself
        }
        // Path comes from the first positional arg which was a StringNode,
        // resolved as a string_constant node. The IR stores string_arg on *that* node,
        // but during resolve_expr, string args in calls get stored on the call node.
        // Check both.
        if (!node.string_arg.empty()) {
            path = node.string_arg;
        }

        if (path.empty()) {
            auto* img = ctx.pool.alloc_image(node.id, ctx.default_width, ctx.default_height);
            std::vector<float> black(ctx.default_width * ctx.default_height * 4, 0.0f);
            ctx.pool.upload(img, black.data(), black.size() * sizeof(float));
            return;
        }

        int w, h, channels;
        float* data = stbi_loadf(path.c_str(), &w, &h, &channels, 4);
        if (!data) {
            auto* img = ctx.pool.alloc_image(node.id, ctx.default_width, ctx.default_height);
            std::vector<float> black(ctx.default_width * ctx.default_height * 4, 0.0f);
            ctx.pool.upload(img, black.data(), black.size() * sizeof(float));
            return;
        }

        auto* img = ctx.pool.alloc_image(node.id, w, h);
        ctx.pool.upload(img, data, w * h * 4 * sizeof(float));
        stbi_image_free(data);
    });
}

} // namespace joon::nodes
