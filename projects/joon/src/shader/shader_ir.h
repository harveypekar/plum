#pragma once
#include <string>
#include <vector>
#include <variant>
#include <memory>
#include <optional>
#include <utility>
#include <cstdint>

namespace joon {

struct ShaderLiteral { float value; };
struct ShaderVar { std::string name; };

struct ShaderCall;
struct ShaderAssign;
struct ShaderVecConstruct;
struct ShaderDotAccess;
struct ShaderPrepassSample;

using ShaderExpr = std::variant<
    ShaderLiteral,
    ShaderVar,
    ShaderCall,
    ShaderAssign,
    ShaderVecConstruct,
    ShaderDotAccess,
    ShaderPrepassSample
>;

using ShaderExprPtr = std::unique_ptr<ShaderExpr>;

struct ShaderCall {
    std::string op;
    std::vector<ShaderExprPtr> args;
    std::vector<std::pair<std::string, float>> kwargs;
};

struct ShaderAssign {
    std::string target;
    ShaderExprPtr value;
};

struct ShaderVecConstruct {
    std::vector<ShaderExprPtr> elements;
};

struct ShaderDotAccess {
    ShaderExprPtr object;
    std::string field;
};

struct ShaderPrepassSample {
    uint32_t prepass_index;
};

struct ShaderFnOutput {
    std::string name;
    std::string type_name;
};

struct ShaderFnIR {
    std::vector<std::string> params;
    std::vector<ShaderFnOutput> outputs;
    std::vector<ShaderExprPtr> body;
};

ShaderExprPtr clone_expr(const ShaderExpr& expr);

enum class ShaderOpKind { INLINEABLE, PREPASS_REQUIRED, UNKNOWN };

struct ShaderIR {
    std::optional<ShaderFnIR> vertex;
    std::optional<ShaderFnIR> fragment;
    std::optional<ShaderFnIR> brdf;
};

} // namespace joon
