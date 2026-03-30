#include "app.h"
#include <imgui.h>

void App::init() {
    ctx = joon::Context::create();

    dsl_source = R"(; Joon - edit this code
(def base (noise :scale 4.0 :octaves 3))
(param contrast float 1.2 :min 0.0 :max 3.0)
(def result (levels base :contrast contrast))
(output result)
)";

    VkSamplerCreateInfo sampler_info{};
    sampler_info.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    sampler_info.magFilter = VK_FILTER_LINEAR;
    sampler_info.minFilter = VK_FILTER_LINEAR;
    sampler_info.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    sampler_info.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    vkCreateSampler(ctx->device().device, &sampler_info, nullptr, &sampler);

    reparse();
}

void App::reparse() {
    try {
        graph = ctx->parse_string(dsl_source.c_str());
        if (!graph.has_errors()) {
            eval = ctx->create_evaluator(graph);
            eval->evaluate();
        } else {
            eval.reset();
        }
    } catch (const std::exception&) {
        eval.reset();
    }
    source_dirty = false;
}

void App::update() {
    if (source_dirty) {
        reparse();
    }
}
