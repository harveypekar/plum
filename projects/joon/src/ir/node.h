#pragma once

#include <joon/types.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <cstdint>

namespace joon {

enum class Tier { CPU, GPU, SCENE, RENDER };

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
