# Joon Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Joon graphics DSL end-to-end for Image type — from DSL text to rendered output in a live GUI.

**Architecture:** Library-first C++ with hybrid Vulkan-native engine. S-expression DSL parsed by hand-written recursive descent parser into an IR graph. Interpreter mode dispatches precompiled Vulkan compute shaders per node. Dear ImGui (docking branch) provides the RenderMonkey-style GUI. CLI is a thin library consumer.

**Tech Stack:** C++20, Premake5, Vulkan SDK, Dear ImGui (docking), Catch2 (testing), stb_image/stb_image_write (image I/O), VulkanMemoryAllocator (VMA)

**Spec:** `docs/superpowers/specs/2026-03-29-joon-design.md`

---

## File Structure

```
projects/joon/
├── premake5.lua                    # Build configuration
├── CLAUDE.md                       # Project-specific instructions
├── include/joon/
│   ├── joon.h                      # Public umbrella header
│   ├── types.h                     # Core type definitions (float, vec, image handle)
│   ├── context.h                   # joon::Context (Vulkan device, pools)
│   ├── graph.h                     # joon::Graph (parsed, validated IR)
│   ├── evaluator.h                 # joon::Evaluator (interpreter)
│   ├── param.h                     # joon::Param<T> typed param handle
│   └── result.h                    # joon::Result (output handle)
├── src/
│   ├── dsl/
│   │   ├── token.h                 # Token types and Token struct
│   │   ├── lexer.h                 # Lexer interface
│   │   ├── lexer.cpp               # Tokenizer
│   │   ├── ast.h                   # AST node types
│   │   ├── parser.h                # Parser interface
│   │   └── parser.cpp              # Recursive descent parser
│   ├── ir/
│   │   ├── node.h                  # IR node (type sig, tier, params)
│   │   ├── ir_graph.h              # IR graph (nodes + edges)
│   │   ├── ir_graph.cpp            # Graph construction from AST
│   │   ├── type_checker.h          # Type inference and checking
│   │   └── type_checker.cpp        # Broadcast rules, promotion, errors
│   ├── vulkan/
│   │   ├── device.h                # Vulkan device/instance setup
│   │   ├── device.cpp
│   │   ├── resource_pool.h         # Buffer/image allocation via VMA
│   │   ├── resource_pool.cpp
│   │   ├── pipeline_cache.h        # Shader module + pipeline management
│   │   └── pipeline_cache.cpp
│   ├── nodes/
│   │   ├── node_registry.h         # Maps node names to implementations
│   │   ├── node_registry.cpp
│   │   ├── image_load.cpp          # (image "path") — CPU tier, stb_image
│   │   ├── noise.cpp               # (noise ...) — GPU tier
│   │   ├── color.cpp               # (color r g b) — CPU tier (constant)
│   │   ├── math_ops.cpp            # +, -, *, / — GPU tier
│   │   ├── image_ops.cpp           # blur, levels, blend, invert, threshold — GPU tier
│   │   └── save.cpp                # (save ...) — CPU tier, stb_image_write
│   ├── interpreter/
│   │   ├── interpreter.h           # Interpreter interface
│   │   └── interpreter.cpp         # Topological eval with precompiled passes
│   ├── context.cpp                 # joon::Context implementation
│   ├── graph.cpp                   # joon::Graph (parse + validate)
│   └── evaluator.cpp               # joon::Evaluator implementation
├── shaders/
│   ├── add.comp                    # Element-wise add
│   ├── sub.comp                    # Element-wise subtract
│   ├── mul.comp                    # Element-wise multiply
│   ├── div.comp                    # Element-wise divide
│   ├── noise.comp                  # Perlin/simplex noise
│   ├── blur.comp                   # Gaussian blur
│   ├── levels.comp                 # Levels adjustment
│   ├── blend.comp                  # Blend modes
│   ├── invert.comp                 # Invert
│   └── threshold.comp              # Threshold
├── cli/
│   └── main.cpp                    # CLI entry point
├── gui/
│   ├── main.cpp                    # GUI entry point, ImGui setup
│   ├── app.h                       # Application state
│   ├── app.cpp                     # Application loop
│   ├── panel_tree.cpp              # Graph tree panel
│   ├── panel_properties.cpp        # Property editor panel
│   ├── panel_code.cpp              # Code editor panel
│   ├── panel_viewport.cpp          # Output viewport panel
│   ├── panel_preview.cpp           # Node preview panel
│   └── panel_log.cpp               # Output log panel
├── tests/
│   ├── main.cpp                    # Catch2 main
│   ├── test_lexer.cpp
│   ├── test_parser.cpp
│   ├── test_type_checker.cpp
│   ├── test_interpreter.cpp
│   └── test_cli.cpp
└── third_party/
    ├── catch2/                     # Catch2 header(s)
    ├── imgui/                      # Dear ImGui (docking branch)
    ├── stb/                        # stb_image, stb_image_write
    └── vma/                        # VulkanMemoryAllocator
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `projects/joon/premake5.lua`
- Create: `projects/joon/CLAUDE.md`
- Create: `projects/joon/tests/main.cpp`
- Create: `projects/joon/include/joon/types.h`

- [ ] **Step 1: Create directory structure**

```bash
cd /mnt/d/prg/plum
mkdir -p projects/joon/{include/joon,src/{dsl,ir,vulkan,nodes,interpreter},shaders,cli,gui,tests,third_party}
```

- [ ] **Step 2: Write premake5.lua**

```lua
-- projects/joon/premake5.lua
workspace "Joon"
    configurations { "Debug", "Release" }
    architecture "x86_64"
    language "C++"
    cppdialect "C++20"
    location "build"

    filter "configurations:Debug"
        defines { "DEBUG" }
        symbols "On"
        optimize "Off"

    filter "configurations:Release"
        defines { "NDEBUG" }
        optimize "Speed"

    filter "system:windows"
        systemversion "latest"

    filter {}

    -- Find Vulkan SDK
    local vulkan_sdk = os.getenv("VULKAN_SDK")
    if not vulkan_sdk then
        error("VULKAN_SDK environment variable not set")
    end

project "joon-lib"
    kind "StaticLib"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/lib"

    files {
        "include/**.h",
        "src/**.h",
        "src/**.cpp"
    }

    includedirs {
        "include",
        "src",
        "third_party",
        "third_party/imgui",
        "third_party/vma",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "vulkan-1" }

project "joon-cli"
    kind "ConsoleApp"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/cli"

    files { "cli/**.cpp" }

    includedirs {
        "include",
        "third_party",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "joon-lib", "vulkan-1" }

project "joon-gui"
    kind "WindowedApp"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/gui"

    files {
        "gui/**.h",
        "gui/**.cpp",
        "third_party/imgui/*.cpp",
        "third_party/imgui/backends/imgui_impl_vulkan.cpp",
        "third_party/imgui/backends/imgui_impl_glfw.cpp"
    }

    includedirs {
        "include",
        "src",
        "third_party",
        "third_party/imgui",
        "third_party/imgui/backends",
        "third_party/vma",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "joon-lib", "vulkan-1", "glfw3" }

project "joon-tests"
    kind "ConsoleApp"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/tests"

    files { "tests/**.cpp" }

    includedirs {
        "include",
        "src",
        "third_party",
        "third_party/catch2",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "joon-lib", "vulkan-1" }
```

- [ ] **Step 3: Write Catch2 test main**

```cpp
// tests/main.cpp
#define CATCH_CONFIG_MAIN
#include <catch2/catch_all.hpp>
```

- [ ] **Step 4: Write core types header**

```cpp
// include/joon/types.h
#pragma once

#include <cstdint>
#include <string>
#include <variant>
#include <vector>

namespace joon {

struct vec2 { float x, y; };
struct vec3 { float x, y, z; };
struct vec4 { float x, y, z, w; };
struct mat3 { float m[9]; };
struct mat4 { float m[16]; };

// Type tag for the DSL type system
enum class Type {
    Float,
    Int,
    Bool,
    Vec2,
    Vec3,
    Vec4,
    Mat3,
    Mat4,
    Image
};

// Runtime value (used by interpreter for scalars/constants)
using Value = std::variant<
    float, int, bool,
    vec2, vec3, vec4,
    mat3, mat4
>;

// Image handle — refers to a Vulkan resource
struct ImageHandle {
    uint32_t id;
    uint32_t width;
    uint32_t height;
};

} // namespace joon
```

- [ ] **Step 5: Write CLAUDE.md**

```markdown
# Joon

Graphics DSL and visual compute framework. C++20, Vulkan, Premake.

## Build

Requires: Vulkan SDK, Premake5

```bash
cd projects/joon
premake5 vs2022        # or gmake2 on Linux
# Then build via VS or make
```

## Structure

- `include/joon/` — public library headers
- `src/` — library implementation
- `cli/` — CLI entry point
- `gui/` — GUI entry point (ImGui)
- `shaders/` — Vulkan GLSL compute shaders
- `tests/` — Catch2 tests
- `third_party/` — vendored dependencies

## Conventions

- C++20, no exceptions (use result types)
- All public types in `joon` namespace
- One class per header in `include/joon/`
- Implementation details in `src/` subfolders
- Tests mirror src structure
```

- [ ] **Step 6: Download third-party dependencies**

```bash
cd projects/joon/third_party
# Catch2 v3 single-header
git clone --depth 1 --branch v3.5.2 https://github.com/catchorg/Catch2.git catch2
# Dear ImGui docking branch
git clone --depth 1 --branch docking https://github.com/ocornut/imgui.git imgui
# stb
git clone --depth 1 https://github.com/nothings/stb.git stb
# VulkanMemoryAllocator
git clone --depth 1 https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator.git vma
```

- [ ] **Step 7: Verify build compiles**

```bash
cd projects/joon
premake5 gmake2
make config=debug joon-tests
```

- [ ] **Step 8: Commit**

```bash
git add projects/joon/
git commit -m "feat(joon): project scaffolding with premake, types, and test harness"
```

---

## Task 2: DSL Lexer

**Files:**
- Create: `projects/joon/src/dsl/token.h`
- Create: `projects/joon/src/dsl/lexer.h`
- Create: `projects/joon/src/dsl/lexer.cpp`
- Create: `projects/joon/tests/test_lexer.cpp`

- [ ] **Step 1: Write lexer test**

```cpp
// tests/test_lexer.cpp
#include <catch2/catch_all.hpp>
#include "dsl/lexer.h"

TEST_CASE("Lexer tokenizes S-expression", "[lexer]") {
    joon::dsl::Lexer lexer("(def x (+ 1.0 2.0))");
    auto tokens = lexer.tokenize();

    REQUIRE(tokens.size() == 8); // ( def x ( + 1.0 2.0 ) ) EOF
    CHECK(tokens[0].type == joon::dsl::TokenType::LParen);
    CHECK(tokens[1].type == joon::dsl::TokenType::Symbol);
    CHECK(tokens[1].text == "def");
    CHECK(tokens[2].type == joon::dsl::TokenType::Symbol);
    CHECK(tokens[2].text == "x");
    CHECK(tokens[3].type == joon::dsl::TokenType::LParen);
    CHECK(tokens[4].type == joon::dsl::TokenType::Symbol);
    CHECK(tokens[4].text == "+");
    CHECK(tokens[5].type == joon::dsl::TokenType::Number);
    CHECK(tokens[5].text == "1.0");
    CHECK(tokens[6].type == joon::dsl::TokenType::Number);
    CHECK(tokens[6].text == "2.0");
    CHECK(tokens[7].type == joon::dsl::TokenType::RParen);
}

TEST_CASE("Lexer handles keywords", "[lexer]") {
    joon::dsl::Lexer lexer("(noise :scale 4.0 :octaves 3)");
    auto tokens = lexer.tokenize();

    CHECK(tokens[2].type == joon::dsl::TokenType::Keyword);
    CHECK(tokens[2].text == ":scale");
    CHECK(tokens[4].type == joon::dsl::TokenType::Keyword);
    CHECK(tokens[4].text == ":octaves");
}

TEST_CASE("Lexer handles strings", "[lexer]") {
    joon::dsl::Lexer lexer(R"((image "textures/stone.png"))");
    auto tokens = lexer.tokenize();

    CHECK(tokens[2].type == joon::dsl::TokenType::String);
    CHECK(tokens[2].text == "textures/stone.png");
}

TEST_CASE("Lexer handles comments", "[lexer]") {
    joon::dsl::Lexer lexer("; this is a comment\n(def x 1.0)");
    auto tokens = lexer.tokenize();

    CHECK(tokens[0].type == joon::dsl::TokenType::LParen);
    CHECK(tokens[1].text == "def");
}

TEST_CASE("Lexer tracks line and column", "[lexer]") {
    joon::dsl::Lexer lexer("(def x\n  1.0)");
    auto tokens = lexer.tokenize();

    CHECK(tokens[0].line == 1);
    CHECK(tokens[0].col == 1);
    CHECK(tokens[3].line == 2);
    CHECK(tokens[3].col == 3);
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd projects/joon && make config=debug joon-tests && ./build/bin/Debug/joon-tests --reporter compact "[lexer]"
```

Expected: Compile error — `dsl/lexer.h` not found.

- [ ] **Step 3: Write token.h**

```cpp
// src/dsl/token.h
#pragma once

#include <string>
#include <cstdint>

namespace joon::dsl {

enum class TokenType {
    LParen,     // (
    RParen,     // )
    Symbol,     // def, noise, +, -, *, /
    Keyword,    // :scale, :min
    Number,     // 1.0, 42
    String,     // "path/to/file"
    Eof
};

struct Token {
    TokenType type;
    std::string text;
    uint32_t line;
    uint32_t col;
};

} // namespace joon::dsl
```

- [ ] **Step 4: Write lexer.h**

```cpp
// src/dsl/lexer.h
#pragma once

#include "dsl/token.h"
#include <string>
#include <string_view>
#include <vector>

namespace joon::dsl {

class Lexer {
public:
    explicit Lexer(std::string_view source);
    std::vector<Token> tokenize();

private:
    std::string_view source_;
    size_t pos_ = 0;
    uint32_t line_ = 1;
    uint32_t col_ = 1;

    char peek() const;
    char advance();
    void skip_whitespace_and_comments();
    Token read_symbol_or_keyword();
    Token read_number();
    Token read_string();
};

} // namespace joon::dsl
```

- [ ] **Step 5: Write lexer.cpp**

```cpp
// src/dsl/lexer.cpp
#include "dsl/lexer.h"
#include <stdexcept>

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
    size_t start = pos_;
    while (pos_ < source_.size() && (isdigit(peek()) || peek() == '.')) advance();
    return { TokenType::Number, std::string(source_.substr(start, pos_ - start)), line_, start_col };
}

Token Lexer::read_string() {
    uint32_t start_col = col_;
    advance(); // skip opening "
    size_t start = pos_;
    while (pos_ < source_.size() && peek() != '"') advance();
    std::string text(source_.substr(start, pos_ - start));
    if (pos_ < source_.size()) advance(); // skip closing "
    return { TokenType::String, text, line_, start_col };
}

Token Lexer::read_symbol_or_keyword() {
    uint32_t start_col = col_;
    bool is_keyword = (peek() == ':');
    size_t start = pos_;
    advance(); // first char
    while (pos_ < source_.size()) {
        char c = peek();
        if (c == '(' || c == ')' || c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == ';') break;
        advance();
    }
    std::string text(source_.substr(start, pos_ - start));
    return { is_keyword ? TokenType::Keyword : TokenType::Symbol, text, line_, start_col };
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
        } else if (isdigit(c)) {
            tokens.push_back(read_number());
        } else {
            tokens.push_back(read_symbol_or_keyword());
        }
    }
    return tokens;
}

} // namespace joon::dsl
```

- [ ] **Step 6: Run tests**

```bash
cd projects/joon && make config=debug joon-tests && ./build/bin/Debug/joon-tests --reporter compact "[lexer]"
```

Expected: All 5 tests pass.

- [ ] **Step 7: Commit**

```bash
git add projects/joon/src/dsl/ projects/joon/tests/test_lexer.cpp
git commit -m "feat(joon): S-expression lexer with keywords, strings, line tracking"
```

---

## Task 3: DSL Parser

**Files:**
- Create: `projects/joon/src/dsl/ast.h`
- Create: `projects/joon/src/dsl/parser.h`
- Create: `projects/joon/src/dsl/parser.cpp`
- Create: `projects/joon/tests/test_parser.cpp`

- [ ] **Step 1: Write AST node types**

```cpp
// src/dsl/ast.h
#pragma once

#include <string>
#include <vector>
#include <memory>
#include <variant>
#include <cstdint>

namespace joon::dsl {

struct AstNode;
using AstPtr = std::unique_ptr<AstNode>;

// Keyword argument: :name value
struct KeywordArg {
    std::string name; // without the colon
    AstPtr value;
};

// (def name expr)
struct DefNode {
    std::string name;
    AstPtr value;
};

// (param name type default :key val ...)
struct ParamNode {
    std::string name;
    std::string type_name;
    AstPtr default_value;
    std::vector<KeywordArg> constraints;
};

// (output expr)
struct OutputNode {
    AstPtr value;
};

// (op args... :key val ...)
struct CallNode {
    std::string op;
    std::vector<AstPtr> args;
    std::vector<KeywordArg> kwargs;
};

// Literal number
struct NumberNode {
    double value;
};

// Literal string
struct StringNode {
    std::string value;
};

// Symbol reference
struct SymbolNode {
    std::string name;
};

struct AstNode {
    std::variant<
        DefNode,
        ParamNode,
        OutputNode,
        CallNode,
        NumberNode,
        StringNode,
        SymbolNode
    > data;
    uint32_t line;
    uint32_t col;
};

// Top-level program: list of (def ...), (param ...), (output ...)
struct Program {
    std::vector<AstPtr> statements;
};

} // namespace joon::dsl
```

- [ ] **Step 2: Write parser test**

```cpp
// tests/test_parser.cpp
#include <catch2/catch_all.hpp>
#include "dsl/parser.h"

using namespace joon::dsl;

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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd projects/joon && make config=debug joon-tests && ./build/bin/Debug/joon-tests --reporter compact "[parser]"
```

Expected: Compile error — `dsl/parser.h` not found.

- [ ] **Step 4: Write parser.h**

```cpp
// src/dsl/parser.h
#pragma once

#include "dsl/ast.h"
#include "dsl/token.h"
#include <string>
#include <string_view>
#include <vector>
#include <stdexcept>

namespace joon::dsl {

struct ParseError : std::runtime_error {
    uint32_t line, col;
    ParseError(const std::string& msg, uint32_t line, uint32_t col)
        : std::runtime_error(msg), line(line), col(col) {}
};

class Parser {
public:
    explicit Parser(std::string_view source);
    Program parse();

private:
    std::vector<Token> tokens_;
    size_t pos_ = 0;

    const Token& peek() const;
    const Token& advance();
    bool at_end() const;
    void expect(TokenType type, const std::string& context);

    AstPtr parse_form();          // ( ... )
    AstPtr parse_def();           // (def name expr)
    AstPtr parse_param();         // (param name type default ...)
    AstPtr parse_output();        // (output expr)
    AstPtr parse_call(const Token& op); // (op args... :key val ...)
    AstPtr parse_expr();          // atom or form
};

} // namespace joon::dsl
```

- [ ] **Step 5: Write parser.cpp**

```cpp
// src/dsl/parser.cpp
#include "dsl/parser.h"
#include "dsl/lexer.h"

namespace joon::dsl {

Parser::Parser(std::string_view source) {
    Lexer lexer(source);
    tokens_ = lexer.tokenize();
}

const Token& Parser::peek() const {
    static Token eof{ TokenType::Eof, "", 0, 0 };
    if (pos_ >= tokens_.size()) return eof;
    return tokens_[pos_];
}

const Token& Parser::advance() {
    return tokens_[pos_++];
}

bool Parser::at_end() const {
    return pos_ >= tokens_.size();
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
    expect(TokenType::LParen, "'('");
    advance(); // skip (

    expect(TokenType::Symbol, "form name");
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

    expect(TokenType::RParen, "')'");
    advance(); // skip )
    return result;
}

AstPtr Parser::parse_def() {
    auto line = peek().line, col = peek().col;
    advance(); // skip 'def'

    expect(TokenType::Symbol, "binding name");
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

    expect(TokenType::Symbol, "param name");
    auto name = advance().text;

    expect(TokenType::Symbol, "param type");
    auto type_name = advance().text;

    auto default_value = parse_expr();

    std::vector<KeywordArg> constraints;
    while (peek().type == TokenType::Keyword) {
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
    auto op_name = advance().text; // consume op

    std::vector<AstPtr> args;
    std::vector<KeywordArg> kwargs;

    while (peek().type != TokenType::RParen) {
        if (peek().type == TokenType::Keyword) {
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

AstPtr Parser::parse_expr() {
    const auto& tok = peek();

    if (tok.type == TokenType::LParen) {
        return parse_form();
    }

    if (tok.type == TokenType::Number) {
        auto t = advance();
        auto node = std::make_unique<AstNode>();
        node->data = NumberNode{ std::stod(t.text) };
        node->line = t.line;
        node->col = t.col;
        return node;
    }

    if (tok.type == TokenType::String) {
        auto t = advance();
        auto node = std::make_unique<AstNode>();
        node->data = StringNode{ t.text };
        node->line = t.line;
        node->col = t.col;
        return node;
    }

    if (tok.type == TokenType::Symbol) {
        auto t = advance();
        auto node = std::make_unique<AstNode>();
        node->data = SymbolNode{ t.text };
        node->line = t.line;
        node->col = t.col;
        return node;
    }

    throw ParseError("Unexpected token: " + tok.text, tok.line, tok.col);
}

} // namespace joon::dsl
```

- [ ] **Step 6: Run tests**

```bash
cd projects/joon && make config=debug joon-tests && ./build/bin/Debug/joon-tests --reporter compact "[parser]"
```

Expected: All 6 tests pass.

- [ ] **Step 7: Commit**

```bash
git add projects/joon/src/dsl/ast.h projects/joon/src/dsl/parser.h projects/joon/src/dsl/parser.cpp projects/joon/tests/test_parser.cpp
git commit -m "feat(joon): recursive descent S-expression parser with AST"
```

---

## Task 4: IR Graph & Type Checker

**Files:**
- Create: `projects/joon/src/ir/node.h`
- Create: `projects/joon/src/ir/ir_graph.h`
- Create: `projects/joon/src/ir/ir_graph.cpp`
- Create: `projects/joon/src/ir/type_checker.h`
- Create: `projects/joon/src/ir/type_checker.cpp`
- Create: `projects/joon/tests/test_type_checker.cpp`

- [ ] **Step 1: Write IR node types**

```cpp
// src/ir/node.h
#pragma once

#include <joon/types.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <cstdint>

namespace joon::ir {

enum class Tier { GPU, CPU };

// An edge connects one node's output to another node's input
struct Edge {
    uint32_t from_node;
    uint32_t to_node;
    uint32_t to_input; // which input slot on the target
};

// A keyword argument resolved to a value
struct ResolvedKwarg {
    std::string name;
    Value value; // constant value (numbers, etc.)
};

struct Node {
    uint32_t id;
    std::string op;               // "image", "noise", "+", "blur", etc.
    Tier tier;
    Type output_type;
    std::vector<uint32_t> inputs; // node IDs feeding into this node
    std::vector<ResolvedKwarg> kwargs;

    // For constant nodes
    bool is_constant = false;
    Value constant_value;

    // For string args (file paths)
    std::string string_arg;
};

struct ParamInfo {
    std::string name;
    Type type;
    Value default_value;
    std::unordered_map<std::string, float> constraints; // min, max, etc.
    uint32_t node_id; // the node this param feeds
};

struct OutputInfo {
    uint32_t node_id;
};

} // namespace joon::ir
```

- [ ] **Step 2: Write IR graph**

```cpp
// src/ir/ir_graph.h
#pragma once

#include "ir/node.h"
#include "dsl/ast.h"
#include <vector>
#include <unordered_map>
#include <string>
#include <variant>

namespace joon::ir {

struct Diagnostic {
    enum class Level { Error, Warning };
    Level level;
    std::string message;
    uint32_t line, col;
};

class IRGraph {
public:
    std::vector<Node> nodes;
    std::vector<Edge> edges;
    std::vector<ParamInfo> params;
    std::vector<OutputInfo> outputs;
    std::vector<Diagnostic> diagnostics;

    // Build IR from AST
    static IRGraph from_ast(const dsl::Program& program);

    // Get topological order for evaluation
    std::vector<uint32_t> topological_order() const;

    const Node* find_node(uint32_t id) const;
    const Node* find_node_by_name(const std::string& name) const;

private:
    std::unordered_map<std::string, uint32_t> name_to_node_;

    uint32_t add_node(const std::string& op, Tier tier);
    void resolve_ast(const dsl::Program& program);
    uint32_t resolve_expr(const dsl::AstNode& expr);
};
```

- [ ] **Step 3: Write ir_graph.cpp**

```cpp
// src/ir/ir_graph.cpp
#include "ir/ir_graph.h"
#include <algorithm>
#include <queue>
#include <stdexcept>

namespace joon::ir {

IRGraph IRGraph::from_ast(const dsl::Program& program) {
    IRGraph graph;
    graph.resolve_ast(program);
    return graph;
}

uint32_t IRGraph::add_node(const std::string& op, Tier tier) {
    uint32_t id = static_cast<uint32_t>(nodes.size());
    nodes.push_back({ id, op, tier, Type::Float, {}, {}, false, {}, {} });
    return id;
}

void IRGraph::resolve_ast(const dsl::Program& program) {
    for (auto& stmt : program.statements) {
        if (auto* def = std::get_if<dsl::DefNode>(&stmt->data)) {
            uint32_t node_id = resolve_expr(*def->value);
            name_to_node_[def->name] = node_id;
        } else if (auto* param = std::get_if<dsl::ParamNode>(&stmt->data)) {
            uint32_t id = add_node("param", Tier::CPU);
            nodes[id].is_constant = true;
            nodes[id].constant_value = std::stof(
                std::get<dsl::NumberNode>(param->default_value->data).value
            );

            ParamInfo pi;
            pi.name = param->name;
            pi.type = Type::Float; // resolved by type checker
            if (param->type_name == "float") pi.type = Type::Float;
            else if (param->type_name == "int") pi.type = Type::Int;
            else if (param->type_name == "vec3") pi.type = Type::Vec3;
            else if (param->type_name == "vec4") pi.type = Type::Vec4;

            pi.default_value = nodes[id].constant_value;
            for (auto& c : param->constraints) {
                auto* num = std::get_if<dsl::NumberNode>(&c.value->data);
                if (num) pi.constraints[c.name] = static_cast<float>(num->value);
            }
            pi.node_id = id;
            params.push_back(pi);
            name_to_node_[param->name] = id;
        } else if (auto* output = std::get_if<dsl::OutputNode>(&stmt->data)) {
            uint32_t node_id = resolve_expr(*output->value);
            outputs.push_back({ node_id });
        }
    }
}

uint32_t IRGraph::resolve_expr(const dsl::AstNode& expr) {
    if (auto* num = std::get_if<dsl::NumberNode>(&expr.data)) {
        uint32_t id = add_node("constant", Tier::CPU);
        nodes[id].is_constant = true;
        nodes[id].constant_value = static_cast<float>(num->value);
        return id;
    }

    if (auto* str = std::get_if<dsl::StringNode>(&expr.data)) {
        uint32_t id = add_node("string_constant", Tier::CPU);
        nodes[id].string_arg = str->value;
        return id;
    }

    if (auto* sym = std::get_if<dsl::SymbolNode>(&expr.data)) {
        auto it = name_to_node_.find(sym->name);
        if (it == name_to_node_.end()) {
            diagnostics.push_back({
                Diagnostic::Level::Error,
                "Undefined symbol: " + sym->name,
                expr.line, expr.col
            });
            return add_node("error", Tier::CPU);
        }
        return it->second;
    }

    if (auto* call = std::get_if<dsl::CallNode>(&expr.data)) {
        // Determine tier based on op
        Tier tier = Tier::GPU;
        if (call->op == "image" || call->op == "color" || call->op == "save") {
            tier = Tier::CPU;
        }

        uint32_t id = add_node(call->op, tier);

        // Resolve positional args as input edges
        for (auto& arg : call->args) {
            uint32_t input_id = resolve_expr(*arg);
            uint32_t input_slot = static_cast<uint32_t>(nodes[id].inputs.size());
            nodes[id].inputs.push_back(input_id);
            edges.push_back({ input_id, id, input_slot });
        }

        // Resolve keyword args
        for (auto& kw : call->kwargs) {
            if (auto* num = std::get_if<dsl::NumberNode>(&kw.value->data)) {
                nodes[id].kwargs.push_back({ kw.name, static_cast<float>(num->value) });
            } else if (auto* str = std::get_if<dsl::StringNode>(&kw.value->data)) {
                nodes[id].string_arg = str->value;
            }
        }

        return id;
    }

    diagnostics.push_back({
        Diagnostic::Level::Error,
        "Unexpected expression",
        expr.line, expr.col
    });
    return add_node("error", Tier::CPU);
}

std::vector<uint32_t> IRGraph::topological_order() const {
    std::vector<uint32_t> in_degree(nodes.size(), 0);
    std::vector<std::vector<uint32_t>> dependents(nodes.size());

    for (auto& edge : edges) {
        in_degree[edge.to_node]++;
        dependents[edge.from_node].push_back(edge.to_node);
    }

    std::queue<uint32_t> queue;
    for (uint32_t i = 0; i < nodes.size(); i++) {
        if (in_degree[i] == 0) queue.push(i);
    }

    std::vector<uint32_t> order;
    while (!queue.empty()) {
        uint32_t n = queue.front();
        queue.pop();
        order.push_back(n);
        for (uint32_t dep : dependents[n]) {
            if (--in_degree[dep] == 0) queue.push(dep);
        }
    }

    return order;
}

const Node* IRGraph::find_node(uint32_t id) const {
    if (id < nodes.size()) return &nodes[id];
    return nullptr;
}

const Node* IRGraph::find_node_by_name(const std::string& name) const {
    auto it = name_to_node_.find(name);
    if (it != name_to_node_.end()) return &nodes[it->second];
    return nullptr;
}

} // namespace joon::ir
```

- [ ] **Step 4: Write type checker**

```cpp
// src/ir/type_checker.h
#pragma once

#include "ir/ir_graph.h"

namespace joon::ir {

// Run type inference and checking on the graph.
// Populates node output_type fields and appends diagnostics for errors.
void type_check(IRGraph& graph);

} // namespace joon::ir
```

```cpp
// src/ir/type_checker.cpp
#include "ir/type_checker.h"

namespace joon::ir {

static Type promote(Type a, Type b) {
    if (a == b) return a;
    // Float promotes into higher types
    if (a == Type::Float) return b;
    if (b == Type::Float) return a;
    // Vec promotes: vec3 * image = image
    if (a == Type::Image || b == Type::Image) return Type::Image;
    if (a == Type::Vec4 || b == Type::Vec4) return Type::Vec4;
    if (a == Type::Vec3 || b == Type::Vec3) return Type::Vec3;
    if (a == Type::Vec2 || b == Type::Vec2) return Type::Vec2;
    return a;
}

static bool is_math_op(const std::string& op) {
    return op == "+" || op == "-" || op == "*" || op == "/";
}

void type_check(IRGraph& graph) {
    auto order = graph.topological_order();

    for (uint32_t id : order) {
        auto& node = graph.nodes[id];

        if (node.op == "constant" || node.op == "param") {
            // Already typed from construction (Float by default)
            continue;
        }

        if (node.op == "image") {
            node.output_type = Type::Image;
            continue;
        }

        if (node.op == "color") {
            node.output_type = Type::Vec3;
            continue;
        }

        if (node.op == "noise") {
            node.output_type = Type::Float;
            continue;
        }

        if (is_math_op(node.op)) {
            if (node.inputs.size() != 2) {
                graph.diagnostics.push_back({
                    Diagnostic::Level::Error,
                    "Operator " + node.op + " expects 2 arguments, got " +
                        std::to_string(node.inputs.size()),
                    0, 0
                });
                continue;
            }
            Type a = graph.nodes[node.inputs[0]].output_type;
            Type b = graph.nodes[node.inputs[1]].output_type;
            node.output_type = promote(a, b);
            continue;
        }

        // Image operations: blur, levels, blend, invert, threshold
        if (node.op == "invert" || node.op == "threshold") {
            if (!node.inputs.empty()) {
                node.output_type = graph.nodes[node.inputs[0]].output_type;
            }
            continue;
        }

        if (node.op == "blur" || node.op == "levels") {
            if (!node.inputs.empty()) {
                node.output_type = graph.nodes[node.inputs[0]].output_type;
            }
            continue;
        }

        if (node.op == "blend") {
            if (node.inputs.size() >= 2) {
                Type a = graph.nodes[node.inputs[0]].output_type;
                Type b = graph.nodes[node.inputs[1]].output_type;
                node.output_type = promote(a, b);
            }
            continue;
        }

        if (node.op == "save") {
            if (!node.inputs.empty()) {
                node.output_type = graph.nodes[node.inputs[0]].output_type;
            }
            continue;
        }

        graph.diagnostics.push_back({
            Diagnostic::Level::Error,
            "Unknown node type: " + node.op,
            0, 0
        });
    }
}

} // namespace joon::ir
```

- [ ] **Step 5: Write type checker tests**

```cpp
// tests/test_type_checker.cpp
#include <catch2/catch_all.hpp>
#include "dsl/parser.h"
#include "ir/ir_graph.h"
#include "ir/type_checker.h"

using namespace joon;

static ir::IRGraph build(const char* src) {
    dsl::Parser parser(src);
    auto program = parser.parse();
    auto graph = ir::IRGraph::from_ast(program);
    ir::type_check(graph);
    return graph;
}

TEST_CASE("Type: noise is float", "[types]") {
    auto g = build("(def n (noise :scale 4.0)) (output n)");
    auto* n = g.find_node_by_name("n");
    REQUIRE(n);
    CHECK(n->output_type == Type::Float);
}

TEST_CASE("Type: image load is image", "[types]") {
    auto g = build(R"((def b (image "t.png")) (output b))");
    auto* b = g.find_node_by_name("b");
    REQUIRE(b);
    CHECK(b->output_type == Type::Image);
}

TEST_CASE("Type: float * image promotes to image", "[types]") {
    auto g = build(R"(
        (def b (image "t.png"))
        (def n (noise :scale 1.0))
        (def r (* b n))
        (output r)
    )");
    auto* r = g.find_node_by_name("r");
    REQUIRE(r);
    CHECK(r->output_type == Type::Image);
}

TEST_CASE("Type: color is vec3", "[types]") {
    auto g = build("(def c (color 0.8 0.3 0.1)) (output c)");
    auto* c = g.find_node_by_name("c");
    REQUIRE(c);
    CHECK(c->output_type == Type::Vec3);
}

TEST_CASE("Type: undefined symbol produces error", "[types]") {
    auto g = build("(def r (* x 1.0)) (output r)");
    bool has_error = false;
    for (auto& d : g.diagnostics) {
        if (d.level == ir::Diagnostic::Level::Error &&
            d.message.find("Undefined symbol") != std::string::npos) {
            has_error = true;
        }
    }
    CHECK(has_error);
}

TEST_CASE("Type: topological order is valid", "[types]") {
    auto g = build(R"(
        (def b (image "t.png"))
        (def n (noise :scale 1.0))
        (def r (* b n))
        (output r)
    )");
    auto order = g.topological_order();
    REQUIRE(order.size() == g.nodes.size());
}

TEST_CASE("Diagnostics: no errors on valid graph", "[types]") {
    auto g = build(R"(
        (def b (image "t.png"))
        (def n (noise :scale 4.0))
        (def r (* b n))
        (output r)
    )");
    for (auto& d : g.diagnostics) {
        REQUIRE(d.level != ir::Diagnostic::Level::Error);
    }
}
```

- [ ] **Step 6: Run tests**

```bash
cd projects/joon && make config=debug joon-tests && ./build/bin/Debug/joon-tests --reporter compact "[types]"
```

Expected: All 7 tests pass.

- [ ] **Step 7: Commit**

```bash
git add projects/joon/src/ir/ projects/joon/tests/test_type_checker.cpp
git commit -m "feat(joon): IR graph construction and type checker with broadcast promotion"
```

---

## Task 5: Vulkan Context & Resource Pool

**Files:**
- Create: `projects/joon/src/vulkan/device.h`
- Create: `projects/joon/src/vulkan/device.cpp`
- Create: `projects/joon/src/vulkan/resource_pool.h`
- Create: `projects/joon/src/vulkan/resource_pool.cpp`
- Create: `projects/joon/include/joon/context.h`
- Create: `projects/joon/src/context.cpp`

- [ ] **Step 1: Write Vulkan device wrapper**

```cpp
// src/vulkan/device.h
#pragma once

#include <vulkan/vulkan.h>
#include <vk_mem_alloc.h>
#include <memory>

namespace joon::vk {

struct Device {
    VkInstance instance = VK_NULL_HANDLE;
    VkPhysicalDevice physical_device = VK_NULL_HANDLE;
    VkDevice device = VK_NULL_HANDLE;
    VkQueue compute_queue = VK_NULL_HANDLE;
    VkQueue graphics_queue = VK_NULL_HANDLE;
    uint32_t compute_family = 0;
    uint32_t graphics_family = 0;
    VkCommandPool command_pool = VK_NULL_HANDLE;
    VmaAllocator allocator = VK_NULL_HANDLE;

    static std::unique_ptr<Device> create(bool enable_validation = true);
    ~Device();

    Device(const Device&) = delete;
    Device& operator=(const Device&) = delete;

    VkCommandBuffer begin_single_command() const;
    void end_single_command(VkCommandBuffer cmd) const;
};

} // namespace joon::vk
```

- [ ] **Step 2: Write device.cpp**

```cpp
// src/vulkan/device.cpp
#define VMA_IMPLEMENTATION
#include "vulkan/device.h"
#include <stdexcept>
#include <vector>

namespace joon::vk {

std::unique_ptr<Device> Device::create(bool enable_validation) {
    auto dev = std::make_unique<Device>();

    // Instance
    VkApplicationInfo app_info{};
    app_info.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app_info.pApplicationName = "Joon";
    app_info.applicationVersion = VK_MAKE_VERSION(0, 1, 0);
    app_info.pEngineName = "Joon Engine";
    app_info.engineVersion = VK_MAKE_VERSION(0, 1, 0);
    app_info.apiVersion = VK_API_VERSION_1_2;

    VkInstanceCreateInfo create_info{};
    create_info.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    create_info.pApplicationInfo = &app_info;

    std::vector<const char*> layers;
    if (enable_validation) {
        layers.push_back("VK_LAYER_KHRONOS_validation");
    }
    create_info.enabledLayerCount = static_cast<uint32_t>(layers.size());
    create_info.ppEnabledLayerNames = layers.data();

    if (vkCreateInstance(&create_info, nullptr, &dev->instance) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create Vulkan instance");
    }

    // Physical device — pick first discrete GPU, fallback to any
    uint32_t device_count = 0;
    vkEnumeratePhysicalDevices(dev->instance, &device_count, nullptr);
    std::vector<VkPhysicalDevice> devices(device_count);
    vkEnumeratePhysicalDevices(dev->instance, &device_count, devices.data());

    dev->physical_device = devices[0]; // default
    for (auto& pd : devices) {
        VkPhysicalDeviceProperties props;
        vkGetPhysicalDeviceProperties(pd, &props);
        if (props.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) {
            dev->physical_device = pd;
            break;
        }
    }

    // Queue families
    uint32_t family_count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(dev->physical_device, &family_count, nullptr);
    std::vector<VkQueueFamilyProperties> families(family_count);
    vkGetPhysicalDeviceQueueFamilyProperties(dev->physical_device, &family_count, families.data());

    for (uint32_t i = 0; i < family_count; i++) {
        if (families[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) {
            dev->graphics_family = i;
        }
        if (families[i].queueFlags & VK_QUEUE_COMPUTE_BIT) {
            dev->compute_family = i;
        }
    }

    // Logical device
    float priority = 1.0f;
    std::vector<VkDeviceQueueCreateInfo> queue_infos;

    VkDeviceQueueCreateInfo qi{};
    qi.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    qi.queueFamilyIndex = dev->graphics_family;
    qi.queueCount = 1;
    qi.pQueuePriorities = &priority;
    queue_infos.push_back(qi);

    if (dev->compute_family != dev->graphics_family) {
        qi.queueFamilyIndex = dev->compute_family;
        queue_infos.push_back(qi);
    }

    VkDeviceCreateInfo device_info{};
    device_info.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    device_info.queueCreateInfoCount = static_cast<uint32_t>(queue_infos.size());
    device_info.pQueueCreateInfos = queue_infos.data();

    if (vkCreateDevice(dev->physical_device, &device_info, nullptr, &dev->device) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create Vulkan device");
    }

    vkGetDeviceQueue(dev->device, dev->graphics_family, 0, &dev->graphics_queue);
    vkGetDeviceQueue(dev->device, dev->compute_family, 0, &dev->compute_queue);

    // Command pool
    VkCommandPoolCreateInfo pool_info{};
    pool_info.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    pool_info.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    pool_info.queueFamilyIndex = dev->compute_family;
    vkCreateCommandPool(dev->device, &pool_info, nullptr, &dev->command_pool);

    // VMA allocator
    VmaAllocatorCreateInfo alloc_info{};
    alloc_info.physicalDevice = dev->physical_device;
    alloc_info.device = dev->device;
    alloc_info.instance = dev->instance;
    alloc_info.vulkanApiVersion = VK_API_VERSION_1_2;
    vmaCreateAllocator(&alloc_info, &dev->allocator);

    return dev;
}

Device::~Device() {
    if (device) vkDeviceWaitIdle(device);
    if (allocator) vmaDestroyAllocator(allocator);
    if (command_pool) vkDestroyCommandPool(device, command_pool, nullptr);
    if (device) vkDestroyDevice(device, nullptr);
    if (instance) vkDestroyInstance(instance, nullptr);
}

VkCommandBuffer Device::begin_single_command() const {
    VkCommandBufferAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    alloc_info.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    alloc_info.commandPool = command_pool;
    alloc_info.commandBufferCount = 1;

    VkCommandBuffer cmd;
    vkAllocateCommandBuffers(device, &alloc_info, &cmd);

    VkCommandBufferBeginInfo begin_info{};
    begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vkBeginCommandBuffer(cmd, &begin_info);
    return cmd;
}

void Device::end_single_command(VkCommandBuffer cmd) const {
    vkEndCommandBuffer(cmd);
    VkSubmitInfo submit{};
    submit.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit.commandBufferCount = 1;
    submit.pCommandBuffers = &cmd;
    vkQueueSubmit(compute_queue, 1, &submit, VK_NULL_HANDLE);
    vkQueueWaitIdle(compute_queue);
    vkFreeCommandBuffers(device, command_pool, 1, &cmd);
}

} // namespace joon::vk
```

- [ ] **Step 3: Write resource pool**

```cpp
// src/vulkan/resource_pool.h
#pragma once

#include "vulkan/device.h"
#include <joon/types.h>
#include <unordered_map>

namespace joon::vk {

struct GpuImage {
    VkImage image = VK_NULL_HANDLE;
    VkImageView view = VK_NULL_HANDLE;
    VmaAllocation allocation = VK_NULL_HANDLE;
    uint32_t width, height;
    VkFormat format;
};

class ResourcePool {
public:
    explicit ResourcePool(Device& device);
    ~ResourcePool();

    // Allocate an image for a node's output
    GpuImage* alloc_image(uint32_t node_id, uint32_t width, uint32_t height,
                          VkFormat format = VK_FORMAT_R32G32B32A32_SFLOAT);

    // Get existing image for a node
    GpuImage* get_image(uint32_t node_id);

    // Upload CPU data to a GPU image
    void upload(GpuImage* img, const void* data, size_t size);

    // Download GPU image to CPU
    void download(GpuImage* img, void* data, size_t size);

    // Release all resources
    void clear();

private:
    Device& device_;
    std::unordered_map<uint32_t, GpuImage> images_;
};

} // namespace joon::vk
```

- [ ] **Step 4: Write resource_pool.cpp**

```cpp
// src/vulkan/resource_pool.cpp
#include "vulkan/resource_pool.h"
#include <cstring>
#include <stdexcept>

namespace joon::vk {

ResourcePool::ResourcePool(Device& device) : device_(device) {}

ResourcePool::~ResourcePool() { clear(); }

GpuImage* ResourcePool::alloc_image(uint32_t node_id, uint32_t width, uint32_t height,
                                     VkFormat format) {
    // Clean up existing if present
    auto it = images_.find(node_id);
    if (it != images_.end()) {
        auto& old = it->second;
        vkDestroyImageView(device_.device, old.view, nullptr);
        vmaDestroyImage(device_.allocator, old.image, old.allocation);
        images_.erase(it);
    }

    GpuImage img{};
    img.width = width;
    img.height = height;
    img.format = format;

    VkImageCreateInfo img_info{};
    img_info.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    img_info.imageType = VK_IMAGE_TYPE_2D;
    img_info.format = format;
    img_info.extent = { width, height, 1 };
    img_info.mipLevels = 1;
    img_info.arrayLayers = 1;
    img_info.samples = VK_SAMPLE_COUNT_1_BIT;
    img_info.tiling = VK_IMAGE_TILING_OPTIMAL;
    img_info.usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
                     VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;

    VmaAllocationCreateInfo alloc_info{};
    alloc_info.usage = VMA_MEMORY_USAGE_GPU_ONLY;

    vmaCreateImage(device_.allocator, &img_info, &alloc_info,
                   &img.image, &img.allocation, nullptr);

    VkImageViewCreateInfo view_info{};
    view_info.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    view_info.image = img.image;
    view_info.viewType = VK_IMAGE_VIEW_TYPE_2D;
    view_info.format = format;
    view_info.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    view_info.subresourceRange.levelCount = 1;
    view_info.subresourceRange.layerCount = 1;

    vkCreateImageView(device_.device, &view_info, nullptr, &img.view);

    images_[node_id] = img;
    return &images_[node_id];
}

GpuImage* ResourcePool::get_image(uint32_t node_id) {
    auto it = images_.find(node_id);
    if (it == images_.end()) return nullptr;
    return &it->second;
}

void ResourcePool::upload(GpuImage* img, const void* data, size_t size) {
    // Create staging buffer
    VkBufferCreateInfo buf_info{};
    buf_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    buf_info.size = size;
    buf_info.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT;

    VmaAllocationCreateInfo alloc_info{};
    alloc_info.usage = VMA_MEMORY_USAGE_CPU_ONLY;

    VkBuffer staging;
    VmaAllocation staging_alloc;
    vmaCreateBuffer(device_.allocator, &buf_info, &alloc_info, &staging, &staging_alloc, nullptr);

    void* mapped;
    vmaMapMemory(device_.allocator, staging_alloc, &mapped);
    memcpy(mapped, data, size);
    vmaUnmapMemory(device_.allocator, staging_alloc);

    // Copy to image
    auto cmd = device_.begin_single_command();

    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.image = img->image;
    barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    barrier.subresourceRange.levelCount = 1;
    barrier.subresourceRange.layerCount = 1;
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                         VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, nullptr, 0, nullptr, 1, &barrier);

    VkBufferImageCopy region{};
    region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    region.imageSubresource.layerCount = 1;
    region.imageExtent = { img->width, img->height, 1 };
    vkCmdCopyBufferToImage(cmd, staging, img->image,
                           VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

    barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, 0, 0, nullptr, 0, nullptr, 1, &barrier);

    device_.end_single_command(cmd);

    vmaDestroyBuffer(device_.allocator, staging, staging_alloc);
}

void ResourcePool::download(GpuImage* img, void* data, size_t size) {
    VkBufferCreateInfo buf_info{};
    buf_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    buf_info.size = size;
    buf_info.usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT;

    VmaAllocationCreateInfo alloc_info{};
    alloc_info.usage = VMA_MEMORY_USAGE_CPU_ONLY;

    VkBuffer staging;
    VmaAllocation staging_alloc;
    vmaCreateBuffer(device_.allocator, &buf_info, &alloc_info, &staging, &staging_alloc, nullptr);

    auto cmd = device_.begin_single_command();

    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.oldLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    barrier.image = img->image;
    barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    barrier.subresourceRange.levelCount = 1;
    barrier.subresourceRange.layerCount = 1;
    barrier.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, nullptr, 0, nullptr, 1, &barrier);

    VkBufferImageCopy region{};
    region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    region.imageSubresource.layerCount = 1;
    region.imageExtent = { img->width, img->height, 1 };
    vkCmdCopyImageToBuffer(cmd, img->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           staging, 1, &region);

    device_.end_single_command(cmd);

    void* mapped;
    vmaMapMemory(device_.allocator, staging_alloc, &mapped);
    memcpy(data, mapped, size);
    vmaUnmapMemory(device_.allocator, staging_alloc);

    vmaDestroyBuffer(device_.allocator, staging, staging_alloc);
}

void ResourcePool::clear() {
    for (auto& [id, img] : images_) {
        vkDestroyImageView(device_.device, img.view, nullptr);
        vmaDestroyImage(device_.allocator, img.image, img.allocation);
    }
    images_.clear();
}

} // namespace joon::vk
```

- [ ] **Step 5: Write public Context header and implementation**

```cpp
// include/joon/context.h
#pragma once

#include <memory>

namespace joon {

namespace vk { struct Device; class ResourcePool; }

class Graph;
class Evaluator;

class Context {
public:
    static std::unique_ptr<Context> create();
    ~Context();

    Graph parse_file(const char* path);
    Graph parse_string(const char* source);
    std::unique_ptr<Evaluator> create_evaluator(const Graph& graph);

    vk::Device& device() const;
    vk::ResourcePool& pool() const;

private:
    Context();
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace joon
```

```cpp
// src/context.cpp
#include <joon/context.h>
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include <fstream>
#include <sstream>

namespace joon {

struct Context::Impl {
    std::unique_ptr<vk::Device> device;
    std::unique_ptr<vk::ResourcePool> pool;
};

Context::Context() : impl_(std::make_unique<Impl>()) {}
Context::~Context() = default;

std::unique_ptr<Context> Context::create() {
    auto ctx = std::unique_ptr<Context>(new Context());
    ctx->impl_->device = vk::Device::create();
    ctx->impl_->pool = std::make_unique<vk::ResourcePool>(*ctx->impl_->device);
    return ctx;
}

vk::Device& Context::device() const { return *impl_->device; }
vk::ResourcePool& Context::pool() const { return *impl_->pool; }

} // namespace joon
```

- [ ] **Step 6: Verify it compiles**

```bash
cd projects/joon && make config=debug joon-lib
```

Expected: Compiles without errors. No runtime test — Vulkan tests require a GPU.

- [ ] **Step 7: Commit**

```bash
git add projects/joon/src/vulkan/ projects/joon/include/joon/context.h projects/joon/src/context.cpp
git commit -m "feat(joon): Vulkan device, VMA resource pool, and Context API"
```

---

## Task 6: Compute Shaders

**Files:**
- Create: `projects/joon/shaders/add.comp`
- Create: `projects/joon/shaders/sub.comp`
- Create: `projects/joon/shaders/mul.comp`
- Create: `projects/joon/shaders/div.comp`
- Create: `projects/joon/shaders/noise.comp`
- Create: `projects/joon/shaders/blur.comp`
- Create: `projects/joon/shaders/levels.comp`
- Create: `projects/joon/shaders/blend.comp`
- Create: `projects/joon/shaders/invert.comp`
- Create: `projects/joon/shaders/threshold.comp`
- Create: `projects/joon/shaders/compile.bat`

- [ ] **Step 1: Write element-wise math shaders**

All math shaders follow the same pattern — two input images, one output image, one operation.

```glsl
// shaders/add.comp
#version 450
layout(local_size_x = 16, local_size_y = 16) in;

layout(set = 0, binding = 0, rgba32f) uniform readonly image2D input_a;
layout(set = 0, binding = 1, rgba32f) uniform readonly image2D input_b;
layout(set = 0, binding = 2, rgba32f) uniform writeonly image2D output_img;

void main() {
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(output_img);
    if (pos.x >= size.x || pos.y >= size.y) return;

    vec4 a = imageLoad(input_a, pos);
    vec4 b = imageLoad(input_b, pos);
    imageStore(output_img, pos, a + b);
}
```

```glsl
// shaders/sub.comp — identical but a - b
// shaders/mul.comp — identical but a * b
// shaders/div.comp — identical but a / max(b, vec4(0.0001))
```

- [ ] **Step 2: Write noise shader**

```glsl
// shaders/noise.comp
#version 450
layout(local_size_x = 16, local_size_y = 16) in;

layout(set = 0, binding = 0, rgba32f) uniform writeonly image2D output_img;

layout(push_constant) uniform Params {
    float scale;
    float octaves;
    float width;
    float height;
} params;

// Simplex-style noise hash
vec2 hash(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}

float simplex_noise(vec2 p) {
    const float K1 = 0.366025404; // (sqrt(3)-1)/2
    const float K2 = 0.211324865; // (3-sqrt(3))/6
    vec2 i = floor(p + (p.x + p.y) * K1);
    vec2 a = p - i + (i.x + i.y) * K2;
    float m = step(a.y, a.x);
    vec2 o = vec2(m, 1.0 - m);
    vec2 b = a - o + K2;
    vec2 c = a - 1.0 + 2.0 * K2;
    vec3 h = max(0.5 - vec3(dot(a, a), dot(b, b), dot(c, c)), 0.0);
    vec3 n = h * h * h * h * vec3(dot(a, hash(i)), dot(b, hash(i + o)), dot(c, hash(i + 1.0)));
    return dot(n, vec3(70.0));
}

void main() {
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(output_img);
    if (pos.x >= size.x || pos.y >= size.y) return;

    vec2 uv = vec2(pos) / vec2(params.width, params.height);

    float value = 0.0;
    float amplitude = 1.0;
    float frequency = params.scale;
    int oct = int(params.octaves);

    for (int i = 0; i < oct; i++) {
        value += amplitude * simplex_noise(uv * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
    }

    value = value * 0.5 + 0.5; // normalize to 0-1
    imageStore(output_img, pos, vec4(value, value, value, 1.0));
}
```

- [ ] **Step 3: Write image operation shaders**

```glsl
// shaders/invert.comp
#version 450
layout(local_size_x = 16, local_size_y = 16) in;

layout(set = 0, binding = 0, rgba32f) uniform readonly image2D input_img;
layout(set = 0, binding = 1, rgba32f) uniform writeonly image2D output_img;

void main() {
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(output_img);
    if (pos.x >= size.x || pos.y >= size.y) return;

    vec4 c = imageLoad(input_img, pos);
    imageStore(output_img, pos, vec4(1.0 - c.rgb, c.a));
}
```

```glsl
// shaders/threshold.comp
#version 450
layout(local_size_x = 16, local_size_y = 16) in;

layout(set = 0, binding = 0, rgba32f) uniform readonly image2D input_img;
layout(set = 0, binding = 1, rgba32f) uniform writeonly image2D output_img;

layout(push_constant) uniform Params {
    float threshold;
} params;

void main() {
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(output_img);
    if (pos.x >= size.x || pos.y >= size.y) return;

    vec4 c = imageLoad(input_img, pos);
    float lum = dot(c.rgb, vec3(0.299, 0.587, 0.114));
    float v = step(params.threshold, lum);
    imageStore(output_img, pos, vec4(v, v, v, c.a));
}
```

```glsl
// shaders/levels.comp
#version 450
layout(local_size_x = 16, local_size_y = 16) in;

layout(set = 0, binding = 0, rgba32f) uniform readonly image2D input_img;
layout(set = 0, binding = 1, rgba32f) uniform writeonly image2D output_img;

layout(push_constant) uniform Params {
    float contrast;
    float brightness;
} params;

void main() {
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(output_img);
    if (pos.x >= size.x || pos.y >= size.y) return;

    vec4 c = imageLoad(input_img, pos);
    vec3 adjusted = (c.rgb - 0.5) * params.contrast + 0.5 + params.brightness;
    imageStore(output_img, pos, vec4(clamp(adjusted, 0.0, 1.0), c.a));
}
```

```glsl
// shaders/blend.comp
#version 450
layout(local_size_x = 16, local_size_y = 16) in;

layout(set = 0, binding = 0, rgba32f) uniform readonly image2D input_a;
layout(set = 0, binding = 1, rgba32f) uniform readonly image2D input_b;
layout(set = 0, binding = 2, rgba32f) uniform writeonly image2D output_img;

layout(push_constant) uniform Params {
    float opacity;
    int mode; // 0=normal, 1=multiply, 2=screen, 3=overlay
} params;

void main() {
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(output_img);
    if (pos.x >= size.x || pos.y >= size.y) return;

    vec4 a = imageLoad(input_a, pos);
    vec4 b = imageLoad(input_b, pos);

    vec3 result;
    if (params.mode == 0) result = b.rgb;                          // normal
    else if (params.mode == 1) result = a.rgb * b.rgb;             // multiply
    else if (params.mode == 2) result = 1.0 - (1.0 - a.rgb) * (1.0 - b.rgb); // screen
    else result = mix(2.0 * a.rgb * b.rgb,
                      1.0 - 2.0 * (1.0 - a.rgb) * (1.0 - b.rgb),
                      step(0.5, a.rgb));                           // overlay

    result = mix(a.rgb, result, params.opacity);
    imageStore(output_img, pos, vec4(result, max(a.a, b.a)));
}
```

```glsl
// shaders/blur.comp
#version 450
layout(local_size_x = 16, local_size_y = 16) in;

layout(set = 0, binding = 0, rgba32f) uniform readonly image2D input_img;
layout(set = 0, binding = 1, rgba32f) uniform writeonly image2D output_img;

layout(push_constant) uniform Params {
    float radius;
} params;

void main() {
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    ivec2 size = imageSize(output_img);
    if (pos.x >= size.x || pos.y >= size.y) return;

    int r = int(ceil(params.radius));
    vec4 sum = vec4(0.0);
    float weight_sum = 0.0;

    for (int dy = -r; dy <= r; dy++) {
        for (int dx = -r; dx <= r; dx++) {
            ivec2 sample_pos = clamp(pos + ivec2(dx, dy), ivec2(0), size - 1);
            float dist = length(vec2(dx, dy));
            float w = exp(-dist * dist / (2.0 * params.radius * params.radius));
            sum += w * imageLoad(input_img, sample_pos);
            weight_sum += w;
        }
    }

    imageStore(output_img, pos, sum / weight_sum);
}
```

- [ ] **Step 4: Write shader compilation script**

```bat
@echo off
REM shaders/compile.bat
REM Compile all GLSL compute shaders to SPIR-V
set GLSLC=%VULKAN_SDK%\Bin\glslc.exe

for %%f in (*.comp) do (
    echo Compiling %%f...
    %GLSLC% %%f -o %%~nf.spv
)
echo Done.
```

- [ ] **Step 5: Compile shaders and verify**

```bash
cd projects/joon/shaders
$VULKAN_SDK/Bin/glslc.exe add.comp -o add.spv
$VULKAN_SDK/Bin/glslc.exe noise.comp -o noise.spv
# ... repeat for all
```

Expected: All compile to .spv without errors.

- [ ] **Step 6: Commit**

```bash
git add projects/joon/shaders/
git commit -m "feat(joon): compute shaders for math ops, noise, blur, levels, blend, invert, threshold"
```

---

## Task 7: Pipeline Cache & Node Registry

**Files:**
- Create: `projects/joon/src/vulkan/pipeline_cache.h`
- Create: `projects/joon/src/vulkan/pipeline_cache.cpp`
- Create: `projects/joon/src/nodes/node_registry.h`
- Create: `projects/joon/src/nodes/node_registry.cpp`
- Create: `projects/joon/src/nodes/image_load.cpp`
- Create: `projects/joon/src/nodes/noise.cpp`
- Create: `projects/joon/src/nodes/color.cpp`
- Create: `projects/joon/src/nodes/math_ops.cpp`
- Create: `projects/joon/src/nodes/image_ops.cpp`
- Create: `projects/joon/src/nodes/save.cpp`

- [ ] **Step 1: Write pipeline cache**

```cpp
// src/vulkan/pipeline_cache.h
#pragma once

#include "vulkan/device.h"
#include <string>
#include <unordered_map>

namespace joon::vk {

struct ComputePipeline {
    VkShaderModule shader_module = VK_NULL_HANDLE;
    VkPipelineLayout layout = VK_NULL_HANDLE;
    VkPipeline pipeline = VK_NULL_HANDLE;
    VkDescriptorSetLayout desc_layout = VK_NULL_HANDLE;
};

class PipelineCache {
public:
    explicit PipelineCache(Device& device, const std::string& shader_dir);
    ~PipelineCache();

    // Get or create a pipeline for a shader name (e.g., "add", "noise")
    const ComputePipeline& get(const std::string& name,
                                uint32_t num_images,
                                uint32_t push_constant_size = 0);

private:
    Device& device_;
    std::string shader_dir_;
    std::unordered_map<std::string, ComputePipeline> pipelines_;

    std::vector<uint8_t> read_spirv(const std::string& name);
};
```

- [ ] **Step 2: Write pipeline_cache.cpp**

```cpp
// src/vulkan/pipeline_cache.cpp
#include "vulkan/pipeline_cache.h"
#include <fstream>
#include <stdexcept>

namespace joon::vk {

PipelineCache::PipelineCache(Device& device, const std::string& shader_dir)
    : device_(device), shader_dir_(shader_dir) {}

PipelineCache::~PipelineCache() {
    for (auto& [name, p] : pipelines_) {
        vkDestroyPipeline(device_.device, p.pipeline, nullptr);
        vkDestroyPipelineLayout(device_.device, p.layout, nullptr);
        vkDestroyDescriptorSetLayout(device_.device, p.desc_layout, nullptr);
        vkDestroyShaderModule(device_.device, p.shader_module, nullptr);
    }
}

std::vector<uint8_t> PipelineCache::read_spirv(const std::string& name) {
    std::string path = shader_dir_ + "/" + name + ".spv";
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file.is_open()) throw std::runtime_error("Cannot open shader: " + path);
    size_t size = file.tellg();
    std::vector<uint8_t> data(size);
    file.seekg(0);
    file.read(reinterpret_cast<char*>(data.data()), size);
    return data;
}

const ComputePipeline& PipelineCache::get(const std::string& name,
                                           uint32_t num_images,
                                           uint32_t push_constant_size) {
    auto it = pipelines_.find(name);
    if (it != pipelines_.end()) return it->second;

    ComputePipeline p{};

    // Shader module
    auto spirv = read_spirv(name);
    VkShaderModuleCreateInfo shader_info{};
    shader_info.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
    shader_info.codeSize = spirv.size();
    shader_info.pCode = reinterpret_cast<const uint32_t*>(spirv.data());
    vkCreateShaderModule(device_.device, &shader_info, nullptr, &p.shader_module);

    // Descriptor set layout — N storage images
    std::vector<VkDescriptorSetLayoutBinding> bindings(num_images);
    for (uint32_t i = 0; i < num_images; i++) {
        bindings[i].binding = i;
        bindings[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        bindings[i].descriptorCount = 1;
        bindings[i].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
    }

    VkDescriptorSetLayoutCreateInfo desc_info{};
    desc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    desc_info.bindingCount = num_images;
    desc_info.pBindings = bindings.data();
    vkCreateDescriptorSetLayout(device_.device, &desc_info, nullptr, &p.desc_layout);

    // Pipeline layout
    VkPipelineLayoutCreateInfo layout_info{};
    layout_info.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    layout_info.setLayoutCount = 1;
    layout_info.pSetLayouts = &p.desc_layout;

    VkPushConstantRange push_range{};
    if (push_constant_size > 0) {
        push_range.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
        push_range.offset = 0;
        push_range.size = push_constant_size;
        layout_info.pushConstantRangeCount = 1;
        layout_info.pPushConstantRanges = &push_range;
    }

    vkCreatePipelineLayout(device_.device, &layout_info, nullptr, &p.layout);

    // Compute pipeline
    VkComputePipelineCreateInfo pipeline_info{};
    pipeline_info.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
    pipeline_info.stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    pipeline_info.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
    pipeline_info.stage.module = p.shader_module;
    pipeline_info.stage.pName = "main";
    pipeline_info.layout = p.layout;

    vkCreateComputePipelines(device_.device, VK_NULL_HANDLE, 1, &pipeline_info, nullptr,
                             &p.pipeline);

    pipelines_[name] = p;
    return pipelines_[name];
}

} // namespace joon::vk
```

- [ ] **Step 3: Write node registry interface**

```cpp
// src/nodes/node_registry.h
#pragma once

#include "ir/node.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include "vulkan/pipeline_cache.h"
#include <functional>
#include <string>
#include <unordered_map>

namespace joon::nodes {

struct EvalContext {
    vk::Device& device;
    vk::ResourcePool& pool;
    vk::PipelineCache& pipelines;
    uint32_t default_width;
    uint32_t default_height;
    VkDescriptorPool desc_pool;
};

// A node executor takes the IR node and evaluation context, executes, and stores result in pool
using NodeExecutor = std::function<void(const ir::Node& node, EvalContext& ctx)>;

class NodeRegistry {
public:
    void register_node(const std::string& op, NodeExecutor executor);
    const NodeExecutor* find(const std::string& op) const;

    // Register all built-in nodes
    static NodeRegistry create_default();

private:
    std::unordered_map<std::string, NodeExecutor> executors_;
};

// Built-in node registration functions
void register_image_load(NodeRegistry& reg);
void register_noise(NodeRegistry& reg);
void register_color(NodeRegistry& reg);
void register_math_ops(NodeRegistry& reg);
void register_image_ops(NodeRegistry& reg);
void register_save(NodeRegistry& reg);

} // namespace joon::nodes
```

- [ ] **Step 4: Write node_registry.cpp and individual node implementations**

```cpp
// src/nodes/node_registry.cpp
#include "nodes/node_registry.h"

namespace joon::nodes {

void NodeRegistry::register_node(const std::string& op, NodeExecutor executor) {
    executors_[op] = std::move(executor);
}

const NodeExecutor* NodeRegistry::find(const std::string& op) const {
    auto it = executors_.find(op);
    if (it == executors_.end()) return nullptr;
    return &it->second;
}

NodeRegistry NodeRegistry::create_default() {
    NodeRegistry reg;
    register_image_load(reg);
    register_noise(reg);
    register_color(reg);
    register_math_ops(reg);
    register_image_ops(reg);
    register_save(reg);
    return reg;
}

} // namespace joon::nodes
```

```cpp
// src/nodes/image_load.cpp
#include "nodes/node_registry.h"
#define STB_IMAGE_IMPLEMENTATION
#include <stb/stb_image.h>

namespace joon::nodes {

void register_image_load(NodeRegistry& reg) {
    reg.register_node("image", [](const ir::Node& node, EvalContext& ctx) {
        // The first input should be a string constant with the path
        // Or the string_arg directly on this node
        std::string path = node.string_arg;
        if (path.empty() && !node.inputs.empty()) {
            auto* input_node = &ctx.pool; // handled by string_arg
        }

        int w, h, channels;
        float* data = stbi_loadf(path.c_str(), &w, &h, &channels, 4);
        if (!data) {
            // Allocate a black image as fallback
            auto* img = ctx.pool.alloc_image(node.id, ctx.default_width, ctx.default_height);
            std::vector<float> black(ctx.default_width * ctx.default_height * 4, 0.0f);
            ctx.pool.upload(img, black.data(), black.size() * sizeof(float));
            return;
        }

        auto* img = ctx.pool.alloc_image(node.id, w, h);
        ctx.pool.upload(img, data, w * h * 4 * sizeof(float));
        stbi_image_free(data);
    });
}

} // namespace joon::nodes
```

```cpp
// src/nodes/color.cpp
#include "nodes/node_registry.h"

namespace joon::nodes {

void register_color(NodeRegistry& reg) {
    reg.register_node("color", [](const ir::Node& node, EvalContext& ctx) {
        float r = 0, g = 0, b = 0;
        // Color args come as positional inputs (constant nodes)
        // or from kwargs
        // For now, read from constant inputs
        auto* img = ctx.pool.alloc_image(node.id, ctx.default_width, ctx.default_height);
        std::vector<float> data(ctx.default_width * ctx.default_height * 4);
        for (size_t i = 0; i < data.size(); i += 4) {
            data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = 1.0f;
        }
        ctx.pool.upload(img, data.data(), data.size() * sizeof(float));
    });
}

} // namespace joon::nodes
```

```cpp
// src/nodes/noise.cpp
#include "nodes/node_registry.h"

namespace joon::nodes {

void register_noise(NodeRegistry& reg) {
    reg.register_node("noise", [](const ir::Node& node, EvalContext& ctx) {
        auto* img = ctx.pool.alloc_image(node.id, ctx.default_width, ctx.default_height);

        float scale = 4.0f, octaves = 1.0f;
        for (auto& kw : node.kwargs) {
            if (kw.name == "scale") scale = std::get<float>(kw.value);
            else if (kw.name == "octaves") octaves = std::get<float>(kw.value);
        }

        struct PushConstants {
            float scale, octaves, width, height;
        } pc{ scale, octaves,
              static_cast<float>(ctx.default_width),
              static_cast<float>(ctx.default_height) };

        auto& pipeline = ctx.pipelines.get("noise", 1, sizeof(PushConstants));

        // Allocate descriptor set
        VkDescriptorSetAllocateInfo alloc_info{};
        alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        alloc_info.descriptorPool = ctx.desc_pool;
        alloc_info.descriptorSetCount = 1;
        alloc_info.pSetLayouts = &pipeline.desc_layout;

        VkDescriptorSet desc_set;
        vkAllocateDescriptorSets(ctx.device.device, &alloc_info, &desc_set);

        VkDescriptorImageInfo img_info{};
        img_info.imageView = img->view;
        img_info.imageLayout = VK_IMAGE_LAYOUT_GENERAL;

        VkWriteDescriptorSet write{};
        write.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        write.dstSet = desc_set;
        write.dstBinding = 0;
        write.descriptorCount = 1;
        write.descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        write.pImageInfo = &img_info;
        vkUpdateDescriptorSets(ctx.device.device, 1, &write, 0, nullptr);

        auto cmd = ctx.device.begin_single_command();

        // Transition to general
        VkImageMemoryBarrier barrier{};
        barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
        barrier.image = img->image;
        barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
        barrier.dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
        vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                             VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                             0, 0, nullptr, 0, nullptr, 1, &barrier);

        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline.pipeline);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE,
                                pipeline.layout, 0, 1, &desc_set, 0, nullptr);
        vkCmdPushConstants(cmd, pipeline.layout, VK_SHADER_STAGE_COMPUTE_BIT,
                          0, sizeof(PushConstants), &pc);
        vkCmdDispatch(cmd,
                      (ctx.default_width + 15) / 16,
                      (ctx.default_height + 15) / 16, 1);

        ctx.device.end_single_command(cmd);
    });
}

} // namespace joon::nodes
```

```cpp
// src/nodes/math_ops.cpp
#include "nodes/node_registry.h"

namespace joon::nodes {

static void register_binary_op(NodeRegistry& reg, const std::string& op,
                                const std::string& shader_name) {
    reg.register_node(op, [shader_name](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.size() != 2) return;

        auto* a = ctx.pool.get_image(node.inputs[0]);
        auto* b = ctx.pool.get_image(node.inputs[1]);
        if (!a || !b) return;

        uint32_t w = a->width, h = a->height;
        auto* out = ctx.pool.alloc_image(node.id, w, h);

        auto& pipeline = ctx.pipelines.get(shader_name, 3);

        VkDescriptorSetAllocateInfo alloc_info{};
        alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        alloc_info.descriptorPool = ctx.desc_pool;
        alloc_info.descriptorSetCount = 1;
        alloc_info.pSetLayouts = &pipeline.desc_layout;

        VkDescriptorSet desc_set;
        vkAllocateDescriptorSets(ctx.device.device, &alloc_info, &desc_set);

        VkDescriptorImageInfo imgs[3] = {};
        imgs[0] = { VK_NULL_HANDLE, a->view, VK_IMAGE_LAYOUT_GENERAL };
        imgs[1] = { VK_NULL_HANDLE, b->view, VK_IMAGE_LAYOUT_GENERAL };
        imgs[2] = { VK_NULL_HANDLE, out->view, VK_IMAGE_LAYOUT_GENERAL };

        VkWriteDescriptorSet writes[3] = {};
        for (int i = 0; i < 3; i++) {
            writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
            writes[i].dstSet = desc_set;
            writes[i].dstBinding = i;
            writes[i].descriptorCount = 1;
            writes[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
            writes[i].pImageInfo = &imgs[i];
        }
        vkUpdateDescriptorSets(ctx.device.device, 3, writes, 0, nullptr);

        auto cmd = ctx.device.begin_single_command();

        VkImageMemoryBarrier barrier{};
        barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
        barrier.image = out->image;
        barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
        barrier.dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
        vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                             VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                             0, 0, nullptr, 0, nullptr, 1, &barrier);

        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline.pipeline);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE,
                                pipeline.layout, 0, 1, &desc_set, 0, nullptr);
        vkCmdDispatch(cmd, (w + 15) / 16, (h + 15) / 16, 1);

        ctx.device.end_single_command(cmd);
    });
}

void register_math_ops(NodeRegistry& reg) {
    register_binary_op(reg, "+", "add");
    register_binary_op(reg, "-", "sub");
    register_binary_op(reg, "*", "mul");
    register_binary_op(reg, "/", "div");
}

} // namespace joon::nodes
```

```cpp
// src/nodes/image_ops.cpp
#include "nodes/node_registry.h"

namespace joon::nodes {

static void register_unary_op(NodeRegistry& reg, const std::string& op,
                               const std::string& shader_name,
                               uint32_t push_size = 0) {
    reg.register_node(op, [shader_name, push_size](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.empty()) return;

        auto* input = ctx.pool.get_image(node.inputs[0]);
        if (!input) return;

        uint32_t w = input->width, h = input->height;
        auto* out = ctx.pool.alloc_image(node.id, w, h);

        auto& pipeline = ctx.pipelines.get(shader_name, 2, push_size);

        VkDescriptorSetAllocateInfo alloc_info{};
        alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        alloc_info.descriptorPool = ctx.desc_pool;
        alloc_info.descriptorSetCount = 1;
        alloc_info.pSetLayouts = &pipeline.desc_layout;

        VkDescriptorSet desc_set;
        vkAllocateDescriptorSets(ctx.device.device, &alloc_info, &desc_set);

        VkDescriptorImageInfo imgs[2] = {};
        imgs[0] = { VK_NULL_HANDLE, input->view, VK_IMAGE_LAYOUT_GENERAL };
        imgs[1] = { VK_NULL_HANDLE, out->view, VK_IMAGE_LAYOUT_GENERAL };

        VkWriteDescriptorSet writes[2] = {};
        for (int i = 0; i < 2; i++) {
            writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
            writes[i].dstSet = desc_set;
            writes[i].dstBinding = i;
            writes[i].descriptorCount = 1;
            writes[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
            writes[i].pImageInfo = &imgs[i];
        }
        vkUpdateDescriptorSets(ctx.device.device, 2, writes, 0, nullptr);

        auto cmd = ctx.device.begin_single_command();

        VkImageMemoryBarrier barrier{};
        barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
        barrier.image = out->image;
        barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
        barrier.dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
        vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                             VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                             0, 0, nullptr, 0, nullptr, 1, &barrier);

        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline.pipeline);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE,
                                pipeline.layout, 0, 1, &desc_set, 0, nullptr);

        // Push constants for ops that need them
        if (push_size > 0) {
            std::vector<float> push_data;
            for (auto& kw : node.kwargs) {
                push_data.push_back(std::get<float>(kw.value));
            }
            // Pad to expected size
            while (push_data.size() * sizeof(float) < push_size) {
                push_data.push_back(0.0f);
            }
            vkCmdPushConstants(cmd, pipeline.layout, VK_SHADER_STAGE_COMPUTE_BIT,
                              0, push_size, push_data.data());
        }

        vkCmdDispatch(cmd, (w + 15) / 16, (h + 15) / 16, 1);
        ctx.device.end_single_command(cmd);
    });
}

void register_image_ops(NodeRegistry& reg) {
    register_unary_op(reg, "invert", "invert");
    register_unary_op(reg, "threshold", "threshold", sizeof(float));
    register_unary_op(reg, "levels", "levels", sizeof(float) * 2);
    register_unary_op(reg, "blur", "blur", sizeof(float));

    // Blend is binary with push constants
    reg.register_node("blend", [](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.size() < 2) return;

        auto* a = ctx.pool.get_image(node.inputs[0]);
        auto* b = ctx.pool.get_image(node.inputs[1]);
        if (!a || !b) return;

        uint32_t w = a->width, h = a->height;
        auto* out = ctx.pool.alloc_image(node.id, w, h);

        struct BlendParams { float opacity; int mode; } bp{ 1.0f, 0 };
        for (auto& kw : node.kwargs) {
            if (kw.name == "opacity") bp.opacity = std::get<float>(kw.value);
            else if (kw.name == "mode") bp.mode = static_cast<int>(std::get<float>(kw.value));
        }

        auto& pipeline = ctx.pipelines.get("blend", 3, sizeof(BlendParams));

        VkDescriptorSetAllocateInfo alloc_info{};
        alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        alloc_info.descriptorPool = ctx.desc_pool;
        alloc_info.descriptorSetCount = 1;
        alloc_info.pSetLayouts = &pipeline.desc_layout;

        VkDescriptorSet desc_set;
        vkAllocateDescriptorSets(ctx.device.device, &alloc_info, &desc_set);

        VkDescriptorImageInfo imgs[3] = {};
        imgs[0] = { VK_NULL_HANDLE, a->view, VK_IMAGE_LAYOUT_GENERAL };
        imgs[1] = { VK_NULL_HANDLE, b->view, VK_IMAGE_LAYOUT_GENERAL };
        imgs[2] = { VK_NULL_HANDLE, out->view, VK_IMAGE_LAYOUT_GENERAL };

        VkWriteDescriptorSet writes[3] = {};
        for (int i = 0; i < 3; i++) {
            writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
            writes[i].dstSet = desc_set;
            writes[i].dstBinding = i;
            writes[i].descriptorCount = 1;
            writes[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
            writes[i].pImageInfo = &imgs[i];
        }
        vkUpdateDescriptorSets(ctx.device.device, 3, writes, 0, nullptr);

        auto cmd = ctx.device.begin_single_command();

        VkImageMemoryBarrier barrier{};
        barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
        barrier.image = out->image;
        barrier.subresourceRange = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
        barrier.dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
        vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                             VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                             0, 0, nullptr, 0, nullptr, 1, &barrier);

        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline.pipeline);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE,
                                pipeline.layout, 0, 1, &desc_set, 0, nullptr);
        vkCmdPushConstants(cmd, pipeline.layout, VK_SHADER_STAGE_COMPUTE_BIT,
                          0, sizeof(BlendParams), &bp);
        vkCmdDispatch(cmd, (w + 15) / 16, (h + 15) / 16, 1);

        ctx.device.end_single_command(cmd);
    });
}

} // namespace joon::nodes
```

```cpp
// src/nodes/save.cpp
#include "nodes/node_registry.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb/stb_image_write.h>

namespace joon::nodes {

void register_save(NodeRegistry& reg) {
    reg.register_node("save", [](const ir::Node& node, EvalContext& ctx) {
        if (node.inputs.empty()) return;
        auto* input = ctx.pool.get_image(node.inputs[0]);
        if (!input) return;

        std::string path = node.string_arg;
        if (path.empty()) return;

        size_t pixel_count = input->width * input->height;
        std::vector<float> float_data(pixel_count * 4);
        ctx.pool.download(input, float_data.data(), float_data.size() * sizeof(float));

        // Convert float 0-1 to uint8
        std::vector<uint8_t> byte_data(pixel_count * 4);
        for (size_t i = 0; i < float_data.size(); i++) {
            byte_data[i] = static_cast<uint8_t>(
                std::clamp(float_data[i] * 255.0f, 0.0f, 255.0f));
        }

        stbi_write_png(path.c_str(), input->width, input->height, 4,
                       byte_data.data(), input->width * 4);
    });
}

} // namespace joon::nodes
```

- [ ] **Step 5: Verify compile**

```bash
cd projects/joon && make config=debug joon-lib
```

- [ ] **Step 6: Commit**

```bash
git add projects/joon/src/vulkan/pipeline_cache.* projects/joon/src/nodes/
git commit -m "feat(joon): pipeline cache, node registry, and all built-in node implementations"
```

---

## Task 8: Interpreter & Evaluator

**Files:**
- Create: `projects/joon/src/interpreter/interpreter.h`
- Create: `projects/joon/src/interpreter/interpreter.cpp`
- Create: `projects/joon/include/joon/graph.h`
- Create: `projects/joon/include/joon/evaluator.h`
- Create: `projects/joon/include/joon/param.h`
- Create: `projects/joon/include/joon/result.h`
- Create: `projects/joon/src/graph.cpp`
- Create: `projects/joon/src/evaluator.cpp`

- [ ] **Step 1: Write interpreter**

```cpp
// src/interpreter/interpreter.h
#pragma once

#include "ir/ir_graph.h"
#include "nodes/node_registry.h"

namespace joon {

class Interpreter {
public:
    Interpreter(nodes::EvalContext& ctx, const nodes::NodeRegistry& registry);

    void evaluate(const ir::IRGraph& graph);

private:
    nodes::EvalContext& ctx_;
    const nodes::NodeRegistry& registry_;
};

} // namespace joon
```

```cpp
// src/interpreter/interpreter.cpp
#include "interpreter/interpreter.h"

namespace joon {

Interpreter::Interpreter(nodes::EvalContext& ctx, const nodes::NodeRegistry& registry)
    : ctx_(ctx), registry_(registry) {}

void Interpreter::evaluate(const ir::IRGraph& graph) {
    auto order = graph.topological_order();

    for (uint32_t id : order) {
        auto& node = graph.nodes[id];

        // Skip constants and string constants — handled inline
        if (node.op == "constant" || node.op == "string_constant" || node.op == "param") {
            continue;
        }

        auto* executor = registry_.find(node.op);
        if (executor) {
            (*executor)(node, ctx_);
        }
    }
}

} // namespace joon
```

- [ ] **Step 2: Write public API headers**

```cpp
// include/joon/param.h
#pragma once

#include <joon/types.h>
#include <string>
#include <unordered_map>

namespace joon {

namespace ir { struct IRGraph; }

template<typename T>
class Param {
public:
    Param(ir::IRGraph& graph, uint32_t node_id) : graph_(graph), node_id_(node_id) {}

    Param& operator=(const T& value);
    operator T() const;

private:
    ir::IRGraph& graph_;
    uint32_t node_id_;
};

} // namespace joon
```

```cpp
// include/joon/result.h
#pragma once

#include <joon/types.h>
#include <vulkan/vulkan.h>
#include <string>
#include <vector>

namespace joon {

namespace vk { class ResourcePool; struct GpuImage; }

class Result {
public:
    Result(vk::ResourcePool& pool, uint32_t node_id);

    VkImage vk_image() const;
    VkImageView vk_image_view() const;
    uint32_t width() const;
    uint32_t height() const;

    void save_image(const char* path);
    std::vector<float> read_pixels();

private:
    vk::ResourcePool& pool_;
    uint32_t node_id_;
};

} // namespace joon
```

```cpp
// include/joon/graph.h
#pragma once

#include <memory>
#include <string>
#include <vector>

namespace joon {

namespace ir { class IRGraph; struct Diagnostic; }

class Graph {
public:
    Graph();
    ~Graph();
    Graph(Graph&&) noexcept;
    Graph& operator=(Graph&&) noexcept;

    bool has_errors() const;
    const std::vector<ir::Diagnostic>& diagnostics() const;

    ir::IRGraph& ir();
    const ir::IRGraph& ir() const;

private:
    friend class Context;
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace joon
```

```cpp
// include/joon/evaluator.h
#pragma once

#include <joon/param.h>
#include <joon/result.h>
#include <memory>
#include <string>
#include <vector>

namespace joon {

class Context;
class Graph;
namespace ir { struct Diagnostic; }

class Evaluator {
public:
    ~Evaluator();

    void evaluate();

    template<typename T>
    Param<T> param(const std::string& name);

    Result result(const std::string& name);
    Result node_result(const std::string& name);

    const std::vector<ir::Diagnostic>& diagnostics() const;

private:
    friend class Context;
    Evaluator(Context& ctx, const Graph& graph);
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace joon
```

- [ ] **Step 3: Write graph.cpp and evaluator.cpp**

```cpp
// src/graph.cpp
#include <joon/graph.h>
#include "ir/ir_graph.h"
#include "ir/type_checker.h"
#include "dsl/parser.h"

namespace joon {

struct Graph::Impl {
    ir::IRGraph ir;
};

Graph::Graph() : impl_(std::make_unique<Impl>()) {}
Graph::~Graph() = default;
Graph::Graph(Graph&&) noexcept = default;
Graph& Graph::operator=(Graph&&) noexcept = default;

bool Graph::has_errors() const {
    for (auto& d : impl_->ir.diagnostics) {
        if (d.level == ir::Diagnostic::Level::Error) return true;
    }
    return false;
}

const std::vector<ir::Diagnostic>& Graph::diagnostics() const {
    return impl_->ir.diagnostics;
}

ir::IRGraph& Graph::ir() { return impl_->ir; }
const ir::IRGraph& Graph::ir() const { return impl_->ir; }

} // namespace joon
```

```cpp
// src/evaluator.cpp
#include <joon/evaluator.h>
#include <joon/context.h>
#include <joon/graph.h>
#include "ir/ir_graph.h"
#include "interpreter/interpreter.h"
#include "nodes/node_registry.h"
#include "vulkan/device.h"
#include "vulkan/resource_pool.h"
#include "vulkan/pipeline_cache.h"

namespace joon {

struct Evaluator::Impl {
    Context& ctx;
    const Graph& graph;
    nodes::NodeRegistry registry;
    std::unique_ptr<vk::PipelineCache> pipelines;
    nodes::EvalContext eval_ctx;
    VkDescriptorPool desc_pool = VK_NULL_HANDLE;

    Impl(Context& ctx, const Graph& graph)
        : ctx(ctx), graph(graph),
          registry(nodes::NodeRegistry::create_default()),
          pipelines(std::make_unique<vk::PipelineCache>(ctx.device(), "shaders")),
          eval_ctx{ ctx.device(), ctx.pool(), *pipelines, 512, 512, VK_NULL_HANDLE } {
        // Create descriptor pool
        VkDescriptorPoolSize pool_size{};
        pool_size.type = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        pool_size.descriptorCount = 256;

        VkDescriptorPoolCreateInfo pool_info{};
        pool_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
        pool_info.maxSets = 128;
        pool_info.poolSizeCount = 1;
        pool_info.pPoolSizes = &pool_size;
        pool_info.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;
        vkCreateDescriptorPool(ctx.device().device, &pool_info, nullptr, &desc_pool);
        eval_ctx.desc_pool = desc_pool;
    }

    ~Impl() {
        if (desc_pool) {
            vkDestroyDescriptorPool(ctx.device().device, desc_pool, nullptr);
        }
    }
};

Evaluator::Evaluator(Context& ctx, const Graph& graph)
    : impl_(std::make_unique<Impl>(ctx, graph)) {}

Evaluator::~Evaluator() = default;

void Evaluator::evaluate() {
    vkResetDescriptorPool(impl_->ctx.device().device, impl_->desc_pool, 0);
    Interpreter interp(impl_->eval_ctx, impl_->registry);
    interp.evaluate(impl_->graph.ir());
}

Result Evaluator::result(const std::string& name) {
    if (!impl_->graph.ir().outputs.empty()) {
        return Result(impl_->ctx.pool(), impl_->graph.ir().outputs[0].node_id);
    }
    return Result(impl_->ctx.pool(), 0);
}

Result Evaluator::node_result(const std::string& name) {
    auto* node = impl_->graph.ir().find_node_by_name(name);
    if (node) return Result(impl_->ctx.pool(), node->id);
    return Result(impl_->ctx.pool(), 0);
}

const std::vector<ir::Diagnostic>& Evaluator::diagnostics() const {
    return impl_->graph.ir().diagnostics;
}

} // namespace joon
```

- [ ] **Step 4: Complete Context implementation (parse methods)**

Add to `src/context.cpp`:

```cpp
Graph Context::parse_string(const char* source) {
    Graph g;
    dsl::Parser parser(source);
    auto program = parser.parse();
    g.ir() = ir::IRGraph::from_ast(program);
    ir::type_check(g.ir());
    return g;
}

Graph Context::parse_file(const char* path) {
    std::ifstream file(path);
    std::stringstream buf;
    buf << file.rdbuf();
    return parse_string(buf.str().c_str());
}

std::unique_ptr<Evaluator> Context::create_evaluator(const Graph& graph) {
    return std::unique_ptr<Evaluator>(new Evaluator(*this, graph));
}
```

- [ ] **Step 5: Verify compile**

```bash
cd projects/joon && make config=debug joon-lib
```

- [ ] **Step 6: Commit**

```bash
git add projects/joon/include/joon/ projects/joon/src/interpreter/ projects/joon/src/graph.cpp projects/joon/src/evaluator.cpp projects/joon/src/context.cpp
git commit -m "feat(joon): interpreter, evaluator, and complete public API"
```

---

## Task 9: CLI

**Files:**
- Create: `projects/joon/cli/main.cpp`

- [ ] **Step 1: Write CLI**

```cpp
// cli/main.cpp
#include <joon/context.h>
#include <joon/graph.h>
#include <joon/evaluator.h>
#include <iostream>
#include <string>
#include <vector>

static void print_usage() {
    std::cout << "Usage:\n"
              << "  joon run <file.jn> [-o output.png] [-p key=val ...]\n"
              << "  joon check <file.jn>\n"
              << "  joon info <file.jn>\n";
}

static int cmd_check(const char* path) {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_file(path);

    for (auto& d : graph.diagnostics()) {
        const char* level = d.level == joon::ir::Diagnostic::Level::Error ? "error" : "warning";
        std::cerr << path << ":" << d.line << ":" << d.col << ": "
                  << level << ": " << d.message << "\n";
    }

    return graph.has_errors() ? 1 : 0;
}

static int cmd_info(const char* path) {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_file(path);

    auto& ir = graph.ir();
    std::cout << "Nodes: " << ir.nodes.size() << "\n";
    std::cout << "Params:\n";
    for (auto& p : ir.params) {
        std::cout << "  " << p.name << " : " << static_cast<int>(p.type) << "\n";
    }
    std::cout << "Outputs: " << ir.outputs.size() << "\n";
    return 0;
}

static int cmd_run(const char* path, const char* output,
                    const std::vector<std::pair<std::string, std::string>>& overrides) {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_file(path);

    if (graph.has_errors()) {
        for (auto& d : graph.diagnostics()) {
            if (d.level == joon::ir::Diagnostic::Level::Error) {
                std::cerr << d.line << ":" << d.col << ": " << d.message << "\n";
            }
        }
        return 1;
    }

    auto eval = ctx->create_evaluator(graph);

    // Apply param overrides
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
    if (cmd == "info" && argc >= 3) return cmd_info(argv[2]);

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
```

- [ ] **Step 2: Build and verify**

```bash
cd projects/joon && make config=debug joon-cli
```

- [ ] **Step 3: Commit**

```bash
git add projects/joon/cli/
git commit -m "feat(joon): CLI with run, check, and info commands"
```

---

## Task 10: GUI — ImGui Application Shell

**Files:**
- Create: `projects/joon/gui/main.cpp`
- Create: `projects/joon/gui/app.h`
- Create: `projects/joon/gui/app.cpp`
- Create: `projects/joon/gui/panel_tree.cpp`
- Create: `projects/joon/gui/panel_properties.cpp`
- Create: `projects/joon/gui/panel_code.cpp`
- Create: `projects/joon/gui/panel_viewport.cpp`
- Create: `projects/joon/gui/panel_preview.cpp`
- Create: `projects/joon/gui/panel_log.cpp`

- [ ] **Step 1: Write app state**

```cpp
// gui/app.h
#pragma once

#include <joon/context.h>
#include <joon/graph.h>
#include <joon/evaluator.h>
#include <string>
#include <vector>
#include <memory>

struct App {
    std::unique_ptr<joon::Context> ctx;
    joon::Graph graph;
    std::unique_ptr<joon::Evaluator> eval;

    std::string dsl_source;
    bool source_dirty = true;
    uint32_t selected_node_id = UINT32_MAX;

    // ImGui texture IDs for viewport
    VkDescriptorSet viewport_desc = VK_NULL_HANDLE;
    VkDescriptorSet preview_desc = VK_NULL_HANDLE;
    VkSampler sampler = VK_NULL_HANDLE;

    void init();
    void reparse();
    void update();

    // Panel draw functions
    void draw_tree();
    void draw_properties();
    void draw_code();
    void draw_viewport();
    void draw_preview();
    void draw_log();
};
```

- [ ] **Step 2: Write app.cpp with init, reparse, update**

```cpp
// gui/app.cpp
#include "app.h"
#include "ir/ir_graph.h"
#include "ir/type_checker.h"
#include "dsl/parser.h"
#include <imgui.h>

void App::init() {
    ctx = joon::Context::create();

    // Default DSL
    dsl_source = R"(; Joon - edit this code
(def base (noise :scale 4.0 :octaves 3))
(param contrast float 1.2 :min 0.0 :max 3.0)
(def result (levels base :contrast contrast))
(output result)
)";

    // Create sampler for ImGui texture display
    VkSamplerCreateInfo sampler_info{};
    sampler_info.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    sampler_info.magFilter = VK_FILTER_LINEAR;
    sampler_info.minFilter = VK_FILTER_LINEAR;
    vkCreateSampler(ctx->device().device, &sampler_info, nullptr, &sampler);

    reparse();
}

void App::reparse() {
    try {
        graph = ctx->parse_string(dsl_source.c_str());
        if (!graph.has_errors()) {
            eval = ctx->create_evaluator(graph);
            eval->evaluate();
        }
    } catch (const std::exception& e) {
        // Parse error — diagnostics will show in log panel
    }
    source_dirty = false;
}

void App::update() {
    if (source_dirty) {
        reparse();
    }
}
```

- [ ] **Step 3: Write panel implementations**

```cpp
// gui/panel_tree.cpp
#include "app.h"
#include "ir/ir_graph.h"
#include <imgui.h>

void App::draw_tree() {
    ImGui::Begin("Graph Tree");

    if (!graph.has_errors()) {
        auto& ir = graph.ir();

        if (ImGui::TreeNode("Params")) {
            for (auto& p : ir.params) {
                bool selected = (selected_node_id == p.node_id);
                if (ImGui::Selectable(p.name.c_str(), selected)) {
                    selected_node_id = p.node_id;
                }
            }
            ImGui::TreePop();
        }

        if (ImGui::TreeNode("Nodes")) {
            for (auto& node : ir.nodes) {
                if (node.op == "constant" || node.op == "string_constant" || node.op == "param")
                    continue;
                bool selected = (selected_node_id == node.id);
                std::string label = node.op + " ##" + std::to_string(node.id);
                if (ImGui::Selectable(label.c_str(), selected)) {
                    selected_node_id = node.id;
                }
            }
            ImGui::TreePop();
        }

        if (ImGui::TreeNode("Outputs")) {
            for (size_t i = 0; i < ir.outputs.size(); i++) {
                std::string label = "output " + std::to_string(i);
                bool selected = (selected_node_id == ir.outputs[i].node_id);
                if (ImGui::Selectable(label.c_str(), selected)) {
                    selected_node_id = ir.outputs[i].node_id;
                }
            }
            ImGui::TreePop();
        }
    }

    ImGui::End();
}
```

```cpp
// gui/panel_properties.cpp
#include "app.h"
#include "ir/ir_graph.h"
#include <imgui.h>

void App::draw_properties() {
    ImGui::Begin("Properties");

    if (!graph.has_errors()) {
        for (auto& p : graph.ir().params) {
            float val = std::get<float>(p.default_value);
            float min_v = 0.0f, max_v = 1.0f;
            auto it = p.constraints.find("min");
            if (it != p.constraints.end()) min_v = it->second;
            it = p.constraints.find("max");
            if (it != p.constraints.end()) max_v = it->second;

            if (ImGui::SliderFloat(p.name.c_str(), &val, min_v, max_v)) {
                if (eval) {
                    auto param = eval->param<float>(p.name);
                    param = val;
                    eval->evaluate();
                }
            }
        }
    }

    ImGui::End();
}
```

```cpp
// gui/panel_code.cpp
#include "app.h"
#include <imgui.h>

void App::draw_code() {
    ImGui::Begin("Code Editor");

    // Resize buffer if needed
    static char buf[4096];
    strncpy(buf, dsl_source.c_str(), sizeof(buf) - 1);

    if (ImGui::InputTextMultiline("##code", buf, sizeof(buf),
                                   ImVec2(-1, -1),
                                   ImGuiInputTextFlags_AllowTabInput)) {
        dsl_source = buf;
        source_dirty = true;
    }

    ImGui::End();
}
```

```cpp
// gui/panel_viewport.cpp
#include "app.h"
#include <imgui.h>

void App::draw_viewport() {
    ImGui::Begin("Viewport");

    if (eval && !graph.has_errors() && !graph.ir().outputs.empty()) {
        auto result = eval->result("output");
        // Bind result image as ImGui texture
        // viewport_desc would be updated each frame with the result's VkImageView
        ImVec2 avail = ImGui::GetContentRegionAvail();
        if (viewport_desc) {
            ImGui::Image((ImTextureID)viewport_desc, avail);
        }
    } else {
        ImGui::TextDisabled("No output");
    }

    ImGui::End();
}
```

```cpp
// gui/panel_preview.cpp
#include "app.h"
#include "ir/ir_graph.h"
#include <imgui.h>

void App::draw_preview() {
    ImGui::Begin("Node Preview");

    if (eval && selected_node_id != UINT32_MAX) {
        auto* node = graph.ir().find_node(selected_node_id);
        if (node) {
            ImGui::Text("Node: %s (#%u)", node->op.c_str(), node->id);
            // Display intermediate image similar to viewport
            ImVec2 avail = ImGui::GetContentRegionAvail();
            if (preview_desc) {
                ImGui::Image((ImTextureID)preview_desc, avail);
            }
        }
    } else {
        ImGui::TextDisabled("Select a node");
    }

    ImGui::End();
}
```

```cpp
// gui/panel_log.cpp
#include "app.h"
#include "ir/ir_graph.h"
#include <imgui.h>

void App::draw_log() {
    ImGui::Begin("Output Log");

    for (auto& d : graph.diagnostics()) {
        ImVec4 color = (d.level == joon::ir::Diagnostic::Level::Error)
            ? ImVec4(1, 0.3f, 0.3f, 1) : ImVec4(1, 0.8f, 0.3f, 1);
        ImGui::TextColored(color, "%u:%u: %s", d.line, d.col, d.message.c_str());
    }

    ImGui::End();
}
```

- [ ] **Step 4: Write main.cpp with ImGui + Vulkan + GLFW setup**

```cpp
// gui/main.cpp
#include "app.h"
#include <vulkan/vulkan.h>
#define GLFW_INCLUDE_VULKAN
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_vulkan.h>

int main() {
    glfwInit();
    glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API);
    GLFWwindow* window = glfwCreateWindow(1280, 720, "Joon", nullptr, nullptr);

    App app;
    app.init();

    // ImGui setup
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;

    ImGui::StyleColorsDark();
    // Note: Full Vulkan swapchain + ImGui backend init would go here
    // This is a skeleton — the Vulkan surface, swapchain, and render pass
    // setup depends on the device created by joon::Context

    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();

        ImGui_ImplVulkan_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();
        ImGui::DockSpaceOverViewport();

        app.update();
        app.draw_tree();
        app.draw_properties();
        app.draw_code();
        app.draw_viewport();
        app.draw_preview();
        app.draw_log();

        ImGui::Render();
        // Submit ImGui draw data to Vulkan would go here
    }

    vkDeviceWaitIdle(app.ctx->device().device);

    ImGui_ImplVulkan_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();
    return 0;
}
```

- [ ] **Step 5: Build**

```bash
cd projects/joon && make config=debug joon-gui
```

- [ ] **Step 6: Commit**

```bash
git add projects/joon/gui/
git commit -m "feat(joon): ImGui GUI with dockable tree, properties, code editor, viewport, preview, and log panels"
```
