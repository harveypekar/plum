# Joon LLVM Coding Standards Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor joon codebase to use LLVM coding standards (CamelCase classes, camelCase functions, UPPER_CASE constants, m_ prefix for private members).

**Architecture:** Systematic module-by-module refactoring in dependency order. Each module's headers are refactored first, then implementations, then all dependent modules are updated. Compilation validation after each module group. Single squash commit at the end.

**Tech Stack:** C++20, LLVM naming conventions, Premake5, Visual Studio 2022

---

## Task 1: Refactor types.h — Type Enum and Value Variant

**Files:**
- Modify: `include/joon/types.h`
- Update: All files that include `types.h` (checked in later tasks)

**Changes:**
- `Type` enum values: `Float` → `FLOAT`, `Int` → `INT`, `Bool` → `BOOL`, etc.
- `Value` variant — no name change needed (it's already lowercase as a type alias)
- Struct names stay lowercase: `vec2`, `vec3`, `vec4`, `mat3`, `mat4`

**Step 1: View current types.h**

```bash
cat "D:/prg/plum/.worktrees/joon/projects/joon/include/joon/types.h"
```

**Step 2: Edit types.h — Enum values to UPPER_CASE**

Find all enum values in `Type` enum and rename:
- `Float` → `FLOAT`
- `Int` → `INT`
- `Bool` → `BOOL`
- `Vec2` → `VEC2`
- `Vec3` → `VEC3`
- `Vec4` → `VEC4`
- `Mat3` → `MAT3`
- `Mat4` → `MAT4`
- `Image` → `IMAGE`

(Use Edit tool — exact changes)

**Step 3: Compile check**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
msbuild build/joon-lib.vcxproj /p:Configuration=Debug 2>&1 | head -50
```

**Expected:** Compilation errors listing all Type::FLOAT usage that needs updating (this is OK — we'll fix in next module that uses types.h)

**Step 4: Commit types.h**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
git add include/joon/types.h
git commit -m "refactor: rename Type enum values to UPPER_CASE (FLOAT, INT, BOOL, VEC2, VEC3, VEC4, MAT3, MAT4, IMAGE)"
```

---

## Task 2: Update All Type Enum References in Implementation

**Files:**
- Modify: `src/context.cpp` (find/replace `Type::Float` → `Type::FLOAT`, etc.)
- Modify: `src/dsl/lexer.cpp`, `src/dsl/parser.cpp`, `src/dsl/ast.h`
- Modify: `src/evaluator.cpp`
- Modify: `src/nodes/*.cpp`
- Modify: `src/vulkan/device.cpp`
- Modify: All test files

**Step 1: Find all Type enum usages**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
grep -r "Type::" src/ include/ tests/ cli/ gui/ --include="*.cpp" --include="*.h" | grep -E "(Float|Int|Bool|Vec2|Vec3|Vec4|Mat3|Mat4|Image)" | head -20
```

**Step 2: Bulk replace in src/**

For each file found, use Edit tool to replace:
- `Type::Float` → `Type::FLOAT`
- `Type::Int` → `Type::INT`
- `Type::Bool` → `Type::BOOL`
- `Type::Vec2` → `Type::VEC2`
- `Type::Vec3` → `Type::VEC3`
- `Type::Vec4` → `Type::VEC4`
- `Type::Mat3` → `Type::MAT3`
- `Type::Mat4` → `Type::MAT4`
- `Type::Image` → `Type::IMAGE`

(File-by-file as needed)

**Step 3: Compile check after each major file**

```bash
msbuild build/joon-lib.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error" | head -10
```

**Step 4: Commit**

```bash
git add src/ tests/ cli/ gui/
git commit -m "refactor: update all Type enum references to UPPER_CASE"
```

---

## Task 3: Refactor graph.h — Class and Function Names

**Files:**
- Modify: `include/joon/graph.h`
- Modify: `src/graph.cpp`

**Changes:**
- `class Graph` → stays `Graph` (already CamelCase)
- `class Node` → stays `Node` (already CamelCase)
- Function names:
  - `addNode` → stays `addNode` (already camelCase)
  - `removeNode` → stays `removeNode`
  - `getNode` → stays `getNode`
  - Any private members add `m_` prefix if not present

**Step 1: View graph.h**

```bash
cat "D:/prg/plum/.worktrees/joon/projects/joon/include/joon/graph.h"
```

**Step 2: Check for inconsistencies and add m_ to private members**

Identify any private member variables and add `m_` prefix:
- Example: `std::vector<Node*> nodes;` → `std::vector<Node*> m_nodes;`

(Use Edit tool for each change)

**Step 3: Update graph.cpp to match**

Any references to private members in implementation files need `m_` prefix.

**Step 4: Compile check**

```bash
msbuild build/joon-lib.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error" | head -10
```

**Step 5: Commit**

```bash
git add include/joon/graph.h src/graph.cpp
git commit -m "refactor: add m_ prefix to private members in Graph and Node classes"
```

---

## Task 4: Refactor DSL Components (Lexer, Parser, AST)

**Files:**
- Modify: `src/dsl/lexer.h`, `src/dsl/lexer.cpp`
- Modify: `src/dsl/parser.h`, `src/dsl/parser.cpp`
- Modify: `src/dsl/ast.h`

**Changes:**
- Classes: Ensure CamelCase (e.g., `class Lexer` → stays, `class Parser` → stays, `class ASTNode` → stays)
- Functions: Ensure camelCase (e.g., `tokenize` → stays, `parse` → stays)
- Private members: Add `m_` prefix
- Enums: Rename values to UPPER_CASE if not already (e.g., `TokenType::Identifier` → `TokenType::IDENTIFIER`)

**Step 1: View lexer.h**

```bash
cat "D:/prg/plum/.worktrees/joon/projects/joon/src/dsl/lexer.h"
```

**Step 2: Refactor lexer.h — Private members and enums**

Add `m_` to private members, rename enum values to UPPER_CASE

**Step 3: Refactor lexer.cpp**

Update all references to match

**Step 4: Repeat for parser.h, parser.cpp, ast.h**

(Same process)

**Step 5: Compile check**

```bash
msbuild build/joon-lib.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error" | head -20
```

**Step 6: Commit**

```bash
git add src/dsl/
git commit -m "refactor: apply LLVM standards to DSL components (Lexer, Parser, AST)"
```

---

## Task 5: Refactor Evaluator and Interpreter

**Files:**
- Modify: `include/joon/evaluator.h`, `src/evaluator.cpp`
- Modify: `src/interpreter/interpreter.h`, `src/interpreter/interpreter.cpp`

**Changes:**
- Classes: Ensure CamelCase
- Functions: Ensure camelCase
- Private members: Add `m_` prefix
- Any constants: UPPER_CASE

**Step 1: View evaluator.h**

```bash
cat "D:/prg/plum/.worktrees/joon/projects/joon/include/joon/evaluator.h"
```

**Step 2: Refactor headers and implementations**

(Use Edit tool as needed)

**Step 3: Compile check**

```bash
msbuild build/joon-lib.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error" | head -20
```

**Step 4: Commit**

```bash
git add include/joon/evaluator.h src/evaluator.cpp src/interpreter/
git commit -m "refactor: apply LLVM standards to Evaluator and Interpreter"
```

---

## Task 6: Refactor Node Classes (nodes/ directory)

**Files:**
- Modify: All files in `src/nodes/` (color.h/cpp, gpu_dispatch.h/cpp, image_load.h/cpp, etc.)

**Changes:**
- Classes: Ensure CamelCase (e.g., `class ColorNode` → stays if already named that, check actual names)
- Functions: Ensure camelCase
- Private members: Add `m_` prefix
- Constants: UPPER_CASE

**Step 1: List all node files**

```bash
ls "D:/prg/plum/.worktrees/joon/projects/joon/src/nodes/"
```

**Step 2: Refactor each node file systematically**

For each `.h` and `.cpp` pair, apply LLVM standards

**Step 3: Compile check**

```bash
msbuild build/joon-lib.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error" | head -20
```

**Step 4: Commit**

```bash
git add src/nodes/
git commit -m "refactor: apply LLVM standards to all node implementations"
```

---

## Task 7: Refactor Vulkan Backend

**Files:**
- Modify: `src/vulkan/device.h`, `src/vulkan/device.cpp`
- Modify: `src/vulkan/pipeline_cache.h`, `src/vulkan/pipeline_cache.cpp`
- Modify: `src/vulkan/resource_pool.h`, `src/vulkan/resource_pool.cpp`

**Changes:**
- Classes: Ensure CamelCase
- Functions: Ensure camelCase
- Private members: Add `m_` prefix
- Constants: UPPER_CASE

**Step 1: View vulkan/device.h**

```bash
cat "D:/prg/plum/.worktrees/joon/projects/joon/src/vulkan/device.h"
```

**Step 2: Refactor Vulkan components**

(Use Edit tool as needed)

**Step 3: Compile check**

```bash
msbuild build/joon-lib.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error" | head -20
```

**Step 4: Commit**

```bash
git add src/vulkan/
git commit -m "refactor: apply LLVM standards to Vulkan backend components"
```

---

## Task 8: Refactor Main API (context.h and joon.h)

**Files:**
- Modify: `include/joon/context.h`, `src/context.cpp`
- Modify: `include/joon/joon.h`

**Changes:**
- Classes: Ensure CamelCase (e.g., `class Context` → stays)
- Functions: Ensure camelCase
- Public API consistency

**Step 1: View context.h and joon.h**

```bash
cat "D:/prg/plum/.worktrees/joon/projects/joon/include/joon/context.h"
cat "D:/prg/plum/.worktrees/joon/projects/joon/include/joon/joon.h"
```

**Step 2: Refactor as needed**

(Most likely already correct, but verify)

**Step 3: Compile full library**

```bash
msbuild build/joon-lib.vcxproj /p:Configuration=Debug 2>&1 | tail -20
```

**Expected:** No errors, warnings OK

**Step 4: Commit**

```bash
git add include/joon/ src/context.cpp
git commit -m "refactor: finalize LLVM standards in public API"
```

---

## Task 9: Refactor Tests

**Files:**
- Modify: All files in `tests/` directory

**Changes:**
- Test function names: Keep as `test_*` or update to `TEST_*` if using Catch2
- Update all type references (Type::FLOAT, etc.)
- Update all class/function name calls to match refactored names

**Step 1: List test files**

```bash
ls "D:/prg/plum/.worktrees/joon/projects/joon/tests/"
```

**Step 2: Refactor test files**

Update all references to match refactored code

**Step 3: Compile tests**

```bash
msbuild build/joon-tests.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error"
```

**Step 4: Run tests**

```bash
"D:/prg/plum/.worktrees/joon/projects/joon/build/bin/Debug/joon-tests.exe"
```

**Expected:** All tests pass

**Step 5: Commit**

```bash
git add tests/
git commit -m "refactor: update tests to use refactored names"
```

---

## Task 10: Refactor GUI Components

**Files:**
- Modify: All files in `gui/` directory (app.h/cpp, panels, etc.)

**Changes:**
- Classes: Ensure CamelCase
- Functions: Ensure camelCase
- Private members: Add `m_` prefix

**Step 1: List GUI files**

```bash
ls "D:/prg/plum/.worktrees/joon/projects/joon/gui/"
```

**Step 2: Refactor GUI files**

(Use Edit tool as needed)

**Step 3: Compile GUI**

```bash
msbuild build/joon-gui.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error"
```

**Step 4: Commit**

```bash
git add gui/
git commit -m "refactor: apply LLVM standards to GUI components"
```

---

## Task 11: Refactor CLI

**Files:**
- Modify: `cli/main.cpp`

**Changes:**
- Function calls: Update to match refactored names

**Step 1: View cli/main.cpp**

```bash
cat "D:/prg/plum/.worktrees/joon/projects/joon/cli/main.cpp"
```

**Step 2: Update function calls**

(Use Edit tool)

**Step 3: Compile CLI**

```bash
msbuild build/joon-cli.vcxproj /p:Configuration=Debug 2>&1 | grep -i "error"
```

**Step 4: Commit**

```bash
git add cli/main.cpp
git commit -m "refactor: update CLI to use refactored API"
```

---

## Task 12: Full Compilation and Validation

**Step 1: Regenerate Premake5 project files**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
/tmp/premake5.exe vs2022
```

**Step 2: Clean build**

```bash
msbuild build/Joon.sln /p:Configuration=Debug /p:Platform=x64 /t:Clean
msbuild build/Joon.sln /p:Configuration=Debug /p:Platform=x64 2>&1 | tail -50
```

**Expected:** All projects build successfully, no errors

**Step 3: Run full test suite**

```bash
"D:/prg/plum/.worktrees/joon/projects/joon/build/bin/Debug/joon-tests.exe"
```

**Expected:** All tests pass

**Step 4: Verify executables**

```bash
ls -lh "D:/prg/plum/.worktrees/joon/projects/joon/build/bin/Debug/"
```

**Expected:** joon-cli.exe, joon-gui.exe, joon-tests.exe all present

**Step 5: Commit any final fixes**

```bash
git status
git add .
git commit -m "refactor: fix remaining compilation issues after full LLVM standards refactoring"
```

---

## Task 13: Update Documentation (CLAUDE.md)

**Files:**
- Modify: `CLAUDE.md` (in worktree root)

**Changes:**
- Add new "Coding Standards" section documenting LLVM conventions

**Step 1: View current CLAUDE.md**

```bash
cat "D:/prg/plum/.worktrees/joon/CLAUDE.md"
```

**Step 2: Add Coding Standards Section**

Add after "Structure" section:

```markdown
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
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add LLVM coding standards section to CLAUDE.md"
```

---

## Task 14: Final Squash and Cleanup

**Step 1: Count commits**

```bash
git log --oneline --graph | head -20
```

**Step 2: View full refactoring history**

```bash
git log --oneline | grep "refactor:" | wc -l
```

**Step 3: Squash all refactoring commits**

```bash
# Find the commit before the refactoring started
git log --oneline | grep -B1 "refactor:" | tail -1

# Interactive rebase (squash all refactor commits into first)
git rebase -i <hash-before-refactoring>
```

(In the rebase editor, mark first commit as `pick`, rest as `s` for squash)

**Step 4: Write final commit message**

```
refactor: apply LLVM coding standards to entire joon codebase

- Rename Type enum values to UPPER_CASE (FLOAT, INT, VEC2, etc.)
- Apply CamelCase to all classes
- Apply camelCase to all functions and variables
- Add m_ prefix to private members
- Rename enum values to UPPER_CASE
- Update all call sites and type references
- All tests passing, full compilation successful
```

**Step 5: Verify final state**

```bash
git log --oneline | head -10
git status
```

**Expected:** Clean working directory, one large "refactor" commit

**Step 6: Final commit**

If not already squashed:
```bash
git add -A
git commit -m "refactor: apply LLVM coding standards to entire joon codebase

- Type enum values: UPPER_CASE (FLOAT, INT, BOOL, VEC2, VEC3, VEC4, MAT3, MAT4, IMAGE)
- Classes: CamelCase (Context, Evaluator, Graph, Node, Lexer, Parser, etc.)
- Functions/methods: camelCase (addNode, evaluateExpression, tokenize, etc.)
- Variables: camelCase (nodeCount, localValue, etc.)
- Constants: UPPER_CASE (MAX_NODES, DEFAULT_SIZE, etc.)
- Macros: UPPER_CASE (JOON_ASSERT, JOON_CHECK, etc.)
- Structs: lowercase (vec2, vec3, vec4, mat3, mat4)
- Enums: CamelCase type, UPPER_CASE values (NodeType::FLOAT_NODE, etc.)
- Private members: m_ prefix (m_nodeRegistry, m_vulkanContext, etc.)

All tests passing, full compilation successful. Updated CLAUDE.md with coding standards.
"
```

---

## Success Criteria

✓ All code compiles without errors
✓ All tests pass (`joon-tests.exe` runs successfully)
✓ LLVM naming conventions applied consistently across all modules
✓ No functional changes to API behavior
✓ Single clean commit with comprehensive message
✓ CLAUDE.md updated with coding standards section
✓ Worktree ready to be merged or kept for further work
