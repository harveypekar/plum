# Particle System Editors, VFX Graph Tools, and Artist-Facing Node Graph Systems

Research for Joon: a Lisp-style DSL that compiles to a Vulkan compute node graph for image processing.

**Date:** 2026-03-31

---

## Table of Contents

1. [Game Engine VFX / Particle Systems](#1-game-engine-vfx--particle-systems)
2. [Shader Compilation Systems](#2-shader-compilation-systems)
3. [Raytracing and Path Tracing Tools](#3-raytracing-and-path-tracing-tools)
4. [Artist Graph Tools (General)](#4-artist-graph-tools-general)
5. [Academic / Research](#5-academic--research)
6. [Design Lessons for Joon](#6-design-lessons-for-joon)
7. [Papers to Download](#7-papers-to-download)

---

## 1. Game Engine VFX / Particle Systems

### 1.1 Unity VFX Graph

**What it is:** GPU-based visual effect system using compute shaders, part of Unity's Scriptable Render Pipeline (SRP). Simulates millions of particles in real-time. [1]

**Architecture:**

- **Context model:** Effects are organized into four sequential contexts (stages):
  - **Spawn** -- determines when and how many particles to create
  - **Initialize** -- sets initial attribute values (position, color, lifetime, etc.)
  - **Update** -- per-frame simulation logic, runs as a **compute shader** operating directly on particle data in GPU buffers
  - **Output** -- rendering; runs as part of the **vertex shader** pipeline; any changes to particle data are discarded after this stage [2]
- **Attributes:** Particles carry typed attributes (position, velocity, color, age, lifetime, custom attributes). Custom attributes can be defined and accessed via `Get CustomAttribute` / `Set CustomAttribute` nodes. [2]
- **Compilation:** Every time nodes are added, removed, or connected, the graph recompiles changed elements and restarts the effect. The compiled output is stored as child assets (Shader and ComputeShader) of the VisualEffectAsset. [3]
- **Shader Graph integration:** VFX Graph can use Shader Graph for output rendering. When a slot is constant in VFX, MultiCompile keywords are stripped to prevent shader variant explosion. [4]
- **GPU events:** Instancing support for GPU events added in Unity 6.3. [5]

**What is NOT public:** The internal `VFXCompiler` and `VFXCodeGenerator` classes are not well-documented. The code generation pipeline from graph to compute shader is largely a black box, though the package source can be inspected via Unity's package cache.

**Joon relevance:**
- The four-stage context model (spawn/init/update/output) is a clean separation of concerns that maps well to distinct compute shader dispatches
- The attribute system (typed per-particle data flowing through stages) is analogous to Joon's typed node ports
- Recompilation on graph edit is the norm -- incremental compilation matters for interactive use

**References:**
- [1] [Unity VFX Graph](https://unity.com/visual-effect-graph)
- [2] [How to VFX Graph (Qriva)](https://qriva.github.io/posts/how-to-vfx-graph/)
- [3] [Where does generated shader for VFX graph live?](https://discussions.unity.com/t/where-does-generated-shader-for-vfx-graph-live/891554)
- [4] [Shader Graph in VFX Graph](https://docs.unity3d.com/Packages/com.unity.visualeffectgraph@17.0/manual/sg-working-with.html)
- [5] [Unity 6.3 LTS features](https://www.cgchannel.com/2025/12/unity-6-3-lts-is-out-see-5-key-features-for-cg-artists/)

---

### 1.2 Unity Shader Graph

**What it is:** Visual node-based shader authoring for Unity's SRP (URP/HDRP). Generates HLSL from node graphs. [6]

**Code generation pipeline:**

1. Artist builds a graph of nodes with typed input/output ports
2. Each node has a `generate_code()` equivalent that emits HLSL fragments
3. The system handles function signatures, braces, indentation automatically (in string mode)
4. A precision system uses the `$precision` token, replaced at generation time with `half` or `float` based on the node's precision setting
5. In file mode, the graph injects `#include` references into the final shader rather than generating inline code
6. Generated functions get a precision suffix appended to their names (e.g., `MyFunction_float`, `MyFunction_half`)
7. The output is a complete HLSL shader with SubShader/Pass structure wrapped in Unity's ShaderLab syntax [7]

**Custom Function Node:** Allows injecting arbitrary HLSL. Pipeline-specific functions require `#if defined()` guards because the preview shader has no pipeline context. [7]

**Joon relevance:**
- The precision token substitution pattern (`$precision` -> `half`/`float`) is a simple but effective way to handle type polymorphism in generated code. Joon could use similar template tokens in GLSL generation.
- The string-mode vs file-mode distinction (inline generation vs include reference) mirrors a design choice Joon will face: generate everything inline vs reference precompiled shader libraries.

**References:**
- [6] [Shader Graph Custom Function Node](https://docs.unity3d.com/Packages/com.unity.shadergraph@17.0/manual/Custom-Function-Node.html)
- [7] [Adding HLSL to Shader Graph](https://connect.unity.com/p/adding-your-own-hlsl-code-to-shader-graph-the-custom-function-node)

---

### 1.3 Unreal Niagara

**What it is:** Unreal Engine's GPU particle/VFX system, replacing Cascade. Fully scriptable, modular, supports millions of GPU particles. [8]

**Architecture -- Module/Emitter/System hierarchy:**

- **System:** Top-level container placed in the level. Contains one or more Emitters.
- **Emitter:** Defines spawn, simulate, render behavior. Can run on CPU or GPU.
- **Module:** Building block used inside emitters. Assigned to execution groups:
  - System group (shared behavior, executes first)
  - Emitter group (per-emitter)
  - Particle group (per-particle)
  - Render group (rendering instructions)
- Stack simulation: modules execute top-to-bottom within each group. [8][9]

**GPU simulation:**

- GPU emitters support up to 2 million particles (20x CPU limit)
- Requires GPU resource allocation, HLSL code, CPU-GPU data marshaling
- **Data Interface:** A "bridge" between CPU and GPU. Custom Niagara Data Interface Proxy (NDI) gives full control over memory layout and data conversion. Standard types like `TArray` cannot be used on GPU. [10]
- **Simulation Stages:** Advanced GPU feature enabling multiple spawn/update stages per frame, used for fluid simulations and complex structures [11]

**Custom HLSL integration:**
- Custom HLSL nodes provide a text area ("Niagara wrangle") for writing GPU code
- Modules can be created in the Script Editor using a visual node graph that generates HLSL
- GPU code must avoid branching patterns that harm SIMT performance [10]

**Joon relevance:**
- The Data Interface concept (typed bridge between host/device with explicit memory layout control) is directly relevant to Joon's CPU-GPU data transfer model
- The module stack (ordered list of transformations on particle data) is essentially a linear node graph -- similar to Joon's pipeline concept but with explicit ordering rather than dataflow
- Simulation Stages (multiple dispatches per frame) map to Joon's multi-pass compute pipeline

**References:**
- [8] [Niagara Key Concepts](https://dev.epicgames.com/documentation/en-us/unreal-engine/niagara-key-concepts)
- [9] [Niagara System and Emitter Module Reference](https://dev.epicgames.com/documentation/en-us/unreal-engine/system-and-emitter-module-reference-for-niagara-effects-in-unreal-engine)
- [10] [Niagara Deep Dive (cgwiki)](https://tokeru.com/cgwiki/Niagara.html)
- [11] [Niagara Simulation Stage Basics](https://heyyocg.link/en/ue4-26-niagara-adavanced-simulation-stage-basic/)

---

### 1.4 Unreal Material Editor

**What it is:** Node-based material authoring that compiles to HLSL shaders. [12]

**Node-to-HLSL compilation pipeline:**

1. Each Material Expression node contains a small HLSL snippet
2. The Main Material Node displays the combined result
3. On compilation, the engine traverses the expression tree
4. Each node's `Compile(FMaterialCompiler* compiler, int32 pinIdx)` generates code for its output pin
5. Code is assembled into `CalcPixelMaterialInputs()` which assigns computed values to a `PixelMaterialInputs` structure
6. Custom Expression nodes are copy-pasted as `CustomExpressionX()` functions
7. Generated code is injected via `#include "/Engine/Generated/Material.ush"`
8. `FMaterialPixelParameters` is passed as a secret input to all expressions
9. Final HLSL viewable via Window > Shader Code > HLSL Code (read-only) [12][13]

**Performance note:** Custom nodes prevent constant folding and may use more instructions than equivalent built-in nodes. [14]

**Joon relevance:**
- The `Compile()` method pattern (each node knows how to generate its own code fragment, driven by a compiler visitor) is exactly how Joon's IR nodes could emit GLSL
- The "secret parameter" pattern (FMaterialPixelParameters always available) is like Joon passing a standard context struct to all generated compute shader functions
- Constant folding prevention in custom nodes is a cautionary tale: Joon should ensure its optimization passes can see through all node types

**References:**
- [12] [How UE Translates Material Graph to HLSL](https://dev.epicgames.com/community/learning/knowledge-base/0qGY/how-the-unreal-engine-translates-a-material-graph-to-hlsl)
- [13] [Materials Compilation in UE: Nuts and Bolts](https://kseniia-shestakova.medium.com/materials-compilation-in-unreal-engine-nuts-and-bolts-bba28abeb789)
- [14] [Custom Material Expressions](https://dev.epicgames.com/documentation/en-us/unreal-engine/custom-material-expressions-in-unreal-engine)

---

### 1.5 Godot VisualShader

**What it is:** Open-source node-to-GLSL shader system in the Godot engine. [15]

**Source code architecture (three layers):**

1. **Graph structure:** `VisualShader` class (inherits from `Shader`) manages nodes, connections, and code generation. Output node always has ID 0. User nodes start from ID 2. Each shader type (vertex, fragment, light, etc.) maintains its own independent graph. [15]

2. **Node system:** Each node type inherits from `VisualShaderNode`. Every node implements `generate_code()` which produces GLSL fragments. Output variables follow the naming pattern `n_out{node_id}p{port_index}` for unique identification. [15]

3. **Code generation pipeline:**
   - `_update_shader()` orchestrates compilation
   - Connection tracking enables topological sorting
   - Graphs for each type (vertex/fragment/light/etc.) are compiled separately
   - Results are combined into a single shader with multiple functions
   - Available inputs depend on `shader_mode` (Spatial, Canvas, Particles, Sky, Fog) and `shader_type` [15]

**Joon relevance:**
- The variable naming convention (`n_out{id}p{port}`) is a clean approach Joon can adopt for generated GLSL variable names to avoid collisions
- Topological sort of the connection graph before code generation is exactly what Joon's IR graph needs
- The separation of graph types (vertex/fragment/etc.) compiled independently then merged is analogous to Joon potentially having different compute passes compiled separately
- Being open-source, the Godot implementation is inspectable: see `scene/resources/visual_shader.cpp` in the Godot repository

**References:**
- [15] [Godot Visual Shader System (DeepWiki)](https://deepwiki.com/godotengine/godot/11-visual-shader-system)
- [16] [Godot VisualShader docs](https://docs.godotengine.org/en/stable/tutorials/shaders/visual_shaders.html)
- Source: https://github.com/godotengine/godot (`scene/resources/visual_shader.cpp`)

---

### 1.6 Bevy (Rust) -- Hanabi Particle System

**What it is:** GPU particle system plugin for Bevy, the Rust game engine. [17]

**Architecture:**

- **Render Graph:** Bevy uses a stateless `RenderGraph` holding stateful nodes. Nodes pass GPU resources (textures, buffers) forming a DAG. Nodes can run arbitrary code including compute passes. Read-only ECS access. [18]
- **Hanabi:** Dynamically generates particle simulation compute shaders based on user configurations. The Expression API defines animations that are hard-coded into the generated compute shader at JIT time. [17]
- **GPU-driven rendering:** Bevy 0.16+ shifts more work to the GPU (frustum/occlusion culling on GPU). [18]
- **Sprinkles:** A newer project providing a visual editor for Bevy particles, since tweaking values in code is impractical for VFX iteration. [19]

**Joon relevance:**
- Hanabi's approach of dynamically generating compute shader source from a high-level expression API is the closest analog to Joon's pipeline (DSL -> compute shader)
- The Expression API design (composable expressions that compile to GPU code) maps directly to Joon's Lisp expressions compiling to GLSL
- Bevy's render graph (stateless DAG of GPU passes) is architecturally similar to Joon's compute node graph
- Being Rust, Hanabi is a good reference for type-safe shader code generation

**References:**
- [17] [Bevy Hanabi](https://github.com/djeedai/bevy_hanabi)
- [18] [Bevy Render Architecture](https://bevy-cheatbook.github.io/gpu/intro.html)
- [19] [Sprinkles: GPU particle editor for Bevy](https://doce.sh/blog/bevy-sprinkles)

---

## 2. Shader Compilation Systems

### 2.1 Slang (Shader-slang)

**What it is:** Cross-platform shading language extending HLSL with generics, interfaces, modules, and automatic differentiation. Compiles to SPIR-V, DXIL, Metal, CUDA, C++, WGSL. By Yong He, Tim Foley, Kayvon Fatahalian. [20]

**Compilation architecture:**

1. Slang source parsed to AST
2. AST lowered to Slang IR (SSA-form)
3. **Legalization passes** prepare IR for target:
   - SPIR-V requires structured control flow; restructuring pass converts arbitrary CFGs
   - Resource legalization for descriptor sets and push constants
4. **SPIR-V emission:** `SPIRVEmitContext` directly emits SPIR-V binary from Slang IR (no intermediate compiler like glslc)
5. Emission organized into logical sections matching SPIR-V physical layout
6. Dead code elimination and other optimizations at IR level [20][21]

**Key features:**
- Generics and interfaces enable composable shader modules (same motivation as Spark)
- Automatic differentiation built into the compiler
- No downstream compiler dependency for SPIR-V (direct emission)

**Joon relevance:**
- Slang's direct SPIR-V emission (no glslangValidator) is the gold standard for a DSL -> SPIR-V pipeline. Joon currently generates GLSL and uses glslangValidator; Slang proves direct SPIR-V emission is achievable and faster.
- The legalization pass concept (transforming IR to conform to target constraints) is relevant: Joon's IR may need similar passes before GLSL/SPIR-V generation
- Slang's generics/interfaces for shader composition could inspire Joon's type system design

**References:**
- [20] [Slang GitHub](https://github.com/shader-slang/slang)
- [21] [Slang Compiler Overview](http://shader-slang.org/slang/design/overview.html)
- Paper: [Slang (SIGGRAPH 2018)](https://d1qx31qr3h6wln.cloudfront.net/publications/he18_slang.pdf)
- Thesis: [Yong He thesis](http://graphics.cs.cmu.edu/projects/renderergenerator/yong_he_thesis.pdf)

---

### 2.2 OpenShadingLanguage (OSL)

**What it is:** Production shading language used by major renderers (Arnold, RenderMan, Cycles, appleseed). LLVM JIT-compiled. Academy Software Foundation project. [22]

**Compilation pipeline:**

1. `oslc` compiler translates OSL source to `.oso` bytecode (assembly-like intermediate code)
2. `liboslexec` (the `ShadingSystem`) loads `.oso` at runtime
3. `RuntimeOptimizer` analyzes and optimizes shader networks with full knowledge of runtime parameters and constant values
4. `BackendLLVM` translates optimized IR to LLVM IR
5. LLVM JIT compiles to native x86 instructions
6. Result: OSL shader networks run 25% faster than equivalent hand-written C [22][23]

**Key design:**
- Two-phase optimization: compile-time (oslc) and runtime (RuntimeOptimizer with full parameter knowledge)
- Network-level optimization: the optimizer sees the entire shader network, not just individual shaders, enabling cross-shader constant folding and dead code elimination
- Plugin architecture: renderers integrate OSL via the ShadingSystem API

**Joon relevance:**
- The two-phase optimization (offline compilation + runtime optimization with parameter knowledge) is directly applicable. Joon could pre-compile node implementations, then do a final optimization pass at runtime when parameter values are known.
- Network-level optimization (seeing the whole graph) is exactly what Joon needs: optimize across node boundaries, not just within individual nodes
- The `.oso` intermediate format concept (stable bytecode between compilation phases) could inspire Joon's IR serialization format

**References:**
- [22] [OSL GitHub](https://github.com/AcademySoftwareFoundation/OpenShadingLanguage)
- [23] [OSL LLVM Talk (2010)](https://llvm.org/devmtg/2010-11/Gritz-OpenShadingLang.pdf)
- [24] [OSL LLVM Integration (DeepWiki)](https://deepwiki.com/AcademySoftwareFoundation/OpenShadingLanguage/3.1-llvm-integration-and-jit-compilation)

---

## 3. Raytracing and Path Tracing Tools

### 3.1 Mitsuba 3

**What it is:** Research-oriented physically-based renderer with first-class differentiable rendering. Retargetable to multiple backends. [25]

**Architecture:**

- **Variant system:** Each "variant" is a unique combination of:
  - Backend: scalar (CPU, no JIT), llvm (LLVM JIT), cuda (CUDA/OptiX)
  - Color: rgb, spectral, mono, polarized
  - Implemented via C++ template metaprogramming; all components (BSDFs, emitters, integrators) are parameterized by variant type [25]

- **Dr.Jit integration:** A just-in-time compilation framework tightly coupled with Mitsuba:
  - Traces computation, building a graph of all operations while postponing evaluation (lazy evaluation)
  - When evaluated, fuses all operations into efficient kernels
  - LLVM backend for CPU, CUDA/OptiX backend for GPU
  - Supports automatic differentiation for inverse rendering [26]

- **Plugin system:** All rendering components (integrators, shapes, materials, sensors, emitters) are plugins instantiated from a common scene description (XML or Python dicts). Researchers can add new plugins without modifying core code. [25]

- **Python extensibility:** Materials, textures, and even full rendering algorithms can be developed in Python, which the system JIT-compiles and optionally differentiates on the fly. [25]

**Scene description:** XML format or Python dict specifying a tree of plugin instances with parameters. Purely declarative.

**Joon relevance:**
- The **lazy evaluation + kernel fusion** model is extremely relevant. Joon's node graph represents deferred computation; at dispatch time, the system could fuse multiple nodes into a single compute kernel, similar to Dr.Jit.
- The **variant/backend retargetability** through template parameterization shows how a single codebase can target different GPU APIs. Joon currently targets only Vulkan compute, but the architecture should not preclude future backends.
- Dr.Jit's approach of tracing computation as a graph then JIT-compiling is essentially what Joon does: build an IR graph from DSL, then compile to SPIR-V.

**References:**
- [25] [Mitsuba 3 GitHub](https://github.com/mitsuba-renderer/mitsuba3)
- [26] [Dr.Jit Core](https://github.com/mitsuba-renderer/drjit-core)
- Paper: [Mitsuba 2: A Retargetable Forward and Inverse Renderer (SIGGRAPH Asia 2019)](https://dl.acm.org/doi/10.1145/3355089.3356498)

---

### 3.2 PBRT (v4)

**What it is:** The reference physically-based renderer accompanying the textbook. [27]

**Scene file format:**

- Plain text, designed to be easy to parse and easy to generate from other applications
- Structure: camera/film/sampler directives, then `WorldBegin`, then lights/materials/shapes in the world block
- Plugin-like architecture: shapes, materials, textures are specified by string type + parameter list (e.g., `Shape "sphere" "float radius" 1.0`)
- Materials evolved significantly in v4: physically-motivated names like "conductor" and "coateddiffuse" replaced ad-hoc names like "mirror" and "plastic" [27][28]

**Joon relevance:**
- PBRT's scene format is a non-visual DSL for describing rendering -- Joon's Lisp DSL serves the same role for image processing
- The string-type + parameter-list pattern for instantiating components is similar to Joon's node registry
- PBRT's evolution toward physically-motivated material names (v4) shows the value of domain-appropriate abstractions

**References:**
- [27] [PBRT v4 File Format](https://pbrt.org/fileformat-v4)
- [28] [PBRT v4 Source](https://github.com/mmp/pbrt-v4)

---

### 3.3 LuxCoreRender

**What it is:** Open-source physically-based renderer with a node-based material system. [29]

**Node-based material architecture:**

- Every material has an associated node tree
- **Material nodes:** Can have interior/exterior volumes on output. Multiple output nodes allowed for testing, but only one active.
- **Common sockets:** All materials share Opacity, Bump, and Emission sockets
- **Abstraction layer:** Nodes don't expose LuxCore properties 1:1. One node may create multiple LuxCore materials behind the scenes (e.g., glass node -> glass/roughglass/archglass depending on settings) [29]
- **Runtime evaluation:** Materials and textures use a **stack-based evaluation method**, allowing greater flexibility and avoiding kernel recompilation when settings change [30]

**Joon relevance:**
- The stack-based runtime evaluation (avoiding recompilation on parameter change) is a key performance pattern. Joon should separate parameter changes (uniform updates, no recompile) from topology changes (graph rewiring, requires recompile).
- The abstraction layer (one user-facing node maps to multiple internal nodes) is a useful pattern for Joon's DSL: high-level functions that expand to multiple IR nodes.

**References:**
- [29] [BlendLuxCore Node Editor](https://wiki.luxcorerender.org/BlendLuxCore_Node_Editor)
- [30] [LuxCoreRender v2.4 Release Notes](https://wiki.luxcorerender.org/LuxCoreRender_Release_Notes_v2.4)

---

### 3.4 Appleseed

**What it is:** Open-source production renderer with full OSL integration. [31]

**OSL integration approach:**

- Rather than building a custom shading system, appleseed integrates OSL entirely
- Compiles OSL shaders on the fly (no manual oslc step needed)
- On startup, scans the shaders directory, reads `.oso` files, and dynamically builds node types from their parameter declarations
- Plugins for Blender, 3ds Max, Maya, and Gaffer all expose the same OSL shader set [31]

**Joon relevance:**
- The "scan directory, build nodes from metadata" pattern is excellent for extensibility. Joon could support user-defined compute shader snippets that are auto-registered as nodes by scanning their parameter declarations.

**References:**
- [31] [Appleseed Features](https://appleseed.readthedocs.io/en/latest/features/features.html)
- [32] [Appleseed GitHub](https://github.com/appleseedhq/appleseed)

---

## 4. Artist Graph Tools (General)

### 4.1 Gaffer

**What it is:** Open-source node-based application framework for VFX lookdev, lighting, and automation. Originally by John Haddon (2007), used in production at Image Engine since 2011. [33]

**Node evaluation model:**

- **Multi-threaded deferred evaluation:** Computation is deferred until results are needed (pull-based evaluation)
- **Built on Cortex libraries:** Core datatypes and algorithms for VFX, with support libraries for Maya, Nuke, Houdini, RenderMan [33]
- **Caching:** Results are cached; expressions that don't access frequently-changing context variables are evaluated only once
- **Complexity model:** Rough estimate = `num_locations * num_nodes`. Performance scales linearly with both. [34]
- **Qt-based UI:** Flexible framework for editing and viewing node graphs [33]

**Joon relevance:**
- The **pull-based deferred evaluation** model is relevant for Joon's GUI: only compute what's visible/needed, not the entire graph
- The caching strategy (cache based on which context variables an expression accesses) is applicable to Joon's parameter invalidation: only recompute nodes whose inputs actually changed

**References:**
- [33] [Gaffer GitHub](https://github.com/GafferHQ/gaffer)
- [34] [Gaffer Performance Best Practices](https://www.gafferhq.org/documentation/1.3.5.0/WorkingWithTheNodeGraph/PerformanceBestPractices/index.html)
- Paper: [Gaffer: An Open-Source Application Framework for VFX (DigiPro 2016)](https://dl.acm.org/doi/10.1145/2947688.2947696)

---

### 4.2 Katana (Foundry)

**What it is:** Look development and lighting tool for film VFX. Handles enormous scene graphs through deferred evaluation. [35]

**Deferred evaluation architecture:**

- Scene data is described as a **tree of filters** (functional representation)
- Filters are **statelessly, lazily evaluated** -- scene data calculated on demand as the renderer requests it
- Scene graph contains "potential work" -- locations and children are only known through expansion
- Deferred procedures (e.g., material copies) are postponed until needed by the renderer
- Benefits: faster initial scene graph generation, higher-level editing, easier overrides [35][36]

**Designed for renderers with deferred recursive procedurals** (RenderMan, Arnold): the filter tree is handed directly to the renderer. [36]

**Performance optimization:** Node graph design directly impacts performance. Minimizing the number of locations that pass through expensive nodes is key. [37]

**Joon relevance:**
- Katana's **lazy evaluation** is the most mature implementation of deferred scene processing. For Joon, this means: don't evaluate the entire graph when the user changes one parameter. Only recompute the subgraph that feeds into the currently-viewed output.
- The **filter tree** concept (each node is a function that transforms the scene) maps to Joon's compute nodes as functions that transform image data
- The "potential work" model is important for Joon's GUI: show the graph structure without executing it until the user requests a preview

**References:**
- [35] [What is Katana?](https://learn.foundry.com/katana/content/ug/preface/what_is_katana.html)
- [36] [Katana 2.0 (fxguide)](https://www.fxguide.com/fxfeatured/katana-2-0/)
- [37] [Katana Node Graph Performance](https://learn.foundry.com/katana/dev-guide/PerformanceOptimizationGuide/NodeGraph.html)
- White paper: https://www.cgw.com/documents/pdfs/katana_white_paper.pdf

---

### 4.3 Guerilla Render

**What it is:** Assembly and bi-directional path tracing render engine with nodal, procedural, non-destructive workflow. [38]

**Architecture:**

- Lights and shaders assigned via a **nodal render graph**
- Shading via RSL (RenderMan Shading Language) shaders or shading networks using **SLBox nodes** (subset of RSL for shading expressions)
- Library of hundreds of nodes: materials, lights, environments, sub-shaders, shading nodes, procedurals, render passes
- Both a Reyes renderer and an unbiased path tracer
- AOVs use OSL Light Path Expressions
- Surface2/Volume2 shaders with GGX specular and energy conservation [38]

**Joon relevance:**
- The SLBox concept (lightweight expression nodes using a subset of a shading language) is similar to Joon's approach: nodes are essentially small compute shader snippets
- Separating the render graph (node assignment) from the shading graph (material definition) is a useful architectural separation

**References:**
- [38] [Guerilla Render Features](http://guerillarender.com/?cat=5)
- [39] [Guerilla Render in Production (Chris Brejon)](https://chrisbrejon.com/articles/guerilla-render-in-production/)

---

### 4.4 ICE (Softimage)

**What it is:** Interactive Creative Environment -- visual programming platform introduced in Softimage XSI 7 (2008). One of the first visual programming systems for 3D. [40]

**Architecture:**

- Node-based dataflow diagram where each node has specific capabilities
- Data flows through connected nodes, visually representing the processing pipeline
- **Parallel processing engine:** Takes advantage of multi-core CPUs for scalable performance
- Main uses: procedural modeling, deformation, rigging, particle simulation, scene attribute control
- No scripting required for complex effects [40]

**Historical importance:**
- Pioneered the concept that visual graphs could express sophisticated math, constraints, and state management without degenerating into "spaghetti" if designed carefully
- Key influence on subsequent node-based systems in 3D (Houdini VOP, Niagara, Bifrost)
- Autodesk discontinued Softimage in 2015; Bifrost is considered its spiritual successor [41]

**Joon relevance:**
- ICE proved that dataflow visual programming could handle production complexity -- the graph metaphor works for serious computation, not just simple parameter tweaking
- The lesson about careful design preventing "spaghetti" is critical for Joon's GUI: node grouping, subgraphs, and good layout algorithms matter

**References:**
- [40] [Softimage ICE Guide](https://download.autodesk.com/global/docs/softimage2014/en_us/userguide/index.html?url=files/ice_cover.htm)
- [41] [Visual Programming in Design (Novedge)](https://novedge.com/blogs/design-news/design-software-history-visual-programming-in-design-from-scripts-and-nodes-to-enterprise-infrastructure)

---

### 4.5 Fabric Engine / Canvas / KL

**What it is:** High-performance platform for 3D graphics applications with a custom language (KL), visual programming (Canvas), and multi-threaded core. Defunct (company closed ~2017), but architecturally influential. [42]

**Architecture:**

- **KL (Kernel Language):** JavaScript-like syntax with C++ performance. Compiled via LLVM MCJIT.
  - Two-pass compilation: unoptimized first pass for fast startup, fully optimized code generated in background
  - Crash-free with on-the-fly updates
  - Automatic multi-threading handled by the runtime [42][43]

- **Canvas:** Visual programming environment (node graph). Generates "intelligent assets" and logic. Wider user base than KL directly. [42]

- **Splice API:** Exposes Fabric Engine to other applications (Maya, 3ds Max, Softimage), enabling cross-DCC asset portability. [42]

- **Core execution engine:** Multi-threaded scheduler managing KL kernel execution across available cores.

**Joon relevance:**
- KL's **two-pass JIT compilation** (fast unoptimized -> background optimized) is directly applicable to Joon's interactive use case: show a quick preview immediately, then swap in the optimized version
- The **Splice API pattern** (embedding a compute engine in host applications) could inspire Joon being usable as a library, not just a standalone tool
- KL's LLVM-based compilation of a custom language is architecturally similar to what Joon does with its DSL, just targeting CPU rather than GPU

**References:**
- [42] [Fabric Engine 2.0](https://www.awn.com/news/fabric-engine-20-adds-visual-programming)
- [43] [Fabric Engine KL + LLVM (LLVM Dev Meeting 2014)](https://llvm.org/devmtg/2014-04/PDFs/Talks/FabricEngine-LLVM.pdf) -- PDF

---

### 4.6 Substance Designer

**What it is:** Adobe's node-based procedural texture authoring tool, industry standard for PBR material creation. [44]

**Execution model:**

- **Dual engine:** SSE2 (CPU) and GPU (DirectX 9/10/OpenGL) backends
  - CPU engine: computes up to 2K, no 16-bit color support
  - GPU engine: computes up to 4K, supports all bit depth/channel combinations, significantly faster [45]
- **Node evaluation:** Complex node setups involve many calculations, especially at high bit depth and resolution. GPU engine speeds these up considerably.
- **Procedural generators:** Texture generators require no inputs and generate images from scratch (noise, patterns). These are the "true procedurals." [44]
- **Non-destructive workflow:** All operations are stored as a graph; changing any parameter re-evaluates downstream nodes

**Joon relevance:**
- Substance Designer is the closest commercial analog to Joon's use case (node graph for image processing/generation)
- The dual-engine approach (CPU fallback + GPU fast path) is a pragmatic design Joon could adopt
- Substance's node library (hundreds of texture generators, filters, blends) provides a reference for what operations Joon should support

**References:**
- [44] [Substance Designer Node Library](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/node-library.html)
- [45] [Substance Designer Performance Optimization](https://helpx.adobe.com/substance-3d-designer/best-practices/performance-optimization-guidelines.html)

---

## 5. Academic / Research

### 5.1 Spark: Modular, Composable Shaders for Graphics Hardware

**Authors:** Tim Foley, Pat Hanrahan (Stanford/Intel). **SIGGRAPH 2011.** [46]

**Key contribution:** A shading language where a shader class can encapsulate code mapping to **more than one pipeline stage** and can be extended via object-oriented inheritance.

**Technical details:**
- Addresses the problem that current shading languages enforce a fixed decomposition into per-pipeline-stage procedures, preventing modular decomposition
- Spark compiler performs global optimizations on each shader class
- **Dead-code elimination over the shader graph** is the most important optimization
- Performance: within **2% of hand-written HLSL** [46]

**Joon relevance:**
- Spark's core insight (let abstractions span multiple pipeline stages) applies to Joon: a single Lisp expression might expand to code in multiple compute passes. The DSL should not force the user to think about dispatch boundaries.
- The finding that dead-code elimination is the most important graph-level optimization confirms Joon should prioritize this in its IR optimization passes.

**References:**
- [46] Paper: https://graphics.stanford.edu/papers/spark/spark_preprint.pdf
- [47] [SIGGRAPH History](https://history.siggraph.org/learning/spark-modular-composable-shaders-for-graphics-hardware-by-foley-and-hanrahan/)

---

### 5.2 Halide: Decoupling Algorithms from Schedules

**Authors:** Jonathan Ragan-Kelley et al. (MIT/Stanford). **PLDI 2013.** [48]

**Core innovation:** Separation of the **algorithm** (what to compute) from the **schedule** (how to compute it -- loop ordering, tiling, parallelism, vectorization).

**Compilation pipeline:**
1. User writes algorithm in Halide's functional DSL (pure functions over integer domains)
2. User (or autoscheduler) specifies a schedule
3. Compiler generates optimized code: GPU kernels, vectorized CPU loops, memory management, synchronization
4. A schedule can transform a graph of GPU kernels into an entirely different graph
5. Targets: CPU (x86, ARM), GPU (CUDA, OpenCL, Metal, Vulkan via SPIR-V) [48][49]

**Autoscheduling:** Initially CPU-only; later extended to CUDA GPUs with novel optimization passes. [50]

**Joon relevance:**
- **THE** most directly relevant system to Joon's design. Halide proves that separating "what" from "how" enables dramatic optimization without changing the algorithm.
- Joon's Lisp DSL is the algorithm description; the compilation to Vulkan compute is the schedule. Currently these are interleaved. Consider making scheduling decisions (work group size, tiling, memory layout) separately specifiable.
- Halide's functional DSL over integer domains is essentially what Joon's image processing operations are: pure functions over pixel coordinates.
- The autoscheduler concept could eventually apply to Joon: automatically determine optimal work group sizes, tiling strategies, and buffer layouts.

**References:**
- [48] Paper: https://people.csail.mit.edu/jrk/halide-pldi13.pdf
- [49] [Halide website](https://halide-lang.org/)
- [50] [Schedule Synthesis for Halide on GPUs](https://dl.acm.org/doi/10.1145/3406117)
- Earlier paper: [Decoupling Algorithms from Schedules (2012)](https://people.csail.mit.edu/jrk/halide12/halide12.pdf)

---

### 5.3 Taichi: High-Performance GPU DSL

**Authors:** Yuanming Hu et al. (MIT). **SIGGRAPH Asia 2019.** [51]

**Compilation pipeline:**

1. Python code decorated with `@ti.kernel` is traced
2. Python AST transformed to **Frontend IR** (tree-like, preserving high-level semantics)
3. Lowered to **Core IR** (SSA-form statements suitable for optimization)
4. Optimized: CSE, dead code elimination, CFG analysis -- all at IR level, backend-independent
5. Lowered to **Backend IR** (target-specific: LLVM IR, SPIR-V, CUDA PTX)
6. JIT-compiled via LLVM (CPU), CUDA (NVIDIA GPU), or Vulkan (via SPIR-V) [52]

**Key features:**
- **SNode** data structure abstraction: hierarchical, dense or sparse, multi-dimensional fields
- Source-code-level automatic differentiation (at IR level) for differentiable simulation
- Quantization support (SIGGRAPH 2021) [53]

**Joon relevance:**
- Taichi's **multi-level IR pipeline** (Frontend IR -> Core IR -> Backend IR) is the most sophisticated open-source example of what Joon needs. Joon currently has AST -> IR graph -> GLSL. Adding a core IR optimization layer between the IR graph and GLSL generation would enable backend-independent optimizations.
- Taichi targets **Vulkan via SPIR-V** -- exactly Joon's target. The Taichi source code is a reference for SPIR-V generation from a high-level DSL.
- The SNode data structure abstraction (describing memory layout independently from computation) is relevant to Joon's image buffer management.
- Taichi is open-source: https://github.com/taichi-dev/taichi

**References:**
- [51] Paper: [Taichi (SIGGRAPH Asia 2019)](https://dl.acm.org/doi/10.1145/3355089.3356506)
- [52] [Taichi Architecture (DeepWiki)](https://deepwiki.com/taichi-dev/taichi)
- [53] [DiffTaichi paper](https://openreview.net/pdf/6d9976c7113eb4ad907e38be6d4797388ff35a3b.pdf)
- [54] [Taichi thesis](https://yuanming.taichi.graphics/publication/2021-taichi-thesis/taichi-thesis.pdf)

---

### 5.4 Other Relevant Papers

**Shader-Driven Compilation of Rendering Assets (SIGGRAPH 2002)**
- Pre-processing geometric data with knowledge of shading programs
- Data converted into structures targeted directly at hardware [55]

**Dataflow VFX Programming (SIGGRAPH 2020)**
- Multiple SIGGRAPH/SIGGRAPH Asia course editions (2015-2019) on dataflow programming for artists
- Covers the general principles of node-based VFX authoring [56]

**GPU Work Graphs for Procedural Generation (2024)**
- Novel GPU programming model where work graph nodes are shaders that dynamically generate workloads for connected nodes
- Simplifies recursive procedural algorithms on GPUs [57]

**Efficient Implementation of Data Flow Graphs on Multi-GPU Clusters**
- High-level DFG programming model abstracting architecture
- Automated computation-communication overlap [58]

**References:**
- [55] [Shader-driven compilation (SIGGRAPH 2002)](https://dl.acm.org/doi/10.1145/566570.566641)
- [56] [Dataflow VFX Programming (SIGGRAPH 2020)](https://dl.acm.org/doi/abs/10.1145/3388763.3407760)
- [57] [GPU Work Graphs for Procedural Generation](https://dl.acm.org/doi/10.1145/3675376)
- [58] [DFG on Multi-GPU Clusters](https://link.springer.com/article/10.1007/s11554-012-0279-0)

---

## 6. Design Lessons for Joon

### 6.1 Compilation Pipeline Design

| System | Pipeline | Key Insight |
|--------|----------|-------------|
| Taichi | Python -> Frontend IR -> Core IR -> Backend IR -> SPIR-V/LLVM | Multi-level IR enables backend-agnostic optimization |
| Halide | Algorithm + Schedule -> optimized kernel graph | Separate what from how |
| Slang | Source -> AST -> Slang IR -> legalization -> SPIR-V | Direct SPIR-V emission, no intermediate compiler |
| OSL | Source -> .oso bytecode -> runtime optimize -> LLVM IR -> native | Two-phase: compile-time + runtime with parameter knowledge |
| Godot | Node graph -> topological sort -> per-node GLSL fragments -> combined shader | Simple, effective, inspectable |
| UE Materials | Expression tree traversal -> per-node code chunks -> CalcPixelMaterialInputs() | Each node generates its own code via Compile() visitor |

**Recommendation for Joon:** Adopt a multi-level IR similar to Taichi:
1. **Lisp AST** (what you have: `src/dsl/ast.h`)
2. **High-level IR graph** (what you have: `src/ir/ir_graph.h`, typed, with type checking)
3. **Optimized IR** (new: after dead-code elimination, constant folding, kernel fusion -- backend-agnostic)
4. **GLSL/SPIR-V emission** (what you have: compute shader generation)

### 6.2 Optimization Priorities

Based on every system surveyed:

1. **Dead-code elimination** -- Spark found this to be the single most important graph-level optimization
2. **Constant folding** -- OSL's runtime optimizer gets 25% speedup largely from this
3. **Kernel fusion** -- Dr.Jit traces lazy computation graphs and fuses into minimal kernel count
4. **Parameter separation** -- LuxCore avoids recompilation for parameter changes by using stack-based evaluation; at minimum, Joon should distinguish uniform updates (no recompile) from topology changes (recompile)

### 6.3 Evaluation Strategy

| System | Strategy | When Used |
|--------|----------|-----------|
| Katana | Lazy/pull-based | Huge scenes, render on demand |
| Gaffer | Deferred + cached | Interactive lookdev |
| Unity VFX Graph | Eager recompile on edit | Real-time preview |
| Mitsuba/Dr.Jit | Lazy trace, fused dispatch | Batch rendering |

**Recommendation for Joon:**
- **GUI mode:** Lazy/pull-based (Katana model). Only evaluate what feeds the current preview.
- **CLI/batch mode:** Eager full-graph evaluation with kernel fusion (Dr.Jit model).
- **Two-pass compilation** (Fabric Engine model): Fast unoptimized preview, background-optimized dispatch.

### 6.4 Extensibility Patterns

| System | Pattern |
|--------|---------|
| Appleseed | Scan directory, build nodes from shader parameter metadata |
| Mitsuba | Plugin system: all components instantiated from scene description |
| PBRT | String type + parameter list for component instantiation |
| Niagara | Data Interface abstraction for CPU-GPU bridging |
| Substance | Hundreds of built-in nodes + custom function escape hatch |

**Recommendation for Joon:** Support user-defined nodes as GLSL compute shader snippets with declared typed inputs/outputs. Auto-register by scanning a directory (appleseed pattern). The Lisp DSL should be able to call these as first-class functions.

### 6.5 Text-First vs Visual-First

Joon's "text-first Lisp DSL" is unusual -- most systems surveyed are visual-first with text escape hatches. The closest analogs to Joon's approach:

- **Halide:** Text DSL, no visual editor. Proven at scale (used in Google camera pipeline).
- **Taichi:** Python DSL, no visual editor. Proven for research and production simulation.
- **PBRT:** Text scene description. Industry reference implementation.
- **Mitsuba:** XML/Python scene description. Research standard.

Systems that added visual editors to text-based foundations:
- **Fabric Engine:** KL (text) came first, Canvas (visual) added later in v2.0
- **Bevy Hanabi:** Code API came first, Sprinkles visual editor being added after

**Recommendation for Joon:** The text-first approach is well-validated. When adding the GUI, treat the visual graph as a view/editor for the Lisp DSL, not a replacement. The Lisp text should remain the canonical representation (like Houdini VEX underlying VOPs).

---

## 7. Papers to Download

Direct PDF links for key papers:

| Paper | URL |
|-------|-----|
| Spark (Foley & Hanrahan, SIGGRAPH 2011) | https://graphics.stanford.edu/papers/spark/spark_preprint.pdf |
| Halide (Ragan-Kelley et al., PLDI 2013) | https://people.csail.mit.edu/jrk/halide-pldi13.pdf |
| Halide: Decoupling (2012) | https://people.csail.mit.edu/jrk/halide12/halide12.pdf |
| Slang (He et al., SIGGRAPH 2018) | https://d1qx31qr3h6wln.cloudfront.net/publications/he18_slang.pdf |
| Slang Thesis (Yong He) | http://graphics.cs.cmu.edu/projects/renderergenerator/yong_he_thesis.pdf |
| OSL + LLVM (Gritz, 2010) | https://llvm.org/devmtg/2010-11/Gritz-OpenShadingLang.pdf |
| Fabric Engine KL + LLVM (2014) | https://llvm.org/devmtg/2014-04/PDFs/Talks/FabricEngine-LLVM.pdf |
| DiffTaichi (ICLR 2020) | https://openreview.net/pdf/6d9976c7113eb4ad907e38be6d4797388ff35a3b.pdf |
| Taichi Thesis (Yuanming Hu) | https://yuanming.taichi.graphics/publication/2021-taichi-thesis/taichi-thesis.pdf |
| Katana White Paper | https://www.cgw.com/documents/pdfs/katana_white_paper.pdf |
| Mitsuba 2 (SIGGRAPH Asia 2019) | https://dl.acm.org/doi/10.1145/3355089.3356498 |
| Halide GPU Autoscheduler | https://dl.acm.org/doi/10.1145/3406117 |
| Gaffer (DigiPro 2016) | https://dl.acm.org/doi/10.1145/2947688.2947696 |

---

## Key Source Code Repositories

| Project | Repository | Language |
|---------|-----------|----------|
| Godot VisualShader | https://github.com/godotengine/godot | C++ |
| Slang | https://github.com/shader-slang/slang | C++ |
| OSL | https://github.com/AcademySoftwareFoundation/OpenShadingLanguage | C++ |
| Taichi | https://github.com/taichi-dev/taichi | C++/Python |
| Mitsuba 3 | https://github.com/mitsuba-renderer/mitsuba3 | C++/Python |
| Dr.Jit | https://github.com/mitsuba-renderer/drjit-core | C++ |
| Bevy Hanabi | https://github.com/djeedai/bevy_hanabi | Rust |
| PBRT v4 | https://github.com/mmp/pbrt-v4 | C++ |
| LuxCoreRender | https://github.com/LuxCoreRender/LuxCore | C++ |
| Appleseed | https://github.com/appleseedhq/appleseed | C++ |
| Gaffer | https://github.com/GafferHQ/gaffer | C++/Python |
| Halide | https://github.com/halide/Halide | C++ |
