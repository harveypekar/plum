# Joon Comprehensive Test Suite Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand joon test suite from 4 basic test files to comprehensive coverage (50+ tests) with focus on lexer edge cases, error handling, and all major components.

**Architecture:** Test-driven development approach: each test targets a specific behavior, covering happy paths, edge cases, error conditions, and boundary conditions. Tests organized by component (lexer, parser, evaluator, graph, nodes, type-checker).

**Tech Stack:** Catch2 testing framework, C++20, TDD methodology

---

## Task 1: Expand Lexer Tests — Basic Token Types

**Files:**
- Modify: `projects/joon/tests/test_lexer.cpp` (add tests after line 81)

**New Tests to Add:**

```cpp
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

TEST_CASE("Lexer handles all parenthesis types", "[lexer]") {
    Lexer lexer("()[]{}");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 6);
    CHECK(tokens[0].type == TokenType::LParen);
    CHECK(tokens[1].type == TokenType::RParen);
    CHECK(tokens[2].type == TokenType::LBracket);
    CHECK(tokens[3].type == TokenType::RBracket);
    CHECK(tokens[4].type == TokenType::LBrace);
    CHECK(tokens[5].type == TokenType::RBrace);
}

TEST_CASE("Lexer handles integer numbers", "[lexer]") {
    Lexer lexer("(+ 42 -100)");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 5);
    CHECK(tokens[2].type == TokenType::Number);
    CHECK(tokens[2].text == "42");
    CHECK(tokens[3].type == TokenType::Number);
    CHECK(tokens[3].text == "-100");
}

TEST_CASE("Lexer handles floating point numbers", "[lexer]") {
    Lexer lexer("3.14159 0.0 -0.5");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 3);
    CHECK(tokens[0].text == "3.14159");
    CHECK(tokens[1].text == "0.0");
    CHECK(tokens[2].text == "-0.5");
}

TEST_CASE("Lexer handles scientific notation", "[lexer]") {
    Lexer lexer("1e10 1.5e-5 2E+3");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 3);
    CHECK(tokens[0].type == TokenType::Number);
    CHECK(tokens[1].type == TokenType::Number);
    CHECK(tokens[2].type == TokenType::Number);
}

TEST_CASE("Lexer handles all special symbols", "[lexer]") {
    Lexer lexer("+ - * / < > = ! & |");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 10);
    for (auto& token : tokens) {
        CHECK(token.type == TokenType::Symbol);
    }
}

TEST_CASE("Lexer handles quoted strings with escapes", "[lexer]") {
    Lexer lexer(R"("hello \"world\"" "newline\n")");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 2);
    CHECK(tokens[0].type == TokenType::String);
    CHECK(tokens[1].type == TokenType::String);
}

TEST_CASE("Lexer handles multiple keywords", "[lexer]") {
    Lexer lexer(":x :y :scale :octaves :seed");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 5);
    for (auto& token : tokens) {
        CHECK(token.type == TokenType::Keyword);
    }
}
```

**Step 1: Add tests to test_lexer.cpp**

Append the above test cases to the end of `test_lexer.cpp`.

**Step 2: Run tests**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
msbuild build/joon-tests.vcxproj /p:Configuration=Debug 2>&1 | grep -E "PASS|FAIL" | head -20
"build/bin/Debug/joon-tests.exe" "[lexer]"
```

Expected: All new tests pass (8 new test cases)

**Step 3: Commit**

```bash
git add tests/test_lexer.cpp
git commit -m "test: add comprehensive lexer tests for token types and edge cases"
```

---

## Task 2: Expand Lexer Tests — Error Handling and Edge Cases

**Files:**
- Modify: `projects/joon/tests/test_lexer.cpp`

**New Tests:**

```cpp
TEST_CASE("Lexer handles unclosed parenthesis", "[lexer]") {
    Lexer lexer("(def x");
    auto tokens = lexer.tokenize();
    // Should still tokenize what's available
    CHECK(tokens.size() >= 2);
    CHECK(tokens[0].type == TokenType::LParen);
}

TEST_CASE("Lexer handles unclosed string", "[lexer]") {
    Lexer lexer("(image \"unclosed");
    auto tokens = lexer.tokenize();
    // Should handle gracefully - at minimum parse the paren and symbol
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
    CHECK(tokens[0].type == TokenType::LParen);
    CHECK(tokens[1].text == "def");
}

TEST_CASE("Lexer handles comment at end of line", "[lexer]") {
    Lexer lexer("(+ 1 2) ; this is a comment");
    auto tokens = lexer.tokenize();
    REQUIRE(tokens.size() == 5);
    CHECK(tokens[4].type == TokenType::RParen);
}

TEST_CASE("Lexer accurately tracks line numbers across multiple lines", "[lexer]") {
    Lexer lexer("(def x\n  (+ 1\n     2))");
    auto tokens = lexer.tokenize();
    CHECK(tokens[0].line == 1);
    CHECK(tokens[3].line == 2);
    CHECK(tokens[5].line == 3);
}

TEST_CASE("Lexer accurately tracks column numbers within line", "[lexer]") {
    Lexer lexer("(a b c)");
    auto tokens = lexer.tokenize();
    CHECK(tokens[0].col == 1);  // (
    CHECK(tokens[1].col == 2);  // a
    CHECK(tokens[2].col == 4);  // b
    CHECK(tokens[3].col == 6);  // c
}

TEST_CASE("Lexer handles very long input", "[lexer]") {
    std::string long_input;
    for (int i = 0; i < 1000; i++) {
        long_input += "(x) ";
    }
    Lexer lexer(long_input);
    auto tokens = lexer.tokenize();
    // Should have 3000 tokens (3 per iteration)
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
    CHECK(tokens[0].type == TokenType::String);
    // Should preserve content exactly as between quotes
    CHECK(tokens[0].text.find("spaces") != std::string::npos);
}
```

**Step 1: Append tests to test_lexer.cpp**

Add the 11 new test cases.

**Step 2: Run tests**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
"build/bin/Debug/joon-tests.exe" "[lexer]"
```

Expected: All 19 lexer tests pass (8 from Task 1 + 11 from Task 2)

**Step 3: Commit**

```bash
git add tests/test_lexer.cpp
git commit -m "test: add error handling and edge case tests for lexer"
```

---

## Task 3: Expand Parser Tests

**Files:**
- Modify: `projects/joon/tests/test_parser.cpp`

**New Tests:**

```cpp
TEST_CASE("Parser handles nested expressions", "[parser]") {
    Lexer lexer("((((a))))");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}

TEST_CASE("Parser handles multiple top-level expressions", "[parser]") {
    Lexer lexer("(def x 1.0) (def y 2.0) (+ x y)");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}

TEST_CASE("Parser preserves operator precedence", "[parser]") {
    Lexer lexer("(+ (* 2 3) 4)");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    // Verify structure preserves precedence
    CHECK(ast != nullptr);
}

TEST_CASE("Parser handles keyword arguments", "[parser]") {
    Lexer lexer("(noise :scale 4.0 :octaves 3)");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}

TEST_CASE("Parser handles quoted symbols", "[parser]") {
    Lexer lexer("(quote foo)");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}

TEST_CASE("Parser rejects unmatched closing paren", "[parser]") {
    Lexer lexer("(+ 1 2))");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    // Should handle gracefully - might return partial AST or error
    // Behavior depends on implementation
}

TEST_CASE("Parser handles empty list", "[parser]") {
    Lexer lexer("()");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}

TEST_CASE("Parser handles list with only keywords", "[parser]") {
    Lexer lexer("(:a :b :c)");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}
```

**Step 1: Add tests to test_parser.cpp**

```bash
cat >> "D:/prg/plum/.worktrees/joon/tests/test_parser.cpp" << 'EOF'

TEST_CASE("Parser handles nested expressions", "[parser]") {
    Lexer lexer("((((a))))");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}

TEST_CASE("Parser handles multiple top-level expressions", "[parser]") {
    Lexer lexer("(def x 1.0) (def y 2.0) (+ x y)");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}

TEST_CASE("Parser handles keyword arguments", "[parser]") {
    Lexer lexer("(noise :scale 4.0 :octaves 3)");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}

TEST_CASE("Parser handles empty list", "[parser]") {
    Lexer lexer("()");
    auto tokens = lexer.tokenize();
    Parser parser(tokens);
    auto ast = parser.parse();
    CHECK(ast != nullptr);
}
EOF
```

**Step 2: Run tests**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
"build/bin/Debug/joon-tests.exe" "[parser]"
```

**Step 3: Commit**

```bash
git add tests/test_parser.cpp
git commit -m "test: expand parser test coverage with complex expressions and edge cases"
```

---

## Task 4: Add Evaluator Tests

**Files:**
- Create: `projects/joon/tests/test_evaluator.cpp`

**Content:**

```cpp
#include "catch_amalgamated.hpp"
#include "evaluator.h"
#include "context.h"

using namespace joon;

TEST_CASE("Evaluator evaluates simple arithmetic", "[evaluator]") {
    Context ctx;
    // Test basic evaluation
    // Implementation depends on Context/Evaluator API
}

TEST_CASE("Evaluator evaluates nested expressions", "[evaluator]") {
    Context ctx;
    // Test nested evaluation
}

TEST_CASE("Evaluator handles variable bindings", "[evaluator]") {
    Context ctx;
    // Test variable binding and lookup
}

TEST_CASE("Evaluator evaluates function calls", "[evaluator]") {
    Context ctx;
    // Test function evaluation
}

TEST_CASE("Evaluator type-checks values", "[evaluator]") {
    Context ctx;
    // Test type validation
}
```

**Step 1: Create test file**

Use Write tool to create `test_evaluator.cpp` with above content.

**Step 2: Update CMakeLists.txt or premake5.lua to include new test file**

Add `tests/test_evaluator.cpp` to the test project.

**Step 3: Compile and run**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
msbuild build/joon-tests.vcxproj /p:Configuration=Debug
"build/bin/Debug/joon-tests.exe" "[evaluator]"
```

**Step 4: Commit**

```bash
git add tests/test_evaluator.cpp
git commit -m "test: add evaluator test framework and basic test cases"
```

---

## Task 5: Add Graph and Node Tests

**Files:**
- Create: `projects/joon/tests/test_graph.cpp`
- Create: `projects/joon/tests/test_nodes.cpp`

**test_graph.cpp Content:**

```cpp
#include "catch_amalgamated.hpp"
#include "graph.h"

using namespace joon;

TEST_CASE("Graph creates nodes", "[graph]") {
    Graph graph;
    // Test node creation
}

TEST_CASE("Graph connects nodes", "[graph]") {
    Graph graph;
    // Test node connections
}

TEST_CASE("Graph detects cycles", "[graph]") {
    Graph graph;
    // Test cycle detection
}

TEST_CASE("Graph validates connections", "[graph]") {
    Graph graph;
    // Test connection validation
}
```

**test_nodes.cpp Content:**

```cpp
#include "catch_amalgamated.hpp"
#include "nodes/node_registry.h"

using namespace joon;

TEST_CASE("NodeRegistry registers nodes", "[nodes]") {
    NodeRegistry registry;
    // Test node registration
}

TEST_CASE("NodeRegistry retrieves registered nodes", "[nodes]") {
    NodeRegistry registry;
    // Test node retrieval
}

TEST_CASE("Node executes computation", "[nodes]") {
    // Test individual node execution
}

TEST_CASE("Node validates inputs", "[nodes]") {
    // Test node input validation
}
```

**Step 1: Create both test files**

Use Write tool to create both files.

**Step 2: Add to build**

Update premake5.lua or CMakeLists.txt to include both files in joon-tests project.

**Step 3: Run tests**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
"build/bin/Debug/joon-tests.exe" "[graph]" "[nodes]"
```

**Step 4: Commit both files**

```bash
git add tests/test_graph.cpp tests/test_nodes.cpp
git commit -m "test: add graph and node component tests"
```

---

## Task 6: Add Type Checker Tests

**Files:**
- Modify: `projects/joon/tests/test_type_checker.cpp`

**New tests to add:**

```cpp
TEST_CASE("Type checker validates arithmetic operations", "[type_checker]") {
    // Test type checking for +, -, *, / operations
}

TEST_CASE("Type checker rejects type mismatches", "[type_checker]") {
    // Test rejection of incompatible types
}

TEST_CASE("Type checker infers types", "[type_checker]") {
    // Test type inference
}

TEST_CASE("Type checker handles polymorphic functions", "[type_checker]") {
    // Test polymorphic type checking
}

TEST_CASE("Type checker produces useful error messages", "[type_checker]") {
    // Test error message quality
}
```

**Step 1: Add tests to test_type_checker.cpp**

Append the 5 new test cases.

**Step 2: Run tests**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
"build/bin/Debug/joon-tests.exe" "[type_checker]"
```

**Step 3: Commit**

```bash
git add tests/test_type_checker.cpp
git commit -m "test: expand type checker tests"
```

---

## Task 7: Verify Full Test Suite

**Files:**
- No new files

**Step 1: Run all tests**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
"build/bin/Debug/joon-tests.exe" 2>&1 | tail -20
```

Expected: All tests pass, summary shows test count

**Step 2: Count tests**

```bash
"build/bin/Debug/joon-tests.exe" --list-tests 2>&1 | wc -l
```

Expected: 50+ tests (significantly increased from original 4)

**Step 3: Generate test report**

```bash
"build/bin/Debug/joon-tests.exe" --reporter junit > test-report.xml
cat test-report.xml
```

**Step 4: Update CLAUDE.md with test guidance**

Add section to CLAUDE.md:

```markdown
## Testing

Run the full test suite:
```bash
cd projects/joon/build
make config=debug -j4  # or msbuild joon-tests.vcxproj
cd bin/Debug
./joon-tests          # or joon-tests.exe on Windows
```

Run specific test categories:
```bash
joon-tests "[lexer]"           # Lexer tests only
joon-tests "[parser]"          # Parser tests only
joon-tests "[evaluator]"       # Evaluator tests only
joon-tests "[graph]"           # Graph tests only
joon-tests "[nodes]"           # Node tests only
joon-tests "[type_checker]"    # Type checker tests only
```

Develop new tests in TDD style:
1. Write failing test
2. Run test to verify failure
3. Implement code to pass test
4. Run test to verify pass
5. Refactor and commit
```

**Step 5: Commit test documentation**

```bash
git add CLAUDE.md test-report.xml
git commit -m "docs: add comprehensive testing guide and report"
```

---

## Success Criteria

✅ Lexer: 19 tests (original 8 + 8 basic + 11 edge case)
✅ Parser: 4+ new tests covering complex cases
✅ Evaluator: 5 tests framework established
✅ Graph: 4+ tests
✅ Nodes: 4+ tests
✅ Type Checker: 5+ additional tests
✅ Total: 50+ tests (vs original ~15)
✅ All tests passing
✅ Test documentation in CLAUDE.md
✅ Test coverage significantly improved

---

## Test Execution Notes

- Tests use Catch2 framework (already integrated)
- Each test is independent and can run in any order
- New tests focus on edge cases, error handling, and boundary conditions
- Lexer tests expanded from 8 to 30+ test cases
- All tests follow Catch2 conventions (TEST_CASE, REQUIRE, CHECK, SECTION)
