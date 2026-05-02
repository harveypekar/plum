# Joon Sub-Project 3: DSL-Generated Shaders & Deferred Lighting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace joon's hardcoded shaders with a DSL-driven shader codegen system — materials define surface properties and custom BRDFs via DSL expressions that compile to HLSL, rendered via deferred shading with automatic pre-pass extraction for non-inlineable ops.

**Architecture:** New parser nodes (`FnNode`, `VectorNode`, `DotAccessNode`) support the `(shader ...)` DSL. A `Tier::MATERIAL` IR phase compiles shader ASTs into HLSL via a `ShaderIR` → `HlslEmitter` pipeline. The geometry pass renders to MRT G-buffers with per-material pipelines. A fullscreen deferred lighting pass evaluates BRDFs (default Cook-Torrance or custom) per-light. Non-inlineable ops inside shader bodies are auto-extracted into compute pre-passes.

**Tech Stack:** C++20, Vulkan, VMA, HLSL, DXC, Catch2.

**Worktree:** `/mnt/d/prg/plum-joon-shader-codegen` (branch `joon-shader-codegen`)

**Design spec:** `docs/superpowers/specs/2026-05-01-joon-shader-codegen-design.md`

---

## Conventions

- TDD: write the failing test first, run it, see the exact failure, then implement.
- Each commit message starts with `feat(joon):`, `test(joon):`, or `fix(joon):` and is one imperative sentence.
- After every task: build the full solution and run **all** tests. If anything regresses, stop and fix before moving on.
- Co-author trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
  ```
- Build command (from worktree root):
  ```bash
  cd projects/joon/build && \
  "/c/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" \
    Joon.sln -p:Configuration=Debug -p:Platform=x64 -m -v:minimal
  ```
- Test command (from worktree root):
  ```bash
  projects/joon/build/bin/Debug/joon-tests.exe
  ```
- Run specific tags:
  ```bash
  projects/joon/build/bin/Debug/joon-tests.exe "[shader]"
  ```

---

## File Map

| Area | Action | File | Purpose |
|------|--------|------|---------|
| Lexer | Modify | `src/dsl/token.h` | Add LBRACKET, RBRACKET, DOT, ARROW token types |
| Lexer | Modify | `src/dsl/lexer.cpp` | Emit bracket, dot, arrow tokens |
| AST | Modify | `src/dsl/ast.h` | Add `FnNode`, `VectorNode`, `DotAccessNode` to variant |
| Parser | Modify | `src/dsl/parser.cpp` | Parse `(fn ...)`, `[...]`, `a.b`, `-> [...]` syntax |
| IR node | Modify | `src/ir/node.h` | Add `Tier::MATERIAL`; add `ShaderDef` struct on Node for shader ASTs |
| IR types | Modify | `include/joon/types.h` | Add `Type::MATERIAL` |
| IR graph | Modify | `src/ir/ir_graph.cpp` | Lower `shader` to MATERIAL tier; store FnNode kwargs |
| Type checker | Modify | `src/ir/type_checker.cpp` | Handle MATERIAL type |
| Shader IR | Create | `src/shader/shader_ir.h` | Expression tree types for shader bodies |
| Shader analyzer | Create | `src/shader/shader_analyzer.h`, `.cpp` | Build ShaderIR from AST, classify ops |
| HLSL emitter | Create | `src/shader/hlsl_emitter.h`, `.cpp` | ShaderIR → HLSL source code |
| Noise HLSL | Create | `src/shader/noise_hlsl.h` | Inline HLSL noise/fbm source as string constant |
| BRDF emitter | Create | `src/shader/brdf_emitter.h`, `.cpp` | Custom BRDF → lighting shader variant |
| Pre-pass extractor | Create | `src/shader/prepass_extractor.h`, `.cpp` | Extract compute pre-passes from shader bodies |
| Pipeline cache | Modify | `src/vulkan/pipeline_cache.h`, `.cpp` | Add `get_graphics_from_source()` for generated HLSL |
| Render pass | Modify | `src/vulkan/render_pass.h`, `.cpp` | Verify N-attachment support works (already has vector) |
| Resource pool | Modify | `src/vulkan/resource_pool.h`, `.cpp` | Add `alloc_depth_sampled()` with SAMPLED_BIT |
| Buffer | Modify | `src/vulkan/buffer.h`, `.cpp` | Add fullscreen quad helper |
| Lighting pass | Create | `src/scene/lighting_pass.h`, `.cpp` | Fullscreen deferred lighting dispatch |
| Geometry pass | Modify | `src/scene/geometry_pass.cpp` | MRT framebuffer, per-material pipeline dispatch |
| Scene executors | Modify | `src/scene/scene_executors.h`, `.cpp` | Material executor + `:material` kwarg on scene objects |
| Scene types | Modify | `include/joon/scene.h` | Add LightUBO struct for shader upload |
| Evaluator | Modify | `src/evaluator.cpp` | Add material registry to EvalContext; MATERIAL tier phase |
| Interpreter | Modify | `src/interpreter/interpreter.cpp` | MATERIAL walk phase before SCENE |
| Node registry | Modify | `src/nodes/node_registry.h` | EvalContext gains material pipeline map |
| Node registry | Modify | `src/nodes/node_registry.cpp` | Register shader executor |
| Fullscreen vert | Create | `shaders/fullscreen.vert.hlsl` | Passthrough quad vertex shader |
| Default lighting | Create | `shaders/deferred_default.frag.hlsl` | Cook-Torrance GGX default |
| GUI | Modify | `gui/app.cpp` | Default DSL with material + lighting |
| Tests | Create | `tests/test_shader_parser.cpp` | Parser tests for fn, vector, dot, arrow syntax |
| Tests | Create | `tests/test_shader_ir.cpp` | ShaderIR construction and op classification |
| Tests | Create | `tests/test_hlsl_emitter.cpp` | HLSL code generation tests |
| Tests | Create | `tests/test_prepass.cpp` | Pre-pass extraction tests |
| Tests | Create | `tests/test_lighting_pass.cpp` | Deferred lighting GPU integration tests |
| Tests | Create | `tests/test_deferred.cpp` | End-to-end deferred rendering with materials |

---

## Phase 1: Language Extensions

### Task 1: Add FnNode, VectorNode, and arrow syntax to parser

**Files:**
- Modify: `projects/joon/src/dsl/token.h`
- Modify: `projects/joon/src/dsl/lexer.cpp`
- Modify: `projects/joon/src/dsl/ast.h`
- Modify: `projects/joon/src/dsl/parser.cpp`
- Create: `projects/joon/tests/test_shader_parser.cpp`

- [ ] **Step 1: Write failing tests for FnNode, VectorNode, and arrow syntax**

```cpp
// tests/test_shader_parser.cpp
#include "catch_amalgamated.hpp"
#include "dsl/parser.h"
using namespace joon;

TEST_CASE("Parse vector literal", "[shader][parser]") {
    Parser p("[1.0 2.0 3.0]");
    auto expr = p.parse_expression();
    auto* vec = std::get_if<VectorNode>(&expr->data);
    REQUIRE(vec != nullptr);
    CHECK(vec->elements.size() == 3);
    auto* e0 = std::get_if<NumberNode>(&vec->elements[0]->data);
    REQUIRE(e0);
    CHECK(e0->value == Approx(1.0));
}

TEST_CASE("Parse fn with body", "[shader][parser]") {
    Parser p("(fn [pos normal uv] (set pos.y (* pos.x 2.0)))");
    auto expr = p.parse_expression();
    auto* fn = std::get_if<FnNode>(&expr->data);
    REQUIRE(fn != nullptr);
    CHECK(fn->params.size() == 3);
    CHECK(fn->params[0] == "pos");
    CHECK(fn->params[1] == "normal");
    CHECK(fn->params[2] == "uv");
    CHECK(fn->body.size() == 1);
}

TEST_CASE("Parse fn with arrow outputs", "[shader][parser]") {
    Parser p("(fn [normal uv] -> [albedo vec4, normal vec4] (set albedo [1 0 0 1]))");
    auto expr = p.parse_expression();
    auto* fn = std::get_if<FnNode>(&expr->data);
    REQUIRE(fn != nullptr);
    CHECK(fn->params.size() == 2);
    CHECK(fn->outputs.size() == 2);
    CHECK(fn->outputs[0].name == "albedo");
    CHECK(fn->outputs[0].type_name == "vec4");
    CHECK(fn->outputs[1].name == "normal");
    CHECK(fn->body.size() == 1);
}

TEST_CASE("Parse shader call with fn kwargs", "[shader][parser]") {
    Parser p(R"(
        (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [1 0 0 1])))
    )");
    auto expr = p.parse_expression();
    auto* call = std::get_if<CallNode>(&expr->data);
    REQUIRE(call != nullptr);
    CHECK(call->op == "shader");
    CHECK(call->kwargs.size() == 1);
    CHECK(call->kwargs[0].name == "fragment");
    auto* fn = std::get_if<FnNode>(&call->kwargs[0].value->data);
    REQUIRE(fn != nullptr);
    CHECK(fn->outputs.size() == 1);
}

TEST_CASE("Vector literal with expressions", "[shader][parser]") {
    Parser p("[(+ 1 2) 3.0 x]");
    auto expr = p.parse_expression();
    auto* vec = std::get_if<VectorNode>(&expr->data);
    REQUIRE(vec != nullptr);
    CHECK(vec->elements.size() == 3);
    CHECK(std::get_if<CallNode>(&vec->elements[0]->data) != nullptr);
    CHECK(std::get_if<NumberNode>(&vec->elements[1]->data) != nullptr);
    CHECK(std::get_if<SymbolNode>(&vec->elements[2]->data) != nullptr);
}
```

- [ ] **Step 2: Build and verify tests fail (compile errors — new types don't exist yet)**

Run build. Expected: compile error on `VectorNode`, `FnNode`.

- [ ] **Step 3: Add new token types**

In `src/dsl/token.h`, add to the `TokenType` enum:
```cpp
LBRACKET,    // [
RBRACKET,    // ]
DOT,         // .
ARROW,       // ->
```

- [ ] **Step 4: Update lexer to emit new tokens**

In `src/dsl/lexer.cpp`, in the `tokenize()` method's character switch, add cases:
```cpp
case '[': tokens.push_back({TokenType::LBRACKET, "[", line, col}); break;
case ']': tokens.push_back({TokenType::RBRACKET, "]", line, col}); break;
case '.': tokens.push_back({TokenType::DOT, ".", line, col}); break;
```

For `->` (arrow), handle inside the `-` case: peek at the next character; if it's `>`, consume both and emit `ARROW`; otherwise fall through to existing `-` handling (which treats it as part of a number or symbol).

- [ ] **Step 5: Add AST node types**

In `src/dsl/ast.h`, add before the variant definition:

```cpp
struct FnOutput {
    std::string name;
    std::string type_name;
};

struct FnNode {
    std::vector<std::string> params;
    std::vector<FnOutput> outputs;  // from -> [name type, ...]
    std::vector<AstPtr> body;
};

struct VectorNode {
    std::vector<AstPtr> elements;
};
```

Add `FnNode` and `VectorNode` to the `AstData` variant:
```cpp
using AstData = std::variant<
    DefNode, ParamNode, OutputNode, CallNode,
    NumberNode, StringNode, SymbolNode,
    FnNode, VectorNode
>;
```

- [ ] **Step 6: Implement parser for vector literals**

In `src/dsl/parser.cpp`, in `parse_expr()`, add a case for `LBRACKET`:
```cpp
if (peek().type == TokenType::LBRACKET) {
    return parse_vector();
}
```

Implement `parse_vector()`:
```cpp
AstPtr Parser::parse_vector() {
    auto start = advance(); // consume [
    VectorNode vec;
    while (peek().type != TokenType::RBRACKET) {
        vec.elements.push_back(parse_expr());
        // skip optional comma
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
```

- [ ] **Step 7: Implement parser for fn expressions**

In `parse_expr()` inside the `LPAREN` case, before dispatching as a regular call, check if the op is `fn`:
```cpp
if (call_op == "fn") {
    return parse_fn(start_line, start_col);
}
```

Implement `parse_fn()`:
```cpp
AstPtr Parser::parse_fn(uint32_t line, uint32_t col) {
    // Already consumed ( and fn
    FnNode fn;

    // Parse parameter list [param1 param2 ...]
    expect(TokenType::LBRACKET);
    while (peek().type != TokenType::RBRACKET) {
        auto tok = advance();
        fn.params.push_back(tok.text);
    }
    advance(); // consume ]

    // Parse optional arrow outputs: -> [name type, name type, ...]
    if (peek().type == TokenType::ARROW) {
        advance(); // consume ->
        expect(TokenType::LBRACKET);
        while (peek().type != TokenType::RBRACKET) {
            FnOutput out;
            out.name = advance().text;      // output name
            out.type_name = advance().text;  // output type
            fn.outputs.push_back(std::move(out));
            // skip optional comma
            if (peek().type == TokenType::SYMBOL && peek().text == ",")
                advance();
        }
        advance(); // consume ]
    }

    // Parse body expressions until closing )
    while (peek().type != TokenType::RPAREN) {
        fn.body.push_back(parse_expr());
    }
    advance(); // consume )

    auto node = std::make_unique<AstNode>();
    node->data = std::move(fn);
    node->line = line;
    node->col = col;
    return node;
}
```

Add `parse_vector()` and `parse_fn()` declarations to `parser.h`.

- [ ] **Step 8: Build and run shader parser tests**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][parser]"
```
Expected: all 5 tests pass.

- [ ] **Step 9: Run full test suite**

```bash
projects/joon/build/bin/Debug/joon-tests.exe
```
Expected: all existing tests still pass + 5 new = total passes.

- [ ] **Step 10: Commit**

```bash
git add projects/joon/src/dsl/ projects/joon/tests/test_shader_parser.cpp
git commit -m "feat(joon): add FnNode, VectorNode, and arrow syntax to parser"
```

---

### Task 2: Add DotAccessNode for G-buffer channel access

**Files:**
- Modify: `projects/joon/src/dsl/ast.h`
- Modify: `projects/joon/src/dsl/parser.cpp`
- Modify: `projects/joon/tests/test_shader_parser.cpp`

- [ ] **Step 1: Write failing test**

Add to `tests/test_shader_parser.cpp`:
```cpp
TEST_CASE("Parse dot access", "[shader][parser]") {
    Parser p("gbuf.albedo");
    auto expr = p.parse_expression();
    auto* dot = std::get_if<DotAccessNode>(&expr->data);
    REQUIRE(dot != nullptr);
    CHECK(dot->field == "albedo");
    auto* obj = std::get_if<SymbolNode>(&dot->object->data);
    REQUIRE(obj != nullptr);
    CHECK(obj->name == "gbuf");
}

TEST_CASE("Parse chained dot access", "[shader][parser]") {
    Parser p("a.b.c");
    auto expr = p.parse_expression();
    auto* dot = std::get_if<DotAccessNode>(&expr->data);
    REQUIRE(dot != nullptr);
    CHECK(dot->field == "c");
    auto* inner = std::get_if<DotAccessNode>(&dot->object->data);
    REQUIRE(inner != nullptr);
    CHECK(inner->field == "b");
}
```

- [ ] **Step 2: Build, verify compile error (DotAccessNode undefined)**

- [ ] **Step 3: Add DotAccessNode to AST**

In `src/dsl/ast.h`:
```cpp
struct DotAccessNode {
    AstPtr object;
    std::string field;
};
```

Add to variant:
```cpp
using AstData = std::variant<
    DefNode, ParamNode, OutputNode, CallNode,
    NumberNode, StringNode, SymbolNode,
    FnNode, VectorNode, DotAccessNode
>;
```

- [ ] **Step 4: Implement dot access parsing**

In `src/dsl/parser.cpp`, modify `parse_expr()`. After parsing a primary expression (symbol, number, etc.), check for a trailing DOT token and wrap in DotAccessNode:

```cpp
AstPtr Parser::parse_expr() {
    auto primary = parse_primary(); // existing parse logic
    // Chain dot access
    while (peek().type == TokenType::DOT) {
        advance(); // consume .
        auto field_tok = advance(); // field name
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
```

This requires refactoring `parse_expr()` to separate the primary-expression logic from the dot-chaining. The existing body of `parse_expr()` becomes `parse_primary()`, and `parse_expr()` calls `parse_primary()` then chains dots.

- [ ] **Step 5: Build and run tests**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][parser]"
```
Expected: all 7 parser tests pass.

- [ ] **Step 6: Run full suite, verify no regressions**

- [ ] **Step 7: Commit**

```bash
git add projects/joon/src/dsl/ projects/joon/tests/test_shader_parser.cpp
git commit -m "feat(joon): add DotAccessNode for G-buffer channel access"
```

---

## Phase 2: IR Extensions

### Task 3: Add Tier::MATERIAL and lower `shader` op

**Files:**
- Modify: `projects/joon/src/ir/node.h`
- Modify: `projects/joon/include/joon/types.h`
- Modify: `projects/joon/src/ir/ir_graph.cpp`
- Modify: `projects/joon/src/ir/type_checker.cpp`
- Modify: `projects/joon/tests/test_shader_parser.cpp` (add IR tests here)

- [ ] **Step 1: Write failing test**

Add to `tests/test_shader_parser.cpp`:
```cpp
TEST_CASE("shader op lowers to MATERIAL tier", "[shader][ir]") {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [1 0 0 1]))))
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto& ir = graph.ir();
    bool found_material = false;
    for (auto& n : ir.nodes) {
        if (n.tier == joon::Tier::MATERIAL) {
            found_material = true;
            CHECK(n.op == "shader");
            CHECK(n.output_type == joon::Type::MATERIAL);
        }
    }
    CHECK(found_material);
}
```

- [ ] **Step 2: Build, verify compile error (Tier::MATERIAL, Type::MATERIAL undefined)**

- [ ] **Step 3: Add Tier::MATERIAL and Type::MATERIAL**

In `src/ir/node.h`, update the Tier enum. Insert MATERIAL between GPU and SCENE to maintain the execution order comment:
```cpp
enum class Tier { CPU, GPU, MATERIAL, SCENE, RENDER };
```

In `include/joon/types.h`, add to the Type enum:
```cpp
MATERIAL
```

- [ ] **Step 4: Add ShaderDef struct to IR Node for storing shader function ASTs**

In `src/ir/node.h`, add a struct to hold the parsed shader functions:
```cpp
struct ShaderFnDef {
    std::vector<std::string> params;
    struct Output { std::string name; std::string type_name; };
    std::vector<Output> outputs;
    std::vector<AstPtr> body;  // raw AST subtrees — processed by shader analyzer
};

struct ShaderDef {
    std::optional<ShaderFnDef> vertex;
    std::optional<ShaderFnDef> fragment;
    std::optional<ShaderFnDef> brdf;
};
```

Add `#include <optional>` and `#include "dsl/ast.h"` to node.h. Add to the `Node` struct:
```cpp
std::optional<ShaderDef> shader_def;
```

- [ ] **Step 5: Lower `shader` calls to MATERIAL tier in IR graph**

In `src/ir/ir_graph.cpp`, add `"shader"` to a new MATERIAL_OPS set alongside the existing SCENE_OPS and RENDER_OPS:

```cpp
static const std::unordered_set<std::string> MATERIAL_OPS{ "shader" };
```

In the tier classification block:
```cpp
} else if (MATERIAL_OPS.count(call->op)) {
    tier = Tier::MATERIAL;
    output_type = Type::MATERIAL;
```

Then, after creating the node and processing kwargs, extract FnNode kwargs into the ShaderDef:

```cpp
if (call->op == "shader") {
    ShaderDef sd;
    for (auto& kw : call->kwargs) {
        auto* fn = std::get_if<FnNode>(&kw.value->data);
        if (!fn) continue;
        ShaderFnDef fndef;
        fndef.params = fn->params;
        for (auto& o : fn->outputs)
            fndef.outputs.push_back({o.name, o.type_name});
        fndef.body = std::move(fn->body);  // take ownership of AST
        if (kw.name == "vertex") sd.vertex = std::move(fndef);
        else if (kw.name == "fragment") sd.fragment = std::move(fndef);
        else if (kw.name == "brdf") sd.brdf = std::move(fndef);
    }
    nodes[id].shader_def = std::move(sd);
}
```

Note: `fn->body` uses `std::move` on the AstPtr vector elements. Since `kw.value` is already an owned `AstPtr`, this transfer is safe. However, the FnNode stored inside `kw.value` will have its body emptied. This is fine because the shader node doesn't use kwargs for anything else.

- [ ] **Step 6: Update type checker to handle MATERIAL type**

In `src/ir/type_checker.cpp`, add a case for the `shader` op that sets output type to `Type::MATERIAL`:

```cpp
if (node.op == "shader") {
    node.output_type = Type::MATERIAL;
    continue;
}
```

- [ ] **Step 7: Build and run shader IR tests**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][ir]"
```
Expected: 1 test passes.

- [ ] **Step 8: Run full suite, verify no regressions**

- [ ] **Step 9: Commit**

```bash
git add projects/joon/src/ir/ projects/joon/include/joon/types.h projects/joon/tests/test_shader_parser.cpp
git commit -m "feat(joon): add Tier::MATERIAL and lower shader op to MATERIAL tier"
```

---

## Phase 3: Shader IR & Analysis

### Task 4: Define ShaderIR expression tree types

**Files:**
- Create: `projects/joon/src/shader/shader_ir.h`
- Create: `projects/joon/tests/test_shader_ir.cpp`

- [ ] **Step 1: Write failing test**

```cpp
// tests/test_shader_ir.cpp
#include "catch_amalgamated.hpp"
#include "shader/shader_ir.h"
using namespace joon;

TEST_CASE("ShaderExpr: literal float", "[shader][ir]") {
    ShaderExpr e = ShaderLiteral{1.5f};
    CHECK(std::get<ShaderLiteral>(e).value == Approx(1.5f));
}

TEST_CASE("ShaderExpr: binary add", "[shader][ir]") {
    auto a = std::make_unique<ShaderExpr>(ShaderLiteral{1.0f});
    auto b = std::make_unique<ShaderExpr>(ShaderLiteral{2.0f});
    ShaderExpr e = ShaderCall{"+", {std::move(a), std::move(b)}, {}};
    auto& call = std::get<ShaderCall>(e);
    CHECK(call.op == "+");
    CHECK(call.args.size() == 2);
}

TEST_CASE("ShaderExpr: noise with kwargs", "[shader][ir]") {
    ShaderExpr e = ShaderCall{"noise", {}, {{"scale", 4.0f}, {"octaves", 3.0f}}};
    auto& call = std::get<ShaderCall>(e);
    CHECK(call.kwargs.size() == 2);
    CHECK(call.kwargs[0].first == "scale");
}

TEST_CASE("ShaderExpr: variable reference", "[shader][ir]") {
    ShaderExpr e = ShaderVar{"normal"};
    CHECK(std::get<ShaderVar>(e).name == "normal");
}

TEST_CASE("ShaderExpr: assignment", "[shader][ir]") {
    auto val = std::make_unique<ShaderExpr>(ShaderLiteral{1.0f});
    ShaderExpr e = ShaderAssign{"albedo", std::move(val)};
    CHECK(std::get<ShaderAssign>(e).target == "albedo");
}

TEST_CASE("ShaderExpr: vector constructor", "[shader][ir]") {
    std::vector<std::unique_ptr<ShaderExpr>> elems;
    elems.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    elems.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    elems.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    ShaderExpr e = ShaderVecConstruct{std::move(elems)};
    CHECK(std::get<ShaderVecConstruct>(e).elements.size() == 3);
}

TEST_CASE("ShaderExpr: dot access", "[shader][ir]") {
    auto obj = std::make_unique<ShaderExpr>(ShaderVar{"pos"});
    ShaderExpr e = ShaderDotAccess{std::move(obj), "y"};
    CHECK(std::get<ShaderDotAccess>(e).field == "y");
}

TEST_CASE("ShaderExpr: prepass texture sample", "[shader][ir]") {
    ShaderExpr e = ShaderPrepassSample{0};
    CHECK(std::get<ShaderPrepassSample>(e).prepass_index == 0);
}
```

- [ ] **Step 2: Build, verify compile error (shader_ir.h doesn't exist)**

- [ ] **Step 3: Implement ShaderIR types**

```cpp
// src/shader/shader_ir.h
#pragma once
#include <string>
#include <vector>
#include <variant>
#include <memory>
#include <utility>

namespace joon {

struct ShaderLiteral { float value; };
struct ShaderVar { std::string name; };

struct ShaderCall;
struct ShaderAssign;
struct ShaderVecConstruct;
struct ShaderDotAccess;
struct ShaderPrepassSample;

using ShaderExpr = std::variant<
    ShaderLiteral,
    ShaderVar,
    ShaderCall,
    ShaderAssign,
    ShaderVecConstruct,
    ShaderDotAccess,
    ShaderPrepassSample
>;

using ShaderExprPtr = std::unique_ptr<ShaderExpr>;

struct ShaderCall {
    std::string op;
    std::vector<ShaderExprPtr> args;
    std::vector<std::pair<std::string, float>> kwargs;
};

struct ShaderAssign {
    std::string target;
    ShaderExprPtr value;
};

struct ShaderVecConstruct {
    std::vector<ShaderExprPtr> elements;
};

struct ShaderDotAccess {
    ShaderExprPtr object;
    std::string field;
};

struct ShaderPrepassSample {
    uint32_t prepass_index;
};

struct ShaderFnOutput {
    std::string name;
    std::string type_name;
};

struct ShaderFnIR {
    std::vector<std::string> params;
    std::vector<ShaderFnOutput> outputs;
    std::vector<ShaderExprPtr> body;
};

enum class ShaderOpKind { INLINEABLE, PREPASS_REQUIRED, UNKNOWN };

struct ShaderIR {
    std::optional<ShaderFnIR> vertex;
    std::optional<ShaderFnIR> fragment;
    std::optional<ShaderFnIR> brdf;
};

} // namespace joon
```

- [ ] **Step 4: Build and run tests**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][ir]"
```
Expected: 8 tests pass.

- [ ] **Step 5: Run full suite, verify no regressions**

- [ ] **Step 6: Commit**

```bash
git add projects/joon/src/shader/shader_ir.h projects/joon/tests/test_shader_ir.cpp
git commit -m "feat(joon): define ShaderIR expression tree types"
```

---

### Task 5: Shader analyzer — build ShaderIR from AST and classify ops

**Files:**
- Create: `projects/joon/src/shader/shader_analyzer.h`
- Create: `projects/joon/src/shader/shader_analyzer.cpp`
- Modify: `projects/joon/tests/test_shader_ir.cpp`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_shader_ir.cpp`:

```cpp
#include "shader/shader_analyzer.h"
#include "ir/node.h"

TEST_CASE("Analyzer builds ShaderIR from ShaderDef", "[shader][analyzer]") {
    // Simulate a parsed shader with a simple fragment body: (set albedo [1 0 0 1])
    ShaderDef sd;
    ShaderFnDef frag;
    frag.params = {"normal", "uv"};
    frag.outputs = {{"albedo", "vec4"}};

    // Build AST for (set albedo [1 0 0 1])
    auto vec = std::make_unique<AstNode>();
    VectorNode vn;
    for (float v : {1.0f, 0.0f, 0.0f, 1.0f}) {
        auto num = std::make_unique<AstNode>();
        num->data = NumberNode{v};
        vn.elements.push_back(std::move(num));
    }
    vec->data = std::move(vn);

    auto set_call = std::make_unique<AstNode>();
    CallNode cn;
    cn.op = "set";
    auto target = std::make_unique<AstNode>();
    target->data = SymbolNode{"albedo"};
    cn.args.push_back(std::move(target));
    cn.args.push_back(std::move(vec));
    set_call->data = std::move(cn);

    frag.body.push_back(std::move(set_call));
    sd.fragment = std::move(frag);

    ShaderAnalyzer analyzer;
    auto ir = analyzer.analyze(sd);

    REQUIRE(ir.fragment.has_value());
    CHECK(ir.fragment->params.size() == 2);
    CHECK(ir.fragment->outputs.size() == 1);
    CHECK(ir.fragment->body.size() == 1);

    auto* assign = std::get_if<ShaderAssign>(ir.fragment->body[0].get());
    REQUIRE(assign != nullptr);
    CHECK(assign->target == "albedo");
}

TEST_CASE("Op classification: inlineable ops", "[shader][analyzer]") {
    ShaderAnalyzer analyzer;
    CHECK(analyzer.classify("sin") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("dot") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("noise") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("+") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("mix") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("step") == ShaderOpKind::INLINEABLE);
    CHECK(analyzer.classify("encode") == ShaderOpKind::INLINEABLE);
}

TEST_CASE("Op classification: prepass-required ops", "[shader][analyzer]") {
    ShaderAnalyzer analyzer;
    CHECK(analyzer.classify("blur") == ShaderOpKind::PREPASS_REQUIRED);
    CHECK(analyzer.classify("levels") == ShaderOpKind::PREPASS_REQUIRED);
    CHECK(analyzer.classify("blend") == ShaderOpKind::PREPASS_REQUIRED);
}

TEST_CASE("Op classification: unknown ops", "[shader][analyzer]") {
    ShaderAnalyzer analyzer;
    CHECK(analyzer.classify("foobar") == ShaderOpKind::UNKNOWN);
}
```

- [ ] **Step 2: Build, verify compile error**

- [ ] **Step 3: Implement ShaderAnalyzer**

```cpp
// src/shader/shader_analyzer.h
#pragma once
#include "shader/shader_ir.h"
#include "ir/node.h"
#include "dsl/ast.h"
#include <unordered_set>

namespace joon {

class ShaderAnalyzer {
public:
    ShaderIR analyze(const ShaderDef& sd);
    ShaderOpKind classify(const std::string& op) const;

private:
    ShaderExprPtr convert_expr(const AstNode& ast);
    ShaderFnIR convert_fn(const ShaderFnDef& fndef);

    static const std::unordered_set<std::string> INLINEABLE_OPS;
    static const std::unordered_set<std::string> PREPASS_OPS;
};

} // namespace joon
```

```cpp
// src/shader/shader_analyzer.cpp
#include "shader/shader_analyzer.h"

namespace joon {

const std::unordered_set<std::string> ShaderAnalyzer::INLINEABLE_OPS = {
    "+", "-", "*", "/",
    "pow", "sqrt", "abs", "floor", "ceil", "fract", "mod", "clamp", "min", "max",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "dot", "cross", "normalize", "length", "reflect", "refract",
    "mix", "step", "smoothstep",
    "noise", "fbm", "voronoi",
    "sample", "encode", "decode",
    "set"
};

const std::unordered_set<std::string> ShaderAnalyzer::PREPASS_OPS = {
    "blur", "levels", "blend", "threshold", "invert"
};

ShaderOpKind ShaderAnalyzer::classify(const std::string& op) const {
    if (INLINEABLE_OPS.count(op)) return ShaderOpKind::INLINEABLE;
    if (PREPASS_OPS.count(op)) return ShaderOpKind::PREPASS_REQUIRED;
    return ShaderOpKind::UNKNOWN;
}

ShaderExprPtr ShaderAnalyzer::convert_expr(const AstNode& ast) {
    if (auto* num = std::get_if<NumberNode>(&ast.data)) {
        return std::make_unique<ShaderExpr>(ShaderLiteral{static_cast<float>(num->value)});
    }
    if (auto* sym = std::get_if<SymbolNode>(&ast.data)) {
        return std::make_unique<ShaderExpr>(ShaderVar{sym->name});
    }
    if (auto* vec = std::get_if<VectorNode>(&ast.data)) {
        ShaderVecConstruct vc;
        for (auto& e : vec->elements)
            vc.elements.push_back(convert_expr(*e));
        return std::make_unique<ShaderExpr>(std::move(vc));
    }
    if (auto* dot = std::get_if<DotAccessNode>(&ast.data)) {
        ShaderDotAccess da;
        da.object = convert_expr(*dot->object);
        da.field = dot->field;
        return std::make_unique<ShaderExpr>(std::move(da));
    }
    if (auto* call = std::get_if<CallNode>(&ast.data)) {
        if (call->op == "set") {
            ShaderAssign sa;
            if (!call->args.empty()) {
                if (auto* target_sym = std::get_if<SymbolNode>(&call->args[0]->data))
                    sa.target = target_sym->name;
                else if (auto* target_dot = std::get_if<DotAccessNode>(&call->args[0]->data))
                    sa.target = target_dot->field; // simplified: pos.y → target="pos.y"
            }
            if (call->args.size() > 1)
                sa.value = convert_expr(*call->args[1]);
            return std::make_unique<ShaderExpr>(std::move(sa));
        }

        ShaderCall sc;
        sc.op = call->op;
        for (auto& a : call->args)
            sc.args.push_back(convert_expr(*a));
        for (auto& kw : call->kwargs) {
            if (auto* knum = std::get_if<NumberNode>(&kw.value->data))
                sc.kwargs.push_back({kw.name, static_cast<float>(knum->value)});
        }
        return std::make_unique<ShaderExpr>(std::move(sc));
    }
    return std::make_unique<ShaderExpr>(ShaderLiteral{0.0f});
}

ShaderFnIR ShaderAnalyzer::convert_fn(const ShaderFnDef& fndef) {
    ShaderFnIR fn;
    fn.params = fndef.params;
    for (auto& o : fndef.outputs)
        fn.outputs.push_back({o.name, o.type_name});
    for (auto& stmt : fndef.body)
        fn.body.push_back(convert_expr(*stmt));
    return fn;
}

ShaderIR ShaderAnalyzer::analyze(const ShaderDef& sd) {
    ShaderIR ir;
    if (sd.vertex) ir.vertex = convert_fn(*sd.vertex);
    if (sd.fragment) ir.fragment = convert_fn(*sd.fragment);
    if (sd.brdf) ir.brdf = convert_fn(*sd.brdf);
    return ir;
}

} // namespace joon
```

- [ ] **Step 4: Build and run tests**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][analyzer]"
```
Expected: 4 tests pass.

- [ ] **Step 5: Run full suite**

- [ ] **Step 6: Commit**

```bash
git add projects/joon/src/shader/ projects/joon/tests/test_shader_ir.cpp
git commit -m "feat(joon): shader analyzer builds ShaderIR from AST and classifies ops"
```

---

## Phase 4: HLSL Code Generation

### Task 6: HLSL emitter — fragment shader generation

**Files:**
- Create: `projects/joon/src/shader/hlsl_emitter.h`
- Create: `projects/joon/src/shader/hlsl_emitter.cpp`
- Create: `projects/joon/src/shader/noise_hlsl.h`
- Create: `projects/joon/tests/test_hlsl_emitter.cpp`

- [ ] **Step 1: Write failing tests**

```cpp
// tests/test_hlsl_emitter.cpp
#include "catch_amalgamated.hpp"
#include "shader/hlsl_emitter.h"
#include "shader/shader_ir.h"
using namespace joon;

TEST_CASE("Emit literal", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderExpr e = ShaderLiteral{1.5f};
    auto code = emitter.emit_expr(e);
    CHECK(code == "1.500000");
}

TEST_CASE("Emit binary op", "[shader][hlsl]") {
    HlslEmitter emitter;
    auto a = std::make_unique<ShaderExpr>(ShaderLiteral{1.0f});
    auto b = std::make_unique<ShaderExpr>(ShaderLiteral{2.0f});
    ShaderExpr e = ShaderCall{"+", {std::move(a), std::move(b)}, {}};
    auto code = emitter.emit_expr(e);
    CHECK(code == "(1.000000 + 2.000000)");
}

TEST_CASE("Emit function call", "[shader][hlsl]") {
    HlslEmitter emitter;
    auto arg = std::make_unique<ShaderExpr>(ShaderVar{"x"});
    ShaderExpr e = ShaderCall{"sin", {std::move(arg)}, {}};
    auto code = emitter.emit_expr(e);
    CHECK(code == "sin(x)");
}

TEST_CASE("Emit mix maps to lerp", "[shader][hlsl]") {
    HlslEmitter emitter;
    auto a = std::make_unique<ShaderExpr>(ShaderVar{"a"});
    auto b = std::make_unique<ShaderExpr>(ShaderVar{"b"});
    auto t = std::make_unique<ShaderExpr>(ShaderVar{"t"});
    ShaderExpr e = ShaderCall{"mix", {std::move(a), std::move(b), std::move(t)}, {}};
    auto code = emitter.emit_expr(e);
    CHECK(code == "lerp(a, b, t)");
}

TEST_CASE("Emit vector constructor", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderVecConstruct vc;
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    ShaderExpr e = std::move(vc);
    auto code = emitter.emit_expr(e);
    CHECK(code == "float3(1.000000, 0.000000, 0.000000)");
}

TEST_CASE("Emit encode normal", "[shader][hlsl]") {
    HlslEmitter emitter;
    auto n = std::make_unique<ShaderExpr>(ShaderVar{"normal"});
    ShaderExpr e = ShaderCall{"encode", {std::move(n)}, {}};
    auto code = emitter.emit_expr(e);
    CHECK(code == "float4(normal * 0.5 + 0.5, 1.0)");
}

TEST_CASE("Emit complete fragment shader", "[shader][hlsl]") {
    HlslEmitter emitter;
    ShaderFnIR frag;
    frag.params = {"normal", "uv"};
    frag.outputs = {{"albedo", "vec4"}, {"normal_out", "vec4"}};

    // (set albedo [1 0 0 1])
    ShaderVecConstruct vc;
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{0.0f}));
    vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
    ShaderAssign sa;
    sa.target = "albedo";
    sa.value = std::make_unique<ShaderExpr>(std::move(vc));
    frag.body.push_back(std::make_unique<ShaderExpr>(std::move(sa)));

    auto hlsl = emitter.emit_fragment(frag, 0);
    CHECK(hlsl.find("struct PSOut") != std::string::npos);
    CHECK(hlsl.find("SV_TARGET0") != std::string::npos);
    CHECK(hlsl.find("SV_TARGET1") != std::string::npos);
    CHECK(hlsl.find("o.albedo") != std::string::npos);
}
```

- [ ] **Step 2: Build, verify compile error**

- [ ] **Step 3: Create noise HLSL helper**

```cpp
// src/shader/noise_hlsl.h
#pragma once

namespace joon {

inline const char* NOISE_HLSL_FUNCTIONS = R"(
float hash31(float3 p) {
    p = frac(p * float3(443.8975, 397.2973, 491.1871));
    p += dot(p, p.yzx + 19.19);
    return frac((p.x + p.y) * p.z);
}

float noise3d(float3 p) {
    float3 i = floor(p);
    float3 f = frac(p);
    f = f * f * (3.0 - 2.0 * f);
    return lerp(
        lerp(lerp(hash31(i), hash31(i + float3(1,0,0)), f.x),
             lerp(hash31(i + float3(0,1,0)), hash31(i + float3(1,1,0)), f.x), f.y),
        lerp(lerp(hash31(i + float3(0,0,1)), hash31(i + float3(1,0,1)), f.x),
             lerp(hash31(i + float3(0,1,1)), hash31(i + float3(1,1,1)), f.x), f.y),
        f.z);
}

float fbm(float3 p, int octaves) {
    float val = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i = 0; i < octaves; i++) {
        val += amp * noise3d(p * freq);
        freq *= 2.0;
        amp *= 0.5;
    }
    return val;
}
)";

} // namespace joon
```

- [ ] **Step 4: Implement HlslEmitter**

```cpp
// src/shader/hlsl_emitter.h
#pragma once
#include "shader/shader_ir.h"
#include <string>

namespace joon {

class HlslEmitter {
public:
    std::string emit_expr(const ShaderExpr& expr);
    std::string emit_fragment(const ShaderFnIR& fn, uint32_t prepass_count);
    std::string emit_vertex(const ShaderFnIR& fn);

private:
    std::string emit_call(const ShaderCall& call);
    std::string emit_assign(const ShaderAssign& assign, bool is_fragment);
    std::string emit_vec(const ShaderVecConstruct& vc);
    std::string emit_dot(const ShaderDotAccess& da);

    static const std::unordered_map<std::string, std::string> OP_RENAMES;
    static const std::unordered_set<std::string> BINARY_OPS;
};

} // namespace joon
```

```cpp
// src/shader/hlsl_emitter.cpp
#include "shader/hlsl_emitter.h"
#include "shader/noise_hlsl.h"
#include <sstream>
#include <unordered_map>
#include <unordered_set>

namespace joon {

const std::unordered_map<std::string, std::string> HlslEmitter::OP_RENAMES = {
    {"mix", "lerp"}, {"fract", "frac"}, {"mod", "fmod"},
    {"atan2", "atan2"}, {"encode", "__encode_normal"},
    {"decode", "__decode_normal"},
};

const std::unordered_set<std::string> HlslEmitter::BINARY_OPS = {
    "+", "-", "*", "/"
};

std::string HlslEmitter::emit_expr(const ShaderExpr& expr) {
    if (auto* lit = std::get_if<ShaderLiteral>(&expr)) {
        char buf[32];
        snprintf(buf, sizeof(buf), "%f", lit->value);
        return buf;
    }
    if (auto* var = std::get_if<ShaderVar>(&expr))
        return var->name;
    if (auto* call = std::get_if<ShaderCall>(&expr))
        return emit_call(*call);
    if (auto* assign = std::get_if<ShaderAssign>(&expr))
        return emit_assign(*assign, true);
    if (auto* vc = std::get_if<ShaderVecConstruct>(&expr))
        return emit_vec(*vc);
    if (auto* da = std::get_if<ShaderDotAccess>(&expr))
        return emit_dot(*da);
    if (auto* ps = std::get_if<ShaderPrepassSample>(&expr)) {
        std::ostringstream ss;
        ss << "__prepass_" << ps->prepass_index
           << ".Sample(__sampler_" << ps->prepass_index << ", uv)";
        return ss.str();
    }
    return "0.0";
}

std::string HlslEmitter::emit_call(const ShaderCall& call) {
    if (call.op == "encode" && call.args.size() == 1) {
        return "float4(" + emit_expr(*call.args[0]) + " * 0.5 + 0.5, 1.0)";
    }
    if (call.op == "decode" && call.args.size() == 1) {
        return "(" + emit_expr(*call.args[0]) + ".xyz * 2.0 - 1.0)";
    }
    if (call.op == "noise") {
        float scale = 1.0f, octaves = 4.0f;
        for (auto& kw : call.kwargs) {
            if (kw.first == "scale") scale = kw.second;
            if (kw.first == "octaves") octaves = kw.second;
        }
        std::ostringstream ss;
        ss << "fbm(world_pos * " << scale << ", " << static_cast<int>(octaves) << ")";
        return ss.str();
    }

    if (BINARY_OPS.count(call.op) && call.args.size() == 2) {
        return "(" + emit_expr(*call.args[0]) + " " + call.op + " " + emit_expr(*call.args[1]) + ")";
    }

    std::string name = call.op;
    auto rename = OP_RENAMES.find(call.op);
    if (rename != OP_RENAMES.end()) name = rename->second;

    std::ostringstream ss;
    ss << name << "(";
    for (size_t i = 0; i < call.args.size(); i++) {
        if (i > 0) ss << ", ";
        ss << emit_expr(*call.args[i]);
    }
    ss << ")";
    return ss.str();
}

std::string HlslEmitter::emit_assign(const ShaderAssign& assign, bool is_fragment) {
    std::string prefix = is_fragment ? "o." : "";
    return prefix + assign.target + " = " + emit_expr(*assign.value);
}

std::string HlslEmitter::emit_vec(const ShaderVecConstruct& vc) {
    std::ostringstream ss;
    ss << "float" << vc.elements.size() << "(";
    for (size_t i = 0; i < vc.elements.size(); i++) {
        if (i > 0) ss << ", ";
        ss << emit_expr(*vc.elements[i]);
    }
    ss << ")";
    return ss.str();
}

std::string HlslEmitter::emit_dot(const ShaderDotAccess& da) {
    return emit_expr(*da.object) + "." + da.field;
}

std::string HlslEmitter::emit_fragment(const ShaderFnIR& fn, uint32_t prepass_count) {
    std::ostringstream ss;

    // Output struct
    ss << "struct PSOut {\n";
    for (size_t i = 0; i < fn.outputs.size(); i++) {
        std::string hlsl_type = (fn.outputs[i].type_name == "vec4") ? "float4" :
                                 (fn.outputs[i].type_name == "vec3") ? "float3" :
                                 (fn.outputs[i].type_name == "vec2") ? "float2" : "float";
        ss << "    " << hlsl_type << " " << fn.outputs[i].name
           << " : SV_TARGET" << i << ";\n";
    }
    ss << "};\n\n";

    // Input struct
    ss << "struct PSIn {\n"
       << "    float4 sv : SV_POSITION;\n"
       << "    float3 normal : NORMAL;\n"
       << "    float2 uv : TEXCOORD0;\n"
       << "    float3 world_pos : TEXCOORD1;\n"
       << "};\n\n";

    // Fragment UBO for time
    ss << "struct FragUBO { float time; float3 pad; };\n"
       << "[[vk::binding(0, 1)]] ConstantBuffer<FragUBO> frag_ubo;\n\n";

    // Pre-pass textures
    for (uint32_t i = 0; i < prepass_count; i++) {
        uint32_t binding = 1 + i * 2;
        ss << "[[vk::binding(" << binding << ", 1)]] Texture2D __prepass_" << i << ";\n";
        ss << "[[vk::binding(" << (binding + 1) << ", 1)]] SamplerState __sampler_" << i << ";\n";
    }
    if (prepass_count > 0) ss << "\n";

    // Noise helpers (if needed)
    // TODO: only emit if noise/fbm is used in the body
    ss << NOISE_HLSL_FUNCTIONS << "\n";

    // Main function
    ss << "PSOut main(PSIn i) {\n";
    ss << "    float3 normal = normalize(i.normal);\n";
    ss << "    float2 uv = i.uv;\n";
    ss << "    float3 world_pos = i.world_pos;\n";
    ss << "    float time = frag_ubo.time;\n";
    ss << "    PSOut o;\n";

    for (auto& stmt : fn.body) {
        ss << "    " << emit_expr(*stmt) << ";\n";
    }

    ss << "    return o;\n";
    ss << "}\n";
    return ss.str();
}

std::string HlslEmitter::emit_vertex(const ShaderFnIR& fn) {
    std::ostringstream ss;

    ss << "struct UBO { float4x4 mvp; float4x4 model; float time; float3 pad; };\n";
    ss << "[[vk::binding(0, 0)]] ConstantBuffer<UBO> ubo;\n\n";

    ss << "struct VSIn  { float3 pos : POSITION; float3 nrm : NORMAL; float2 uv : TEXCOORD0; };\n";
    ss << "struct VSOut { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; float3 world_pos : TEXCOORD1; };\n\n";

    ss << "VSOut main(VSIn v) {\n";
    ss << "    float3 pos = v.pos;\n";
    ss << "    float3 normal = v.nrm;\n";
    ss << "    float2 uv = v.uv;\n";
    ss << "    float time = ubo.time;\n";

    for (auto& stmt : fn.body) {
        ss << "    " << emit_expr(*stmt) << ";\n";
    }

    ss << "    VSOut o;\n";
    ss << "    o.sv = mul(ubo.mvp, float4(pos, 1.0));\n";
    ss << "    o.normal = normalize(mul((float3x3)ubo.model, normal));\n";
    ss << "    o.uv = uv;\n";
    ss << "    o.world_pos = mul(ubo.model, float4(pos, 1.0)).xyz;\n";
    ss << "    return o;\n";
    ss << "}\n";
    return ss.str();
}

} // namespace joon
```

- [ ] **Step 5: Build and run HLSL emitter tests**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][hlsl]"
```
Expected: 7 tests pass.

- [ ] **Step 6: Run full suite**

- [ ] **Step 7: Commit**

```bash
git add projects/joon/src/shader/ projects/joon/tests/test_hlsl_emitter.cpp
git commit -m "feat(joon): HLSL emitter generates fragment and vertex shaders from ShaderIR"
```

---

### Task 7: PipelineCache — accept generated HLSL source strings

**Files:**
- Modify: `projects/joon/src/vulkan/pipeline_cache.h`
- Modify: `projects/joon/src/vulkan/pipeline_cache.cpp`

- [ ] **Step 1: Write failing test**

Add to `tests/test_hlsl_emitter.cpp`:

```cpp
#include <joon/joon.h>

TEST_CASE("PipelineCache compiles generated HLSL source", "[shader][pipeline][gpu]") {
    auto ctx = joon::Context::create();
    auto& cache = ctx->pipeline_cache();

    std::string vert_src = R"(
struct UBO { float4x4 mvp; float4x4 model; float time; float3 pad; };
[[vk::binding(0, 0)]] ConstantBuffer<UBO> ubo;
struct VSIn  { float3 pos : POSITION; float3 nrm : NORMAL; float2 uv : TEXCOORD0; };
struct VSOut { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; float3 world_pos : TEXCOORD1; };
VSOut main(VSIn v) {
    VSOut o;
    o.sv = mul(ubo.mvp, float4(v.pos, 1.0));
    o.normal = normalize(mul((float3x3)ubo.model, v.nrm));
    o.uv = v.uv;
    o.world_pos = mul(ubo.model, float4(v.pos, 1.0)).xyz;
    return o;
}
)";

    std::string frag_src = R"(
struct PSOut { float4 albedo : SV_TARGET0; };
struct PSIn { float4 sv : SV_POSITION; float3 normal : NORMAL; float2 uv : TEXCOORD0; float3 world_pos : TEXCOORD1; };
PSOut main(PSIn i) {
    PSOut o;
    o.albedo = float4(1, 0, 0, 1);
    return o;
}
)";

    // Need a render pass for the pipeline
    auto rp = joon::create_color_depth_renderpass(ctx->device(), {VK_FORMAT_R8G8B8A8_UNORM});
    auto& gp = cache.get_graphics_from_source("test_gen", vert_src, frag_src, rp.pass, 0);
    CHECK(gp.pipeline != VK_NULL_HANDLE);
    joon::destroy_renderpass(ctx->device(), rp);
}
```

- [ ] **Step 2: Build, verify compile error (method doesn't exist)**

- [ ] **Step 3: Add `get_graphics_from_source()` to PipelineCache**

In `pipeline_cache.h`, add the new method declaration:
```cpp
const GraphicsPipeline& get_graphics_from_source(
    const std::string& key,
    const std::string& vert_hlsl_source,
    const std::string& frag_hlsl_source,
    VkRenderPass render_pass,
    uint32_t push_constant_size = 0,
    uint32_t num_color_attachments = 1);
```

In `pipeline_cache.cpp`, implement it. The key difference from `get_graphics()`: instead of calling `load_or_compile_stage()` with a filename, write the HLSL source to a temp file and compile that:

```cpp
const GraphicsPipeline& PipelineCache::get_graphics_from_source(
    const std::string& key,
    const std::string& vert_hlsl_source,
    const std::string& frag_hlsl_source,
    VkRenderPass render_pass,
    uint32_t push_constant_size,
    uint32_t num_color_attachments) {

    auto it = m_graphics_pipelines.find(key);
    if (it != m_graphics_pipelines.end()) return it->second;

    // Write HLSL source to temp files, compile via DXC
    std::string vert_tmp = m_shaderDir + "/__gen_" + key + ".vert.hlsl";
    std::string frag_tmp = m_shaderDir + "/__gen_" + key + ".frag.hlsl";
    std::string vert_spv = m_shaderDir + "/__gen_" + key + ".vert.spv";
    std::string frag_spv = m_shaderDir + "/__gen_" + key + ".frag.spv";

    // Write source to temp files
    { std::ofstream f(vert_tmp); f << vert_hlsl_source; }
    { std::ofstream f(frag_tmp); f << frag_hlsl_source; }

    auto vs_spirv = compile_hlsl(vert_tmp, vert_spv, "vs_6_0");
    auto fs_spirv = compile_hlsl(frag_tmp, frag_spv, "ps_6_0");

    // Rest is identical to get_graphics() — create modules, layout, pipeline
    // ... (reuse the same pipeline creation code, but pass num_color_attachments
    //      for the blend state to have the right attachment count)

    // Store and return
    m_graphics_pipelines[key] = p;
    return m_graphics_pipelines[key];
}
```

The blend state array needs `num_color_attachments` entries instead of the hardcoded 1. Extract the pipeline-creation logic from `get_graphics()` into a shared helper to avoid duplication.

- [ ] **Step 4: Expose `pipeline_cache()` on Context if not already available**

Check `include/joon/joon.h` for the Context class. If `pipeline_cache()` isn't public, add a method or use the test accessor pattern from sub-project 2.

- [ ] **Step 5: Build and run test**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][pipeline]"
```
Expected: 1 test passes.

- [ ] **Step 6: Run full suite**

- [ ] **Step 7: Commit**

```bash
git add projects/joon/src/vulkan/pipeline_cache.* projects/joon/tests/test_hlsl_emitter.cpp
git commit -m "feat(joon): PipelineCache accepts generated HLSL source strings"
```

---

## Phase 5: MRT & Depth Sampling

### Task 8: Resource pool — add sampled depth and MRT allocation

**Files:**
- Modify: `projects/joon/src/vulkan/resource_pool.h`
- Modify: `projects/joon/src/vulkan/resource_pool.cpp`

- [ ] **Step 1: Write failing test**

Add to `tests/test_hlsl_emitter.cpp` (or a new test file):

```cpp
TEST_CASE("alloc_depth_sampled creates depth with SAMPLED_BIT", "[shader][gpu]") {
    auto ctx = joon::Context::create();
    auto& pool = ctx->pool();
    auto* depth = pool.alloc_depth_sampled(999, 512, 512);
    REQUIRE(depth != nullptr);
    CHECK(depth->view != VK_NULL_HANDLE);
    CHECK(depth->format == VK_FORMAT_D32_SFLOAT);
}
```

- [ ] **Step 2: Build, verify compile error**

- [ ] **Step 3: Implement `alloc_depth_sampled()`**

In `resource_pool.h`:
```cpp
GpuImage* alloc_depth_sampled(uint32_t node_id, uint32_t w, uint32_t h,
                               VkFormat format = VK_FORMAT_D32_SFLOAT);
```

In `resource_pool.cpp`, copy the existing `alloc_depth()` but add `VK_IMAGE_USAGE_SAMPLED_BIT` to the usage flags:
```cpp
img_info.usage = VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT
               | VK_IMAGE_USAGE_SAMPLED_BIT;
```

- [ ] **Step 4: Build and run test**

- [ ] **Step 5: Run full suite**

- [ ] **Step 6: Commit**

```bash
git add projects/joon/src/vulkan/resource_pool.*
git commit -m "feat(joon): add alloc_depth_sampled with SAMPLED_BIT for deferred lighting"
```

---

## Phase 6: Material System

### Task 9: Material executor — compile shader and store pipeline

**Files:**
- Modify: `projects/joon/src/nodes/node_registry.h`
- Modify: `projects/joon/src/nodes/node_registry.cpp`
- Modify: `projects/joon/src/scene/scene_executors.h`
- Modify: `projects/joon/src/scene/scene_executors.cpp`
- Modify: `projects/joon/src/evaluator.cpp`
- Modify: `projects/joon/src/interpreter/interpreter.cpp`

- [ ] **Step 1: Write failing test**

```cpp
// Add to tests/test_shader_ir.cpp or create tests/test_deferred.cpp
TEST_CASE("Material executor compiles shader and stores pipeline", "[shader][material][gpu]") {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [1 0 0 1]))))
        (def c (cube :material mat))
        (def cam (camera))
        (def l (light))
        (def gbuf (pass))
        (output gbuf)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);
    // With a red material, we should see red pixels
    int red_pixels = 0;
    for (size_t i = 0; i < px.size(); i += 4)
        if (px[i] > 0.5f && px[i+1] < 0.2f && px[i+2] < 0.2f) ++red_pixels;
    CHECK(red_pixels > 50);
}
```

- [ ] **Step 2: Build, verify test fails (material not processed)**

- [ ] **Step 3: Extend EvalContext with material pipeline map**

In `src/nodes/node_registry.h`, add to `EvalContext`:
```cpp
std::unordered_map<uint32_t, const GraphicsPipeline*> material_pipelines;
```

This maps material node IDs to compiled pipelines.

- [ ] **Step 4: Add MATERIAL phase to interpreter**

In `src/interpreter/interpreter.cpp`, add a phase between the SCENE phase and the existing CPU/GPU/RENDER phase:

```cpp
// Phase 2: MATERIAL tier — compile shaders, cache pipelines
for (uint32_t id : order) {
    auto& node = ir.nodes[id];
    if (node.tier != Tier::MATERIAL) continue;
    auto* executor = m_registry.find(node.op);
    if (executor) (*executor)(node, m_ctx);
}
```

- [ ] **Step 5: Implement material executor**

In `src/scene/scene_executors.cpp`, add:

```cpp
#include "shader/shader_analyzer.h"
#include "shader/hlsl_emitter.h"
#include "vulkan/render_pass.h"

static void exec_shader(const Node& n, EvalContext& ctx) {
    if (!n.shader_def) return;

    ShaderAnalyzer analyzer;
    auto ir = analyzer.analyze(*n.shader_def);

    HlslEmitter emitter;

    // Generate vertex shader (use default if no custom vertex)
    std::string vert_src;
    if (ir.vertex) {
        vert_src = emitter.emit_vertex(*ir.vertex);
    } else {
        // Default vertex shader — same as scene_basic.vert.hlsl but with world_pos
        vert_src = emitter.emit_vertex(ShaderFnIR{{"pos", "normal", "uv"}, {}, {}});
    }

    // Generate fragment shader
    std::string frag_src;
    if (ir.fragment) {
        frag_src = emitter.emit_fragment(*ir.fragment, 0);
    } else {
        // Default: white albedo
        ShaderFnIR default_frag;
        default_frag.params = {"normal", "uv"};
        default_frag.outputs = {{"albedo", "vec4"}};
        ShaderAssign sa;
        sa.target = "albedo";
        ShaderVecConstruct vc;
        for (int i = 0; i < 4; i++)
            vc.elements.push_back(std::make_unique<ShaderExpr>(ShaderLiteral{1.0f}));
        sa.value = std::make_unique<ShaderExpr>(std::move(vc));
        default_frag.body.push_back(std::make_unique<ShaderExpr>(std::move(sa)));
        frag_src = emitter.emit_fragment(default_frag, 0);
    }

    // Compile via PipelineCache
    std::string key = "mat_" + std::to_string(n.id);
    uint32_t num_outputs = ir.fragment ? static_cast<uint32_t>(ir.fragment->outputs.size()) : 1;

    // Create a temporary render pass matching the output count
    std::vector<VkFormat> formats(num_outputs, VK_FORMAT_R8G8B8A8_UNORM);
    auto rp = create_color_depth_renderpass(ctx.device, formats);

    auto& gp = ctx.pipelines.get_graphics_from_source(key, vert_src, frag_src, rp.pass, 0, num_outputs);
    ctx.material_pipelines[n.id] = &gp;

    destroy_renderpass(ctx.device, rp);
}
```

Register the executor in `register_scene_nodes()` (or create a new `register_material_nodes()`):
```cpp
reg.register_node("shader", exec_shader);
```

- [ ] **Step 6: Wire `:material` kwarg on scene objects**

In `scene_executors.cpp`, modify `exec_cube` (and other scene executors) to read `:material` kwarg and store the material node ID on the SceneObject:

```cpp
void exec_cube(const Node& n, EvalContext& ctx) {
    SceneObject o;
    o.mesh = gen_cube(kwarg_float(n, "scale", 1.0f));
    o.position = kwarg_vec3(n, "position", {0, 0, 0});
    o.rotation = kwarg_vec3(n, "rotation", {0, 0, 0});
    // Material kwarg — source_node points to the material node
    for (auto& kw : n.kwargs) {
        if (kw.name == "material" && kw.source_node != UINT32_MAX)
            o.material_node_id = kw.source_node;
    }
    ctx.scene.add_object(std::move(o));
}
```

Apply the same pattern to `exec_sphere`, `exec_plane`, `exec_cylinder`, `exec_mesh`.

- [ ] **Step 7: Modify geometry pass to use per-material pipelines**

In `src/scene/geometry_pass.cpp`, modify `exec_pass`:

- Check if `ctx.material_pipelines` is non-empty.
- If it is, group objects by `material_node_id` and bind the matching pipeline per group.
- If an object has `material_node_id == UINT32_MAX` (no material), use the default `scene_basic` pipeline.
- Create the render pass and framebuffer based on the material's output count (for now, all materials must have the same output count — the G-buffer contract).

This is the most complex step. The key change: instead of one `vkCmdBindPipeline` for all draws, iterate over material groups and bind the appropriate pipeline for each.

- [ ] **Step 8: Build and run test**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][material]"
```
Expected: 1 test passes (red cube rendered via generated shader).

- [ ] **Step 9: Run full suite — verify existing tests still pass**

The existing `[render][gpu]` tests use `(pass)` without materials and should fall back to the hardcoded `scene_basic` pipeline.

- [ ] **Step 10: Commit**

```bash
git add projects/joon/src/ projects/joon/tests/
git commit -m "feat(joon): material executor compiles DSL shaders and renders per-material"
```

---

## Phase 7: Deferred Lighting

### Task 10: Fullscreen quad infrastructure

**Files:**
- Modify: `projects/joon/src/vulkan/buffer.h`, `buffer.cpp`
- Create: `projects/joon/shaders/fullscreen.vert.hlsl`

- [ ] **Step 1: Create fullscreen vertex shader**

```hlsl
// shaders/fullscreen.vert.hlsl
struct VSOut {
    float4 sv : SV_POSITION;
    float2 uv : TEXCOORD0;
};

VSOut main(uint vid : SV_VertexID) {
    VSOut o;
    // Full-screen triangle trick: 3 vertices, no vertex buffer needed
    o.uv = float2((vid << 1) & 2, vid & 2);
    o.sv = float4(o.uv * 2.0 - 1.0, 0.0, 1.0);
    o.uv.y = 1.0 - o.uv.y; // Flip Y for Vulkan
    return o;
}
```

- [ ] **Step 2: Verify it compiles via DXC**

```bash
"$VULKAN_SDK/Bin/dxc.exe" -T vs_6_0 -E main -spirv \
  -fspv-target-env=vulkan1.1 \
  projects/joon/shaders/fullscreen.vert.hlsl \
  -Fo projects/joon/shaders/fullscreen.vert.spv
```

- [ ] **Step 3: Commit**

```bash
git add projects/joon/shaders/fullscreen.vert.hlsl
git commit -m "feat(joon): fullscreen triangle vertex shader for deferred lighting"
```

---

### Task 11: Default Cook-Torrance lighting pass

**Files:**
- Create: `projects/joon/shaders/deferred_default.frag.hlsl`
- Create: `projects/joon/src/scene/lighting_pass.h`
- Create: `projects/joon/src/scene/lighting_pass.cpp`
- Modify: `projects/joon/include/joon/scene.h`
- Create: `projects/joon/tests/test_lighting_pass.cpp`

- [ ] **Step 1: Write failing test**

```cpp
// tests/test_lighting_pass.cpp
#include "catch_amalgamated.hpp"
#include <joon/joon.h>
using namespace joon;

TEST_CASE("Deferred lighting produces lit output", "[shader][lighting][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [0.8 0.2 0.1 1]))))
        (def c (cube :scale 1.5 :material mat))
        (def cam (camera :fov 60))
        (def l (light :intensity 1.0))
        (def gbuf (pass))
        (output gbuf)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);

    // Should have lit pixels (not just raw albedo — lighting applied)
    int lit = 0;
    for (size_t i = 0; i < px.size(); i += 4)
        if (px[i] > 0.05f) ++lit;
    CHECK(lit > 100);
}

TEST_CASE("Multiple lights produce brighter output", "[shader][lighting][gpu]") {
    auto ctx = Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [0.5 0.5 0.5 1]))))
        (def c (cube :material mat))
        (def cam (camera))
        (def l1 (light :intensity 1.0))
        (def l2 (light :intensity 1.0))
        (def gbuf (pass))
        (output gbuf)
    )");
    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);
}
```

- [ ] **Step 2: Build, verify test fails**

- [ ] **Step 3: Add LightUBO struct to scene.h**

In `include/joon/scene.h`:
```cpp
struct LightData {
    float position_type[4];   // xyz = position/direction, w = type (0=dir, 1=point, 2=spot)
    float color_intensity[4]; // xyz = color * intensity, w = unused
    float spot_params[4];     // xyz = spot direction, w = cos(angle)
};

struct LightUBO {
    LightData lights[16];
    int light_count;
    float camera_pos[3];
    float inv_view_proj[16]; // mat4 for world pos reconstruction
};
```

- [ ] **Step 4: Create default lighting fragment shader**

```hlsl
// shaders/deferred_default.frag.hlsl
struct LightData {
    float4 position_type;
    float4 color_intensity;
    float4 spot_params;
};

[[vk::binding(0, 0)]] Texture2D gbuf_albedo;
[[vk::binding(1, 0)]] Texture2D gbuf_depth;
[[vk::binding(2, 0)]] SamplerState samp;

struct LightUBO {
    LightData lights[16];
    int light_count;
    float3 camera_pos;
    float4x4 inv_view_proj;
};
[[vk::binding(3, 0)]] ConstantBuffer<LightUBO> light_ubo;

struct PSIn {
    float4 sv : SV_POSITION;
    float2 uv : TEXCOORD0;
};

float4 main(PSIn i) : SV_TARGET {
    float4 albedo = gbuf_albedo.Sample(samp, i.uv);
    if (albedo.a < 0.01) discard;

    float3 result = albedo.rgb * 0.1; // ambient

    for (int li = 0; li < light_ubo.light_count; li++) {
        float3 light_dir;
        float3 light_color = light_ubo.lights[li].color_intensity.xyz;
        float type = light_ubo.lights[li].position_type.w;

        if (type < 0.5) {
            // Directional
            light_dir = -normalize(light_ubo.lights[li].position_type.xyz);
        } else {
            light_dir = normalize(light_ubo.lights[li].position_type.xyz);
        }

        float ndotl = saturate(dot(float3(0, 0, 1), light_dir));
        result += albedo.rgb * light_color * ndotl;
    }

    return float4(result, 1.0);
}
```

Note: This is a simplified first version. The full Cook-Torrance GGX with world position reconstruction, normal map reading, and PBR calculations can be added incrementally after the basic pipeline works.

- [ ] **Step 5: Implement lighting pass**

```cpp
// src/scene/lighting_pass.h
#pragma once
#include "vulkan/device.h"
#include "vulkan/pipeline_cache.h"
#include "vulkan/resource_pool.h"
#include <joon/scene.h>
#include <joon/math.h>

namespace joon {

struct LightingPassConfig {
    Device& device;
    PipelineCache& pipelines;
    ResourcePool& pool;
    VkDescriptorPool desc_pool;
    const SceneCollection& scene;
    uint32_t width, height;
    GpuImage* albedo_target;
    GpuImage* depth_target;
    uint32_t output_node_id;
    mat4 view;
    mat4 proj;
};

void dispatch_lighting_pass(const LightingPassConfig& cfg);

} // namespace joon
```

```cpp
// src/scene/lighting_pass.cpp
#include "scene/lighting_pass.h"
#include "vulkan/buffer.h"
#include "vulkan/render_pass.h"

namespace joon {

void dispatch_lighting_pass(const LightingPassConfig& cfg) {
    // 1. Allocate output image for lit result
    auto* lit_output = cfg.pool.alloc_render_target(
        cfg.output_node_id, cfg.width, cfg.height, VK_FORMAT_R8G8B8A8_UNORM);

    // 2. Create render pass for the lighting output (single color attachment, no depth)
    RenderPass rp = create_color_depth_renderpass(cfg.device, {lit_output->format}, VK_FORMAT_UNDEFINED);
    // Note: need to handle "no depth" case — or create a simpler render pass factory.
    // Alternative: use a compute shader for lighting instead of a graphics pass.
    // For now, create a single-color-attachment render pass.

    VkFramebuffer fb = create_framebuffer(cfg.device, rp,
        {lit_output->view}, VK_NULL_HANDLE, cfg.width, cfg.height);

    // 3. Get the fullscreen + lighting pipeline
    auto& gp = cfg.pipelines.get_graphics("deferred_default_lighting", rp.pass, 0);
    // This needs custom descriptor layout: 2 textures + sampler + UBO

    // 4. Build LightUBO
    LightUBO light_ubo{};
    light_ubo.light_count = static_cast<int>(std::min(cfg.scene.lights.size(), size_t(16)));
    // ... fill light data from scene.lights
    // ... fill camera_pos and inv_view_proj from cfg.view and cfg.proj

    auto ub = create_uniform_buffer(cfg.device, sizeof(LightUBO));
    update_uniform_buffer(cfg.device, ub, &light_ubo, sizeof(LightUBO));

    // 5. Allocate descriptor set, bind G-buffer textures + light UBO
    // ... descriptor writes for albedo, depth, sampler, light UBO

    // 6. Record command buffer
    VkCommandBuffer cmd = cfg.device.begin_single_command();
    // Begin render pass, bind pipeline, bind descriptors, draw 3 vertices (fullscreen tri)
    // End render pass
    // Transition lit_output to GENERAL

    cfg.device.end_single_command(cmd);

    // 7. Cleanup per-frame resources
    destroy_buffer(cfg.device, ub);
    vkDestroyFramebuffer(cfg.device.device, fb, nullptr);
    destroy_renderpass(cfg.device, rp);
}

} // namespace joon
```

- [ ] **Step 6: Integrate lighting pass into geometry pass executor**

In `src/scene/geometry_pass.cpp`, after the existing render pass ends and the color attachment transitions to GENERAL, call `dispatch_lighting_pass()` if materials are present:

```cpp
// After vkCmdEndRenderPass and color-to-GENERAL barrier:
if (!ctx.material_pipelines.empty()) {
    LightingPassConfig lcfg{
        ctx.device, ctx.pipelines, ctx.pool, ctx.desc_pool,
        ctx.scene, ctx.default_width, ctx.default_height,
        albedo, depth, n.id, view, proj
    };
    dispatch_lighting_pass(lcfg);
    // The lit output is now at node_id in the resource pool — downstream reads this
}
```

- [ ] **Step 7: Build and run lighting tests**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][lighting]"
```
Expected: 2 tests pass.

- [ ] **Step 8: Run full suite**

- [ ] **Step 9: Commit**

```bash
git add projects/joon/shaders/deferred_default.frag.hlsl projects/joon/src/scene/lighting_pass.* \
  projects/joon/include/joon/scene.h projects/joon/tests/test_lighting_pass.cpp
git commit -m "feat(joon): deferred lighting pass with Cook-Torrance default and multiple lights"
```

---

## Phase 8: G-Buffer Access

### Task 12: Dot-access resolution for G-buffer channels

**Files:**
- Modify: `projects/joon/src/ir/ir_graph.cpp`
- Modify: `projects/joon/tests/test_shader_parser.cpp`

- [ ] **Step 1: Write failing test**

```cpp
TEST_CASE("Dot access on pass output resolves to sub-image", "[shader][ir]") {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_string(R"(
        (def mat (shader
          :fragment (fn [normal uv] -> [albedo vec4, normals vec4]
            (set albedo [1 0 0 1])
            (set normals (encode normal)))))
        (def c (cube :material mat))
        (def cam (camera))
        (def l (light))
        (def gbuf (pass :outputs [albedo normals depth]))
        (def result (levels gbuf.albedo :contrast 1.5))
        (output result)
    )");
    REQUIRE_FALSE(graph.has_errors());
}
```

- [ ] **Step 2: Build, verify test fails**

Currently, `gbuf.albedo` will parse as a `DotAccessNode` but the IR lowering doesn't know how to resolve it.

- [ ] **Step 3: Implement dot-access resolution in IR graph**

In `src/ir/ir_graph.cpp`, in `resolve_expr()`, add handling for `DotAccessNode`:

```cpp
if (auto* dot = std::get_if<DotAccessNode>(&expr.data)) {
    // Resolve the object (e.g., "gbuf" → pass node)
    auto* obj_sym = std::get_if<SymbolNode>(&dot->object->data);
    if (obj_sym) {
        auto it = m_nameToNode.find(obj_sym->name);
        if (it != m_nameToNode.end()) {
            uint32_t parent_id = it->second;
            // Create a synthetic node that references a sub-image of the parent
            uint32_t id = add_node("channel_select", Tier::CPU);
            nodes[id].inputs.push_back(parent_id);
            edges.push_back({parent_id, id, 0});
            nodes[id].string_arg = dot->field; // "albedo", "normals", "depth"
            nodes[id].output_type = Type::IMAGE;
            return id;
        }
    }
    diagnostics.push_back({Diagnostic::Level::ERROR, "Invalid dot access", expr.line, expr.col});
    return add_node("error", Tier::CPU);
}
```

Then implement a `channel_select` executor that extracts a specific render target from the pass's MRT output. This requires the pass node to register its output images by channel name.

- [ ] **Step 4: Build and run test**

- [ ] **Step 5: Commit**

```bash
git add projects/joon/src/ir/ projects/joon/tests/
git commit -m "feat(joon): dot-access resolution for G-buffer channel selection"
```

---

## Phase 9: Custom BRDF

### Task 13: Custom BRDF codegen and lighting shader variants

**Files:**
- Create: `projects/joon/src/shader/brdf_emitter.h`
- Create: `projects/joon/src/shader/brdf_emitter.cpp`
- Modify: `projects/joon/src/scene/lighting_pass.cpp`

- [ ] **Step 1: Write failing test**

```cpp
TEST_CASE("Custom toon BRDF produces stepped lighting", "[shader][brdf][gpu]") {
    auto ctx = joon::Context::create();
    auto graph = ctx->parse_string(R"(
        (def toon_mat (shader
          :brdf (fn [normal light_dir view_dir albedo]
            (* albedo (step 0.3 (dot normal light_dir))))
          :fragment (fn [normal uv] -> [albedo vec4]
            (set albedo [0.3 0.8 0.2 1]))))
        (def c (cube :material toon_mat))
        (def cam (camera))
        (def l (light))
        (def gbuf (pass))
        (output gbuf)
    )");
    REQUIRE_FALSE(graph.has_errors());

    auto eval = ctx->create_evaluator(graph);
    eval->evaluate();

    auto px = eval->result("").read_pixels();
    REQUIRE(px.size() == 512u * 512u * 4u);
    // Toon shading produces binary lit/unlit — check for distinct value clusters
    int bright = 0, dark = 0;
    for (size_t i = 0; i < px.size(); i += 4) {
        if (px[i+1] > 0.5f) ++bright;
        else if (px[i+1] > 0.01f && px[i+1] < 0.3f) ++dark;
    }
    CHECK(bright > 50);
}
```

- [ ] **Step 2: Build, verify test fails**

- [ ] **Step 3: Implement BRDF emitter**

```cpp
// src/shader/brdf_emitter.h
#pragma once
#include "shader/shader_ir.h"
#include "shader/hlsl_emitter.h"
#include <string>

namespace joon {

class BrdfEmitter {
public:
    std::string emit_lighting_shader(const ShaderFnIR& brdf,
                                      const std::vector<ShaderFnOutput>& gbuf_outputs);
    std::string emit_default_lighting_shader();
};

} // namespace joon
```

```cpp
// src/shader/brdf_emitter.cpp
#include "shader/brdf_emitter.h"
#include <sstream>

namespace joon {

std::string BrdfEmitter::emit_lighting_shader(const ShaderFnIR& brdf,
                                                const std::vector<ShaderFnOutput>& gbuf_outputs) {
    HlslEmitter hlsl;
    std::ostringstream ss;

    // G-buffer texture bindings
    ss << "[[vk::binding(0, 0)]] Texture2D gbuf_albedo;\n";
    ss << "[[vk::binding(1, 0)]] Texture2D gbuf_depth;\n";
    ss << "[[vk::binding(2, 0)]] SamplerState samp;\n\n";

    // Light UBO
    ss << "struct LightData { float4 position_type; float4 color_intensity; float4 spot_params; };\n";
    ss << "struct LightUBO { LightData lights[16]; int light_count; float3 camera_pos; float4x4 inv_view_proj; };\n";
    ss << "[[vk::binding(3, 0)]] ConstantBuffer<LightUBO> light_ubo;\n\n";

    ss << "struct PSIn { float4 sv : SV_POSITION; float2 uv : TEXCOORD0; };\n\n";

    ss << "float4 main(PSIn i) : SV_TARGET {\n";
    ss << "    float4 albedo = gbuf_albedo.Sample(samp, i.uv);\n";
    ss << "    if (albedo.a < 0.01) discard;\n\n";

    // Emit BRDF loop
    ss << "    float3 result = float3(0, 0, 0);\n";
    ss << "    float3 normal = float3(0, 0, 1);\n"; // simplified for single-output materials
    ss << "    float3 view_dir = float3(0, 0, 1);\n\n";

    ss << "    for (int li = 0; li < light_ubo.light_count; li++) {\n";
    ss << "        float3 light_dir = -normalize(light_ubo.lights[li].position_type.xyz);\n";
    ss << "        float3 light_color = light_ubo.lights[li].color_intensity.xyz;\n";

    // Emit the custom BRDF body
    // The BRDF fn returns a color contribution — emit it as the loop body
    for (auto& stmt : brdf.body) {
        ss << "        result += " << hlsl.emit_expr(*stmt) << " * light_color;\n";
    }

    ss << "    }\n\n";
    ss << "    return float4(result, 1.0);\n";
    ss << "}\n";

    return ss.str();
}

std::string BrdfEmitter::emit_default_lighting_shader() {
    // Return the contents of deferred_default.frag.hlsl as a string
    // Or just reference the file — the PipelineCache can load it from disk
    return ""; // use file-based default
}

} // namespace joon
```

- [ ] **Step 4: Integrate BRDF variants into lighting pass**

In `lighting_pass.cpp`, check if the material has a custom BRDF. If so, generate a variant lighting shader via `BrdfEmitter` and compile it via `PipelineCache::get_graphics_from_source()`. Cache by BRDF hash.

- [ ] **Step 5: Build and run test**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][brdf]"
```

- [ ] **Step 6: Run full suite**

- [ ] **Step 7: Commit**

```bash
git add projects/joon/src/shader/brdf_emitter.* projects/joon/src/scene/lighting_pass.cpp \
  projects/joon/tests/
git commit -m "feat(joon): custom BRDF codegen with per-material lighting shader variants"
```

---

## Phase 10: Pre-Pass Extraction

### Task 14: Auto-extract non-inlineable ops from shader bodies

**Files:**
- Create: `projects/joon/src/shader/prepass_extractor.h`
- Create: `projects/joon/src/shader/prepass_extractor.cpp`
- Create: `projects/joon/tests/test_prepass.cpp`

- [ ] **Step 1: Write failing test**

```cpp
// tests/test_prepass.cpp
#include "catch_amalgamated.hpp"
#include "shader/prepass_extractor.h"
#include "shader/shader_analyzer.h"
#include "shader/shader_ir.h"
using namespace joon;

TEST_CASE("Prepass extracts blur from shader body", "[shader][prepass]") {
    // Simulate: (set albedo (blur (noise :scale 4.0) :radius 3))
    // The "blur" is non-inlineable, so it should be extracted.
    ShaderCall noise_call{"noise", {}, {{"scale", 4.0f}, {"octaves", 4.0f}}};
    auto noise = std::make_unique<ShaderExpr>(std::move(noise_call));

    ShaderCall blur_call{"blur", {std::move(noise)}, {{"radius", 3.0f}}};
    auto blur = std::make_unique<ShaderExpr>(std::move(blur_call));

    ShaderAssign assign;
    assign.target = "albedo";
    assign.value = std::move(blur);

    ShaderFnIR frag;
    frag.params = {"normal", "uv"};
    frag.outputs = {{"albedo", "vec4"}};
    frag.body.push_back(std::make_unique<ShaderExpr>(std::move(assign)));

    ShaderAnalyzer analyzer;
    PrepassExtractor extractor(analyzer);
    auto result = extractor.extract(frag);

    CHECK(result.prepasses.size() == 1);
    CHECK(result.prepasses[0].root_op == "blur");

    // The body should now have a prepass sample instead of the blur call
    auto* new_assign = std::get_if<ShaderAssign>(result.modified_body[0].get());
    REQUIRE(new_assign != nullptr);
    auto* sample = std::get_if<ShaderPrepassSample>(new_assign->value.get());
    CHECK(sample != nullptr);
    CHECK(sample->prepass_index == 0);
}

TEST_CASE("Prepass leaves inlineable ops untouched", "[shader][prepass]") {
    // (set albedo (noise :scale 4.0)) — noise is inlineable
    ShaderCall noise{"noise", {}, {{"scale", 4.0f}}};
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
    // Body unchanged — still a ShaderCall noise
    auto* a = std::get_if<ShaderAssign>(result.modified_body[0].get());
    REQUIRE(a != nullptr);
    CHECK(std::get_if<ShaderCall>(a->value.get()) != nullptr);
}
```

- [ ] **Step 2: Build, verify compile error**

- [ ] **Step 3: Implement PrepassExtractor**

```cpp
// src/shader/prepass_extractor.h
#pragma once
#include "shader/shader_ir.h"
#include "shader/shader_analyzer.h"
#include <vector>

namespace joon {

struct ExtractedPrepass {
    std::string root_op;
    ShaderExprPtr compute_tree;  // the sub-tree to run as a compute pass
};

struct ExtractionResult {
    std::vector<ExtractedPrepass> prepasses;
    std::vector<ShaderExprPtr> modified_body;
};

class PrepassExtractor {
public:
    explicit PrepassExtractor(const ShaderAnalyzer& analyzer);
    ExtractionResult extract(const ShaderFnIR& fn);

private:
    const ShaderAnalyzer& m_analyzer;
    uint32_t m_prepass_count = 0;

    ShaderExprPtr walk(ShaderExprPtr expr);
};

} // namespace joon
```

```cpp
// src/shader/prepass_extractor.cpp
#include "shader/prepass_extractor.h"

namespace joon {

PrepassExtractor::PrepassExtractor(const ShaderAnalyzer& analyzer)
    : m_analyzer(analyzer) {}

ShaderExprPtr PrepassExtractor::walk(ShaderExprPtr expr) {
    if (auto* call = std::get_if<ShaderCall>(expr.get())) {
        if (m_analyzer.classify(call->op) == ShaderOpKind::PREPASS_REQUIRED) {
            // Extract this entire sub-tree as a pre-pass
            uint32_t idx = m_prepass_count++;
            // The original expr becomes a prepass sample
            return std::make_unique<ShaderExpr>(ShaderPrepassSample{idx});
        }
        // Recurse into args
        for (auto& arg : call->args)
            arg = walk(std::move(arg));
    }
    if (auto* assign = std::get_if<ShaderAssign>(expr.get())) {
        if (assign->value)
            assign->value = walk(std::move(assign->value));
    }
    return expr;
}

ExtractionResult PrepassExtractor::extract(const ShaderFnIR& fn) {
    ExtractionResult result;
    m_prepass_count = 0;

    // First pass: find prepass-required ops and record them
    // We need to clone the body and walk it, extracting as we go
    // For simplicity, walk in-place on a copy

    for (auto& stmt : fn.body) {
        // Walk each statement, replacing prepass ops with samples
        auto modified = walk(std::make_unique<ShaderExpr>(*stmt)); // needs clone
        result.modified_body.push_back(std::move(modified));
    }

    // Build prepass entries (would need to save the extracted trees — this is simplified)
    // In a full implementation, walk() would save the extracted sub-trees before replacing
    for (uint32_t i = 0; i < m_prepass_count; i++) {
        result.prepasses.push_back({/* root_op from extracted tree */"blur", nullptr});
    }

    return result;
}

} // namespace joon
```

Note: This is a simplified skeleton. The full implementation needs to:
1. Clone ShaderExpr trees (add a clone() method to ShaderExpr)
2. Save the extracted sub-tree before replacing it
3. Convert the extracted ShaderIR sub-tree back to IR graph nodes for compute dispatch

- [ ] **Step 4: Build and run tests**

```bash
projects/joon/build/bin/Debug/joon-tests.exe "[shader][prepass]"
```

- [ ] **Step 5: Run full suite**

- [ ] **Step 6: Commit**

```bash
git add projects/joon/src/shader/prepass_extractor.* projects/joon/tests/test_prepass.cpp
git commit -m "feat(joon): pre-pass extraction for non-inlineable ops in shader bodies"
```

---

## Phase 11: Polish

### Task 15: Update GUI default DSL to showcase materials and lighting

**Files:**
- Modify: `projects/joon/gui/app.cpp`

- [ ] **Step 1: Update default DSL**

```cpp
dsl_source = R"(; Joon - 3D scene with materials
(def red_mat (shader
  :fragment (fn [normal uv] -> [albedo vec4]
    (set albedo [0.8 0.2 0.1 1]))))

(def c (cube :scale 1.0 :material red_mat))
(def cam (camera :fov 60))
(def l (light :intensity 1.0))
(def gbuf (pass))
(param contrast float 1.0 :min 0.0 :max 3.0)
(def final (levels gbuf :contrast contrast))
(output final)
)";
```

- [ ] **Step 2: Build**

- [ ] **Step 3: Launch GUI, verify visual output**

```bash
projects/joon/build/bin/Debug/joon-gui.exe
```

Check: red-shaded cube visible, contrast slider works, no validation errors in log.

- [ ] **Step 4: Commit**

```bash
git add projects/joon/gui/app.cpp
git commit -m "feat(joon): GUI default DSL uses material shader with deferred lighting"
```

---

### Task 16: Final verification and PR

- [ ] **Step 1: Clean build**

```bash
cd projects/joon && rm -rf build && /d/prg/premake5.exe vs2022
cd build && "/c/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" \
  Joon.sln -p:Configuration=Debug -p:Platform=x64 -m -v:minimal
```

- [ ] **Step 2: Run full test suite**

```bash
projects/joon/build/bin/Debug/joon-tests.exe
```
Expected: all tests pass (59 existing + ~20 new shader tests).

- [ ] **Step 3: Run GUI — visual confirmation**

Launch `joon-gui.exe`. Confirm:
- Shaded cube with material renders correctly
- Contrast slider produces real-time updates
- No Vulkan validation errors in log

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin joon-shader-codegen
gh pr create --title "feat(joon): DSL-generated shaders and deferred lighting (sub-project 3)" \
  --body "..."
```

---

## Open Considerations

These are decisions to resolve during implementation if the prescribed approach doesn't work:

1. **Render pass without depth for lighting.** The lighting pass needs a single-color-attachment render pass with no depth. `create_color_depth_renderpass` currently always creates a depth attachment. May need a `create_color_only_renderpass` variant or a flag.

2. **PipelineCache key for generated shaders.** Currently keyed by name + render_pass ptr + push_constant_size. Generated shaders use a string key ("mat_N"). If materials change between evaluations (DSL re-parsed), old pipeline entries stay cached. This is fine for sub-project 3 but may need cache invalidation later.

3. **ShaderExpr cloning for pre-pass extraction.** The pre-pass extractor needs to clone ShaderExpr trees to save the extracted sub-tree before replacing it in the body. Implement a `clone()` method on ShaderExpr using recursive variant visiting. The skeleton in Task 14 step 3 needs this fleshed out — `walk()` must save the extracted sub-tree into `result.prepasses` before replacing it with `ShaderPrepassSample`.

4. **Descriptor set layout for lighting.** The lighting pass binds textures + UBO with a layout different from the compute and geometry pipelines. `get_graphics_from_source()` needs to support custom descriptor set layouts, not just the hardcoded UBO-only layout from `get_graphics()`. Consider passing a descriptor layout specification or auto-reflecting from the SPIR-V.

5. **G-buffer channel_select executor.** The `channel_select` synthetic node created by dot-access resolution needs an executor that returns the Nth color attachment image from the parent pass node's MRT output. The pass node needs to register its output images by channel name in a map on EvalContext.

6. **VectorNode kwargs for pass `:outputs`.** Task 12 uses `(pass :outputs [albedo normals depth])` which is a VectorNode kwarg value. The existing IR graph kwargs handler (and Task 3's extension for FnNode) doesn't handle VectorNode values. Task 12's implementation must also add VectorNode kwarg resolution in `ir_graph.cpp` — extract the symbol names from the vector and store them on the pass node as the channel name list.

7. **Unknown op error in shader bodies.** Task 5 classifies unknown ops as `ShaderOpKind::UNKNOWN` but no task explicitly surfaces a compile error diagnostic. During shader analysis (Task 5) or HLSL emission (Task 6), if an op classifies as UNKNOWN, emit a diagnostic error listing the op and its location. Add this check to `ShaderAnalyzer::convert_expr()` when processing a `CallNode` — if `classify(call->op) == UNKNOWN`, push a diagnostic and return a zero literal.

8. **G-buffer contract validation.** The spec requires that all materials in a `(pass)` share the same fragment output signature. This validation should happen in the geometry pass executor (Task 9 step 7): before rendering, compare each material's `ShaderFnIR::outputs` against the pass's `:outputs` list. If they don't match, emit a diagnostic error with both signatures and skip the material.

9. **Pipeline creation in `get_graphics_from_source()`.** Task 7 step 3 shows the temp-file writing and DXC compilation but elides the VkPipeline creation. The implementation should extract the common pipeline-creation logic from `get_graphics()` into a shared helper (taking shader modules, render pass, push constant size, and num_color_attachments) to avoid duplicating the blend state, rasterizer state, and vertex input setup.

10. **Lighting pass Vulkan details.** Task 11 step 5 elides descriptor set writes and light UBO filling. The implementation must: (a) create a VkDescriptorSetLayout matching the deferred shader bindings (2 textures, 1 sampler, 1 UBO), (b) allocate and write descriptor sets binding `albedo_target->view`, `depth_target->view`, and the light UBO buffer, (c) fill `LightUBO::lights[]` from `SceneCollection::lights` with position/direction, color * intensity, and type, (d) compute `inv_view_proj` as `inverse(proj * view)` and `camera_pos` from the inverse of the view matrix.
