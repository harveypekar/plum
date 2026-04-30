#include "vulkan/render_pass.h"
#include <stdexcept>

namespace joon {

RenderPass create_color_depth_renderpass(
    Device& dev,
    const std::vector<VkFormat>& color_formats,
    VkFormat depth_format) {

    if (color_formats.empty())
        throw std::runtime_error("create_color_depth_renderpass: no color attachments");

    RenderPass out;
    out.color_formats = color_formats;
    out.depth_format = depth_format;

    std::vector<VkAttachmentDescription> attachments;
    attachments.reserve(color_formats.size() + 1);
    std::vector<VkAttachmentReference> color_refs;
    color_refs.reserve(color_formats.size());

    for (uint32_t i = 0; i < color_formats.size(); ++i) {
        VkAttachmentDescription a{};
        a.format = color_formats[i];
        a.samples = VK_SAMPLE_COUNT_1_BIT;
        a.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
        a.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
        a.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        a.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        a.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        a.finalLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        attachments.push_back(a);

        VkAttachmentReference ref{};
        ref.attachment = i;
        ref.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        color_refs.push_back(ref);
    }

    VkAttachmentDescription depth{};
    depth.format = depth_format;
    depth.samples = VK_SAMPLE_COUNT_1_BIT;
    depth.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    depth.storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    depth.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    depth.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    depth.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    depth.finalLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;
    attachments.push_back(depth);

    VkAttachmentReference depth_ref{};
    depth_ref.attachment = static_cast<uint32_t>(color_formats.size());
    depth_ref.layout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

    VkSubpassDescription subpass{};
    subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    subpass.colorAttachmentCount = static_cast<uint32_t>(color_refs.size());
    subpass.pColorAttachments = color_refs.data();
    subpass.pDepthStencilAttachment = &depth_ref;

    // External -> subpass dependency on color + depth writes.
    VkSubpassDependency dep{};
    dep.srcSubpass = VK_SUBPASS_EXTERNAL;
    dep.dstSubpass = 0;
    dep.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT
                     | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dep.dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT
                     | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dep.srcAccessMask = 0;
    dep.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT
                      | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;

    VkRenderPassCreateInfo info{};
    info.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
    info.attachmentCount = static_cast<uint32_t>(attachments.size());
    info.pAttachments = attachments.data();
    info.subpassCount = 1;
    info.pSubpasses = &subpass;
    info.dependencyCount = 1;
    info.pDependencies = &dep;

    if (vkCreateRenderPass(dev.device, &info, nullptr, &out.pass) != VK_SUCCESS)
        throw std::runtime_error("vkCreateRenderPass failed");
    return out;
}

VkFramebuffer create_framebuffer(
    Device& dev, const RenderPass& rp,
    const std::vector<VkImageView>& color_views,
    VkImageView depth_view, uint32_t w, uint32_t h) {

    std::vector<VkImageView> attachments = color_views;
    attachments.push_back(depth_view);

    VkFramebufferCreateInfo info{};
    info.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
    info.renderPass = rp.pass;
    info.attachmentCount = static_cast<uint32_t>(attachments.size());
    info.pAttachments = attachments.data();
    info.width = w;
    info.height = h;
    info.layers = 1;

    VkFramebuffer fb = VK_NULL_HANDLE;
    if (vkCreateFramebuffer(dev.device, &info, nullptr, &fb) != VK_SUCCESS)
        throw std::runtime_error("vkCreateFramebuffer failed");
    return fb;
}

void destroy_renderpass(Device& dev, RenderPass& rp) {
    if (rp.pass) vkDestroyRenderPass(dev.device, rp.pass, nullptr);
    rp.pass = VK_NULL_HANDLE;
}

} // namespace joon
