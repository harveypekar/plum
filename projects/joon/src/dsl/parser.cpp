#include "dsl/parser.h"
#include "dsl/lexer.h"

namespace joon {

Parser::Parser(std::string_view source) {
    Lexer lexer(source);
    m_tokens = lexer.tokenize();
}

const Token& Parser::peek() const {
    static Token eof{ TokenType::EOF_TOKEN, "", 0, 0 };
    if (m_pos >= m_tokens.size()) return eof;
    return m_tokens[m_pos];
}

const Token& Parser::advance() {
    static Token eof{ TokenType::EOF_TOKEN, "", 0, 0 };
    if (m_pos >= m_tokens.size()) return eof;
    return m_tokens[m_pos++];
}

bool Parser::at_end() const {
    return m_pos >= m_tokens.size();
}

void Parser::expect(TokenType type, const std::string& context) {
    if (peek().type != type) {
        throw ParseError("Expected " + context, peek().line, peek().col);
    }
}

Program Parser::parse() {
    Program prog;
    while (!at_end()) {
        prog.statements.push_back(parse_form());
    }
    return prog;
}

AstPtr Parser::parse_form() {
    expect(TokenType::LPAREN, "'('");
    advance();

    expect(TokenType::SYMBOL, "form name");
    const auto& op = peek();

    AstPtr result;
    if (op.text == "def") {
        result = parse_def();
    } else if (op.text == "param") {
        result = parse_param();
    } else if (op.text == "output") {
        result = parse_output();
    } else {
        result = parse_call(op);
    }

    expect(TokenType::RPAREN, "')'");
    advance();
    return result;
}

AstPtr Parser::parse_def() {
    auto line = peek().line, col = peek().col;
    advance(); // skip 'def'

    expect(TokenType::SYMBOL, "binding name");
    auto name = advance().text;
    auto value = parse_expr();

    auto node = std::make_unique<AstNode>();
    node->data = DefNode{ name, std::move(value) };
    node->line = line;
    node->col = col;
    return node;
}

AstPtr Parser::parse_param() {
    auto line = peek().line, col = peek().col;
    advance(); // skip 'param'

    expect(TokenType::SYMBOL, "param name");
    auto name = advance().text;

    expect(TokenType::SYMBOL, "param type");
    auto type_name = advance().text;

    auto default_value = parse_expr();

    std::vector<KeywordArg> constraints;
    while (peek().type == TokenType::KEYWORD) {
        auto kw_name = advance().text.substr(1); // strip ':'
        auto kw_value = parse_expr();
        constraints.push_back({ kw_name, std::move(kw_value) });
    }

    auto node = std::make_unique<AstNode>();
    node->data = ParamNode{ name, type_name, std::move(default_value), std::move(constraints) };
    node->line = line;
    node->col = col;
    return node;
}

AstPtr Parser::parse_output() {
    auto line = peek().line, col = peek().col;
    advance(); // skip 'output'

    auto value = parse_expr();

    auto node = std::make_unique<AstNode>();
    node->data = OutputNode{ std::move(value) };
    node->line = line;
    node->col = col;
    return node;
}

AstPtr Parser::parse_call(const Token& op) {
    auto line = op.line, col = op.col;
    auto op_name = advance().text;

    if (op_name == "fn") {
        return parse_fn(line, col);
    }

    std::vector<AstPtr> args;
    std::vector<KeywordArg> kwargs;

    while (peek().type != TokenType::RPAREN && !at_end()) {
        if (peek().type == TokenType::KEYWORD) {
            auto kw_name = advance().text.substr(1);
            auto kw_value = parse_expr();
            kwargs.push_back({ kw_name, std::move(kw_value) });
        } else {
            args.push_back(parse_expr());
        }
    }

    auto node = std::make_unique<AstNode>();
    node->data = CallNode{ op_name, std::move(args), std::move(kwargs) };
    node->line = line;
    node->col = col;
    return node;
}

AstPtr Parser::parse_fn(uint32_t line, uint32_t col) {
    FnNode fn;

    expect(TokenType::LBRACKET, "'[' for parameter list");
    advance();
    while (peek().type != TokenType::RBRACKET) {
        auto tok = advance();
        fn.params.push_back(tok.text);
    }
    advance(); // consume ]

    if (peek().type == TokenType::ARROW) {
        advance(); // consume ->
        expect(TokenType::LBRACKET, "'[' for output list");
        advance();
        while (peek().type != TokenType::RBRACKET) {
            FnOutput out;
            out.name = advance().text;
            out.type_name = advance().text;
            fn.outputs.push_back(std::move(out));
            if (peek().type == TokenType::SYMBOL && peek().text == ",")
                advance();
        }
        advance(); // consume ]
    }

    while (peek().type != TokenType::RPAREN) {
        fn.body.push_back(parse_expr());
    }

    auto node = std::make_unique<AstNode>();
    node->data = std::move(fn);
    node->line = line;
    node->col = col;
    return node;
}

AstPtr Parser::parse_vector() {
    auto start = advance(); // consume [
    VectorNode vec;
    while (peek().type != TokenType::RBRACKET) {
        vec.elements.push_back(parse_expr());
        if (peek().type == TokenType::SYMBOL && peek().text == ",")
            advance();
    }
    advance(); // consume ]
    auto node = std::make_unique<AstNode>();
    node->data = std::move(vec);
    node->line = start.line;
    node->col = start.col;
    return node;
}

AstPtr Parser::parse_expression() {
    return parse_expr();
}

AstPtr Parser::parse_expr() {
    auto primary = parse_primary();
    while (peek().type == TokenType::DOT) {
        advance(); // consume .
        auto field_tok = advance();
        auto dot = std::make_unique<AstNode>();
        DotAccessNode dn;
        dn.object = std::move(primary);
        dn.field = field_tok.text;
        dot->data = std::move(dn);
        dot->line = field_tok.line;
        dot->col = field_tok.col;
        primary = std::move(dot);
    }
    return primary;
}

AstPtr Parser::parse_primary() {
    const auto& tok = peek();

    if (tok.type == TokenType::LPAREN) {
        return parse_form();
    }

    if (tok.type == TokenType::LBRACKET) {
        return parse_vector();
    }

    if (tok.type == TokenType::NUMBER) {
        auto t = advance();
        double val = 0.0;
        try { val = std::stod(t.text); }
        catch (const std::exception&) {
            throw ParseError("Invalid number: " + t.text, t.line, t.col);
        }
        auto node = std::make_unique<AstNode>();
        node->data = NumberNode{ val };
        node->line = t.line;
        node->col = t.col;
        return node;
    }

    if (tok.type == TokenType::STRING) {
        auto t = advance();
        auto node = std::make_unique<AstNode>();
        node->data = StringNode{ t.text };
        node->line = t.line;
        node->col = t.col;
        return node;
    }

    if (tok.type == TokenType::SYMBOL) {
        auto t = advance();
        auto node = std::make_unique<AstNode>();
        node->data = SymbolNode{ t.text };
        node->line = t.line;
        node->col = t.col;
        return node;
    }

    throw ParseError("Unexpected token: " + tok.text, tok.line, tok.col);
}

} // namespace joon
