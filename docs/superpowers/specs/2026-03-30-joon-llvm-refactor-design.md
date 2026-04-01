# Joon LLVM Coding Standards Refactoring — Design

**Date:** 2026-03-30
**Status:** Approved
**Scope:** Full codebase (headers, implementation, tests, CLI/GUI)

## Overview

Refactor the entire joon codebase from lowercase/mixed conventions to LLVM coding standards, ensuring consistency with industry-standard C++ conventions used by the LLVM project.

## LLVM Naming Conventions

**Classes:** `CamelCase` (e.g., `class Context`, `class Evaluator`)
**Functions/Methods:** `camelCase` (e.g., `evaluateExpression()`, `getNodeType()`)
**Variables:** `camelCase` (e.g., `localVariable`, `functionParameter`)
**Constants:** `UPPER_CASE` (e.g., `MAX_NODES`, `DEFAULT_SIZE`)
**Macros:** `UPPER_CASE` (e.g., `JOON_ASSERT`, `JOON_LIKELY`)
**Structs:** `lowercase` (exception, e.g., `vec2`, `vec3`)
**Enums:** `CamelCase` for type, `UPPER_CASE` for values (e.g., `enum class NodeType { FLOAT_NODE, INT_NODE }`)
**Private members:** `m_` prefix (e.g., `m_nodeRegistry`, `m_vulkanContext`)
**File naming:** Unchanged (snake_case)

## Refactoring Scope & Order

Dependency-ordered modules:

1. **types.h** — Fundamental types, enums, value variant
2. **graph.h/graph.cpp** — Graph structures
3. **dsl/** — Lexer, parser, AST
4. **evaluator.h/evaluator.cpp** — Interpreter/evaluator
5. **nodes/** — Node implementations
6. **vulkan/** — Vulkan backend
7. **context.h/context.cpp** — Main API
8. **tests/** — Unit tests
9. **gui/** — ImGui components
10. **cli/** — CLI entry point

## Implementation Approach

**Per-module workflow:**
- Rename all public types, functions, variables, constants in headers
- Update implementations in `.cpp` files
- Update all call sites in dependent modules
- Update test files covering that module
- Update comments/documentation

**Validation:**
- Regenerate Premake5 project files after each major module
- Attempt compilation to catch missed references
- Run tests after each logical grouping
- Full test suite run after all modules

## Documentation Updates

- Update `CLAUDE.md` with new coding standards section
- Update in-code comments referencing old conventions
- No changes to shader files or vendored third-party code

## Success Criteria

- All code compiles without errors
- All tests pass
- Naming conventions consistently applied across all modules
- No breaking changes to public API behavior (only signatures)
- Single clean commit with clear message
