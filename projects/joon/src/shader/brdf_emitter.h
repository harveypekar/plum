#pragma once
#include "shader/shader_ir.h"
#include <string>

namespace joon {

class BrdfEmitter {
public:
    std::string emit_lighting_shader(const ShaderFnIR& brdf);
};

} // namespace joon
