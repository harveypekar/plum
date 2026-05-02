#include "shader/prepass_extractor.h"

namespace joon {

PrepassExtractor::PrepassExtractor(const ShaderAnalyzer& analyzer)
    : m_analyzer(analyzer) {}

ShaderExprPtr PrepassExtractor::walk(ShaderExprPtr expr) {
    if (auto* call = std::get_if<ShaderCall>(expr.get())) {
        if (m_analyzer.classify(call->op) == ShaderOpKind::PREPASS_REQUIRED) {
            uint32_t idx = static_cast<uint32_t>(m_extracted.size());
            std::string op = call->op;
            m_extracted.push_back({op, std::move(expr)});
            return std::make_unique<ShaderExpr>(ShaderPrepassSample{idx});
        }
        for (auto& arg : call->args)
            arg = walk(std::move(arg));
    }
    if (auto* assign = std::get_if<ShaderAssign>(expr.get())) {
        if (assign->value)
            assign->value = walk(std::move(assign->value));
    }
    return expr;
}

ExtractionResult PrepassExtractor::extract(const ShaderFnIR& fn) {
    ExtractionResult result;
    m_extracted.clear();

    for (auto& stmt : fn.body) {
        result.modified_body.push_back(walk(clone_expr(*stmt)));
    }

    result.prepasses = std::move(m_extracted);
    return result;
}

} // namespace joon
