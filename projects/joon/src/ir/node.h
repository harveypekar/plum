#pragma once

#include <joon/types.h>
#include "dsl/ast.h"
#include <string>
#include <vector>
#include <optional>
#include <unordered_map>
#include <cstdint>

namespace joon {

// Order matches interpreter execution phases: CPU constants resolve first,
// then GPU compute dispatches, then MATERIAL shader compilation,
// then SCENE collection, then RENDER pass.
// Don't reorder without auditing the interpreter walk in interpreter.cpp.
enum class Tier { CPU, GPU, MATERIAL, SCENE, RENDER };

struct Edge {
    uint32_t from_node;
    uint32_t to_node;
    uint32_t to_input;
};

struct ResolvedKwarg {
    std::string name;
    Value value;
    uint32_t source_node = UINT32_MAX;
};

struct ShaderFnDef {
    std::vector<std::string> params;
    struct Output { std::string name; std::string type_name; };
    std::vector<Output> outputs;
    std::vector<std::shared_ptr<AstNode>> body;
};

struct ShaderDef {
    std::optional<ShaderFnDef> vertex;
    std::optional<ShaderFnDef> fragment;
    std::optional<ShaderFnDef> brdf;
};

struct Node {
    uint32_t id;
    std::string name;             // binding name from (def name ...), empty if anonymous
    std::string op;               // "image", "noise", "+", "blur", etc.
    Tier tier;
    Type output_type;
    std::vector<uint32_t> inputs; // node IDs feeding into this node
    std::vector<ResolvedKwarg> kwargs;

    bool is_constant = false;
    Value constant_value;

    std::string string_arg;
};

struct ParamInfo {
    std::string name;
    Type type;
    Value default_value;
    std::unordered_map<std::string, float> constraints;
    uint32_t node_id;
};

struct OutputInfo {
    uint32_t node_id;
};

} // namespace joon
