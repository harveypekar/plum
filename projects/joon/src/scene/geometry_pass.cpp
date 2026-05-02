#include "scene/geometry_pass.h"
#include "scene/lighting_pass.h"
#include "nodes/node_registry.h"
#include "ir/node.h"
#include "vulkan/buffer.h"
#include "vulkan/render_pass.h"
#include <joon/scene.h>
#include <joon/math.h>
#include <vector>
#include <cstring>

namespace joon {

namespace {

// Vertex shader UBO — must match scene_basic.vert.hlsl layout.
struct UBO {
    mat4 mvp;
    mat4 model;
};

// Fragment shader push constant — must match scene_basic.frag.hlsl layout.
struct PushLight {
    float light_dir[3];
    float pad0;
    float light_color[3];
    float pad1;
};

void exec_pass(const Node& n, EvalContext& ctx) {
    bool has_materials = !ctx.material_pipelines.empty();
    // When materials are active, G-buffer goes to an intermediate slot and
    // the lighting pass writes the final lit output to n.id.
    uint32_t color_id = has_materials ? (n.id ^ 0x40000000u) : n.id;
    uint32_t depth_id = n.id ^ 0x80000000u;

    auto* albedo = ctx.pool.alloc_render_target(color_id, ctx.default_width, ctx.default_height);
    auto* depth  = ctx.pool.alloc_depth        (depth_id, ctx.default_width, ctx.default_height);

    // Render pass + framebuffer — created per-evaluate (caching is a follow-up).
    RenderPass rp = create_color_depth_renderpass(ctx.device, { albedo->format });
    VkFramebuffer fb = create_framebuffer(ctx.device, rp, { albedo->view }, depth->view,
                                           ctx.default_width, ctx.default_height);

    const auto& gp = ctx.pipelines.get_graphics("scene_basic", rp.pass, sizeof(PushLight));

    // Camera matrices — fall back to defaults if no camera was set.
    const auto& cam = ctx.scene.camera;
    mat4 view = look_at(cam.position, cam.target, cam.up);
    mat4 proj = perspective_vk(cam.fov_deg,
                                static_cast<float>(ctx.default_width)
                                    / static_cast<float>(ctx.default_height),
                                cam.near_z, cam.far_z);

    // Light push constant — first directional light or default.
    PushLight pc{};
    if (!ctx.scene.lights.empty()) {
        const auto& l = ctx.scene.lights[0];
        pc.light_dir[0]   = l.direction.x;
        pc.light_dir[1]   = l.direction.y;
        pc.light_dir[2]   = l.direction.z;
        pc.light_color[0] = l.color.x * l.intensity;
        pc.light_color[1] = l.color.y * l.intensity;
        pc.light_color[2] = l.color.z * l.intensity;
    } else {
        pc.light_dir[0] = 0; pc.light_dir[1] = -1; pc.light_dir[2] = 0;
        pc.light_color[0] = pc.light_color[1] = pc.light_color[2] = 1.0f;
    }

    VkCommandBuffer cmd = ctx.device.begin_single_command();

    VkClearValue clears[2];
    clears[0].color = {{ 0.0f, 0.0f, 0.0f, 1.0f }};
    clears[1].depthStencil = { 1.0f, 0 };

    VkRenderPassBeginInfo rpi{};
    rpi.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
    rpi.renderPass = rp.pass;
    rpi.framebuffer = fb;
    rpi.renderArea.extent = { ctx.default_width, ctx.default_height };
    rpi.clearValueCount = 2;
    rpi.pClearValues = clears;

    vkCmdBeginRenderPass(cmd, &rpi, VK_SUBPASS_CONTENTS_INLINE);

    VkViewport vp{};
    vp.x = 0; vp.y = 0;
    vp.width  = static_cast<float>(ctx.default_width);
    vp.height = static_cast<float>(ctx.default_height);
    vp.minDepth = 0; vp.maxDepth = 1;
    vkCmdSetViewport(cmd, 0, 1, &vp);

    VkRect2D scissor{};
    scissor.offset = { 0, 0 };
    scissor.extent = { ctx.default_width, ctx.default_height };
    vkCmdSetScissor(cmd, 0, 1, &scissor);

    // Per-frame buffers — freed after submit.
    std::vector<GpuBuffer> per_frame_bufs;
    per_frame_bufs.reserve(ctx.scene.objects.size() * 3);

    VkPipeline bound_pipeline = VK_NULL_HANDLE;

    for (const auto& obj : ctx.scene.objects) {
        if (obj.mesh.vertices.empty() || obj.mesh.indices.empty()) continue;

        // Select pipeline: per-material if available, else default.
        const GraphicsPipeline* cur_gp = &gp;
        if (obj.material_node_id != UINT32_MAX) {
            auto mat_it = ctx.material_pipelines.find(obj.material_node_id);
            if (mat_it != ctx.material_pipelines.end())
                cur_gp = mat_it->second;
        }

        if (cur_gp->pipeline != bound_pipeline) {
            vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, cur_gp->pipeline);
            bound_pipeline = cur_gp->pipeline;
            if (cur_gp == &gp)
                vkCmdPushConstants(cmd, gp.layout, VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(pc), &pc);
        }

        auto vb = create_vertex_buffer(ctx.device,
                                        obj.mesh.vertices.data(),
                                        obj.mesh.vertices.size() * sizeof(Vertex));
        auto ib = create_index_buffer(ctx.device,
                                       obj.mesh.indices.data(),
                                       obj.mesh.indices.size() * sizeof(uint32_t));

        UBO u;
        u.model = compose_trs(obj.position, obj.rotation, obj.scale);
        u.mvp = mul(proj, mul(view, u.model));
        auto ub = create_uniform_buffer(ctx.device, sizeof(UBO));
        update_uniform_buffer(ctx.device, ub, &u, sizeof(UBO));

        VkDescriptorSetAllocateInfo dai{};
        dai.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        dai.descriptorPool = ctx.desc_pool;
        dai.descriptorSetCount = 1;
        dai.pSetLayouts = &cur_gp->desc_layout;
        VkDescriptorSet ds = VK_NULL_HANDLE;
        vkAllocateDescriptorSets(ctx.device.device, &dai, &ds);

        VkDescriptorBufferInfo dbi{};
        dbi.buffer = ub.buffer;
        dbi.offset = 0;
        dbi.range = sizeof(UBO);

        VkWriteDescriptorSet wds{};
        wds.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        wds.dstSet = ds;
        wds.dstBinding = 0;
        wds.descriptorCount = 1;
        wds.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
        wds.pBufferInfo = &dbi;
        vkUpdateDescriptorSets(ctx.device.device, 1, &wds, 0, nullptr);

        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, cur_gp->layout,
                                 0, 1, &ds, 0, nullptr);

        VkBuffer vb_handle = vb.buffer;
        VkDeviceSize offset = 0;
        vkCmdBindVertexBuffers(cmd, 0, 1, &vb_handle, &offset);
        vkCmdBindIndexBuffer(cmd, ib.buffer, 0, VK_INDEX_TYPE_UINT32);
        vkCmdDrawIndexed(cmd, static_cast<uint32_t>(obj.mesh.indices.size()), 1, 0, 0, 0);

        per_frame_bufs.push_back(vb);
        per_frame_bufs.push_back(ib);
        per_frame_bufs.push_back(ub);
    }

    vkCmdEndRenderPass(cmd);

    // Transition color attachment from COLOR_ATTACHMENT_OPTIMAL → GENERAL so
    // downstream compute and the GUI viewport can read it.
    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.image = albedo->image;
    barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
    barrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT
                          | VK_ACCESS_TRANSFER_READ_BIT;
    vkCmdPipelineBarrier(cmd,
                          VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                          VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT
                              | VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT
                              | VK_PIPELINE_STAGE_TRANSFER_BIT,
                          0, 0, nullptr, 0, nullptr, 1, &barrier);

    ctx.device.end_single_command(cmd);

    for (auto& b : per_frame_bufs) destroy_buffer(ctx.device, b);
    vkDestroyFramebuffer(ctx.device.device, fb, nullptr);
    destroy_renderpass(ctx.device, rp);

    if (!ctx.material_pipelines.empty()) {
        const ShaderFnIR* brdf = nullptr;
        for (auto& [mat_id, fn_ir] : ctx.material_brdfs) {
            brdf = &fn_ir;
            break;
        }
        LightingPassConfig lcfg{
            ctx.device, ctx.pipelines, ctx.pool, ctx.desc_pool,
            ctx.scene, ctx.default_width, ctx.default_height,
            albedo, n.id, brdf
        };
        dispatch_lighting_pass(lcfg);
    }
}

} // namespace

void register_geometry_pass(NodeRegistry& reg) {
    reg.register_node("pass", exec_pass);
}

} // namespace joon
