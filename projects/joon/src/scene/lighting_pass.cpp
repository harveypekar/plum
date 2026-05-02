#include "scene/lighting_pass.h"
#include "vulkan/buffer.h"
#include "vulkan/render_pass.h"

namespace joon {

void dispatch_lighting_pass(const LightingPassConfig& cfg) {
    auto* lit_output = cfg.pool.alloc_render_target(
        cfg.output_node_id, cfg.width, cfg.height, VK_FORMAT_R32G32B32A32_SFLOAT);

    RenderPass rp = create_color_renderpass(cfg.device, lit_output->format);
    auto& gp = cfg.pipelines.get_fullscreen("deferred_default", rp.pass);

    VkFramebufferCreateInfo fb_info{};
    fb_info.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
    fb_info.renderPass = rp.pass;
    fb_info.attachmentCount = 1;
    fb_info.pAttachments = &lit_output->view;
    fb_info.width = cfg.width;
    fb_info.height = cfg.height;
    fb_info.layers = 1;
    VkFramebuffer fb = VK_NULL_HANDLE;
    vkCreateFramebuffer(cfg.device.device, &fb_info, nullptr, &fb);

    LightUBO lubo{};
    lubo.light_count = static_cast<int>(
        cfg.scene.lights.size() < 16 ? cfg.scene.lights.size() : 16);
    for (int li = 0; li < lubo.light_count; li++) {
        const auto& l = cfg.scene.lights[li];
        if (l.type == LightType::Directional) {
            lubo.lights[li].position_type[0] = l.direction.x;
            lubo.lights[li].position_type[1] = l.direction.y;
            lubo.lights[li].position_type[2] = l.direction.z;
            lubo.lights[li].position_type[3] = 0.0f;
        } else {
            lubo.lights[li].position_type[0] = l.position.x;
            lubo.lights[li].position_type[1] = l.position.y;
            lubo.lights[li].position_type[2] = l.position.z;
            lubo.lights[li].position_type[3] = 1.0f;
        }
        lubo.lights[li].color_intensity[0] = l.color.x * l.intensity;
        lubo.lights[li].color_intensity[1] = l.color.y * l.intensity;
        lubo.lights[li].color_intensity[2] = l.color.z * l.intensity;
        lubo.lights[li].color_intensity[3] = 0.0f;
    }

    auto ub = create_uniform_buffer(cfg.device, sizeof(LightUBO));
    update_uniform_buffer(cfg.device, ub, &lubo, sizeof(LightUBO));

    VkDescriptorSetAllocateInfo dai{};
    dai.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    dai.descriptorPool = cfg.desc_pool;
    dai.descriptorSetCount = 1;
    dai.pSetLayouts = &gp.desc_layout;
    VkDescriptorSet ds = VK_NULL_HANDLE;
    vkAllocateDescriptorSets(cfg.device.device, &dai, &ds);

    VkDescriptorImageInfo img_info{};
    img_info.imageView = cfg.albedo_target->view;
    img_info.imageLayout = VK_IMAGE_LAYOUT_GENERAL;

    VkSamplerCreateInfo samp_info{};
    samp_info.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    samp_info.magFilter = VK_FILTER_LINEAR;
    samp_info.minFilter = VK_FILTER_LINEAR;
    samp_info.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samp_info.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samp_info.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    VkSampler sampler = VK_NULL_HANDLE;
    vkCreateSampler(cfg.device.device, &samp_info, nullptr, &sampler);

    VkDescriptorImageInfo samp_desc{};
    samp_desc.sampler = sampler;

    VkDescriptorBufferInfo buf_info{};
    buf_info.buffer = ub.buffer;
    buf_info.offset = 0;
    buf_info.range = sizeof(LightUBO);

    VkWriteDescriptorSet writes[3]{};
    writes[0].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[0].dstSet = ds;
    writes[0].dstBinding = 0;
    writes[0].descriptorCount = 1;
    writes[0].descriptorType = VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE;
    writes[0].pImageInfo = &img_info;

    writes[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[1].dstSet = ds;
    writes[1].dstBinding = 1;
    writes[1].descriptorCount = 1;
    writes[1].descriptorType = VK_DESCRIPTOR_TYPE_SAMPLER;
    writes[1].pImageInfo = &samp_desc;

    writes[2].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[2].dstSet = ds;
    writes[2].dstBinding = 2;
    writes[2].descriptorCount = 1;
    writes[2].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    writes[2].pBufferInfo = &buf_info;

    vkUpdateDescriptorSets(cfg.device.device, 3, writes, 0, nullptr);

    VkCommandBuffer cmd = cfg.device.begin_single_command();

    VkClearValue clear{};
    clear.color = {{ 0.0f, 0.0f, 0.0f, 1.0f }};

    VkRenderPassBeginInfo rpi{};
    rpi.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
    rpi.renderPass = rp.pass;
    rpi.framebuffer = fb;
    rpi.renderArea.extent = { cfg.width, cfg.height };
    rpi.clearValueCount = 1;
    rpi.pClearValues = &clear;

    vkCmdBeginRenderPass(cmd, &rpi, VK_SUBPASS_CONTENTS_INLINE);

    VkViewport vp{};
    vp.width = static_cast<float>(cfg.width);
    vp.height = static_cast<float>(cfg.height);
    vp.minDepth = 0; vp.maxDepth = 1;
    vkCmdSetViewport(cmd, 0, 1, &vp);

    VkRect2D scissor{};
    scissor.extent = { cfg.width, cfg.height };
    vkCmdSetScissor(cmd, 0, 1, &scissor);

    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, gp.pipeline);
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, gp.layout,
                             0, 1, &ds, 0, nullptr);
    vkCmdDraw(cmd, 3, 1, 0, 0);

    vkCmdEndRenderPass(cmd);

    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.image = lit_output->image;
    barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
    barrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_TRANSFER_READ_BIT;
    vkCmdPipelineBarrier(cmd,
                          VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                          VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT | VK_PIPELINE_STAGE_TRANSFER_BIT,
                          0, 0, nullptr, 0, nullptr, 1, &barrier);

    cfg.device.end_single_command(cmd);

    vkDestroySampler(cfg.device.device, sampler, nullptr);
    destroy_buffer(cfg.device, ub);
    vkDestroyFramebuffer(cfg.device.device, fb, nullptr);
    destroy_renderpass(cfg.device, rp);
}

} // namespace joon
