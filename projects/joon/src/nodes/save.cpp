#include "nodes/node_registry.h"

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb/stb_image_write.h>

#include <algorithm>

namespace joon::nodes {

void register_save(NodeRegistry& reg) {
    reg.register_node("save", [](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.empty()) return;
        auto* input = ctx.pool.get_image(node.inputs[0]);
        if (!input) return;

        std::string path = node.string_arg;
        if (path.empty()) return;

        size_t pixel_count = input->width * input->height;
        std::vector<float> float_data(pixel_count * 4);
        ctx.pool.download(input, float_data.data(), float_data.size() * sizeof(float));

        std::vector<uint8_t> byte_data(pixel_count * 4);
        for (size_t i = 0; i < float_data.size(); i++) {
            byte_data[i] = static_cast<uint8_t>(
                std::clamp(float_data[i] * 255.0f, 0.0f, 255.0f));
        }

        stbi_write_png(path.c_str(), input->width, input->height, 4,
                       byte_data.data(), input->width * 4);
    });
}

} // namespace joon::nodes
