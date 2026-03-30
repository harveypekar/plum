#pragma once

#include <string>
#include <cstdint>

namespace joon::dsl {

enum class TokenType {
    LParen,     // (
    RParen,     // )
    Symbol,     // def, noise, +, -, *, /
    Keyword,    // :scale, :min
    Number,     // 1.0, 42
    String,     // "path/to/file"
    Eof
};

struct Token {
    TokenType type;
    std::string text;
    uint32_t line;
    uint32_t col;
};

} // namespace joon::dsl
