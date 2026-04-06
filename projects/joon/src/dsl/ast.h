#pragma once

#include <string>
#include <vector>
#include <memory>
#include <variant>
#include <cstdint>

namespace joon {

struct AstNode;
using AstPtr = std::unique_ptr<AstNode>;

struct KeywordArg {
    std::string name; // without the colon
    AstPtr value;
};

struct DefNode {
    std::string name;
    AstPtr value;
};

struct ParamNode {
    std::string name;
    std::string type_name;
    AstPtr default_value;
    std::vector<KeywordArg> constraints;
};

struct OutputNode {
    AstPtr value;
};

struct CallNode {
    std::string op;
    std::vector<AstPtr> args;
    std::vector<KeywordArg> kwargs;
};

struct NumberNode {
    double value;
};

struct StringNode {
    std::string value;
};

struct SymbolNode {
    std::string name;
};

struct AstNode {
    std::variant<
        DefNode,
        ParamNode,
        OutputNode,
        CallNode,
        NumberNode,
        StringNode,
        SymbolNode
    > data;
    uint32_t line;
    uint32_t col;
};

struct Program {
    std::vector<AstPtr> statements;
};

} // namespace joon
