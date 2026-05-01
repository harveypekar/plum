#pragma once
#include "shader/shader_ir.h"
#include "ir/node.h"
#include "dsl/ast.h"
#include <unordered_set>

namespace joon {

class ShaderAnalyzer {
public:
    ShaderIR analyze(const ShaderDef& sd);
    ShaderOpKind classify(const std::string& op) const;

private:
    ShaderExprPtr convert_expr(const AstNode& ast);
    ShaderFnIR convert_fn(const ShaderFnDef& fndef);

    static const std::unordered_set<std::string> INLINEABLE_OPS;
    static const std::unordered_set<std::string> PREPASS_OPS;
};

} // namespace joon
