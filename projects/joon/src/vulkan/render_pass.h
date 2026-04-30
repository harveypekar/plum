#pragma once

#include "vulkan/device.h"
#include <vector>

namespace joon {

struct RenderPass {
    VkRenderPass pass = VK_NULL_HANDLE;
    std::vector<VkFormat> color_formats;
    VkFormat depth_format = VK_FORMAT_D32_SFLOAT;
};

// Create a render pass with N color attachments + one depth attachment.
// Color attachments load=CLEAR, store=STORE, finalLayout=COLOR_ATTACHMENT_OPTIMAL
// (the geometry-pass executor manually transitions them to GENERAL afterwards
//  so downstream compute / viewport binding can sample).
// Depth attachment load=CLEAR, store=DONT_CARE, finalLayout=DEPTH_STENCIL_ATTACHMENT_OPTIMAL.
RenderPass create_color_depth_renderpass(
    Device& dev,
    const std::vector<VkFormat>& color_formats,
    VkFormat depth_format = VK_FORMAT_D32_SFLOAT);

VkFramebuffer create_framebuffer(
    Device& dev, const RenderPass& rp,
    const std::vector<VkImageView>& color_views,
    VkImageView depth_view, uint32_t w, uint32_t h);

void destroy_renderpass(Device& dev, RenderPass& rp);

} // namespace joon
