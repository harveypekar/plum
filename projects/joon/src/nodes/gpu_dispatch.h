#pragma once

#include "nodes/node_registry.h"
#include <vector>

namespace joon {

// Dispatch a compute shader with the given images bound as storage images.
// images[0..n-1] are bound to binding 0..n-1.
// push_data/push_size are optional push constants.
// The last image in the list is assumed to be the output and gets a layout transition.
void gpu_dispatch(EvalContext& ctx,
                  const std::string& shader_name,
                  const std::vector<GpuImage*>& images,
                  uint32_t width, uint32_t height,
                  const void* push_data = nullptr,
                  uint32_t push_size = 0);

} // namespace joon
