#include "catch_amalgamated.hpp"
#include "dsl/parser.h"

using namespace joon;

TEST_CASE("Parser parses def with call", "[parser]") {
    Parser parser("(def x (+ 1.0 2.0))");
    auto program = parser.parse();

    REQUIRE(program.statements.size() == 1);
    auto& def = std::get<DefNode>(program.statements[0]->data);
    CHECK(def.name == "x");

    auto& call = std::get<CallNode>(def.value->data);
    CHECK(call.op == "+");
    REQUIRE(call.args.size() == 2);

    CHECK(std::get<NumberNode>(call.args[0]->data).value == 1.0);
    CHECK(std::get<NumberNode>(call.args[1]->data).value == 2.0);
}

TEST_CASE("Parser parses keyword args", "[parser]") {
    Parser parser("(def n (noise :scale 4.0 :octaves 3))");
    auto program = parser.parse();

    auto& def = std::get<DefNode>(program.statements[0]->data);
    auto& call = std::get<CallNode>(def.value->data);
    CHECK(call.op == "noise");
    REQUIRE(call.kwargs.size() == 2);
    CHECK(call.kwargs[0].name == "scale");
    CHECK(call.kwargs[1].name == "octaves");
}

TEST_CASE("Parser parses param", "[parser]") {
    Parser parser("(param contrast float 1.2 :min 0.0 :max 3.0)");
    auto program = parser.parse();

    auto& param = std::get<ParamNode>(program.statements[0]->data);
    CHECK(param.name == "contrast");
    CHECK(param.type_name == "float");
    CHECK(std::get<NumberNode>(param.default_value->data).value == Catch::Approx(1.2));
    REQUIRE(param.constraints.size() == 2);
    CHECK(param.constraints[0].name == "min");
    CHECK(param.constraints[1].name == "max");
}

TEST_CASE("Parser parses output", "[parser]") {
    Parser parser("(output x)");
    auto program = parser.parse();

    auto& out = std::get<OutputNode>(program.statements[0]->data);
    CHECK(std::get<SymbolNode>(out.value->data).name == "x");
}

TEST_CASE("Parser parses nested calls", "[parser]") {
    Parser parser("(def result (* (+ a b) c))");
    auto program = parser.parse();

    auto& def = std::get<DefNode>(program.statements[0]->data);
    auto& outer = std::get<CallNode>(def.value->data);
    CHECK(outer.op == "*");
    REQUIRE(outer.args.size() == 2);

    auto& inner = std::get<CallNode>(outer.args[0]->data);
    CHECK(inner.op == "+");
}

TEST_CASE("Parser parses string args", "[parser]") {
    Parser parser(R"((def base (image "textures/stone.png")))");
    auto program = parser.parse();

    auto& def = std::get<DefNode>(program.statements[0]->data);
    auto& call = std::get<CallNode>(def.value->data);
    CHECK(call.op == "image");
    REQUIRE(call.args.size() == 1);
    CHECK(std::get<StringNode>(call.args[0]->data).value == "textures/stone.png");
}

TEST_CASE("Parser full program", "[parser]") {
    const char* src = R"(
        (def base (image "stone.png"))
        (def n (noise :scale 4.0))
        (param contrast float 1.2 :min 0.0 :max 3.0)
        (def result (* base n))
        (output result)
    )";
    Parser parser(src);
    auto program = parser.parse();
    REQUIRE(program.statements.size() == 5);
}

TEST_CASE("Parser error on unexpected token", "[parser]") {
    Parser parser(")");
    CHECK_THROWS_AS(parser.parse(), ParseError);
}

TEST_CASE("Parser mixed positional and keyword args", "[parser]") {
    Parser parser("(def r (blend a b :mode multiply :opacity 0.7))");
    auto program = parser.parse();

    auto& def = std::get<DefNode>(program.statements[0]->data);
    auto& call = std::get<CallNode>(def.value->data);
    CHECK(call.op == "blend");
    CHECK(call.args.size() == 2);
    CHECK(call.kwargs.size() == 2);
    CHECK(std::get<SymbolNode>(call.args[0]->data).name == "a");
    CHECK(std::get<SymbolNode>(call.args[1]->data).name == "b");
}
