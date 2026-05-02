#include "catch_amalgamated.hpp"
#include "shader/prepass_extractor.h"
#include "shader/shader_analyzer.h"
#include "shader/shader_ir.h"
using namespace joon;

TEST_CASE("Prepass extracts blur from shader body", "[shader][prepass]") {
    // Build: (set albedo (blur input :radius 3))
    ShaderCall blur_call;
    blur_call.op = "blur";
    blur_call.args.push_back(std::make_unique<ShaderExpr>(ShaderVar{"input"}));
    blur_call.kwargs.push_back({"radius", 3.0f});

    ShaderAssign assign;
    assign.target = "albedo";
    assign.value = std::make_unique<ShaderExpr>(std::move(blur_call));

    ShaderFnIR frag;
    frag.params = {"normal", "uv"};
    frag.outputs = {{"albedo", "vec4"}};
    frag.body.push_back(std::make_unique<ShaderExpr>(std::move(assign)));

    ShaderAnalyzer analyzer;
    PrepassExtractor extractor(analyzer);
    auto result = extractor.extract(frag);

    CHECK(result.prepasses.size() == 1);
    CHECK(result.prepasses[0].root_op == "blur");

    auto* new_assign = std::get_if<ShaderAssign>(result.modified_body[0].get());
    REQUIRE(new_assign != nullptr);
    auto* sample = std::get_if<ShaderPrepassSample>(new_assign->value.get());
    REQUIRE(sample != nullptr);
    CHECK(sample->prepass_index == 0);
}

TEST_CASE("Prepass leaves inlineable ops untouched", "[shader][prepass]") {
    // Build: (set albedo (noise :scale 4.0))
    ShaderCall noise;
    noise.op = "noise";
    noise.kwargs.push_back({"scale", 4.0f});

    ShaderAssign assign;
    assign.target = "albedo";
    assign.value = std::make_unique<ShaderExpr>(std::move(noise));

    ShaderFnIR frag;
    frag.params = {"normal", "uv"};
    frag.outputs = {{"albedo", "vec4"}};
    frag.body.push_back(std::make_unique<ShaderExpr>(std::move(assign)));

    ShaderAnalyzer analyzer;
    PrepassExtractor extractor(analyzer);
    auto result = extractor.extract(frag);

    CHECK(result.prepasses.empty());
    auto* a = std::get_if<ShaderAssign>(result.modified_body[0].get());
    REQUIRE(a != nullptr);
    CHECK(std::get_if<ShaderCall>(a->value.get()) != nullptr);
}
