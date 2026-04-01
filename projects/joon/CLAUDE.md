# Joon

Graphics DSL and visual compute framework. C++20, Vulkan, Premake.

## Build

Requires: Vulkan SDK, Premake5

```bash
cd projects/joon
premake5 vs2022        # Windows
premake5 gmake2        # Linux/macOS
```

## Structure

- `include/joon/` — public library headers
- `src/` — library implementation
- `cli/` — CLI entry point
- `gui/` — GUI entry point (ImGui)
- `shaders/` — Vulkan GLSL compute shaders
- `tests/` — Catch2 tests
- `third_party/` — vendored dependencies

## Coding Standards (LLVM)

This project follows LLVM coding standards for consistency with industry best practices.

- **Classes:** `CamelCase` (e.g., `class Context`, `class Evaluator`)
- **Functions/Methods:** `camelCase` (e.g., `evaluateExpression()`, `addNode()`)
- **Variables:** `camelCase` (e.g., `localValue`, `nodeCount`)
- **Constants:** `UPPER_CASE` (e.g., `MAX_NODES`, `DEFAULT_TIMEOUT`)
- **Macros:** `UPPER_CASE` (e.g., `JOON_ASSERT`, `JOON_CHECK`)
- **Structs:** `lowercase` (e.g., `vec2`, `vec3`, `vec4`)
- **Enums:** `CamelCase` for type, `UPPER_CASE` for values (e.g., `enum class NodeType { FLOAT_NODE, INT_NODE }`)
- **Private members:** `m_` prefix (e.g., `m_nodeRegistry`, `m_vulkanContext`)
- **File naming:** `snake_case` (e.g., `device.cpp`, `evaluator.h`)

See [LLVM Coding Standards](https://llvm.org/docs/CodingStandards/) for full reference.

## Static Analysis

This project uses multiple static analysis tools to ensure code quality:

### Automated Analysis (on PR open)
- **clang-tidy:** LLVM coding standard conformance, readability, performance, and modernization checks
- **MSVC Static Analysis:** Windows/C++ core guidelines checking

Configuration: `.clang-tidy` (LLVM-aligned checks with exclusions for Vulkan/no-exceptions code)

### Local Development: ANALYZE Configuration

Build with ASan/UBSan for comprehensive runtime analysis:

```bash
cd projects/joon
premake5 gmake2      # or: premake5 vs2022 (Windows)
make config=analyze  # Linux
# Or select ANALYZE configuration in Visual Studio (Windows)
```

This configuration enables:
- **AddressSanitizer (ASan)** - Detects memory leaks, buffer overflows, use-after-free
- **UndefinedBehaviorSanitizer (UBSan)** - Detects undefined behavior (integer overflow, etc.)
- Debug symbols and no optimization for accurate error reporting

Expected: Some performance overhead; use for development and testing only.

### Running Checks Locally

```bash
# clang-tidy check specific file
clang-tidy -p build src/vulkan/device.cpp

# Count warnings/errors
clang-tidy -p build src/**/*.cpp 2>&1 | grep -c "warning:"
```

See [LLVM clang-tidy docs](https://clang.llvm.org/extra/clang-tidy/) for details.

## Conventions

- C++20, no exceptions (use result types)
- All public types in `joon` namespace
- One class per header in `include/joon/`
- Implementation details in `src/` subfolders
- Tests mirror src structure

## Testing

Comprehensive test suite with 70+ tests covering all major components (lexer, parser, evaluator, graph, nodes, type checker).

### Running Tests

Build test executable:

```bash
cd projects/joon
premake5 vs2022              # Windows
msbuild build/joon-tests.vcxproj /p:Configuration=Debug
# Or on Linux:
premake5 gmake2
make config=debug
```

Run all tests:

```bash
./build/bin/Debug/joon-tests  # or joon-tests.exe on Windows
```

Run specific test categories:

```bash
joon-tests "[lexer]"           # Lexer tests (30+ test cases)
joon-tests "[parser]"          # Parser tests (10+ test cases)
joon-tests "[evaluator]"       # Evaluator tests (5+ test cases)
joon-tests "[graph]"           # Graph tests (4+ test cases)
joon-tests "[nodes]"           # Node registry tests (4+ test cases)
joon-tests "[types]"           # Type checker tests (11+ test cases)
```

### Test Development

Follow TDD workflow when implementing new features:

1. Write failing test in appropriate `test_*.cpp` file
2. Run test to verify it fails
3. Implement minimal code to pass test
4. Run test to verify pass
5. Refactor and commit

Tests are organized by component:
- `test_lexer.cpp` — S-expression tokenization, edge cases, whitespace/comment handling
- `test_parser.cpp` — AST construction, nested expressions, error handling
- `test_evaluator.cpp` — Graph creation, parsing pipeline, diagnostics
- `test_graph.cpp` — IR graph structure, error reporting
- `test_nodes.cpp` — Node registry, operator lookup
- `test_type_checker.cpp` — Type inference, promotions, error diagnostics

Each test is independent and can run in any order. Tests use Catch2 framework with standard conventions (TEST_CASE, REQUIRE, CHECK, SECTION).
