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

## Conventions

- C++20, no exceptions (use result types)
- All public types in `joon` namespace
- One class per header in `include/joon/`
- Implementation details in `src/` subfolders
- Tests mirror src structure
