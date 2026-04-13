#include "nodes/gpu_dispatch.h"

namespace joon {

void gpu_dispatch(EvalContext& ctx,
                  const std::string& shader_name,
                  const std::vector<GpuImage*>& images,
                  uint32_t width, uint32_t height,
                  const void* push_data,
                  uint32_t push_size) {

    uint32_t num_images = static_cast<uint32_t>(images.size());
    auto& pipeline = ctx.pipelines.get(shader_name, num_images, push_size);

    // Allocate descriptor set
    VkDescriptorSetAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    alloc_info.descriptorPool = ctx.desc_pool;
    alloc_info.descriptorSetCount = 1;
    alloc_info.pSetLayouts = &pipeline.desc_layout;

    VkDescriptorSet desc_set;
    vkAllocateDescriptorSets(ctx.device.device, &alloc_info, &desc_set);

    // Update descriptors
    std::vector<VkDescriptorImageInfo> img_infos(num_images);
    std::vector<VkWriteDescriptorSet> writes(num_images);
    for (uint32_t i = 0; i < num_images; i++) {
        img_infos[i] = {};
        img_infos[i].imageView = images[i]->view;
        img_infos[i].imageLayout = VK_IMAGE_LAYOUT_GENERAL;

        writes[i] = {};
        writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[i].dstSet = desc_set;
        writes[i].dstBinding = i;
        writes[i].descriptorCount = 1;
        writes[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        writes[i].pImageInfo = &img_infos[i];
    }
    vkUpdateDescriptorSets(ctx.device.device, num_images, writes.data(), 0, nullptr);

    auto cmd = ctx.device.begin_single_command();

    // Transition output image (last in the list) to GENERAL layout
    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.image = images.back()->image;
    barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
    barrier.dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                         VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &barrier);

    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline.pipeline);
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE,
                            pipeline.layout, 0, 1, &desc_set, 0, nullptr);

    if (push_data && push_size > 0) {
        vkCmdPushConstants(cmd, pipeline.layout, VK_SHADER_STAGE_COMPUTE_BIT,
                          0, push_size, push_data);
    }

    vkCmdDispatch(cmd, (width + 15) / 16, (height + 15) / 16, 1);

    ctx.device.end_single_command(cmd);
}

} // namespace joon
