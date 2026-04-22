---
paths:
  - "projects/joon/**"
---

# Joon — Graphics DSL & Compute Framework

See `projects/joon/CLAUDE.md` for build instructions, coding standards, and project structure.

## Debugging

- **Log file:** runtime output goes to `log.txt` in the working directory. Always read this file before asking the user about errors or behavior.
- **Validation errors:** Vulkan validation messages route through `joon_log`. If you don't see expected errors, check that validation layers are enabled and logging is not filtered.
- **Viewport not updating:** the most common cause is the eval→dispatch→present pipeline not being fully triggered. Before patching, trace the full path: parameter change → dirty flag → re-eval → descriptor rebind → dispatch → barrier → present. Identify which step is broken.
- **Cross-queue sync:** compute and graphics may use different queue families. Barriers must match the queue ownership. Read the existing barrier code before adding new ones.

## Fix Discipline

- **No incremental guessing on rendering bugs.** The viewport/pipeline has multiple stages that must all agree. A fix that changes one barrier or one rebind without understanding the full flow will likely shift the bug rather than fix it.
- **Write a CLI test** (`tests/`) that asserts the output actually changed before claiming a visual bug is fixed. Pixel diff or value comparison, not just "it compiles."
- **Shader changes:** after modifying or adding shaders, verify they compile by running premake + build. Don't assume HLSL compiles just because GLSL did.
