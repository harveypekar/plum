#pragma once

#include <string>
#include <cstdint>

namespace joon::dsl {

enum class TokenType {
    LPAREN,      // (
    RPAREN,      // )
    SYMBOL,      // def, noise, +, -, *, /
    KEYWORD,     // :scale, :min
    NUMBER,      // 1.0, 42
    STRING,      // "path/to/file"
    EOF_TOKEN
};

struct Token {
    TokenType type;
    std::string text;
    uint32_t line;
    uint32_t col;
};

} // namespace joon::dsl
