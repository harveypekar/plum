#pragma once
#include "shader/shader_ir.h"
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace joon {

class HlslEmitter {
public:
    std::string emit_expr(const ShaderExpr& expr);
    std::string emit_fragment(const ShaderFnIR& fn, uint32_t prepass_count);
    std::string emit_vertex(const ShaderFnIR& fn);

private:
    std::string emit_call(const ShaderCall& call);
    std::string emit_assign(const ShaderAssign& assign, bool is_fragment);
    std::string emit_vec(const ShaderVecConstruct& vc);
    std::string emit_dot(const ShaderDotAccess& da);

    static const std::unordered_map<std::string, std::string> OP_RENAMES;
    static const std::unordered_set<std::string> BINARY_OPS;
};

} // namespace joon
