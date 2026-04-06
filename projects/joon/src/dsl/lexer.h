#pragma once

#include "dsl/token.h"
#include <string>
#include <string_view>
#include <vector>

namespace joon {

class Lexer {
public:
    explicit Lexer(std::string_view source);
    std::vector<Token> tokenize();

private:
    std::string_view m_source;
    size_t m_pos = 0;
    uint32_t m_line = 1;
    uint32_t m_col = 1;

    char peek() const;
    char advance();
    void skip_whitespace_and_comments();
    Token read_symbol_or_keyword();
    Token read_number();
    Token read_string();
};

} // namespace joon
