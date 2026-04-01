# Demoscene Tools & Procedural Generation Frameworks

**Date:** 2026-03-31
**Context:** Research for Joon — a Lisp-style DSL that compiles to a Vulkan compute node graph for image processing.

---

## Part 1: Demoscene & Visual Programming Tools

### 1.1 Werkkzeug / Farbrausch (.theprodukkt)

#### Architecture

Werkkzeug is Farbrausch's procedural content authoring tool, used to create demos like fr-08 (The Product) and the 96KB FPS game .kkrieger. The core architectural insight is **operator stacking** — a vertically-stacked graph where operators connect implicitly by position rather than by explicit wires [1][2].

From the GenThree concept document (the internal design doc for the third-generation engine), the system is built around these principles [3]:

- **The demo is a tree of operators of different types.** Operators have no fixed screen positions and can appear in multiple views simultaneously.
- **Lazy evaluation with static analysis.** The system determines which operators are "dynamic" (animated) by traversing upward through the tree. "Done" operators (leaf nodes) generate bytecode command lists for interpretation.
- **Two-phase texture generation.** Texture operators are split into "Page Operators" (process entire textures at full resolution) and "Single Operators" (work per-tile without neighbor access). The scheduler reorders these to maximize cache efficiency: singles process tiles first, then page operators run at full resolution.
- **Operator hierarchy is separate from object hierarchy.** For scene graphs (forward kinematics) these coincide, but for texture/mesh generation the operator tree is a pure command sequence, not an object tree.

Mesh generation follows sequential refinement: BaseMesh (coarse geometry with marking flags) -> Subdivision (Catmull-Clark) -> Decoration (instancing via marks) -> Static Lighting (baking). Marks use dual-part identifiers (numeric value + 8 boolean flags) to selectively apply operations [3].

Materials are **rendering state machines** with multiple passes. Each pass maps texture slots and defines renderstates. FXChain networks compose offscreen surfaces for multi-pass effects [3].

Fabian "ryg" Giesen wrote the texture generator, mesh generator, 3D engine, material/lighting systems, and the executable compressor (kkrunchy). The texture generation system was based on the realization that most effects could be decomposed into very simple functions, and a basic set of filters could produce demo-quality textures with minimal storage [4][5].

**Werkkzeug4 CE** added a scripting layer for operator definition: new operators are described in a script language, and compilation automatically generates C++ code for binding operators to the engine and GUI [6].

#### Lessons for Joon

- **Operator stacking vs. wires.** Werkkzeug's implicit connection model is simpler for linear chains but struggles with complex graphs. Joon's S-expression syntax is more expressive — named bindings (def) handle both linear and branching graphs naturally.
- **Two-phase tile/page execution.** Joon's compiled mode (node fusion) should consider this: element-wise ops can execute per-tile for cache locality, while spatial ops (blur, etc.) require full-resolution intermediates.
- **Bytecode command lists.** Werkkzeug compiles operators to bytecode command lists for the runtime. Joon's scheduler produces Vulkan command buffers — same concept, different target.
- **Operator definition via DSL.** Werkkzeug4's script-based operator definition is analogous to how Joon nodes could be defined — a declaration compiles to both GPU shader code and the engine binding.

#### Sources

- [1] [Werkkzeug on PCG Wiki](http://pcg.wikidot.com/pcg-software:werkkzeug)
- [2] [Werkkzeug4 CE Features](http://werkkzeug4ce.blogspot.com/p/features.html)
- [3] [GenThree concept.txt](https://github.com/farbrausch/fr_public/blob/master/genthree/concept.txt) — Farbrausch's internal design document
- [4] [The Farbrausch Way to make Demos](https://llg.cubic.org/docs/farbrauschDemos/) — Cubic
- [5] [Farbrausch demo tools 2001-2011 (fr_public)](https://github.com/farbrausch/fr_public)
- [6] [Werkkzeug4 CE GitHub](https://github.com/wzman/werkkzeug4CE)
- [7] [OpenKTG texture generator](https://github.com/farbrausch/fr_public/tree/master/ktg) — clean reference implementation with premultiplied alpha, 16-bit per channel
- [8] [kkrieger source (werkkzeug3)](https://github.com/jaromil/kkrieger-werkkzeug3)

---

### 1.2 .kkrieger and Farbrausch's Texture Generation System

.kkrieger is a 96KB first-person shooter that generates all its content procedurally at load time [8][9].

#### How It Works

- Textures are stored as **creation histories**, not pixel data. The executable contains only the history data (a sequence of operator invocations with parameters) and the generator code.
- At load time, the CPU replays the creation history to generate all textures. The Windows font system is also used for text-based texture elements.
- The same principle applies to meshes and sounds — everything is procedural.

OpenKTG (in fr_public) is the cleanest reference implementation of these ideas [7]. It was designed around 2007 as "a simple but relatively powerful and orthogonal subset of texture generation functions." Key properties:
- Written for clarity and simplicity, not speed
- 16 bits per color channel (no precision reduction)
- Proper premultiplied alpha throughout
- Orthogonal operator set — each operator does one thing

#### Lessons for Joon

- **Creation history = graph.** Joon's .jn files are essentially creation histories in a more structured form. The operator sequence with parameters maps directly to Joon's `(def name (op args...))` syntax.
- **Orthogonal operator set.** OpenKTG's design philosophy — simple, orthogonal operators that compose well — is exactly right for Joon's node library.
- **Runtime replay vs. compile.** .kkrieger replays on CPU at load time. Joon's interpreter mode is the same concept but dispatches to GPU. The compiled mode goes further by fusing operators.

#### Sources

- [8] [kkrieger source](https://github.com/jaromil/kkrieger-werkkzeug3)
- [9] [kkrieger Wikipedia](https://en-academic.com/dic.nsf/enwiki/506384)
- [10] [In Defense of Game Developers, and The Public Misconception about .kkrieger](https://thehoodieguy02.medium.com/in-defense-of-game-developers-and-the-public-misconception-about-kkrieger-883c40ac3d19)

---

### 1.3 Tooll3 / Tixl

Tooll 3 (now Tixl) is an open-source C# tool for real-time motion graphics, sitting between real-time rendering, procedural content generation, and keyframe animation [11][12].

#### Architecture

- **C# + DirectX 11** (via SharpDX). Operators are C# classes with typed inputs/outputs.
- **Graph-based composition.** Operators connect via a visual node graph. The graph is the primary authoring surface.
- **Live shader editing.** Fragment and compute shaders can be written and hot-reloaded. Technical artists extend the tool by writing HLSL directly.
- **Standalone export.** Completed compositions can be exported as small standalone executables (demoscene heritage).
- **Inputs.** MIDI controllers, OSC, Spout for live performance (VJ use case).

The operator library is maintained separately (tooll3/Operators repository), allowing community extension.

#### Lessons for Joon

- **Operators as first-class typed objects.** T3's operator model (C# classes with typed inputs/outputs) maps well to Joon's node system. The key difference: Joon operators are defined by their GPU shader, not by host-language code.
- **Standalone export.** The demo exe export pattern is relevant — Joon's CLI `joon run` is similar. A future export mode could bundle the runtime + graph into a standalone.
- **Shader hot-reload.** T3 hot-reloads shaders at edit time. Joon does this implicitly — editing the DSL re-parses the graph and the interpreter dispatches updated shaders immediately.

#### Sources

- [11] [Tooll3 GitHub (t3)](https://github.com/tooll3/t3)
- [12] [Tixl (successor)](https://tixl.app/)
- [13] [Tooll3 Operators](https://github.com/tooll3/Operators)

---

### 1.4 Cables.gl

Cables.gl is a web-based visual programming environment for WebGL/WebGPU, now open source [14][15].

#### Technical Architecture

- **Patch-based execution.** The central concept is the "Patch" which orchestrates operator execution, manages the render loop, and coordinates asset loading.
- **Operators ("Ops")** are the functional units. Each op has typed ports (inputs/outputs). Port types include: numbers, strings, textures, objects, and **trigger signals**.
- **Two evaluation models coexist:**
  1. **Data flow:** When a port value changes, the change propagates through links to connected ports, potentially triggering operator execution.
  2. **Trigger flow:** Execution can be explicitly sequenced through trigger ports. The `MainLoop` op has a trigger port that fires 60 times/second, driving the render loop.
- **Shader composition.** The Shader class handles GLSL compilation, uniform management, and modular shader composition via a module system where shader code fragments are combined dynamically [14].
- **Link validation.** The system validates port compatibility before allowing connections — only compatible types can link.

#### Lessons for Joon

- **Trigger vs. data ports.** Cables.gl's distinction between data flow (value changes propagate) and trigger flow (explicit execution order) is relevant. Joon's interpreter mode is pure data flow (evaluate all upstream deps). The scheduler in compiled mode introduces explicit ordering — similar to trigger flow.
- **Shader module composition.** Cables.gl combines shader fragments dynamically. Joon's compiled mode fuses node shaders into combined shaders — same idea but at the Vulkan compute level.
- **Port type system.** Cables.gl's typed ports mirror Joon's type system. The validation model (check at connection time) maps to Joon's graph compile-time type checking.

#### Sources

- [14] [Cables.gl](https://cables.gl)
- [15] [Cables.gl GitHub](https://github.com/cables-gl)
- [16] [Cables.gl DeepWiki — Architecture Overview](https://deepwiki.com/cables-gl/cables/1-overview)
- [17] [Cables.gl — Operators and Ports](https://deepwiki.com/cables-gl/cables/2.2-operators-and-ports)
- [18] [Cables.gl — Trigger Ports](https://cables.gl/docs/5_writing_ops/dev_creating_ports/dev_ports_trigger/dev_ports_trigger)

---

### 1.5 Shadertoy

Shadertoy is not a node graph tool but its multi-pass buffer system is a minimal, widely-understood model for GPU compute graphs [19][20].

#### Buffer System Architecture

- **4 buffers (A, B, C, D)** plus an **Image** pass (final output). Each buffer is a separate shader program with its own framebuffer.
- **Execution order:** Buffer shaders execute before the Image shader, in order A -> B -> C -> D -> Image.
- **Channels (iChannel0-3):** Each shader can sample up to 4 inputs — these can be textures, other buffers, audio FFT, video, cubemaps, or keyboard state.
- **Temporal feedback:** A buffer can read its own previous frame's output. Buffer A reading from Buffer A gives access to `fragColor` from the last frame — enabling iterative algorithms (reaction-diffusion, fluid sim, cellular automata).
- **Under the hood:** OpenGL FramebufferObjects with attached texture objects. Multi-pass rendering juggles framebuffer textures — shaders draw to specific FBOs and read from multiple FBOs simultaneously [20].

#### Common Patterns

- **Precomputation:** Compute expensive data in a buffer at `iFrame==0`, then reuse every frame.
- **Ping-pong feedback:** Two buffers reading each other's previous frames for iterative algorithms.
- **Multi-buffer pipelines:** Buffer A generates base data, Buffer B post-processes, Image composites.
- **State storage:** Encoding state into pixel values (position, velocity, etc.) for particle systems.

#### Lessons for Joon

- **The simplest possible compute graph.** Shadertoy's buffer system is essentially a 5-node fixed-topology graph with temporal feedback. Joon generalizes this to arbitrary DAGs with `state` for feedback.
- **Buffer = intermediate image.** Each Shadertoy buffer maps to a Joon node output — an intermediate `VkImage` in the resource pool.
- **iChannel = node input.** Shadertoy's channel binding is Joon's edge system. The type system (sampler2D vs. samplerCube) maps to Joon's typed edges.
- **Precomputation pattern.** Joon's caching system (skip nodes whose inputs haven't changed) generalizes Shadertoy's `iFrame==0` pattern.

#### Sources

- [19] [Shadertoy Tutorial Part 15 — Channels, Textures, and Buffers](https://inspirnathan.com/posts/62-shadertoy-tutorial-part-15/)
- [20] [Usual tricks in Shadertoy/GLSL](https://shadertoyunofficial.wordpress.com/2016/07/21/usual-tricks-in-shadertoyglsl/)
- [21] [Shadertoy special features](https://shadertoyunofficial.wordpress.com/2016/07/20/special-shadertoy-features/)

---

### 1.6 Bonzomatic

Bonzomatic is a live-coding tool for demoscene "Shader Showdown" competitions — write a 2D fragment shader while it runs in the background [22].

#### Architecture

- **Single fragment shader** evaluated full-screen every frame. No node graph — pure text-to-GPU.
- **Graphics APIs:** DirectX 9, DirectX 11, OpenGL 4.1+.
- **Audio input:** FFT analysis provides audio-reactive uniforms.
- **Configuration:** JSON config for rendering parameters, MIDI input, texture loading.
- **Network extensions:** Forks add WebSocket-based shader streaming for live performances.
- **Build system:** CMake. Dependencies: xorg-dev, libasound2-dev, libglu1-mesa-dev (Linux).

#### Lessons for Joon

- **Text-first, immediate feedback.** Bonzomatic's core loop is: edit text -> compile shader -> see result. This is exactly Joon's live editing loop, but Joon adds structure (named nodes, types, graph) on top of raw shader text.
- **Minimal runtime.** Bonzomatic proves that a text-to-GPU pipeline can be extremely lean. Joon's interpreter mode should aspire to this latency — text edit to pixels in milliseconds.

#### Sources

- [22] [Bonzomatic GitHub](https://github.com/Gargaj/Bonzomatic)
- [23] [Bonzomatic-Compute fork](https://github.com/wrightwriter/Bonzomatic-Compute) — adds compute shader support

---

### 1.7 KodeLife

KodeLife by Hexler is a professional live shader coding tool [24].

#### Architecture

- **Multi-language:** GLSL (all flavors), Metal Shading Language, DirectX HLSL. Basic compute shader support.
- **Live compilation:** Code is checked, evaluated, and updated in the background as you type — no explicit compile step.
- **Visual pipeline configuration:** Most graphics pipeline states (blend modes, depth testing, etc.) are configured visually rather than in code.
- **Inputs:** Audio FFT, MIDI, gamepad, external keyboards.
- **Cross-platform:** macOS, Windows, Linux, iOS, Android.

#### Lessons for Joon

- **Background compilation model.** KodeLife's "compile as you type" is similar to Joon's interpreter/compiler split — immediate results from the interpreter while the background compiler optimizes.
- **Visual pipeline state.** KodeLife exposes pipeline state as UI. Joon exposes it as `param` declarations in the DSL — same idea, different surface.

#### Sources

- [24] [KodeLife — Hexler](https://hexler.net/kodelife)
- [25] [KodeLife manual — Introduction](https://hexler.net/kodelife/manual/introduction)

---

### 1.8 vvvv

vvvv is a visual programming environment for multimedia, used heavily in installations and live performance [26][27].

#### Execution Model

- **Frame-based evaluation.** The mainloop evaluates the entire graph every frame (~60 FPS). Data flows left-to-right, top-to-bottom through links between nodes.
- **Two node types:**
  - **Process nodes** — maintain state between frames (constructor -> Update loop -> Dispose). Analogous to Joon's `state` nodes.
  - **Operation nodes** — pure functions evaluated each frame. Analogous to Joon's `def` nodes.
- **Always-runtime.** There is no edit-compile-run cycle. You modify the program while it runs, with compilation happening in the background [27].
- **Spreading.** vvvv's signature feature: when spreads (arrays) of differing lengths connect to a node, the system replicates shorter spreads to match the maximum slice count. This is implicit parallel processing — similar to Joon's broadcasting (`float * image` multiplies every element).

#### GPU Integration: VL.Fuse

VL.Fuse is an open-source library for visually programming on the GPU within vvvv gamma [28]. Key aspects:

- Built on VL.Stride (Stride 3D engine integration).
- Follows vvvv's "always runtime" model — no build/compile step.
- Covers: distance fields, raymarching, particles, procedural geometry, textures, materials, GPGPU.
- **Patch once, apply anywhere.** Logic patched with FUSE can be applied to materials, particles, effects, or compute shaders without modification.

#### Lessons for Joon

- **Spreading = broadcasting.** vvvv's spreading mechanism is semantically identical to Joon's type broadcasting. The key difference: vvvv broadcasts at the framework level, Joon at the shader level (GLSL/SPIR-V).
- **Process vs. Operation nodes.** vvvv's distinction between stateful processes and pure operations maps directly to Joon's `state` vs. `def` bindings.
- **Always-runtime as target.** vvvv proves that compile-free live editing is viable for complex GPU work. Joon's interpreter mode achieves this; the background compiler is invisible to the user.
- **FUSE: patch-to-shader.** VL.Fuse compiles visual patches to GPU shaders at runtime. Joon's compiled mode fuses DSL nodes into GPU shaders — same concept, text-first instead of visual-first.

#### Sources

- [26] [vvvv Wikipedia](https://en.wikipedia.org/wiki/Vvvv)
- [27] [vvvv Features](https://vvvv.org/features/)
- [28] [VL.Fuse GitHub](https://github.com/TheFuseLab/VL.Fuse)
- [29] [FUSE project](https://www.thefuselab.io/)
- [30] [vvvv Gray Book — Introduction for Creative Coders](https://thegraybook.vvvv.org/reference/getting-started/cc/introduction-for-creative-coders.html)

---

### 1.9 TouchDesigner

TouchDesigner by Derivative is a commercial real-time visual programming environment [31].

#### Operator Model (TOP/CHOP/SOP/DAT/COMP)

TouchDesigner organizes all computation into typed operator families:

| Family | Domain | Runs On |
|--------|--------|---------|
| **TOP** (Texture) | 2D images, compositing, filters | GPU |
| **CHOP** (Channel) | 1D data streams — animation, audio, math, device I/O | CPU |
| **SOP** (Surface) | 3D geometry — points, polygons, particles | CPU (legacy) or GPU (modern) |
| **DAT** (Data) | Text, tables, scripts, OSC, serial | CPU |
| **COMP** (Component) | Containers, UI, 3D scenes | Meta |

Each family has its own type color and connection rules. You cannot directly connect a TOP output to a CHOP input — explicit converter operators (CHOP to TOP, TOP to CHOP, etc.) bridge between families [31][32].

#### GLSL Integration

- Shaders are written in **Text DATs** and referenced by GLSL TOPs or GLSL Materials.
- GLSL TOPs support vertex shaders, pixel shaders, and **compute shaders** [33].
- Uniforms pass data from TouchDesigner operators into shaders — CHOPs, TOPs, and DATs can all feed uniform values without altering shader code [34].
- The GLSL Multi TOP allows more than 3 inputs for complex compositions.

#### Lessons for Joon

- **Typed operator families.** TouchDesigner's TOP/CHOP/SOP/DAT model is the most explicit typing system in any visual tool. Joon's type system (image, mesh, voxel, float, vec) serves the same purpose but at the DSL level.
- **Converter operators.** TD requires explicit type conversion between families. Joon handles this implicitly via broadcasting rules (float -> image, vec3 -> image), which is more ergonomic for the text-first use case.
- **Shader-in-text-node.** TD's pattern of writing GLSL in Text DATs and referencing it from GLSL TOPs is conceptually close to Joon's model where the DSL text defines the GPU computation.

#### Sources

- [31] [TouchDesigner — TOPs vs CHOPs](https://interactiveimmersive.io/blog/touchdesigner-operators-tricks/touchdesigner-tops-vs-chops/)
- [32] [TouchDesigner SOPs Documentation](https://docs.derivative.ca/SOP)
- [33] [GLSL TOP Documentation](https://docs.derivative.ca/GLSL_TOP)
- [34] [GLSL Uniforms in TouchDesigner](https://interactiveimmersive.io/blog/glsl/how-to-use-uniforms-in-the-glsl-top-in-touchdesigner/)

---

### 1.10 Notch

Notch is a commercial, natively GPU-accelerated real-time VFX tool [35].

#### NURA (Notch Unified Rendering Architecture)

Notch's rendering engine provides four physically-based GPU renderers that share unified lighting, shading, and material behavior [36]:

1. **Path Tracer** — unbiased, full global illumination
2. **Accelerated Path Tracer** — biased ray tracing with path resampling for real-time
3. **RT Renderer** — real-time ray tracing (GI, multi-bounce reflections/refraction)
4. **Standard Renderer** — fastest, reduced feature set for real-time content

You can switch between renderers without changing your scene, lighting, or materials. The engine is 100% GPU-based [36].

#### Node Graph

Notch uses a node-based interface with a real-time rendering viewport, timeline, curve editor, asset browser, and color scopes. The workflow allows create, simulate, render, composite, edit, and playback — all in real time [35].

Scalability targets: billions of polygons, thousands of lights, with deterministic rendering for distributed setups.

#### Lessons for Joon

- **Renderer-independent graph.** Notch proves that the same graph can target different renderers. Joon has interpreter mode vs. compiled mode — similar concept. A future extension could target different GPU backends (Vulkan, Metal, WebGPU) from the same DSL.
- **100% GPU.** Notch's fully GPU-based engine validates Joon's Vulkan-first design. CPU nodes should be the exception, not the rule.

#### Sources

- [35] [Notch](https://www.notch.one/)
- [36] [NURA Rendering Architecture](https://manual.notch.one/1.0/en/docs/learning/lighting-and-rendering/nura-rendering-architecture/)
- [37] [Notch reviewed for mortals](https://cdm.link/notch-tool-explained-and-reviewed-for-mere-mortals/)

---

## Part 2: Procedural Generation Frameworks

### 2.1 Noise Libraries: libnoise, FastNoiseLite, FastNoise2

#### libnoise

libnoise is a C++ library where noise generators are encapsulated in **noise modules** that connect into a graph [38]. Modules have typed inputs/outputs and compose into pipelines:

```
Perlin -> ScaleBias -> Add -> Select -> Output
                       ^       ^
              Ridged --+  Billow +
```

This is a DAG of noise modules — the same concept as Joon's IR graph. The library spawned visual tools like Noise Graph that let you design module pipelines graphically and export C++ code [39].

#### FastNoiseLite

FastNoiseLite is a single-header portable noise library available in 15+ languages including C++, HLSL, and GLSL [40]. Design characteristics:

- **Flat API.** Single class with configuration methods — no graph, no composition. Set noise type, fractal type, parameters, then call `GetNoise(x, y, z)`.
- **Cross-platform.** The same API works in CPU code (C++), vertex/fragment shaders (HLSL/GLSL), and scripting languages.
- **Performance:** ~48M points/sec for 3D Perlin (vs. libnoise's 0.65M).

#### FastNoise2

FastNoise2 is where things get directly relevant to Joon. It is a **modular node-graph-based noise generation library** using SIMD, C++17, and templates [41][42].

Key architectural innovations:

- **SIMD fusion.** The entire node graph computation is fused and executed in SIMD, keeping intermediate values in registers rather than writing to memory. Traditional approaches generate noise arrays separately and combine them in scalar operations — FastNoise2 avoids this by fusing all operations.
- **Node API:** `FastNoise::New<T>()` returns `SmartNode<T>` (reference-counted). Nodes connect programmatically.
- **Serialization.** Node trees serialize to compact strings for runtime loading. The included visual Node Editor exports serialized strings.
- **SIMD-agnostic extensibility.** Custom nodes use the FastSIMD interface, automatically compiling for Scalar, SSE2, SSE4.1, AVX2, AVX512, NEON, WASM SIMD.
- **Thread-safe.** The same node tree can be evaluated from multiple threads simultaneously.

Performance at AVX2 (Intel 7820X @ 4.9GHz):
- Value noise: **494M points/sec** (vs. FastNoiseLite's 64M, libnoise's 27M)
- Perlin: **261M points/sec** (vs. 48M, 0.65M)
- Cellular: **52M points/sec** (vs. 12M)

#### Lessons for Joon

- **FastNoise2's fusion model is the CPU analog of Joon's compiled mode.** FN2 fuses noise graph nodes into single SIMD passes, keeping intermediates in registers. Joon's compiled mode fuses image processing nodes into single Vulkan compute dispatches, keeping intermediates as shader locals. Same principle, different hardware.
- **libnoise's module graph = Joon's IR graph.** The composition model is identical. Joon adds: GPU execution, type broadcasting, and a DSL surface.
- **FastNoiseLite's flat API is the wrong model for Joon.** No composition, no graph — it's a leaf node. But its cross-platform portability (HLSL/GLSL versions) is relevant for Joon's noise node implementation.
- **Serialization.** FastNoise2's compact string serialization for node trees is worth studying. Joon's .jn files serve the same purpose but with human-readable S-expressions.

#### Sources

- [38] [libnoise](https://libnoise.sourceforge.net/)
- [39] [libnoise tutorials](https://libnoise.sourceforge.net/tutorials/)
- [40] [FastNoiseLite GitHub](https://github.com/Auburn/FastNoiseLite)
- [41] [FastNoise2 GitHub](https://github.com/Auburn/FastNoise2)
- [42] [FastNoise2 Wiki — Getting Started](https://github.com/Auburn/FastNoise2/wiki/Getting-started-using-FastNoise2)
- [43] [FastNoise2 Web Editor](https://auburn.github.io/FastNoise2/)

---

### 2.2 Wave Function Collapse

WFC is a constraint-solving algorithm for procedural generation, originally published by Maxim Gumin in 2016 [44].

#### Technical Model

- **Input:** Example image or tileset with adjacency rules.
- **State:** A grid ("wave") where each cell holds a superposition of possible patterns.
- **Algorithm:** Iteratively collapse the lowest-entropy cell (choose a pattern), then propagate constraints to neighbors, removing incompatible patterns. Repeat until all cells are collapsed or a contradiction is found.
- **Two models:**
  - **Overlapping model:** Extract NxN patterns from input, augment with rotations/reflections.
  - **Tile model:** Explicit tileset with adjacency constraints.

#### Graph-Based Extensions

Florian Drux generalized WFC to work on graphs with arbitrary local structure (not just regular grids). This enables generation on arbitrary topologies — hexagonal grids, 3D meshes, irregular graphs [45].

#### Implementations

WFC has been implemented in C++, Python, Rust, Julia, Go, Java, Kotlin, and integrated into Unity, Unreal Engine 5, Godot 4, and Houdini [44].

#### Lessons for Joon

- **WFC as a Joon node.** A `wfc` node could take a tileset/example texture and output constraints-satisfied tiled images. This would be a CPU-tier node (constraint propagation is inherently sequential) that produces GPU-tier output.
- **Graph topology generalization.** WFC on arbitrary graphs suggests that Joon's `voxel` type (3D grids) could support WFC-based 3D structure generation.

#### Sources

- [44] [WFC GitHub](https://github.com/mxgmn/WaveFunctionCollapse)
- [45] [WFC Explained — BorisTheBrave](https://www.boristhebrave.com/2020/04/13/wave-function-collapse-explained/)
- [46] [Graph-based WFC paper](https://www.researchgate.net/publication/336086804_Automatic_Generation_of_Game_Content_using_a_Graph-based_Wave_Function_Collapse_Algorithm)

---

### 2.3 L-Systems and Grammar-Based Generation

L-systems are parallel rewriting systems where production rules expand symbols into larger strings, and a mechanism translates strings into geometric structures. Introduced by Aristid Lindenmayer in 1968 for modeling plant growth [47].

#### Technical Structure

- **Alphabet:** Set of symbols (e.g., F, +, -, [, ])
- **Axiom:** Initial string
- **Production rules:** Symbol -> replacement string (applied in parallel)
- **Interpretation:** Turtle graphics or other geometric mapping

#### Extensions

- **Parametric L-systems:** Symbols carry numeric parameters, rules include conditions.
- **Stochastic L-systems:** Multiple rules per symbol with probabilities.
- **Context-sensitive L-systems:** Rules depend on neighboring symbols.
- **FL-system (Functional L-system):** A functional approach to L-systems for procedural geometric modeling [48].

#### Graph Grammars

Graph grammars extend L-systems from string rewriting to graph rewriting [49]:

- **Shape grammars:** Rules transform geometric shapes according to spatial relationships.
- **Example-based graph grammars:** Automatically learn grammar rules from example shapes, generating new variations without manual rule creation [49].
- **GPU shape grammars:** Map procedural modeling techniques to GPU requirements for real-time execution.

#### Lessons for Joon

- **L-systems as a Joon construct.** An `lsystem` node could take rules + iterations and produce mesh or image output. The rewriting is CPU-tier; geometric interpretation could be GPU-tier.
- **Grammar-based node composition.** Joon's `use` import system could support a simple grammar for composing sub-graphs — templates/macros that expand during parsing.
- **Functional L-systems.** The FL-system paper's functional approach is philosophically aligned with Joon's functional DSL. Production rules could be expressed as Joon functions.

#### Sources

- [47] [L-system — Wikipedia](https://en.wikipedia.org/wiki/L-system)
- [48] [FL-system: A Functional L-system for procedural geometric modeling](https://www.researchgate.net/publication/220067190_FL-system_A_Functional_L-system_for_procedural_geometric_modeling)
- [49] [Example-Based Procedural Modeling Using Graph Grammars — ACM TOG](https://dl.acm.org/doi/10.1145/3592119)

---

### 2.4 Academic Work: Procedural Texture Synthesis

#### Surveys

**"Survey of Procedural Methods for Two-Dimensional Texture Generation" (Dong et al., 2020)** [50] — The most comprehensive survey. Categorizes methods into:

- **Structured:** Cellular automata, texton placement, reaction-diffusion, geometry-based (Voronoi, Islamic patterns, matrix transforms)
- **Unstructured — Frequency domain:** Colored noise, wavelet noise, anisotropic noise, Fourier spectral, spot noise, Gabor noise, stochastic subdivision
- **Unstructured — Spatial domain:** Various tiling and stochastic methods

**"A Survey of Procedural Noise Functions" (Lagae et al., 2010)** [51] — Foundational survey of noise functions used in computer graphics.

#### GPU Operator Graphs

**"Procedural Generation via Operator Graphs using GPU Work Graphs" (University of Stuttgart, 2024)** [52][53] — Directly relevant to Joon:

- Operator graphs serve as a common intermediate representation for procedural generation.
- The operator graph is described using a **domain-specific language (PGA-Shape DSL)**.
- The DSL compiler generates HLSL code from the operator graph — a compiled operator graph produced **1754 lines of generated HLSL**.
- GPU work graphs (DirectX 12 feature, released March 2024) provide the execution model: nodes are shaders that dynamically generate workloads for connected nodes.
- This greatly simplifies recursive procedural algorithms on GPUs.

This is the closest academic precedent to Joon's architecture: DSL -> operator graph -> compiled GPU shaders.

#### Other Relevant Work

- **"Realtime compositing of procedural facade textures on the GPU"** [54] — Uses texture atlases with atomic tiles, composited on-the-fly on the GPU.
- **"Procedural 3D texture synthesis using genetic programming"** [55] — Automatically evolving procedural texture programs.
- **"Interactive Methods for Procedural Texture Generation"** [56] — Interactive tools for procedural texture creation on GPU.
- **GPU linear algebra operators (Kruger & Westermann, SIGGRAPH 2003)** [57] — Framework for implementing linear algebra operators on GPUs using a stream model, providing building blocks for numerical algorithms.

#### Lessons for Joon

- **The Stuttgart work is Joon's closest academic relative.** DSL -> operator graph -> GPU shader compilation. The key difference: they target DX12 work graphs (recursive DAGs on GPU), Joon targets Vulkan compute (pre-scheduled command buffers). Work graphs are more flexible for recursive generation; Vulkan compute is more portable and better for image processing.
- **Noise function taxonomy.** The Lagae survey's categorization of noise functions should inform Joon's noise node library — Perlin, Simplex, Worley/Cellular, Gabor, wavelet, etc.
- **Genetic programming.** Future Joon feature: evolutionary exploration of parameter spaces, using the DSL as the genome representation.

#### Sources

- [50] [Survey of Procedural Methods for 2D Texture Generation](https://www.mdpi.com/1424-8220/20/4/1135) (Dong et al., 2020)
- [51] [A Survey of Procedural Noise Functions](https://www.cs.umd.edu/~zwicker/publications/SurveyProceduralNoise-CGF10.pdf) (Lagae et al., 2010)
- [52] [Procedural Generation via Operator Graphs using GPU Work Graphs](https://elib.uni-stuttgart.de/items/fc57c878-f927-4306-9a71-568436955807) (University of Stuttgart, 2024)
- [53] [Real-Time Procedural Generation with GPU Work Graphs — GPUOpen](https://gpuopen.com/download/publications/Real-Time_Procedural_Generation_with_GPU_Work_Graphs-GPUOpen_preprint.pdf)
- [54] [Realtime compositing of procedural facade textures on GPU](https://www.researchgate.net/publication/287046464_Realtime_compositing_of_procedural_facade_textures_on_the_GPU)
- [55] [Procedural 3D texture synthesis using genetic programming](https://www.sciencedirect.com/science/article/abs/pii/S0097849304000573)
- [56] [Interactive Methods for Procedural Texture Generation](https://www.diva-portal.org/smash/get/diva2:839579/FULLTEXT01.pdf)
- [57] [Linear Algebra Operators for GPU Implementation](https://dl.acm.org/doi/10.1145/882262.882363) (SIGGRAPH 2003)

---

### 2.5 Material Maker (Bonus — Open Source Substance Designer Alternative)

Material Maker is an open-source procedural texture authoring tool built on Godot Engine [58][59].

#### Architecture

- **~250 base nodes** for shapes, patterns, filters, transforms, and SDFs.
- **Shader fusion.** Most nodes are defined as GLSL shaders. When nodes connect, Material Maker generates **combined shaders** instead of rendering an image per node. The engine combines shaders until it reaches a buffer node or the target Material node — making textures resolution-independent until baked.
- **Two extension paths:** (1) Group existing nodes into compound nodes, (2) Write custom GLSL shaders.
- **Export:** Godot, Unity, Unreal materials.
- **Open source:** MIT license, built on Godot 4 [58].

#### Lessons for Joon

- **Shader fusion in practice.** Material Maker's shader fusion is the GPU analog of what Joon's compiled mode does. MM fuses GLSL fragments at the string level; Joon should fuse at the SPIR-V or GLSL level for Vulkan compute.
- **Resolution independence.** Because fused shaders evaluate lazily (only at the final resolution), intermediates never exist at any resolution. Joon's compiled mode achieves the same: fused nodes eliminate intermediate buffers.
- **Buffer nodes as fusion barriers.** MM's "buffer node" forces materialization of an intermediate. Joon needs the same concept — nodes that require full-resolution intermediates (blur, convolution) break fusion chains.

#### Sources

- [58] [Material Maker GitHub](https://github.com/RodZill4/material-maker)
- [59] [Material Maker Website](https://www.materialmaker.org/)
- [60] [Material Maker on Godot Showcase](https://godotengine.org/showcase/material-maker/)

---

## Part 3: Synthesis — Lessons for Joon

### 3.1 Text vs. Visual Authoring

| Tool | Primary Surface | Text Role |
|------|----------------|-----------|
| Werkkzeug | Visual (operator stacking) | None (parameters only) |
| Tooll3 | Visual (node graph) | HLSL for shader nodes |
| Cables.gl | Visual (patch graph) | JavaScript for op internals |
| Shadertoy | Text (GLSL) | Everything |
| Bonzomatic | Text (GLSL) | Everything |
| KodeLife | Text (multi-language) | Everything |
| vvvv | Visual (patch graph) | HLSL for FUSE nodes |
| TouchDesigner | Visual (operator network) | GLSL in Text DATs |
| Notch | Visual (node graph) | None (closed) |
| Material Maker | Visual (node graph) | GLSL for custom nodes |
| **Joon** | **Text (S-expression DSL)** | **Everything** |

Joon is unique: text-first with a visual inspector (GUI), not visual-first with text escape hatches. The closest precedents are Shadertoy (text-first, no graph) and Material Maker (visual-first, shader fusion).

### 3.2 GPU Execution Models

| Tool | GPU Model | Fusion |
|------|-----------|--------|
| Werkkzeug | CPU-side generation (legacy) | No |
| Tooll3 | DirectX 11 | No |
| Cables.gl | WebGL/WebGPU | Shader module composition |
| Shadertoy | OpenGL FBOs | Manual (per-buffer) |
| vvvv/FUSE | DirectX 11 (Stride) | Visual-to-shader compilation |
| TouchDesigner | OpenGL/DirectX | No (per-operator) |
| Notch | Proprietary GPU (NURA) | Internal |
| Material Maker | OpenGL (Godot) | **Shader fusion at string level** |
| FastNoise2 | CPU SIMD | **SIMD fusion** |
| **Joon** | **Vulkan compute** | **Shader fusion at compile time** |

Joon's compiled mode (node fusion into minimal dispatches) is most directly analogous to:
1. **Material Maker's shader fusion** — combining GLSL fragments into single shaders
2. **FastNoise2's SIMD fusion** — keeping intermediates in registers instead of memory
3. **The Stuttgart GPU work graphs paper** — DSL -> operator graph -> compiled GPU code

### 3.3 Key Architectural Patterns to Adopt

1. **Two-tier execution (interpreter + compiler).** Already in Joon's design. Validated by vvvv (always-runtime), KodeLife (background compilation), and the demoscene "edit live, export optimized" pattern.

2. **Fusion barriers.** Material Maker's "buffer nodes" that break shader fusion chains. In Joon: nodes requiring spatial access (blur, convolution) are natural fusion barriers. Element-wise chains between barriers can be fused.

3. **Operator definition via DSL.** Werkkzeug4's script-to-C++ generation for operators. Joon nodes should be definable in a lightweight format that generates both the GPU shader and the host-side binding.

4. **Typed operator families.** TouchDesigner's TOP/CHOP/SOP typing. Joon has image/mesh/voxel/float/vec — ensure the type system drives scheduling decisions (e.g., image nodes -> compute queue, mesh nodes -> graphics queue).

5. **Serialized graph format.** FastNoise2's compact string serialization. Joon's .jn files already serve this purpose, but consider a binary/compact format for compiled graphs.

6. **Temporal feedback via explicit state.** Shadertoy's buffer self-reference. Joon's `state` bindings. Both solve the same problem — making iterative algorithms (reaction-diffusion, fluid, cellular automata) possible in a declarative graph.

7. **Orthogonal operator set.** OpenKTG's design philosophy: each operator does one thing, operators compose freely. Resist the urge to create monolithic "uber-nodes."
