#pragma once
#include "shader/shader_ir.h"
#include "shader/shader_analyzer.h"
#include <vector>

namespace joon {

struct ExtractedPrepass {
    std::string root_op;
    ShaderExprPtr compute_tree;
};

struct ExtractionResult {
    std::vector<ExtractedPrepass> prepasses;
    std::vector<ShaderExprPtr> modified_body;
};

class PrepassExtractor {
public:
    explicit PrepassExtractor(const ShaderAnalyzer& analyzer);
    ExtractionResult extract(const ShaderFnIR& fn);

private:
    const ShaderAnalyzer& m_analyzer;
    std::vector<ExtractedPrepass> m_extracted;

    ShaderExprPtr walk(ShaderExprPtr expr);
};

} // namespace joon
