#include "dsl/lexer.h"

namespace joon::dsl {

Lexer::Lexer(std::string_view source) : source_(source) {}

char Lexer::peek() const {
    if (pos_ >= source_.size()) return '\0';
    return source_[pos_];
}

char Lexer::advance() {
    char c = source_[pos_++];
    if (c == '\n') { line_++; col_ = 1; }
    else { col_++; }
    return c;
}

void Lexer::skip_whitespace_and_comments() {
    while (pos_ < source_.size()) {
        char c = peek();
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
            advance();
        } else if (c == ';') {
            while (pos_ < source_.size() && peek() != '\n') advance();
        } else {
            break;
        }
    }
}

Token Lexer::read_number() {
    uint32_t start_col = col_;
    uint32_t start_line = line_;
    size_t start = pos_;

    if (peek() == '-') advance();
    while (pos_ < source_.size() && isdigit(peek())) advance();
    if (pos_ < source_.size() && peek() == '.') {
        advance();
        while (pos_ < source_.size() && isdigit(peek())) advance();
    }

    return { TokenType::Number, std::string(source_.substr(start, pos_ - start)),
             start_line, start_col };
}

Token Lexer::read_string() {
    uint32_t start_col = col_;
    uint32_t start_line = line_;
    advance(); // skip opening "
    size_t start = pos_;
    while (pos_ < source_.size() && peek() != '"') advance();
    std::string text(source_.substr(start, pos_ - start));
    if (pos_ < source_.size()) advance(); // skip closing "
    return { TokenType::String, text, start_line, start_col };
}

Token Lexer::read_symbol_or_keyword() {
    uint32_t start_col = col_;
    uint32_t start_line = line_;
    bool is_keyword = (peek() == ':');
    size_t start = pos_;
    advance();
    while (pos_ < source_.size()) {
        char c = peek();
        if (c == '(' || c == ')' || c == ' ' || c == '\t' ||
            c == '\n' || c == '\r' || c == ';' || c == '"')
            break;
        advance();
    }
    std::string text(source_.substr(start, pos_ - start));
    return { is_keyword ? TokenType::Keyword : TokenType::Symbol,
             text, start_line, start_col };
}

std::vector<Token> Lexer::tokenize() {
    std::vector<Token> tokens;
    while (true) {
        skip_whitespace_and_comments();
        if (pos_ >= source_.size()) break;

        char c = peek();
        if (c == '(') {
            tokens.push_back({ TokenType::LParen, "(", line_, col_ });
            advance();
        } else if (c == ')') {
            tokens.push_back({ TokenType::RParen, ")", line_, col_ });
            advance();
        } else if (c == '"') {
            tokens.push_back(read_string());
        } else if (isdigit(c) || (c == '-' && pos_ + 1 < source_.size() && isdigit(source_[pos_ + 1]))) {
            tokens.push_back(read_number());
        } else {
            tokens.push_back(read_symbol_or_keyword());
        }
    }
    return tokens;
}

} // namespace joon::dsl
