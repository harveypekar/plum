#include <joon/joon.h>
#include "ir/ir_graph.h"
#include <iostream>
#include <string>
#include <vector>

static void print_usage() {
    std::cerr << "Joon - Graphics DSL\n\n"
              << "Usage:\n"
              << "  joon run <file.jn> [-o output.png] [-p key=val ...]\n"
              << "  joon check <file.jn>\n"
              << "  joon info <file.jn>\n";
}

static const char* type_name(joon::Type t) {
    switch (t) {
        case joon::Type::FLOAT: return "float";
        case joon::Type::INT:   return "int";
        case joon::Type::BOOL:  return "bool";
        case joon::Type::VEC2:  return "vec2";
        case joon::Type::VEC3:  return "vec3";
        case joon::Type::VEC4:  return "vec4";
        case joon::Type::MAT3:  return "mat3";
        case joon::Type::MAT4:  return "mat4";
        case joon::Type::IMAGE: return "image";
        default: return "unknown";
    }
}

static void print_diagnostics(const char* path, const joon::Graph& graph) {
    for (auto& d : graph.diagnostics()) {
        const char* level = d.level == joon::ir::Diagnostic::Level::Error ? "error" : "warning";
        std::cerr << path << ":" << d.line << ":" << d.col << ": "
                  << level << ": " << d.message << "\n";
    }
}

static int cmd_check(const char* path) {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_file(path);
    print_diagnostics(path, graph);

    if (graph.has_errors()) {
        std::cerr << "Check failed.\n";
        return 1;
    }
    std::cout << "OK\n";
    return 0;
}

static int cmd_info(const char* path) {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_file(path);

    auto& ir = graph.ir();
    std::cout << "Nodes: " << ir.nodes.size() << "\n";

    if (!ir.params.empty()) {
        std::cout << "Params:\n";
        for (auto& p : ir.params) {
            std::cout << "  " << p.name << " : " << type_name(p.type);
            if (std::holds_alternative<float>(p.default_value)) {
                std::cout << " = " << std::get<float>(p.default_value);
            }
            for (auto& [k, v] : p.constraints) {
                std::cout << " :" << k << " " << v;
            }
            std::cout << "\n";
        }
    }

    std::cout << "Outputs: " << ir.outputs.size() << "\n";
    return 0;
}

static int cmd_run(const char* path, const char* output,
                    const std::vector<std::pair<std::string, std::string>>& overrides) {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_file(path);

    if (graph.has_errors()) {
        print_diagnostics(path, graph);
        return 1;
    }

    auto eval = ctx->create_evaluator(graph);

    for (auto& [key, val] : overrides) {
        auto p = eval->param<float>(key);
        p = std::stof(val);
    }

    eval->evaluate();

    if (output) {
        auto result = eval->result("output");
        result.save_image(output);
        std::cout << "Saved to " << output << "\n";
    }

    return 0;
}

int main(int argc, char** argv) {
    if (argc < 2) { print_usage(); return 1; }

    std::string cmd = argv[1];

    if (cmd == "check" && argc >= 3) return cmd_check(argv[2]);
    if (cmd == "info" && argc >= 3)  return cmd_info(argv[2]);

    if (cmd == "run" && argc >= 3) {
        const char* output = nullptr;
        std::vector<std::pair<std::string, std::string>> params;

        for (int i = 3; i < argc; i++) {
            std::string arg = argv[i];
            if (arg == "-o" && i + 1 < argc) { output = argv[++i]; }
            else if (arg == "-p" && i + 1 < argc) {
                std::string kv = argv[++i];
                auto eq = kv.find('=');
                if (eq != std::string::npos) {
                    params.push_back({ kv.substr(0, eq), kv.substr(eq + 1) });
                }
            }
        }

        return cmd_run(argv[2], output, params);
    }

    print_usage();
    return 1;
}
