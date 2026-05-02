#include "shader/shader_ir.h"

namespace joon {

ShaderExprPtr clone_expr(const ShaderExpr& expr) {
    if (auto* lit = std::get_if<ShaderLiteral>(&expr))
        return std::make_unique<ShaderExpr>(*lit);
    if (auto* var = std::get_if<ShaderVar>(&expr))
        return std::make_unique<ShaderExpr>(*var);
    if (auto* ps = std::get_if<ShaderPrepassSample>(&expr))
        return std::make_unique<ShaderExpr>(*ps);

    if (auto* call = std::get_if<ShaderCall>(&expr)) {
        ShaderCall c;
        c.op = call->op;
        c.kwargs = call->kwargs;
        for (auto& a : call->args)
            c.args.push_back(clone_expr(*a));
        return std::make_unique<ShaderExpr>(std::move(c));
    }
    if (auto* assign = std::get_if<ShaderAssign>(&expr)) {
        ShaderAssign a;
        a.target = assign->target;
        if (assign->value)
            a.value = clone_expr(*assign->value);
        return std::make_unique<ShaderExpr>(std::move(a));
    }
    if (auto* vc = std::get_if<ShaderVecConstruct>(&expr)) {
        ShaderVecConstruct v;
        for (auto& e : vc->elements)
            v.elements.push_back(clone_expr(*e));
        return std::make_unique<ShaderExpr>(std::move(v));
    }
    if (auto* da = std::get_if<ShaderDotAccess>(&expr)) {
        ShaderDotAccess d;
        d.object = clone_expr(*da->object);
        d.field = da->field;
        return std::make_unique<ShaderExpr>(std::move(d));
    }

    return std::make_unique<ShaderExpr>(ShaderLiteral{0.0f});
}

} // namespace joon
