#include "catch_amalgamated.hpp"
#include "dsl/lexer.h"

using namespace joon::dsl;

TEST_CASE("Lexer tokenizes S-expression", "[lexer]") {
    Lexer lexer("(def x (+ 1.0 2.0))");
    auto tokens = lexer.tokenize();

    REQUIRE(tokens.size() == 9);
    CHECK(tokens[0].type == TokenType::LPAREN);
    CHECK(tokens[1].type == TokenType::SYMBOL);
    CHECK(tokens[1].text == "def");
    CHECK(tokens[2].type == TokenType::SYMBOL);
    CHECK(tokens[2].text == "x");
    CHECK(tokens[3].type == TokenType::LPAREN);
    CHECK(tokens[4].type == TokenType::SYMBOL);
    CHECK(tokens[4].text == "+");
    CHECK(tokens[5].type == TokenType::NUMBER);
    CHECK(tokens[5].text == "1.0");
    CHECK(tokens[6].type == TokenType::NUMBER);
    CHECK(tokens[6].text == "2.0");
    CHECK(tokens[7].type == TokenType::RPAREN);
    CHECK(tokens[8].type == TokenType::RPAREN);
}

TEST_CASE("Lexer handles keywords", "[lexer]") {
    Lexer lexer("(noise :scale 4.0 :octaves 3)");
    auto tokens = lexer.tokenize();

    REQUIRE(tokens.size() == 7);
    CHECK(tokens[2].type == TokenType::KEYWORD);
    CHECK(tokens[2].text == ":scale");
    CHECK(tokens[4].type == TokenType::KEYWORD);
    CHECK(tokens[4].text == ":octaves");
}

TEST_CASE("Lexer handles strings", "[lexer]") {
    Lexer lexer(R"((image "textures/stone.png"))");
    auto tokens = lexer.tokenize();

    REQUIRE(tokens.size() == 4);
    CHECK(tokens[2].type == TokenType::STRING);
    CHECK(tokens[2].text == "textures/stone.png");
}

TEST_CASE("Lexer handles comments", "[lexer]") {
    Lexer lexer("; this is a comment\n(def x 1.0)");
    auto tokens = lexer.tokenize();

    CHECK(tokens[0].type == TokenType::LPAREN);
    CHECK(tokens[1].text == "def");
}

TEST_CASE("Lexer tracks line and column", "[lexer]") {
    Lexer lexer("(def x\n  1.0)");
    auto tokens = lexer.tokenize();

    CHECK(tokens[0].line == 1);
    CHECK(tokens[0].col == 1);
    CHECK(tokens[3].line == 2);
    CHECK(tokens[3].col == 3);
}

TEST_CASE("Lexer handles negative numbers", "[lexer]") {
    Lexer lexer("(+ -1.5 2.0)");
    auto tokens = lexer.tokenize();

    REQUIRE(tokens.size() == 5);
    CHECK(tokens[2].type == TokenType::NUMBER);
    CHECK(tokens[2].text == "-1.5");
}

TEST_CASE("Lexer handles minus as symbol", "[lexer]") {
    Lexer lexer("(- a b)");
    auto tokens = lexer.tokenize();

    CHECK(tokens[1].type == TokenType::SYMBOL);
    CHECK(tokens[1].text == "-");
}

TEST_CASE("Lexer tokenizes empty input", "[lexer]") {
    Lexer lexer("");
    auto tokens = lexer.tokenize();
    CHECK(tokens.empty());
}

TEST_CASE("Lexer tokenizes only whitespace", "[lexer]") {
    Lexer lexer("   \n  \t  \n   ");
    auto tokens = lexer.tokenize();
    CHECK(tokens.empty());
}

TEST_CASE("Lexer handles parentheses", "[lexer]") {
    Lexer lexer("()");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 2);
    CHECK(tokens[0].type == TokenType::LPAREN);
    CHECK(tokens[1].type == TokenType::RPAREN);
}

TEST_CASE("Lexer handles integer numbers", "[lexer]") {
    Lexer lexer("(+ 42 -100)");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 5);
    CHECK(tokens[2].type == TokenType::NUMBER);
    CHECK(tokens[2].text == "42");
    CHECK(tokens[3].type == TokenType::NUMBER);
    CHECK(tokens[3].text == "-100");
}

TEST_CASE("Lexer handles floating point numbers", "[lexer]") {
    Lexer lexer("3.14159 0.0 -0.5");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 3);
    CHECK(tokens[0].type == TokenType::NUMBER);
    CHECK(tokens[0].text == "3.14159");
    CHECK(tokens[1].text == "0.0");
    CHECK(tokens[2].text == "-0.5");
}

TEST_CASE("Lexer handles scientific notation", "[lexer]") {
    Lexer lexer("1e10 1.5e-5 2E+3");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 3);
    for (auto& token : tokens) {
        CHECK(token.type == TokenType::NUMBER);
    }
}

TEST_CASE("Lexer handles all special symbols", "[lexer]") {
    Lexer lexer("+ - * / < > = ! & |");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 10);
    for (auto& token : tokens) {
        CHECK(token.type == TokenType::SYMBOL);
    }
}

TEST_CASE("Lexer handles quoted strings with escapes", "[lexer]") {
    Lexer lexer(R"("hello \"world\"" "newline\n")");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 2);
    CHECK(tokens[0].type == TokenType::STRING);
    CHECK(tokens[1].type == TokenType::STRING);
}

TEST_CASE("Lexer handles multiple keywords", "[lexer]") {
    Lexer lexer(":x :y :scale :octaves :seed");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 5);
    for (auto& token : tokens) {
        CHECK(token.type == TokenType::KEYWORD);
    }
}

TEST_CASE("Lexer handles unclosed parenthesis", "[lexer]") {
    Lexer lexer("(def x");
    auto tokens = lexer.tokenize();
    CHECK(tokens.size() >= 2);
    CHECK(tokens[0].type == TokenType::LPAREN);
}

TEST_CASE("Lexer handles unclosed string", "[lexer]") {
    Lexer lexer("(image \"unclosed");
    auto tokens = lexer.tokenize();
    CHECK(tokens.size() >= 2);
}

TEST_CASE("Lexer handles consecutive whitespace", "[lexer]") {
    Lexer lexer("(   +   1   2   )");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 5);
    CHECK(tokens[1].text == "+");
    CHECK(tokens[2].text == "1");
}

TEST_CASE("Lexer handles tabs and mixed whitespace", "[lexer]") {
    Lexer lexer("(\t+\t1\t2\t)");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 5);
}

TEST_CASE("Lexer handles multiple comments", "[lexer]") {
    Lexer lexer("; comment 1\n(def x 1.0)\n; comment 2");
    auto tokens = lexer.tokenize();
    CHECK(tokens[0].type == TokenType::LPAREN);
    CHECK(tokens[1].text == "def");
}

TEST_CASE("Lexer handles comment at end of line", "[lexer]") {
    Lexer lexer("(+ 1 2) ; this is a comment");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 5);
    CHECK(tokens[4].type == TokenType::RPAREN);
}

TEST_CASE("Lexer accurately tracks line numbers across multiple lines", "[lexer]") {
    Lexer lexer("(def x\n  (+ 1\n     2))");
    auto tokens = lexer.tokenize();
    CHECK(tokens[0].line == 1);
    CHECK(tokens[3].line == 2);
    CHECK(tokens[6].line == 3);
}

TEST_CASE("Lexer accurately tracks column numbers within line", "[lexer]") {
    Lexer lexer("(a b c)");
    auto tokens = lexer.tokenize();
    CHECK(tokens[0].col == 1);
    CHECK(tokens[1].col == 2);
    CHECK(tokens[2].col == 4);
    CHECK(tokens[3].col == 6);
}

TEST_CASE("Lexer handles very long input", "[lexer]") {
    std::string long_input;
    for (int i = 0; i < 1000; i++) {
        long_input += "(x) ";
    }
    Lexer lexer(long_input);
    auto tokens = lexer.tokenize();
    CHECK(tokens.size() == 3000);
}

TEST_CASE("Lexer handles very long token", "[lexer]") {
    std::string long_symbol(1000, 'a');
    Lexer lexer(long_symbol);
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 1);
    CHECK(tokens[0].text.length() == 1000);
}

TEST_CASE("Lexer handles special characters in symbols", "[lexer]") {
    Lexer lexer("foo-bar baz_qux x?y! a->b");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 4);
    CHECK(tokens[0].text == "foo-bar");
    CHECK(tokens[1].text == "baz_qux");
    CHECK(tokens[2].text == "x?y!");
    CHECK(tokens[3].text == "a->b");
}

TEST_CASE("Lexer preserves exact string content", "[lexer]") {
    Lexer lexer(R"("  spaces  \n special chars !@#")");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 1);
    CHECK(tokens[0].type == TokenType::STRING);
    CHECK(tokens[0].text.find("spaces") != std::string::npos);
}
