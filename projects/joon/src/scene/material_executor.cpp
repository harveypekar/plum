#include "scene/material_executor.h"
#include "nodes/node_registry.h"
#include "ir/node.h"
#include "shader/shader_analyzer.h"
#include "shader/hlsl_emitter.h"
#include "vulkan/render_pass.h"

namespace joon {

namespace {

void exec_shader(const Node& n, EvalContext& ctx) {
    if (!ctx.shader_defs) return;
    auto it = ctx.shader_defs->find(n.id);
    if (it == ctx.shader_defs->end()) return;

    ShaderAnalyzer analyzer;
    auto ir = analyzer.analyze(it->second);

    HlslEmitter emitter;

    std::string vert_src;
    if (ir.vertex) {
        vert_src = emitter.emit_vertex(*ir.vertex);
    } else {
        ShaderFnIR default_vert;
        default_vert.params = {"pos", "normal", "uv"};
        vert_src = emitter.emit_vertex(default_vert);
    }

    std::string frag_src;
    if (ir.fragment) {
        frag_src = emitter.emit_fragment(*ir.fragment, 0);
    } else {
        ShaderFnIR default_frag;
        default_frag.params = {"normal", "uv"};
        default_frag.outputs = {{"albedo", "vec4"}};
        ShaderAssign sa;
        sa.target = "albedo";
        ShaderVecConstruct vc;
        for (int i = 0; i < 4; i++)
            vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
        sa.value = std::make_unique<ShaderExpr>(std::move(vc));
        default_frag.body.push_back(std::make_unique<ShaderExpr>(std::move(sa)));
        frag_src = emitter.emit_fragment(default_frag, 0);
    }

    std::string key = "mat_" + std::to_string(n.id);
    uint32_t num_outputs = ir.fragment
        ? static_cast<uint32_t>(ir.fragment->outputs.size()) : 1;

    std::vector<VkFormat> formats(num_outputs, VK_FORMAT_R32G32B32A32_SFLOAT);
    auto rp = create_color_depth_renderpass(ctx.device, formats);

    auto& gp = ctx.pipelines.get_graphics_from_source(
        key, vert_src, frag_src, rp.pass, 0, num_outputs);
    ctx.material_pipelines[n.id] = &gp;

    destroy_renderpass(ctx.device, rp);
}

} // namespace

void register_material_nodes(NodeRegistry& reg) {
    reg.register_node("shader", exec_shader);
}

} // namespace joon
