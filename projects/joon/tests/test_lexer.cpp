#include "catch_amalgamated.hpp"
#include "dsl/lexer.h"

using namespace joon;

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
