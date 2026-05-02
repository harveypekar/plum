#include "shader/shader_analyzer.h"

namespace joon {

const std::unordered_set<std::string> ShaderAnalyzer::INLINEABLE_OPS = {
    "+", "-", "*", "/",
    "pow", "sqrt", "abs", "floor", "ceil", "fract", "mod", "clamp", "min", "max",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "dot", "cross", "normalize", "length", "reflect", "refract",
    "mix", "step", "smoothstep",
    "noise", "fbm", "voronoi",
    "sample", "encode", "decode",
    "set"
};

const std::unordered_set<std::string> ShaderAnalyzer::PREPASS_OPS = {
    "blur", "levels", "blend", "threshold", "invert"
};

ShaderOpKind ShaderAnalyzer::classify(const std::string& op) const {
    if (INLINEABLE_OPS.count(op)) return ShaderOpKind::INLINEABLE;
    if (PREPASS_OPS.count(op)) return ShaderOpKind::PREPASS_REQUIRED;
    return ShaderOpKind::UNKNOWN;
}

ShaderExprPtr ShaderAnalyzer::convert_expr(const AstNode& ast) {
    if (auto* num = std::get_if<NumberNode>(&ast.data)) {
        return std::make_unique<ShaderExpr>(ShaderLiteral{static_cast<float>(num->value)});
    }
    if (auto* sym = std::get_if<SymbolNode>(&ast.data)) {
        return std::make_unique<ShaderExpr>(ShaderVar{sym->name});
    }
    if (auto* vec = std::get_if<VectorNode>(&ast.data)) {
        ShaderVecConstruct vc;
        for (auto& e : vec->elements)
            vc.elements.push_back(convert_expr(*e));
        return std::make_unique<ShaderExpr>(std::move(vc));
    }
    if (auto* dot = std::get_if<DotAccessNode>(&ast.data)) {
        ShaderDotAccess da;
        da.object = convert_expr(*dot->object);
        da.field = dot->field;
        return std::make_unique<ShaderExpr>(std::move(da));
    }
    if (auto* call = std::get_if<CallNode>(&ast.data)) {
        if (call->op == "set") {
            ShaderAssign sa;
            if (!call->args.empty()) {
                if (auto* target_sym = std::get_if<SymbolNode>(&call->args[0]->data))
                    sa.target = target_sym->name;
                else if (auto* target_dot = std::get_if<DotAccessNode>(&call->args[0]->data)) {
                    // pos.y → "pos.y" as a dot-separated target string
                    auto* obj_sym = std::get_if<SymbolNode>(&target_dot->object->data);
                    if (obj_sym)
                        sa.target = obj_sym->name + "." + target_dot->field;
                    else
                        sa.target = target_dot->field;
                }
            }
            if (call->args.size() > 1)
                sa.value = convert_expr(*call->args[1]);
            return std::make_unique<ShaderExpr>(std::move(sa));
        }

        ShaderCall sc;
        sc.op = call->op;
        for (auto& a : call->args)
            sc.args.push_back(convert_expr(*a));
        for (auto& kw : call->kwargs) {
            if (auto* knum = std::get_if<NumberNode>(&kw.value->data))
                sc.kwargs.push_back({kw.name, static_cast<float>(knum->value)});
        }
        return std::make_unique<ShaderExpr>(std::move(sc));
    }
    return std::make_unique<ShaderExpr>(ShaderLiteral{0.0f});
}

ShaderFnIR ShaderAnalyzer::convert_fn(const ShaderFnDef& fndef) {
    ShaderFnIR fn;
    fn.params = fndef.params;
    for (auto& o : fndef.outputs)
        fn.outputs.push_back({o.name, o.type_name});
    for (auto& stmt : fndef.body)
        fn.body.push_back(convert_expr(*stmt));
    return fn;
}

ShaderIR ShaderAnalyzer::analyze(const ShaderDef& sd) {
    ShaderIR ir;
    if (sd.vertex) ir.vertex = convert_fn(*sd.vertex);
    if (sd.fragment) ir.fragment = convert_fn(*sd.fragment);
    if (sd.brdf) ir.brdf = convert_fn(*sd.brdf);
    return ir;
}

} // namespace joon
