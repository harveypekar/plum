# Joon: Graphics DSL & Visual Compute Framework

**Created:** 2026-03-29
**Status:** Design
**Project:** `projects/joon/`

## Overview

Joon is a general-purpose visual compute framework built on a declarative, functional DSL with S-expression syntax. It operates as a library-first C++ project with Vulkan handling all compute, rasterization, and UI rendering. A CLI and a RenderMonkey-style GUI (built with Dear ImGui) consume the library.

The framework supports 2D/3D operations across image, mesh, and voxel data types. AI model inference (using native interfaces) is a design goal for the future.

## DSL

### Syntax

S-expression prefix syntax. Semicolons for comments. Keywords with colon prefix.

```scheme
; Load an image
(def base (image "textures/stone.png"))

; Noise returns float, broadcasts across image elements
(def n (noise :scale 4.0 :octaves 3))

; Element-wise operations
(def blended (* base n))

; Colors normalized 0-1
(def tint (color 0.8 0.3 0.1))
(def tinted (+ blended (* tint 0.2)))

; Expose parameter to GUI with constraints
(param contrast float 1.2 :min 0.0 :max 3.0)
(def adjusted (levels blended :contrast contrast))

; Output
(output adjusted)

; Stateful node (persists across evaluations)
(state accum (+ accum delta))

; Import
(use "library.jn")
```

### Language Features

- **`(def name expr)`** — bind a name to a node. Names are graph nodes. No mutable variables.
- **`(param name type default ...)`** — declare a parameter exposed to the GUI as an editable property. Constraints (`:min`, `:max`) drive slider ranges.
- **`(output expr)`** — mark graph output. Multiple outputs supported.
- **`(state name expr)`** — stateful node. Self-referencing allowed. Engine persists value across evaluations.
- **`(use "file.jn")`** — import and compose graphs from files.
- **Operators** — `+`, `-`, `*`, `/` are element-wise with broadcasting.
- **Keywords** — `:keyword value` for named arguments.

### Semantics

- All nodes are functions that take inputs and return outputs. The DSL makes no distinction between element-wise, spatial, or any other operation type — that is an implementation detail of the node.
- Types are inferred throughout the graph. Type errors are caught at graph compile time.

## Type System

### Scalar Types

| Type | Description |
|------|-------------|
| `float` | 32-bit float, default numeric type |
| `int` | 32-bit integer |
| `bool` | Boolean |
| `vec2`, `vec3`, `vec4` | Float vectors |
| `mat3`, `mat4` | Matrices |

### Resource Types

| Type | Description |
|------|-------------|
| `image` | 2D grid of `vec4` (RGBA, normalized 0-1). Resolution and channel count are value properties, not type properties. |
| `mesh` | Vertex/index buffers + attributes (position, normal, UV). |
| `voxel` | 3D grid — `float` (density) or `vec4` (density + color). |

### Type Behavior

- **Broadcasting:** `float * image` multiplies every element. `vec3 * image` multiplies per-channel. `image * image` is element-wise.
- **Implicit promotion:** `float → vec3` (splat), `float → image` (constant image). Never lossy — no implicit `image → float`.
- **Fixed type set** — no generics or templates. Every type maps to a known Vulkan buffer/image format.

## Architecture

### Hybrid Vulkan-Native Engine

The engine targets Vulkan directly. Nodes have two tiers:

- **GPU nodes** — define shaders/pipelines. The engine schedules them as Vulkan commands.
- **CPU nodes** — run native C++ between GPU submissions (file I/O, state management, control flow). Synchronized with GPU work via fences.

```
DSL text → Parser → IR Graph → Validation → Optimizer → Scheduler → Mixed Schedule
                                                                       ├─ GPU: Vulkan commands
                                                                       └─ CPU: Native callbacks + sync
```

### State Model

Hybrid: pure by default, explicit opt-in for state.

- Most nodes are pure functions — deterministic given inputs.
- `state` nodes carry values across evaluations. These are typically CPU-tier.
- State is explicit in the DSL and visible in the graph.

### Two Execution Modes

- **Interpreter mode** — each node dispatches a precompiled shader/pass with its own intermediate buffer. Simple, correct, immediate. Runs during live editing.
- **Compiled mode** — the optimizer fuses nodes into minimal passes, eliminates intermediate buffers, schedules for throughput. Runs in the background after the graph stabilizes. Hot-swaps seamlessly.

**Live editing workflow:**
1. User edits DSL or adjusts a parameter
2. Interpreter evaluates immediately, viewport updates
3. Background compiler begins optimizing
4. Compiled version swaps in when ready
5. User edits again → falls back to interpreter while recompiling

The compiler is non-blocking — runs on a separate thread, produces a new execution plan that gets hot-swapped.

### Graph Compiler Pipeline

**Parser:** Hand-written recursive descent. Produces IR graph (nodes + edges, each with type signatures and tier). Lives in the library.

**Validation:**
- Type checking — edges type-compatible, broadcast rules satisfied
- Cycle detection — DAG enforced, except controlled back-edges from `state` bindings
- Output reachability — all nodes contribute to an `output` or `state`; warn on dead nodes

**Optimizer (compiled mode):**
- Dead node elimination
- Constant folding — `(* 0.5 0.5)` → `0.25` at compile time
- Node fusion — adjacent element-wise operations merged into a single GPU dispatch

**Scheduler:**
- GPU nodes grouped into Vulkan command buffer submissions with automatic barrier/layout transition insertion
- CPU nodes execute between GPU submissions with proper synchronization
- Async compute queue used for independent GPU work when available

### Caching

Nodes whose inputs haven't changed since last evaluation are skipped. Only the downstream subgraph re-evaluates on parameter changes. This is what makes live preview responsive.

## Vulkan Layer

Single Vulkan context owns everything — compute, rasterization, and UI rendering.

### Resources

- **Images:** `VkImage` — `R32_SFLOAT` for float, `RGBA32_SFLOAT` for vec4/image, etc.
- **Meshes:** vertex/index `VkBuffer` pairs
- **Voxels:** 3D `VkImage` or storage buffers depending on access pattern
- **One resource pool** with recycling. Intermediate buffers allocated from pool, released after downstream consumers finish.

### Interpreter Mode

- Each node type has a corresponding precompiled shader (compute or graphics)
- Node dispatch = bind pipeline + bind descriptor set (inputs/outputs) + dispatch/draw
- Intermediate buffers allocated per node from the pool

### Compiled Mode

- Multiple node shaders fused into single shaders where possible
- Intermediate buffers between fused nodes eliminated (become shader locals)
- Render passes merged where compatible (same framebuffer dimensions, compatible attachments)

### Synchronization

- Automatic pipeline barriers between passes based on resource read/write tracking
- CPU nodes trigger queue submit + fence wait, then execute, then resume GPU work
- Async compute queue for independent GPU work when available

## Library API

The C++ library is the core product.

### Key Interfaces

- **`joon::Context`** — owns Vulkan device, resource pool, pipeline cache. One per application.
- **`joon::Graph`** — parsed and validated graph. Created from DSL text or built programmatically. Immutable once compiled.
- **`joon::Evaluator`** — executes a graph. Holds interpreter and compiler. Manages state across evaluations.
- **`joon::Param<T>`** — typed handle to a graph parameter. Read/write values, query constraints.
- **`joon::Result`** — handle to a node's output. Read back to CPU or bind as Vulkan resource.

### Usage

```cpp
auto ctx = joon::Context::create();
auto graph = ctx.parse_file("effect.jn");
auto eval = ctx.create_evaluator(graph);

// Typed param access
auto contrast = eval.param<float>("contrast");
auto tint = eval.param<vec3>("tint");

contrast = 1.5f;
tint = {0.8f, 0.3f, 0.1f};

eval.evaluate();

auto result = eval.result("output");
result.save_image("out.png");

// GUI usage
float v = contrast; // implicit conversion
auto vk_img = eval.result("output").vk_image();       // viewport
auto node_img = eval.node_result("blended").vk_image(); // node preview
auto diags = eval.diagnostics();                         // output log
```

## GUI (Dear ImGui + Vulkan)

RenderMonkey-style interface using Dear ImGui docking branch.

### Panels

| Panel | Purpose |
|-------|---------|
| **Graph Tree** | Hierarchical view of DSL structure (nodes, params, outputs, state). Click to select → populates property editor and node preview. |
| **Property Editor** | Params and inputs for selected node. Sliders, color pickers, dropdowns driven by `param` constraints. |
| **Code Editor** | Inline DSL editor with syntax highlighting. Edits trigger re-parse → interpreter evaluation. |
| **Viewport** | Displays graph output. Output `VkImage` bound directly as ImGui texture. Pan/zoom for 2D, orbit camera for 3D. |
| **Node Preview** | Displays intermediate output of any selected node. Same viewport widget bound to that node's output buffer. |
| **Output Log** | Syntax errors (line/column), type errors, compilation status, GPU warnings, per-node timing. |

All panels dockable and rearrangeable. Default layout: tree left, viewport center, properties right, code and log bottom.

### Live Editing Loop

1. User edits DSL in code panel or adjusts slider in property panel
2. Parser re-runs, produces new IR graph
3. Interpreter mode evaluates immediately
4. Viewport and node preview update
5. Background compiler begins optimizing
6. Compiled version swaps in when ready

## CLI

Thin consumer of the library.

```bash
# Evaluate and save output
joon run effect.jn -o out.png

# Override params
joon run effect.jn -p contrast=1.5 -p tint=0.8,0.3,0.1 -o out.png

# Inspect graph (nodes, params, types)
joon info effect.jn

# Validate without evaluating
joon check effect.jn

# Dump all intermediate node outputs
joon run effect.jn --dump-all ./intermediates/

# Sequence evaluation for stateful graphs
joon run effect.jn --frames 60 -o frame_%04d.png
```

No logic lives in the CLI that doesn't live in the library.

## Build

- **Language:** C++
- **Build system:** Premake
- **Platform:** Windows primary (MSVC), portable to Linux and macOS
- **Dependencies:** Vulkan SDK, Dear ImGui (docking branch)
- **External libraries:** Native interfaces only. No Python, no FFI plugin system, no subprocess IPC.
- **AI model inference:** Design goal for the future, mechanism not yet specified. Will use native C++ interfaces.

## Vertical Slice (First Milestone)

End-to-end for Image type only.

### In Scope

- DSL parser (full syntax, only image/float/vec types resolve)
- Graph engine: IR, validation, interpreter mode
- Vulkan context, resource pool, precompiled passes
- Image nodes:
  - Sources: `image` (load file), `noise`, `color` (constant)
  - Math: `+`, `-`, `*`, `/` (element-wise, broadcast)
  - Ops: `blur`, `levels`, `blend`, `invert`, `threshold`
  - Output: `save` (to file)
- Typed params with GUI constraints
- CLI: `joon run`, `joon check`, `joon info`
- GUI: all six panels (tree, properties, code editor, viewport, node preview, output log)
- Live editing loop (edit → interpreter → display)

### Deferred

- Compiled mode (optimizer, node fusion)
- Mesh, voxel types and their nodes
- `state` bindings
- `use` imports
- AI model inference
- Async compute scheduling
