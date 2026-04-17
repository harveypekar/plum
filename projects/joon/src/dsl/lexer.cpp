#include "dsl/lexer.h"
#include "dsl/parser.h"

namespace joon {

Lexer::Lexer(std::string_view source) : m_source(source) {}

char Lexer::peek() const {
    if (m_pos >= m_source.size()) return '\0';
    return m_source[m_pos];
}

char Lexer::advance() {
    if (m_pos >= m_source.size()) return '\0';
    char c = m_source[m_pos++];
    if (c == '\n') { m_line++; m_col = 1; }
    else { m_col++; }
    return c;
}

void Lexer::skip_whitespace_and_comments() {
    while (m_pos < m_source.size()) {
        char c = peek();
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
            advance();
        } else if (c == ';') {
            while (m_pos < m_source.size() && peek() != '\n') advance();
        } else {
            break;
        }
    }
}

Token Lexer::read_number() {
    uint32_t start_col = m_col;
    uint32_t start_line = m_line;
    size_t start = m_pos;

    if (peek() == '-') advance();
    while (m_pos < m_source.size() && isdigit(peek())) advance();
    if (m_pos < m_source.size() && peek() == '.') {
        advance();
        while (m_pos < m_source.size() && isdigit(peek())) advance();
    }

    return { TokenType::NUMBER, std::string(m_source.substr(start, m_pos - start)),
             start_line, start_col };
}

Token Lexer::read_string() {
    uint32_t start_col = m_col;
    uint32_t start_line = m_line;
    advance(); // skip opening "
    size_t start = m_pos;
    while (m_pos < m_source.size() && peek() != '"') advance();
    if (m_pos >= m_source.size())
        throw ParseError("Unterminated string literal", start_line, start_col);
    std::string text(m_source.substr(start, m_pos - start));
    advance(); // skip closing "
    return { TokenType::STRING, text, start_line, start_col };
}

Token Lexer::read_symbol_or_keyword() {
    uint32_t start_col = m_col;
    uint32_t start_line = m_line;
    bool is_keyword = (peek() == ':');
    size_t start = m_pos;
    advance();
    while (m_pos < m_source.size()) {
        char c = peek();
        if (c == '(' || c == ')' || c == ' ' || c == '\t' ||
            c == '\n' || c == '\r' || c == ';' || c == '"')
            break;
        advance();
    }
    std::string text(m_source.substr(start, m_pos - start));
    return { is_keyword ? TokenType::KEYWORD : TokenType::SYMBOL,
             text, start_line, start_col };
}

std::vector<Token> Lexer::tokenize() {
    std::vector<Token> tokens;
    while (true) {
        skip_whitespace_and_comments();
        if (m_pos >= m_source.size()) break;

        char c = peek();
        if (c == '(') {
            tokens.push_back({ TokenType::LPAREN, "(", m_line, m_col });
            advance();
        } else if (c == ')') {
            tokens.push_back({ TokenType::RPAREN, ")", m_line, m_col });
            advance();
        } else if (c == '"') {
            tokens.push_back(read_string());
        } else if (isdigit(c) || (c == '-' && m_pos + 1 < m_source.size() && isdigit(m_source[m_pos + 1]))) {
            tokens.push_back(read_number());
        } else {
            tokens.push_back(read_symbol_or_keyword());
        }
    }
    return tokens;
}

} // namespace joon
