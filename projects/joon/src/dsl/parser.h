#pragma once

#include "dsl/ast.h"
#include "dsl/token.h"
#include <string>
#include <string_view>
#include <vector>
#include <stdexcept>

namespace joon::dsl {

struct ParseError : std::runtime_error {
    uint32_t line, col;
    ParseError(const std::string& msg, uint32_t line, uint32_t col)
        : std::runtime_error(msg), line(line), col(col) {}
};

class Parser {
public:
    explicit Parser(std::string_view source);
    Program parse();

private:
    std::vector<Token> m_tokens;
    size_t m_pos = 0;

    const Token& peek() const;
    const Token& advance();
    bool at_end() const;
    void expect(TokenType type, const std::string& context);

    AstPtr parse_form();
    AstPtr parse_def();
    AstPtr parse_param();
    AstPtr parse_output();
    AstPtr parse_call(const Token& op);
    AstPtr parse_expr();
};

} // namespace joon::dsl
