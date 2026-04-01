# Houdini and Blender Internals: Technical Comparison for Joon

Research for Joon: a Lisp-style DSL that compiles to a Vulkan compute node graph for image processing.

**Date:** 2026-03-31

---

## Table of Contents

1. [Houdini (SideFX)](#1-houdini-sidefx)
   - [VEX Shading Language](#11-vex-shading-language)
   - [VOPs (Visual Operators)](#12-vops-visual-operators)
   - [Procedural Model: SOPs, COPs, DOPs](#13-procedural-model-sops-cops-dops)
   - [COPs and Copernicus](#14-cops-and-copernicus)
   - [Parameters, Keyframing, Expressions](#15-parameters-keyframing-expressions)
   - [Scripting Layers: HScript and Python](#16-scripting-layers-hscript-and-python)
   - [OpenCL GPU Compute](#17-opencl-gpu-compute)
   - [Papers and Talks](#18-papers-and-talks)
2. [Blender](#2-blender)
   - [Shader Node System (Cycles/EEVEE)](#21-shader-node-system-cycleseevee)
   - [Geometry Nodes](#22-geometry-nodes)
   - [Compositor](#23-compositor)
   - [OSL Integration](#24-osl-integration)
   - [Lazy Evaluation and Partial Recomputation](#25-lazy-evaluation-and-partial-recomputation)
   - [Papers and Talks](#26-papers-and-talks)
3. [What Joon Can Learn](#3-what-joon-can-learn)

---

## 1. Houdini (SideFX)

### 1.1 VEX Shading Language

**What it is:** VEX (Vector EXpression language) is Houdini's high-performance, C-like DSL used across all contexts -- geometry manipulation, shading, compositing, simulation, audio. It is the workhorse language beneath almost every Houdini operation. [1]

**Type system:**

- **Scalars:** `int`, `float` (both 32-bit or 64-bit depending on engine mode; no mixed-precision -- the entire engine runs in one mode) [2]
- **Vectors:** `vector2`, `vector` (3-component), `vector4` [2]
- **Matrices:** `matrix2` (2x2), `matrix3` (3x3), `matrix` (4x4) [2]
- **Other:** `string`, `bsdf` (bidirectional scattering distribution function, for rendering only), `dict` (dictionary) [2]
- **Arrays:** Single-dimensional arrays of any type, e.g. `float[]`, `vector[]`. No multi-dimensional arrays. Arrays cannot be passed between shaders. [3]
- **Structs:** User-defined structured types (added in Houdini 12). Member data can have default values, similar to C++11 member initialization. Two implicit constructor functions are created per struct. [2]
- **Type dispatch:** VEX dispatches function overloads based on both argument types AND return type (unlike C++, which only dispatches on arguments). You can cast at the function level to select a specific overload with no performance penalty -- it just selects which function to call, no conversion happens. Variable casting is separate and does a type conversion. [2]
- **No generics, no templates.** The type system is fixed and concrete.

**Context model:** VEX programs are written for a specific **context** that determines available global variables, functions, and statements. Key contexts: [1]

| Context | Domain | Runs on |
|---------|--------|---------|
| `surface` | Surface shading | Per-shading-sample |
| `displacement` | Displacement shading | Per-shading-sample |
| `light` | Light illumination | Per-shading-sample |
| `fog` | Volume/atmosphere | Per-shading-sample |
| `sop` | Geometry (SOPs) | Per-element (point/prim/vertex) |
| `cop` | Compositing (COPs) | Per-pixel |
| `chop` | Channel operators | Per-sample |
| `pop` | Particles (legacy) | Per-particle |

Each context provides different global variables. For example, SOP context provides `@P` (position), `@N` (normal), `@Cd` (color); COP context provides pixel coordinates and color planes. The `@` sigil accesses geometry attributes directly. [1]

**Compilation pipeline:**

1. **Source** -- VEX text (hand-written or generated from VOP graph)
2. **vcc compiler** -- The `vcc` frontend parses VEX, performs type checking, and produces an intermediate representation. The compiler inlines functions aggressively by default (hence no recursion support). An inlining "budget" controls how much inlining occurs. [4][5]
3. **LLVM lowering** -- The IR is passed to LLVM for optimization (constant folding, dead code elimination, outlining) and JIT compilation. LLVM modules are cached; the number of cached modules is configurable to trade memory for recompilation speed. [6]
4. **Bytecode execution** -- The final form is executed by a runtime bytecode interpreter. This is NOT native machine code -- it is an interpreted bytecode, but with LLVM optimizations applied to the IR before bytecode emission. [6]

**Runtime execution model:**

- **SIMD / per-element parallel:** VEX follows an implicitly SIMD paradigm. Code is written as if operating on a single element (point, pixel, particle), and the engine automatically runs it across all elements in parallel across CPU threads. [7]
- **Batching:** VEX processes elements in batches (reportedly ~256 elements per batch). This amortizes interpretation overhead and enables SIMD-width parallelism within each batch. You need a significant number of elements to see threading benefits. [7]
- **No GPU execution:** VEX itself runs on the CPU only. GPU compute is handled separately via OpenCL (see section 1.7). There is no VEX-to-GPU compilation path. [8]
- **Performance:** VEX evaluation gives performance "close to compiled C/C++ code" according to SideFX documentation. This is due to the LLVM optimization pass and the tight bytecode interpreter. [1]

**Implications for Joon:** VEX demonstrates that a domain-specific language with a fixed type system and per-element execution model can achieve near-native performance through JIT compilation and SIMD batching. Joon's approach of compiling DSL nodes to Vulkan compute shaders is more aggressive than VEX's CPU bytecode model -- Joon skips the interpreter entirely and targets GPU hardware directly.

### 1.2 VOPs (Visual Operators)

**What they are:** VOPs are the visual/graphical interface to VEX. Each VOP node encapsulates a snippet of VEX code. Wiring VOP nodes together constructs a VEX program visually. [9][10]

**Graph-to-code compilation:**

- The VOP node graph is conceptually a visual abstract syntax tree (AST). Each node maps to a VEX function or operator. [10]
- At **cook time**, Houdini linearizes the graph into a single VEX code snippet -- flattening the visual DAG into sequential VEX statements. [10]
- The resulting VEX code is then compiled through the standard vcc pipeline (see 1.1). [10]
- You can inspect the generated VEX code from any VOP network, which is useful for debugging and learning.

**Key characteristics:**

- VOPs are not a separate language -- they are a 1:1 visual representation of VEX. Every VOP operation has a VEX equivalent. [9]
- VOP networks appear as subnets inside SOPs (as Attribute VOP), SHOPs/Materials (as material shaders), and COPs (as compositing operators). [10]
- Users can create custom VOP nodes by writing VEX code, creating a bidirectional flow between text and visual programming. [9]
- VOP compilation produces optimized VEX that Houdini claims provides "real-time playback and GPU acceleration where supported." [10]

**Implications for Joon:** The VOP-to-VEX relationship is a close analog to what Joon does: a visual/declarative representation (Joon's S-expression DSL) that compiles to an executable form (Vulkan compute dispatches). The key difference is that Houdini's visual graph generates text (VEX) that is then compiled separately, creating a two-stage pipeline. Joon's DSL goes directly to IR graph to GPU commands without an intermediate text representation. This is arguably cleaner -- there is no "generated code" artifact to inspect or debug, but it also means Joon loses the ability to let users drop into hand-written code at the node level (which VEX/VOP provides).

### 1.3 Procedural Model: SOPs, COPs, DOPs

Houdini organizes its procedural engine into separate **contexts**, each with its own network type and data model: [11][12]

| Context | Full Name | Data Type | Temporal Model |
|---------|-----------|-----------|---------------|
| **SOP** | Surface Operators | Geometry (points, prims, vertices, volumes) | Time-independent (stateless per-frame) |
| **DOP** | Dynamic Operators | Simulation state (fields, constraints, objects) | Time-dependent (requires previous frame) |
| **COP** | Compositing Operators | 2D pixel data (images, planes) | Time-independent per-frame |
| **CHOP** | Channel Operators | 1D sample data (audio, motion) | Time-dependent |
| **LOP** | Layout Operators (Solaris) | USD scene description | Time-independent |
| **TOP** | Task Operators (PDG) | Work items (task graph) | Dependency-driven |

**Cook model:** [13][14]

- Evaluation is a **demand-driven dependency graph**. The edges are the wires visible in the network editor.
- When a display/render node needs to evaluate, it recursively requests data from its inputs. Each input node cooks only if its **dirty flag** is set.
- **Dirty propagation:** When a parameter changes, everything downstream in the dependency graph is marked dirty. When the UI recooks, only dirty nodes re-evaluate. If Houdini encounters a clean node during traversal, it stops -- no further upstream cooking occurs. [14]
- Nodes can declare **extra dependencies** via `OP_Node::addExtraInput()`, allowing dependencies on nodes not directly wired (e.g., referencing a parameter on another node via an expression). [14]
- SOPs are **pull-based**: each SOP, when asked to cook, asks its inputs for their cooked geometry first, cooking the most upstream nodes first and passing data down. [13]

**Cross-context data flow:**

- SOP geometry enters DOPs via SOP Geometry DOP nodes (referenced, not copied -- zero memory overhead). [12]
- DOP simulation results return to SOPs via DOP Import nodes.
- COPs can read SOP data (e.g., render a SOP scene, then composite the result).
- The key architectural principle: each context owns its data type, and cross-context transfers are explicit.

**Implications for Joon:** Houdini's dirty-flag dependency invalidation is exactly what Joon's "caching" system needs to implement. Joon's design spec says "nodes whose inputs haven't changed since last evaluation are skipped." Houdini proves this model works at massive scale. The key implementation detail is that dirty propagation must be O(affected nodes), not O(all nodes).

### 1.4 COPs and Copernicus

**Legacy COPs (COP2):** [15][16]

- COP2 networks process 2D pixel data: render passes, depth maps, textures.
- Six categories of COP nodes: Generators (create images/planes), Scoped Filters, Masked Filters, Pixel Filters, Timing Modifiers, Compositing/Blending, Plane Operators, and VEX operations. [16]
- **Pixel filter collapsing:** Houdini "collapses" consecutive pixel filter nodes in a chain into a single cooking operation. Pixel filter nodes have a light-blue background to distinguish them from other node types. This is an automatic fusion optimization -- the closest analog to Joon's planned "node fusion" in compiled mode. [15]
- COPs support custom VEX-based compositing operators, allowing users to write per-pixel VEX shaders within the compositing pipeline. [17]
- Data flow was top-to-bottom.

**Copernicus (Houdini 20.5, mid-2024):** [18][19]

- Complete rewrite and reimagining of the compositing system. Not an upgrade -- a new framework.
- **GPU-accelerated:** Written in OpenCL, hardware-agnostic (NVIDIA, AMD, Intel). Near-real-time performance. [18]
- **Data model change:** New COPs exist as geometry by default -- essentially 2D volumes, with tighter SOP integration. Data flows left-to-right instead of top-to-bottom. [19]
- **Compiled cooking:** You select a network section to cook, and Copernicus analyzes it to build an optimized program. Each non-HDA COP grabs only the inputs necessary for required outputs. Storage is reused; unnecessary intermediate data and layers are deleted to minimize memory usage. [20]
- **GPU memory management:** If VRAM fills up, Houdini automatically moves data to main memory, at a performance cost. The system handles GPU memory pressure gracefully. [20]
- **Key requirement:** Data must stay on the GPU. If a non-OpenCL node processes geometry, data is pulled back to CPU, eliminating the performance benefit. Compiled Blocks prevent this by ensuring a chain of GPU nodes runs without CPU round-trips. [20]

**Implications for Joon:** Copernicus's compiled cooking model is strikingly similar to Joon's planned compiled mode. The "analyze network, build optimized program, reuse storage, delete intermediates" pipeline maps directly to Joon's optimizer (dead node elimination, node fusion, intermediate buffer elimination). The GPU data residency requirement also applies to Joon -- Vulkan resources should stay on GPU; any CPU readback kills performance. Copernicus validates that GPU-first image processing with automatic memory management is the right architecture.

### 1.5 Parameters, Keyframing, Expressions

**Parameter system:** [21]

- Every node has typed parameters (float, int, vector, string, ramp, etc.) editable in the parameter editor UI.
- Parameters can be **static** (fixed value), **keyframed** (interpolated animation curves), or **expression-driven** (computed per-frame).
- Multi-component parameters (e.g., position XYZ) can be keyframed per-component or all-at-once.

**Expression languages:** [21]

- **HScript expressions** (legacy): Variables start with `$`. Global variables include `$F` (current frame), `$T` (current time in seconds), `$FPS`, etc. Functions like `ch("path")` reference other parameters, enabling cross-node dependencies.
- **Python expressions**: Parameters can also use Python expressions. Python is the recommended scripting language; HScript is deprecated. [21]
- Expressions always operate on values from the initial setup of the node, not from the previous frame -- an important constraint that prevents temporal feedback loops in the expression layer. [21]

**Channel referencing:** The `ch()` function creates dynamic dependencies between parameters. For example, `ch("../sphere/tx")` in one node's parameter creates an implicit dependency on another node's translate X value. These are tracked by the dependency system (see 1.3). [21]

**Implications for Joon:** Joon's `(param name type default :min :max)` syntax is a simplified version of Houdini's parameter system. Houdini shows the value of supporting expressions (computed parameters, not just static values). However, Houdini's expression system introduces complexity -- HScript/Python expressions are a separate evaluation pathway from VEX, creating two different execution models for what are conceptually similar operations. Joon's approach of having params be simple typed values with GUI constraints is cleaner for a first version. If Joon ever adds computed parameters, they should be DSL expressions (not a separate language) to avoid Houdini's dual-language problem.

### 1.6 Scripting Layers: HScript and Python

**HScript** (deprecated): [21]

- Original command-line scripting language for Houdini. Used for automating UI operations, batch processing, parameter expressions.
- Still present in parameter expressions (the `$F`, `ch()` syntax) for backwards compatibility.
- Being phased out in favor of Python.

**Python (hou module):** [21]

- Full access to Houdini's object model via the `hou` Python module.
- Can create/modify nodes, set parameters, read geometry, automate workflows.
- Used in: shelf tools, parameter callbacks, asset scripts, PDG/TOPs work items, SOP-level Python nodes.
- Python SOPs allow writing geometry-manipulation logic in Python, but are significantly slower than VEX for per-element operations.

**HDK (Houdini Development Kit):**

- C++ API for writing custom nodes (SOPs, DOPs, COPs, etc.) that integrate as first-class Houdini operators.
- This is how SideFX themselves implement built-in nodes.
- Provides full access to the cook model, dependency system, and geometry data structures. [13][14]

**Three-tier model:** Houdini has three levels of customization, from highest to lowest performance:
1. **HDK (C++)** -- native performance, full API access, compile required
2. **VEX** -- near-native performance, per-element operations, JIT compiled
3. **Python** -- lowest performance, full automation, interpreted

**Implications for Joon:** Joon's design deliberately avoids this layering problem. The spec says "No Python, no FFI plugin system, no subprocess IPC." Everything is either DSL (the S-expression language) or C++ library API. This is the right call for a focused tool -- Houdini's three-tier system exists because it serves a massive, general-purpose audience. Joon only needs two tiers: DSL for graph definition, C++ for extending the node library.

### 1.7 OpenCL GPU Compute

**Architecture:** [22][23]

- OpenCL is Houdini's mechanism for running custom GPU compute kernels within SOP, DOP, and COP contexts.
- Data is copied from CPU (host) to GPU (OpenCL device) before kernel execution, and copied back after. This explicit copy model means GPU benefits only materialize for sufficiently large workloads. [22]
- OpenCL nodes provide a general interface for writing OpenCL C kernels that operate on Houdini attributes, volumes, VDBs, and image layers. [23]

**Key constraints:**

- **Data residency:** The critical performance rule is that data must stay on the GPU. Any non-OpenCL node in a chain forces a CPU round-trip, destroying performance. **Compiled Blocks** solve this by ensuring a chain of OpenCL nodes runs without CPU intervention. [22]
- **Workset batching:** When running over worksets on GPU, many small worksets are executed within one kernel call, with synchronization within the kernel after each workset. If the largest workset fits within one workgroup, a `SINGLE_WORKGROUP` flag is defined and the entire workset array is passed to a single kernel invocation. [22]
- **Multi-GPU:** Houdini supports using one GPU for display and another for OpenCL compute. [22]
- **Vendor detection:** Compilation defines `__H_GPU__`/`__H_CPU__` and vendor-specific flags (`__H_NVIDIA__`, `__H_AMD__`, `__H_INTEL__`, `__H_APPLE__`). [23]

**OpenCL vs. VEX:** [22]

- VEX runs on CPU with SIMD batching. OpenCL runs on GPU.
- VEX is easier to write and debug. OpenCL requires explicit memory management.
- OpenCL is faster for embarrassingly parallel operations on large datasets.
- The two are separate compilation and execution paths -- there is no automatic VEX-to-OpenCL compilation.

**Implications for Joon:** Houdini's OpenCL model is the "manual" version of what Joon automates. In Houdini, users must explicitly choose OpenCL nodes, write OpenCL C kernels, and ensure data stays on GPU via Compiled Blocks. Joon's architecture makes GPU execution the default -- every node dispatches a Vulkan compute shader, and the scheduler handles barriers and synchronization automatically. This is a major UX advantage. However, Houdini's Compiled Block concept directly informs Joon's compiled mode: the idea of analyzing a network section, building an optimized execution plan, and keeping data on GPU is exactly what Joon's optimizer should do.

### 1.8 Papers and Talks

**Houdini Hive presentations (recorded, freely available):**

- SIGGRAPH 2022 presentations: [24] -- https://www.sidefx.com/houdini-hive/siggraph-2022/
- SIGGRAPH 2023 presentations: [25] -- https://www.sidefx.com/houdini-hive/siggraph-2023/
- GDC 2018 presentations: [26] -- https://www.sidefx.com/community/gdc-2018-presentations/
- GDC 2023 presentations: [27] -- https://www.sidefx.com/houdini-hive/gdc-2023/

**Academic foundations:** Many Houdini solvers are based on academic papers -- FLIP (fluid), APIC (affine particle-in-cell), Vellum (XPBD constraints), grain solvers, narrow-band level sets. These are physics simulation papers, not directly relevant to Joon's image processing focus. [28]

**Multithreading Houdini (course notes):** [7]
- https://www.multithreadingandvfx.org/course_notes/MultithreadingHoudini.pdf
- Covers VEX parallelism, node cooking, and Houdini's threading model.

**Copernicus documentation:**
- Cooking model: https://www.sidefx.com/docs/houdini/copernicus/cooking.html [20]
- OpenCL COP: https://www.sidefx.com/docs/houdini/nodes/cop/opencl.html [23]

---

## 2. Blender

### 2.1 Shader Node System (Cycles/EEVEE)

Blender has two render engines with different shader compilation pipelines:

**Cycles -- SVM (Shader Virtual Machine):** [29][30]

- **Architecture:** Shaders are compiled from the node graph into a flat list of bytecode instructions executed by a stack-based virtual machine. This runs identically on CPU and GPU.
- **Encoding:** Each SVM instruction is encoded as one or more `uint4` values in a 1D texture/buffer. If a node's data exceeds one `uint4`, the instruction counter is advanced to skip additional data words. Floats are encoded as `int` and reinterpreted. [29]
- **Stack:** All intermediate values (factors, colors, vectors) are stored in a stack of 16 floats. On GPU, this stack lives in local memory (not registers) because the indices are not known at compile time. When the same shader executes across threads, memory access is coalesced and cached. [30]
- **Stack size limit:** There is a fixed SVM stack size. When complex shader graphs exceed it, compilation time and performance degrade sharply. This is a hard GPU constraint. [30]
- **Optimization passes:** Before SVM bytecode emission, Cycles performs: [31]
  - Node group expansion (flattening all groups into a single graph)
  - Removal of UI-only nodes (frames, reroute nodes)
  - Constant folding
  - Dead node elimination (unused branches from uber-shaders incur no runtime cost)
  - These optimizations happen at both compile time and run-time.

**Cycles -- OSL (Open Shading Language):** [32][33]

- Alternative shader backend using Sony Pictures Imageworks' OSL.
- OSL shaders are compiled by the OSL runtime, which applies extensive compile-time and run-time optimizations.
- **Critical limitation:** Historically CPU-only. GPU support was added in Blender 3.5 via the OptiX backend (NVIDIA RTX only). Not available on other GPU backends. [33]
- **Closure-based model:** OSL does not have a light loop or direct access to scene lights. Materials are built from closures that the renderer implements, allowing importance sampling optimizations. [32]
- Users can write custom OSL shaders via a Script node, which auto-generates input/output sockets from the shader's parameter declarations. [32]

**EEVEE shader compilation:** [34]

- EEVEE compiles shader node graphs to GLSL fragment/vertex shaders for real-time rasterization.
- Shader compilation can be slow for complex graphs, causing UI stalls. This has been a known issue. [34]
- EEVEE Next (Blender 4.0+) rewrote the rendering pipeline but the node-to-GLSL compilation model remains.

**Implications for Joon:** The SVM model is the closest existing analog to what Joon's interpreter mode does: each node is a pre-compiled operation, and the graph is linearized into a sequence of dispatches. The key difference is that SVM uses a software virtual machine (bytecode interpreter) while Joon dispatches actual Vulkan compute shaders per node. Joon's compiled mode (fusing nodes into single shaders) goes beyond what SVM does -- SVM nodes are always executed individually. The SVM stack-size limitation is a cautionary tale: Joon should ensure its resource pool can handle arbitrarily complex graphs without hitting fixed limits.

### 2.2 Geometry Nodes

**What it is:** Blender's procedural geometry system (introduced Blender 2.92, redesigned with "fields" in 3.0+). A node graph that generates and modifies geometry procedurally. [35]

**Evaluation architecture (Evaluator 3.0, by Jacques Lucke):** [35][36][37]

- **Lazy-function system:** Each geometry node group is converted into a **lazy-function graph** prior to evaluation. This system computes only data that is actually necessary, with necessity determined dynamically during evaluation. [36]
- **Composability:** Lazy-functions can be composed in a graph to form a new lazy-function, which can be used in another graph, recursively. This is how node groups (subgraphs) work -- they are not inlined into parents. [36]
- **Zone-based architecture:** The node tree is split into **zones** (introduced for loop support). A separate lazy-function is built for each zone, giving flexibility for repeated evaluation (loops) within a single graph. Each zone gets its own `ComputeContext`. [37]
- **Threading:** Multi-threading is used selectively -- the scheduler avoids threading overhead when it is unlikely to help (small workloads). Threading decisions are made dynamically based on workload size. [38]

**Fields and anonymous attributes:** [39][40]

- **Fields** are functions (not values) that evaluate on a geometry domain. A field might be "the distance from each point to the nearest surface" -- it is a recipe, not precomputed data. Fields are evaluated lazily when a node that consumes geometry actually needs the attribute values. [39]
- **Anonymous attributes** are geometry attributes without user-visible names. They are automatically created by the field system and automatically garbage-collected when no downstream node references them. This solves the name-collision problem that plagues attribute-based systems. [40]
- Anonymous attributes are stored on geometry like regular attributes and are interpolated when geometry changes (e.g., subdivision), so they propagate correctly through the pipeline. [40]

**Implications for Joon:** Blender's lazy-function system is the most sophisticated graph evaluation model among the systems studied. Key ideas for Joon:
- **Lazy evaluation:** Joon's caching (skip nodes whose inputs haven't changed) is a form of laziness, but Blender goes further -- it does not even compute a node's output until a downstream node actually requests it. This distinction matters for graphs with branches: Joon currently evaluates all reachable nodes, while lazy evaluation would skip entire branches that are not needed for the current output.
- **Fields as deferred computation:** Joon's type system treats everything as concrete values (an `image` is a VkImage, a `float` is a float). Blender's fields are recipes that defer evaluation. This is more flexible but more complex. Joon should not adopt this for V1, but it is worth noting for future optimization.
- **Zone-based scoping:** If Joon ever adds loops or conditional execution, Blender's zone model is the right approach -- each loop body becomes a separate execution context.

### 2.3 Compositor

**Architecture overview:** [41][42]

- Node-based image processing pipeline, conceptually similar to Nuke or Houdini COPs.
- Operates on 2D image data: render passes, loaded images, generated patterns.
- Part of Blender's node system framework, which also powers shaders and geometry nodes. [42]

**Three compositor implementations (as of Blender 5.0):** [43][44]

1. **Original tiled compositor (removed in 5.0):** Per-tile evaluation, legacy system. [43]
2. **Full-frame compositor (CPU):** Rewritten for Blender 4.2, processes entire images at once rather than tiles. Several times faster than the tiled system. Now the default CPU path. [43]
3. **Real-time compositor (GPU):** Developed by Omar Emara, introduced in Blender 3.5. Uses GPU compute shaders for real-time viewport compositing. Powers the "Viewport Compositor" overlay that applies compositor effects directly in the 3D viewport without a full render. [44]

**GPU compositor details:** [44]

- Uses OpenGL compute shaders (not Vulkan, not OpenCL).
- Compatible with both EEVEE and Cycles viewport output.
- Not all compositor nodes are supported on GPU -- unsupported nodes are marked "CPU Compositor Only."
- The CPU and GPU compositor implementations are being unified so behavior matches between them. [44]

**Node system internals:** [42]

- The node system has interconnected layers: DNA (data storage), BKE (runtime behavior), RNA/UI (user interface), and specialized evaluation engines.
- Node trees bridge these layers, with each node type knowing how to evaluate itself given its inputs.

**Implications for Joon:** Blender's compositor evolution -- from tiled to full-frame to GPU -- mirrors the trajectory Joon is designed for. The key lesson is that the GPU compositor is strictly a subset of the CPU compositor. Blender could not move everything to GPU because some operations are inherently serial or require CPU-side logic. Joon's architecture accounts for this with the CPU/GPU tier split, but should ensure the fallback path is seamless -- users should not have to think about which tier a node runs on.

### 2.4 OSL Integration

**Open Shading Language (OSL):** [32][33][45]

- Created by Sony Pictures Imageworks, open source.
- C-like shading language with a closure-based material model.
- In Blender, OSL is an alternative backend for Cycles shader evaluation.
- **Script node:** Users load a `.osl` file into a Script node, press compile, and the node auto-generates sockets from the shader's parameter declarations. [32]
- OSL applies extensive optimizations at both compile time and run-time, including specialization (optimizing a shader based on the specific constant values flowing into it). [32]
- **GPU limitation:** Only supported on OptiX (NVIDIA). No support on CUDA, HIP, Metal, or OneAPI backends. [33]

**Technical model:**

- OSL does not have a traditional light loop. Instead, materials are built from closures (`diffuse()`, `reflection()`, etc.) that the renderer composes. This allows the renderer to importance-sample materials without the shader needing to know about lights. [32]
- This closure model is more restrictive than traditional shader languages but enables powerful renderer-side optimizations.

**Implications for Joon:** OSL's approach of separating "what the material looks like" (closure declarations) from "how to render it" (renderer implementation) is an interesting pattern. In Joon's terms, this would be like having node definitions declare their mathematical operation abstractly, with the backend choosing the optimal Vulkan implementation. Joon already does this to some extent (nodes declare types and semantics, the engine chooses shaders), but the pattern could be formalized further for optimization.

### 2.5 Lazy Evaluation and Partial Recomputation

**Geometry Nodes:** [36][37][38]

- Full lazy evaluation as described in 2.2.
- Dynamic necessity determination -- nodes only compute when their output is actually requested.
- Zone-based scoping for loops and conditional execution.
- Selective multi-threading based on workload analysis.

**Compositor:** [43][44]

- The full-frame compositor evaluates entire images at once (no per-tile laziness).
- The GPU compositor processes nodes sequentially, dispatching GPU compute per node.
- No cross-node fusion or shader merging -- each compositor node is a separate GPU dispatch.

**Shader nodes (Cycles):** [31]

- SVM bytecode is generated once and executed per sample. No per-sample laziness.
- Compile-time optimizations (dead branch elimination, constant folding) serve as static laziness.
- OSL's run-time optimization performs a form of dynamic specialization.

**Partial recomputation in Blender:**

- Geometry Nodes re-evaluates the entire node tree when any input changes. There is a known issue where geometry nodes evaluate every frame even when values do not change. [46]
- The compositor caches render results but re-evaluates the full compositing chain when any node changes.
- Blender does NOT have Houdini-style fine-grained dirty-flag propagation at the node level. This is a significant architectural difference.

**Implications for Joon:** Joon's design sits between Houdini and Blender on the partial recomputation spectrum. Houdini has the most mature dirty-flag system (per-node, with dependency tracking). Blender re-evaluates more aggressively. Joon's spec calls for per-node caching ("nodes whose inputs haven't changed are skipped"), which is closer to Houdini's model. This is the right approach for interactive editing responsiveness.

### 2.6 Papers and Talks

**Blender Conference 2024:** "Evaluating Geometry Nodes" presentation [47]
- https://conference.blender.org/2024/presentations/3885/
- Covers the lazy-function evaluation system, zone-based architecture, and performance.

**Blender Developers Blog:**

- "Attributes and Fields" (August 2021) [39]: https://code.blender.org/2021/08/attributes-and-fields/
  - Foundational design document for the fields system.
- "Real-time Compositor" (July 2022) [44]: https://code.blender.org/2022/07/real-time-compositor/
  - Architecture overview of the GPU compositor by Omar Emara.
- "Open Shading Language in Cycles" (September 2012) [45]: https://code.blender.org/2012/09/open-shading-language-in-cycles/
  - Technical details of OSL integration.
- "Geometry Nodes Workshop: September 2025" [48]: https://code.blender.org/2025/10/geometry-nodes-workshop-september-2025/

**Blender source code (key commits):**

- Geometry Nodes new evaluation system: https://projects.blender.org/blender/blender/commit/4130f1e674f83fc3d53979d3061469af34e1f873 [36]
- Lazy threading improvement: https://projects.blender.org/blender/blender/commit/5c81d3bd469 [38]
- Zone-aware evaluation: https://projects.blender.org/blender/blender/pulls/109029 [37]
- Evaluator 3.0 design task: https://developer.blender.org/T98492 [35]

**Blender source code (SVM internals):**

- `intern/cycles/kernel/svm/svm.h`: https://fossies.org/linux/blender/intern/cycles/kernel/svm/svm.h [29]
- SVM-LLVM optimization proposal: https://developer.blender.org/T38187 [30]

**Academic:**

- "Real-Time Procedural Generation with GPU Work Graphs" (ACM 2024): https://dl.acm.org/doi/10.1145/3675376 [49]
  - Uses GPU work graphs where nodes are shaders that dynamically generate workloads for connected nodes. Directly relevant to Joon's node-to-shader model.
- "Shader-driven compilation of rendering assets" (SIGGRAPH 2002): https://dl.acm.org/doi/10.1145/566570.566641 [50]
  - Compiler structured like a traditional code compiler: platform-independent front-end, platform-specific back-end.
- SIGGRAPH 2011 course "Compiler Techniques for Rendering": http://s2011.siggraph.org/content/compiler-techniques-rendering-0.html [51]
  - Covers LLVM for shader compilation, automatic differentiation, dynamic code generation.

---

## 3. What Joon Can Learn

### From Houdini

| Houdini Concept | Joon Equivalent | Lesson |
|----------------|-----------------|--------|
| VEX per-element SIMD execution | Vulkan compute shader per-element dispatch | Houdini proves that writing code for one element and parallelizing automatically is the right UX model. Joon's DSL already does this. |
| VOP-to-VEX compilation | DSL-to-IR-to-Vulkan compilation | Houdini has a two-stage pipeline (visual graph -> text -> compiled). Joon's direct graph-to-GPU path is cleaner. But consider exposing generated GLSL for debugging. |
| Dirty-flag dependency invalidation | Per-node caching | Implement Houdini-style dirty propagation. When a parameter changes, mark only downstream nodes dirty. This is O(affected) not O(all). |
| COP pixel filter collapsing | Compiled mode node fusion | Houdini automatically fuses consecutive pixel filters. This validates Joon's planned node fusion. The key insight: this is a well-understood optimization, not speculative. |
| Copernicus compiled cooking | Compiled mode optimizer | Copernicus's model (analyze network, build optimized program, reuse storage, delete intermediates, keep data on GPU) is exactly what Joon's compiled mode should do. |
| OpenCL Compiled Blocks (data stays on GPU) | Vulkan resource residency | The #1 performance rule: avoid CPU-GPU round-trips. Joon's architecture makes this the default, which is a major advantage over Houdini where users must explicitly opt in. |
| Context-specific global variables (`@P`, `@N`, `@Cd`) | Joon has no equivalent | Consider whether image processing nodes would benefit from implicit access to pixel position, UV coordinates, etc. Currently these would need explicit nodes. |
| HScript/Python/VEX three-tier problem | DSL + C++ only | Houdini's three scripting layers create confusion. Joon's two-tier model (DSL for graphs, C++ for node implementation) is correct. Do not add a third tier. |

### From Blender

| Blender Concept | Joon Equivalent | Lesson |
|----------------|-----------------|--------|
| SVM bytecode VM | Interpreter mode (per-node shader dispatch) | Similar intent, different mechanism. SVM interprets bytecode on GPU; Joon dispatches actual shaders. Joon's approach has lower per-node overhead but higher dispatch overhead. For Joon's V1 (interpreter mode), this is fine. |
| Cycles compile-time optimizations (dead branch elimination, constant folding) | Graph validation + optimizer | Implement these in Joon's validation pass, even before compiled mode. Constant folding is low-hanging fruit. |
| Lazy-function evaluation (Geometry Nodes) | Per-node caching (weaker) | Joon's V1 does not need full lazy evaluation, but the design should not prevent it. Avoid eager evaluation of the entire graph when only one output is requested. |
| Fields (deferred computation) | Not applicable for V1 | Fields are a powerful abstraction for geometry but overkill for image processing. Note for future: if Joon adds mesh/voxel types, fields become relevant. |
| Anonymous attributes (auto-GC'd intermediates) | Resource pool with recycling | Joon's resource pool already plans to recycle intermediate buffers. Blender's anonymous attributes show that automatic lifetime management is essential -- users should never manually manage intermediate resources. |
| GPU compositor (per-node GPU dispatch) | Interpreter mode | Direct analog. Blender dispatches OpenGL compute per compositor node; Joon dispatches Vulkan compute per node. Same model, different API. |
| Full-frame vs. tiled evaluation | Joon evaluates full images | Blender moved away from tiled evaluation to full-frame for simplicity and performance. Joon should start with full-frame and only add tiling if memory pressure demands it for very large images. |
| Blender's lack of fine-grained dirty tracking | Joon should NOT follow this | Blender re-evaluates entire node trees too aggressively. Follow Houdini's dirty-flag model instead. |
| GPU Work Graphs (academic, not in Blender) | Compiled mode scheduling | The SIGGRAPH 2024 paper on GPU Work Graphs shows how nodes-as-shaders can dynamically generate workloads for connected nodes. This is the most forward-looking model for Joon's compiled mode. |

### Key Architectural Takeaways

1. **Dirty-flag propagation is essential.** Houdini's per-node dependency invalidation is the gold standard. Implement it from day one, not as an optimization later.

2. **Node fusion is proven.** Both Houdini (COP pixel filter collapsing) and the academic literature validate that fusing adjacent element-wise operations into single GPU dispatches is a significant optimization. Joon's compiled mode should prioritize this.

3. **GPU data residency is the #1 performance rule.** Both Houdini (Compiled Blocks) and Copernicus (compiled cooking) demonstrate that keeping data on GPU is more important than any other optimization. Joon's Vulkan-first architecture makes this the default, which is correct.

4. **Two-stage evaluation (interpreter + compiler) is the right model.** Houdini has always had immediate evaluation for interactivity. Joon's interpreter/compiled split matches this pattern and is validated by decades of production use.

5. **Avoid the three-language trap.** Houdini has HScript, VEX, and Python. Blender has Python, OSL, and GLSL. Joon should have exactly one DSL and one system language (C++). No more.

6. **Full-frame evaluation first, tiling later.** Blender's migration from tiled to full-frame compositor confirms that full-frame is simpler and often faster. Only add tiling when processing images too large for VRAM.

---

## References

[1] SideFX, "VEX," https://www.sidefx.com/docs/houdini/vex/index.html

[2] SideFX, "VEX language reference," https://www.sidefx.com/docs/houdini/vex/lang.html

[3] SideFX, "Arrays," https://www.sidefx.com/docs/houdini/vex/arrays.html

[4] SideFX, "Vex compiler (vcc)," https://www.sidefx.com/docs/houdini/vex/vcc.html

[5] SideFX, "VEX compiler pragmas," https://www.sidefx.com/docs/houdini/vex/pragmas.html

[6] ikrima, "VEX - Gamedev Guide," https://ikrima.dev/houdini/basics/hou-vex/ (Documents VEX JIT/LLVM pipeline)

[7] "Multithreading Houdini," course notes, https://www.multithreadingandvfx.org/course_notes/MultithreadingHoudini.pdf

[8] SideFX Forum, "VEX SIMD GPU Implementation," https://www.sidefx.com/forum/topic/43672/

[9] SideFX, "VOP nodes," https://www.sidefx.com/docs/houdini/nodes/vop/index.html

[10] Medium, "VEX and VOP in Houdini," https://medium.com/@jxu33/vex-and-vop-in-houdini-d8771b5b9618

[11] "Intro to Houdini Context," https://merwynl.wordpress.com/houdini-context/

[12] "DOPs are not SOPs," https://www.toadstorm.com/blog/?p=1046

[13] SideFX HDK, "SOP Concepts," https://www.sidefx.com/docs/hdk/_h_d_k__data_flow__s_o_p.html

[14] SideFX HDK, "Dependencies," https://www.sidefx.com/docs/hdk/_h_d_k__op_basics__overview__dependencies.html

[15] SideFX, "Compositing node (COP2) networks," https://www.sidefx.com/docs/houdini/nodes/cop2/index.html

[16] tokeru.com, "HoudiniCops," https://tokeru.com/cgwiki/HoudiniCops.html

[17] SideFX, "Create a custom COP with VOPs," https://www.sidefx.com/docs/houdini/composite/comp_vops.html

[18] SideFX, "What's new Copernicus," https://www.sidefx.com/docs/houdini/news/20_5/copernicus.html

[19] SideFX, "Copernicus," https://www.sidefx.com/products/whats-new-in-h205/copernicus/

[20] SideFX, "Copernicus Cooking," https://www.sidefx.com/docs/houdini/copernicus/cooking.html

[21] SideFX, "Parameter expressions," https://www.sidefx.com/docs/houdini/network/expressions.html

[22] SideFX, "OpenCL for VEX users," https://www.sidefx.com/docs/houdini/vex/ocl.html

[23] SideFX, "OpenCL Copernicus node," https://www.sidefx.com/docs/houdini/nodes/cop/opencl.html

[24] SideFX, "SIGGRAPH 2022," https://www.sidefx.com/houdini-hive/siggraph-2022/

[25] SideFX, "SIGGRAPH 2023," https://www.sidefx.com/houdini-hive/siggraph-2023/

[26] SideFX, "GDC 2018 Presentations," https://www.sidefx.com/community/gdc-2018-presentations/

[27] SideFX, "GDC 2023," https://www.sidefx.com/houdini-hive/gdc-2023/

[28] SideFX Forum, "Scientific Paper Implementation in Houdini," https://www.sidefx.com/forum/topic/89563/

[29] Fossies, "intern/cycles/kernel/svm/svm.h," https://fossies.org/linux/blender/intern/cycles/kernel/svm/svm.h

[30] Blender Developer, "SVM Stack optimization #46872," https://developer.blender.org/T46872

[31] Blender Manual, "Shader Nodes - Optimizations," https://docs.blender.org/manual/en/latest/render/cycles/optimizations/nodes.html

[32] Blender Manual, "Open Shading Language," https://docs.blender.org/manual/en/latest/render/cycles/osl/index.html

[33] Blender DevTalk, "OSL shader nodes not available on GPU," https://devtalk.blender.org/t/what-are-the-reasons-for-osl-shader-nodes-script-nodes-being-not-available-on-gpu/12082

[34] Blender DevTalk, "Eevee Shader Compilation," https://devtalk.blender.org/t/eevee-shader-compilation/5573

[35] Blender Developer, "Geometry Nodes Evaluator 3.0," https://developer.blender.org/T98492

[36] Blender commit, "Geometry Nodes: new evaluation system," https://projects.blender.org/blender/blender/commit/4130f1e674f83fc3d53979d3061469af34e1f873

[37] Blender PR, "Geometry Nodes: make evaluation and logging system aware of zones," https://projects.blender.org/blender/blender/pulls/109029

[38] Blender commit, "Geometry Nodes: improve evaluator with lazy threading," https://projects.blender.org/blender/blender/commit/5c81d3bd469

[39] Blender Developers Blog, "Attributes and Fields," https://code.blender.org/2021/08/attributes-and-fields/

[40] Blender DevTalk, "Fields and Anonymous Attributes [Proposal]," https://devtalk.blender.org/t/fields-and-anonymous-attributes-proposal/19450

[41] Blender Manual, "Compositing Introduction," https://docs.blender.org/manual/en/latest/compositing/introduction.html

[42] DeepWiki, "Node System | blender/blender," https://deepwiki.com/blender/blender/2-sculpting-system

[43] Blender Developer Docs, "Blender 5.0 Compositor Migration," https://developer.blender.org/docs/release_notes/5.0/migration/compositor_migration/

[44] Blender Developers Blog, "Real-time Compositor," https://code.blender.org/2022/07/real-time-compositor/

[45] Blender Developers Blog, "Open Shading Language in Cycles," https://code.blender.org/2012/09/open-shading-language-in-cycles/

[46] Blender Projects, "Geometry nodes evaluating every frame," https://projects.blender.org/blender/blender/issues/123598

[47] Blender Conference 2024, "Evaluating Geometry Nodes," https://conference.blender.org/2024/presentations/3885/

[48] Blender Developers Blog, "Geometry Nodes Workshop: September 2025," https://code.blender.org/2025/10/geometry-nodes-workshop-september-2025/

[49] ACM, "Real-Time Procedural Generation with GPU Work Graphs," https://dl.acm.org/doi/10.1145/3675376

[50] ACM SIGGRAPH 2002, "Shader-driven compilation of rendering assets," https://dl.acm.org/doi/10.1145/566570.566641

[51] SIGGRAPH 2011, "Compiler Techniques for Rendering," http://s2011.siggraph.org/content/compiler-techniques-rendering-0.html
