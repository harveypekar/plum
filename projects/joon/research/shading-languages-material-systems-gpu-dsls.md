# Shading Languages, Material Description Systems, and GPU Compute DSLs

**Date:** 2026-03-31
**Context:** Research for Joon -- a Lisp-style DSL that compiles to a Vulkan compute node graph for image processing.

---

## Part 1: Shading Languages

### 1.1 OSL (Open Shading Language)

#### Architecture

OSL was created at Sony Pictures Imageworks by Larry Gritz, first presented publicly in 2009 [1]. It is now an ASWF project. The language is purpose-built for production path tracers and differs fundamentally from GLSL/HLSL in that shaders do not perform lighting calculations -- they return symbolic closures describing surface scattering behavior, which the renderer's integrator evaluates later.

The compilation pipeline has three stages [2][3]:

1. **oslc** (offline compiler): Parses OSL source into `.oso` bytecode files -- a human-readable assembly-like intermediate representation. This is a standalone compiler producing serialized shader IR.
2. **Shader Group Assembly**: At render time, the renderer connects multiple `.oso` shaders into a shader group (DAG). Named outputs of one shader connect to named inputs of another. Connections are established dynamically and do not affect individual shader compilation [1].
3. **LLVM JIT**: The `BackendLLVM` class in `liboslexec` translates the assembled shader group (not individual shaders) into LLVM IR, applying whole-network optimizations: constant folding across connected shaders, dead code elimination across the group, and parameter specialization with runtime values baked in. LLVM then JIT-compiles to native x86/ARM machine code [2][3].

The critical insight is that OSL optimizes the *assembled group*, not individual shaders. When a shader's parameter is connected to another shader's output that happens to be constant after folding, OSL can propagate that constant through and eliminate entire branches across shader boundaries. This is why OSL reports 25% faster execution than hand-written C equivalents [1].

#### Type System

OSL's types reflect its rendering domain [4][5]:

- **Scalars**: `int`, `float`
- **Triples**: `color` (spectral), `point` (position), `vector` (direction), `normal` (shading normal) -- all three-component, but semantically distinct for transformation behavior
- **Matrix**: `matrix` (4x4 homogeneous transformation)
- **String**: `string` (for texture names, coordinate systems)
- **Arrays**: fixed-size arrays of any type
- **Structs**: user-defined aggregate types
- **Closure color**: the key innovation -- `closure color` is an opaque symbolic type representing a BSDF/BSSRDF. You cannot examine its numeric values during shader execution; you can only form linear combinations of closures [4]

The closure model means a surface shader returns something like `Ks * microfacet("ggx", N, roughness) + Kd * diffuse(N)` -- a weighted sum of named BSDFs with captured parameters. The integrator receives this closure tree and can evaluate it for any given incoming/outgoing light direction, reorder sampling, batch ray generation for coherence, or use it for bidirectional methods [1].

#### Execution Model

Shaders evaluate lazily: a node in the shader group only executes when a downstream node pulls its output. This means unused branches of the network are never computed. Execution is batched in SIMD fashion -- many shading points simultaneously [1].

OSL has no light loops, no ray-tracing calls in surface shaders, and no access to other parts of the scene. This is a deliberate constraint: by keeping shaders pure functions that produce closures, the renderer maintains full control over integration strategy [1].

#### Relevance to Joon

OSL's shader group model is directly analogous to Joon's node graph: both are DAGs of connected computation nodes, both are JIT-compiled as a whole (not individually), and both separate the description of computation from its scheduling/execution. The difference is that OSL is domain-specific to surface shading with closures, while Joon targets general image processing with Vulkan compute. OSL's whole-network optimization (constant folding and dead code elimination across node boundaries) is exactly the optimization strategy Joon's compiled mode should pursue.

**Source code**: [github.com/AcademySoftwareFoundation/OpenShadingLanguage](https://github.com/AcademySoftwareFoundation/OpenShadingLanguage)

---

### 1.2 MaterialX

#### Architecture

MaterialX is an open standard (ASWF) for exchanging material and look-development content across applications and renderers. Unlike OSL (which is a programming language), MaterialX is a **declarative node graph schema** -- an XML/JSON document format that describes how nodes connect, with no imperative control flow [6][7].

The shader generation framework (`MaterialXGenShader`) transforms MaterialX node graphs into executable shader source code. It produces **source code, not binary** -- a downstream language compiler (GLSL, HLSL, etc.) handles final compilation [7].

#### Node Graph Schema

MaterialX nodes are typed operations with inputs and outputs. The specification defines hundreds of standard nodes across categories: math operations, texture sampling, procedural patterns, PBR shading models, and compositing operations. Nodes connect via typed ports. The graph is a DAG [6].

Node implementations come in four forms [7]:

1. **Inline expressions**: Simple one-liners with `{{input}}` template syntax -- the generator substitutes variable names directly, avoiding function-call overhead
2. **Source-language functions**: Complete function implementations in the target language (a GLSL implementation of `noise`, for example)
3. **Compound node graphs**: A node's implementation is itself a MaterialX graph -- recursive composition
4. **Dynamic C++ code generators**: `ShaderNodeImpl` subclasses that emit target-specific code programmatically at generation time

#### Code Generation Pipeline

The `ShaderGenerator` class hierarchy has backends for GLSL, OSL, MDL, and MSL [7]. The pipeline:

1. **Graph optimization**: Starting from the output element, prune unreachable nodes, constant-fold where possible, insert default values for unconnected ports
2. **Topological sort**: Order nodes so dependencies resolve before dependents
3. **Variable naming**: Generate scoped variable names following target-language conventions
4. **Code emission**: Walk the sorted graph and emit shader statements per node, using whichever implementation form is available

The output is a single monolithic shader function per output element. The generator inlines everything into one function rather than preserving the node graph structure at the shader level [7].

#### USD Integration

MaterialX integrates with OpenUSD via `UsdShade`. A MaterialX document can be represented either as standalone XML (`.mtlx` files) or as a `UsdShade` node graph within a USD stage. The Alliance for OpenUSD Materials Working Group is standardizing MaterialX's standard library within UsdShade [8].

MaterialX 1.39+ includes the **OpenPBR Surface** shading model as a replacement for the older Standard Surface, with shader translation graphs between the two. OpenPBR is co-developed by ASWF and supported in Maya 2025.3+, 3ds Max 2026+, and Houdini [8].

#### Relevance to Joon

MaterialX validates the "declarative graph of typed nodes" approach but takes the opposite compilation strategy from Joon: MaterialX generates text source code for a downstream compiler, while Joon compiles directly to Vulkan compute dispatches. MaterialX's four-tier node implementation strategy (inline, function, subgraph, dynamic codegen) is worth studying -- Joon could adopt a similar pattern where simple nodes are inline GLSL in compute shaders, complex nodes are precompiled shader programs, and compound nodes are subgraphs.

**Specification**: [materialx.org](https://materialx.org/)
**Source code**: [github.com/AcademySoftwareFoundation/MaterialX](https://github.com/AcademySoftwareFoundation/MaterialX)
**Shader generation docs**: [MaterialX ShaderGeneration.md](https://github.com/AcademySoftwareFoundation/MaterialX/blob/main/documents/DeveloperGuide/ShaderGeneration.md)

---

### 1.3 MDL (Material Definition Language)

#### Architecture

MDL is NVIDIA's language for defining physically-based materials. Unlike OSL (which is for renderers to execute) or MaterialX (which is an interchange format), MDL is a **compilable material language** with an SDK that generates executable code for multiple backends: PTX (CUDA), HLSL, GLSL, native x86 (via LLVM), and LLVM IR [9][10].

MDL materials describe light interaction at a high level using **distribution functions** (BSDFs, EDFs, VDFs). A material is built by composing these distribution functions with layering combinators. The MDL compiler resolves the composition into concrete evaluation code [9][10].

#### Compilation Model

The MDL SDK compilation pipeline [10][11]:

1. **Module loading**: MDL source files (`.mdl`) are parsed and loaded as modules
2. **Material compilation**: A material instance is compiled into a "compiled material" -- an optimized DAG where call expressions are inlined, constants are folded, and common subexpressions are eliminated
3. **Target code generation**: The compiled material is fed to a backend (PTX, HLSL, GLSL, native) which generates callable functions for: material evaluation, BSDF sampling, BSDF evaluation (pdf), BSDF auxiliary data, and emission distribution functions

The SDK provides a GLSL backend example that generates Vulkan compute shader code for a path tracer [11]. This is directly relevant to Joon's architecture: MDL demonstrates that a high-level material language can be compiled to Vulkan compute dispatches.

#### Layered Material Model

MDL's material model is based on composing distribution functions [9]:

- `diffuse_reflection_bsdf`, `specular_bsdf`, `microfacet_*` -- elementary BSDFs
- `weighted_layer`, `fresnel_layer`, `custom_curve_layer` -- vertical layering (coatings over substrates)
- `normalized_mix`, `clamped_mix` -- horizontal mixing by weight
- `measured_bsdf` -- data-driven from measurement

Materials are structs with fields for surface BSDF, emission, volume, geometry (displacement, cutout), and thin-walled behavior. This is a fixed material model (not a general computation graph) with a rich vocabulary of physically-based primitives [9].

#### GPU Design Constraints

MDL is explicitly designed for GPU execution: no dynamic memory allocation, no recursion, no data-dependent control flow that would cause divergence, side-effect-free functions. These constraints mirror what Joon's GPU nodes must obey [9].

#### Relevance to Joon

MDL's compilation pipeline (high-level description -> DAG optimization -> backend code generation to GLSL/SPIR-V) is architecturally similar to Joon's planned compiled mode. MDL proves that compiling a declarative description to Vulkan compute is viable, and the SDK's GLSL/Vulkan example is worth studying. The key difference is scope: MDL is domain-specific to physically-based materials, while Joon targets general image/compute operations.

**SDK**: [github.com/NVIDIA/MDL-SDK](https://github.com/NVIDIA/MDL-SDK)
**Technical intro**: [raytracing-docs.nvidia.com/mdl/introduction](https://raytracing-docs.nvidia.com/mdl/introduction/index.html)
**Vulkan/GLSL example**: [MDL compiled distribution functions (GLSL)](https://raytracing-docs.nvidia.com/mdl/api/mi_neuray_example_df_vulkan.html)
**GTC 2019 presentation**: [Integrating MDL in your application (PDF)](https://developer.download.nvidia.com/video/gputechconf/gtc/2019/presentation/s9177-integrating-the-nvidia-material-definition-language-mdl-in-your-application.pdf)

---

### 1.4 RSL (RenderMan Shading Language)

#### Historical Significance

RSL was designed by Pat Hanrahan and Jim Lawson at Pixar in 1987-1988, shipping with RenderMan 3.0 in May 1988. It was the first production shading language and powered the rendering of Tin Toy (1988) and Toy Story (1995) [12][13].

RSL introduced the paradigm that persisted for two decades:

- **C-like syntax** with domain-specific types (`point`, `vector`, `normal`, `color`, `matrix`)
- **Shader types** corresponding to rendering pipeline stages: `surface`, `light`, `displacement`, `volume`, `imager`
- **Built-in global variables** providing rendering context (`P`, `N`, `Cs`, `Os`, `I`, `u`, `v`)
- **Light loops** where surface shaders explicitly iterate over lights via `illuminance()` construct
- **Coordinate system transforms** as first-class operations (`transform("world", "camera", P)`)

#### Execution Model

RSL shaders ran on the REYES (Renders Everything You Ever Saw) architecture: geometry is diced into micropolygons, shaders execute per-micropolygon-vertex in SIMD batches. The renderer controlled the execution grid, and shaders had no access to global scene state beyond their local variables and the provided rendering context [12][13].

#### Influence and Deprecation

RSL directly influenced [12][13]:

- **GLSL/HLSL**: C-like syntax, built-in vector/matrix types, shader stages as distinct programs
- **Houdini VEX**: closely modeled after RSL with the same type vocabulary
- **Gelato Shading Language** (NVIDIA): nearly identical to RSL with syntactic variations
- **OSL**: inherited RSL's type vocabulary (`point`, `vector`, `normal`, `color`) but replaced the imperative light-loop model with declarative closures

RSL was deprecated in RenderMan 21 (2016) in favor of OSL integration. The light-loop model was replaced by the closure-based approach that gives the integrator full control over sampling [12].

#### Relevance to Joon

RSL's legacy is visible in every modern shading language's type system. Its separation of shader types by pipeline stage foreshadowed the modern approach of separating computation stages -- Joon's distinction between GPU nodes and CPU nodes serves a similar architectural purpose, defining what executes where.

**Historical reference**: [renderman.pixar.com/resources/RenderMan_20/shadingLanguage.html](https://renderman.pixar.com/resources/RenderMan_20/shadingLanguage.html)
**Wikipedia**: [RenderMan Shading Language](https://en.wikipedia.org/wiki/RenderMan_Shading_Language)

---

### 1.5 Slang

#### Architecture

Slang is a shader language developed at Carnegie Mellon and NVIDIA, now hosted by the Khronos Group. It extends HLSL with modern language features -- generics, interfaces, modules, automatic differentiation -- and compiles to SPIR-V, DXIL, HLSL, GLSL, WGSL, Metal, CUDA, and C++ [14][15].

#### Compilation Pipeline

The compiler follows a traditional pipeline with notable additions [16][17]:

1. **Parsing and semantic analysis**: Slang source is parsed into ASTs. The type checker validates generics, interface conformance, and differentiability annotations
2. **IR lowering**: ASTs are lowered to Slang IR -- an SSA-form intermediate representation at roughly the same abstraction level as SPIR-V/DXIL. This step bakes out syntactic sugar: member functions become free functions with `this` parameters, nested structs are flattened, compound expressions become instruction sequences, control flow becomes CFG basic blocks [17]
3. **Specialization and optimization**: Generic types are specialized, interfaces are resolved, link-time specialization fuses modules, dead code and unused features are eliminated
4. **Target lowering**: IR is transformed into target-legal form (e.g., SPIR-V has different struct layout rules than DXIL)
5. **Code emission**: Final output in the target format. SPIR-V is generated directly via `SPIRVEmitContext` using an intermediate `SpvInst` structure. High-level targets (HLSL, GLSL, WGSL) produce source text [16][17]

#### Type System: Generics and Interfaces

Slang's generics are fully pre-checked, unlike C++ templates. An interface defines a set of requirements (methods and associated types), and generic functions constrain type parameters by interface conformance [14][15]:

```
interface IFoo { float compute(float x); }
struct MyImpl : IFoo { float compute(float x) { return x * x; } }
float process<T : IFoo>(T obj, float x) { return obj.compute(x); }
```

At compile time, generics are either specialized (monomorphized for known types) or compiled using dynamic dispatch via witness tables (similar to vtables). The choice depends on the target and optimization level [14].

#### Automatic Differentiation

The SLANG.D paper (SIGGRAPH Asia 2023, Bangaru et al.) formalized Slang's autodiff system [18]:

- A **differentiable type system** where `[Differentiable]` annotations mark types and functions
- The compiler generates both forward-mode (`fwd_diff`) and reverse-mode (`bwd_diff`) derivative propagation code
- Supports arbitrary control flow, dynamic dispatch, generics, and higher-order differentiation
- Developer-controlled checkpointing and gradient aggregation for performance tuning
- Derivative kernels perform as efficiently as hand-written equivalents

This is the first production shading language with built-in automatic differentiation, enabling differentiable rendering for inverse problems and neural material optimization [18].

#### Relevance to Joon

Slang demonstrates that a modern, typed shader language can compile to SPIR-V (Joon's target) while supporting high-level features. Its IR design -- SSA form at SPIR-V abstraction level -- is directly relevant to Joon's compiled mode, where fused node graphs must be lowered to SPIR-V compute shaders. Slang's module system (separate compilation, link-time specialization) offers a model for how Joon's `(use "file.jn")` imports could work.

**Source code**: [github.com/shader-slang/slang](https://github.com/shader-slang/slang)
**User guide**: [shader-slang.org](http://shader-slang.org/)
**IR design**: [shader-slang.org/slang/design/ir.html](http://shader-slang.org/slang/design/ir.html)
**Compiler overview**: [shader-slang.org/slang/design/overview.html](http://shader-slang.org/slang/design/overview.html)
**SLANG.D paper**: [Bangaru et al., ACM TOG 2023](https://dl.acm.org/doi/10.1145/3618353)
**Yong He's thesis**: [Slang -- A Shader Compilation System (CMU, PDF)](http://graphics.cs.cmu.edu/projects/renderergenerator/yong_he_thesis.pdf)

---

### 1.6 WGSL (WebGPU Shading Language)

#### Design Decisions

WGSL is the shading language for WebGPU, developed by the W3C GPU for the Web working group. Its design is driven by browser security constraints, which led to several distinctive choices [19][20]:

- **No preprocessor**: Unlike GLSL/HLSL, WGSL has no `#define`, `#include`, or conditional compilation. All code is plain text -- the browser must be able to fully validate any shader without external state
- **No undefined behavior**: Every valid WGSL program has fully defined semantics. Out-of-bounds array access returns zero rather than causing UB. Integer overflow wraps. This eliminates a class of GPU security exploits
- **Explicit address spaces**: Variables must declare their address space (`uniform`, `storage`, `private`, `workgroup`, `function`). No implicit defaults
- **Rust-influenced syntax**: `fn`, `let`, `var`, explicit type annotations, `->` for return types. Vector types are `vec4<f32>` rather than `vec4` -- fully explicit generic-style parameterization [19][20]
- **Minimal implicit conversions**: No implicit `int` to `float`. Almost everything is explicit

#### Compilation Strategy

WGSL is designed as a "hub" language that can be mechanically translated to each platform's native format [19][20]:

- Vulkan: WGSL -> SPIR-V (via Tint compiler in Chrome, or Naga in Firefox)
- Direct3D 12: WGSL -> HLSL -> DXIL (via DXC)
- Metal: WGSL -> MSL (via Tint or Naga)
- OpenGL (fallback): WGSL -> GLSL

The Tint compiler (Google, used in Dawn/Chrome) and Naga compiler (Mozilla, used in wgpu/Firefox) are the two production WGSL compilers. Both perform full validation and can reject shaders before they reach the GPU driver, adding a security layer that GLSL/HLSL never had [20].

#### Differences from GLSL/HLSL

Key structural differences [19][20]:

- WGSL uses `@binding(0) @group(0)` attributes instead of GLSL's `layout(binding = 0, set = 0)`
- Texture and sampler types are separate and explicitly typed (`texture_2d<f32>`, `sampler`)
- Compute shader entry points use `@compute @workgroup_size(8, 8)` annotations
- Structures use explicit `@location` annotations for all inter-stage data
- No global mutable state outside of declared resource bindings

#### Relevance to Joon

WGSL's emphasis on safety, determinism, and explicit resource binding aligns with Joon's design philosophy of explicit typing and validation at graph compile time. However, WGSL's verbosity and lack of a preprocessor make it unsuitable as a target language for Joon's shader generation -- SPIR-V is a better target since it avoids text-level concerns entirely.

**Specification**: [w3.org/TR/WGSL/](https://www.w3.org/TR/WGSL/)
**Tint compiler**: Part of Dawn -- [dawn.googlesource.com](https://dawn.googlesource.com/dawn)
**Naga compiler**: Part of wgpu -- [github.com/gfx-rs/wgpu](https://github.com/gfx-rs/wgpu)

---

## Part 2: Node-Based Material/Compositing Systems

### 2.1 Substance Designer

#### Architecture

Substance Designer (Adobe, formerly Allegorithmic) is the industry-standard procedural texture authoring tool. Its architecture has two distinct graph types operating at different abstraction levels [21][22][23]:

**Compositing Graph** (top level): A DAG of image-processing nodes -- blurs, blends, noises, color adjustments, and custom pixel processors. Each node processes entire texture maps. This is the main authoring surface. Nodes connect via image outputs (greyscale or color) plus parameter connections.

**Function Graph** (per-pixel level): A separate visual programming environment used inside Pixel Processor and Value Processor nodes. Function graphs define per-pixel mathematical operations -- they receive pixel coordinates, sample inputs, and return a single value. Function graphs compose mathematical operations (arithmetic, trig, conditionals, sampling) in a visual DAG [22].

This two-tier architecture means the compositing graph defines the coarse image-processing pipeline, while function graphs define the fine-grained per-pixel kernel code. The Pixel Processor node executes its function graph **in parallel for every pixel**, with each pixel unaware of its neighbors' results -- a natural fit for GPU compute dispatch [21].

#### .SBS Format

SBS files are XML documents. The XML stores the complete graph structure: nodes, connections between ports, parameter values, and references to embedded or linked resources (bitmaps, other SBS files). The format is human-readable and scriptable via `pysbs` (Python API in the Substance Automation Toolkit) [23].

SBSAR files are compiled, read-only versions. The Substance Engine (embedded in game engines, renderers) consumes SBSAR files at runtime and evaluates the graph on GPU or CPU [23][24].

#### GPU Execution

The Substance Engine uses Direct3D 11 as its primary GPU backend. GPU execution computes up to 4K resolution; the CPU engine (SSE2) is limited to 2K. GPU engines (DX9, DX10, OpenGL variants) are faster than CPU but have different precision characteristics -- GPU supports all 8/16-bit greyscale/color combinations while CPU SSE2 lacks 16-bit color and 8-bit greyscale support [24].

Atomic nodes (the primitive building blocks) are implemented directly in the engine's native code -- they are not graph instances but compiled operations. All higher-level nodes in the library are composed from atomic nodes [21].

#### Relevance to Joon

Substance Designer's two-tier graph architecture (coarse image graph + fine per-pixel function graph) maps closely to Joon's design: the compositing graph is analogous to Joon's top-level node graph (each `def` creates a node processing entire images), while the Pixel Processor's function graph is analogous to what happens inside a Joon GPU node's compute shader. The distinction between "atomic nodes" (engine-native) and "library nodes" (composed from atomics) is similar to Joon's distinction between built-in nodes and composed subgraphs via `(use)`.

**Adobe docs**: [helpx.adobe.com/substance-3d-designer](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/atomic-nodes/pixel-processor.html)
**Function graph reference**: [helpx.adobe.com/substance-3d-designer/function-graphs](https://helpx.adobe.com/substance-3d-designer/function-graphs/the-function-graph.html)
**sd-sex (code-to-function-graph)**: [github.com/igor-elovikov/sd-sex](https://github.com/igor-elovikov/sd-sex)

---

### 2.2 Nuke (Foundry)

#### Architecture

Nuke is the industry-standard compositing tool for film VFX, built around a node-graph paradigm with over 200 built-in nodes. Its core technical distinctions [25][26]:

**Multi-channel pipeline**: Nuke operates on images with over 1,000 user-definable 32-bit floating-point channels. This is not RGBA -- it is an arbitrary-channel system where layers like `depth.Z`, `motion.u`, `motion.v`, `crypto_material.00` coexist in a single image stream. Nodes operate on channel sets, and the channel namespace is hierarchical [26].

**Resolution independence**: All operations are resolution-independent. Images carry their own format (resolution + pixel aspect ratio), and nodes resample as needed. The graph evaluates at whatever resolution the viewer requests -- you can work at proxy resolution and render at full [26].

**Deep compositing**: Nuke supports deep images -- images where each pixel stores multiple samples at different depths, with per-sample opacity and color. Deep merge operations composite CG elements correctly by depth without requiring holdout mattes or re-rendering. This is critical for VFX workflows where CG objects interpenetrate [25].

#### BlinkScript / GPU Execution

Nuke's GPU acceleration uses the **Blink framework** -- a C-like kernel language that compiles to both OpenCL (GPU) and C++/SIMD (CPU) from the same source code. BlinkScript nodes expose this to artists [27]:

```cpp
kernel MyKernel : ImageComputationKernel<ePixelWise> {
  Image<eRead, eAccessPoint> src;
  Image<eWrite> dst;
  param: float gain;
  void process() {
    dst() = src() * gain;
  }
};
```

The kernel type `ePixelWise` means the `process()` function runs once per pixel. Other kernel types include `eComponentWise` (once per channel per pixel). Access patterns (`eAccessPoint`, `eAccessRanged2D`) tell the runtime what memory access the kernel needs, enabling the framework to manage GPU memory and tiling [27].

Built-in GPU-accelerated nodes (Motion Blur, Kronos optical flow, Denoise, ZDefocus) use the same Blink framework internally [25].

#### Relevance to Joon

Nuke's BlinkScript kernel model -- write once, run on GPU or CPU with declared access patterns -- is a simpler version of what Joon's node system does: each node defines a compute kernel with typed inputs/outputs, and the runtime schedules execution. Nuke's approach of declaring memory access patterns (point vs. neighborhood) to enable tiling is worth studying for Joon's future spatial-filter nodes (blur, etc.).

**BlinkScript docs**: [learn.foundry.com/nuke/content/reference_guide/other_nodes/blinkscript.html](https://learn.foundry.com/nuke/content/reference_guide/other_nodes/blinkscript.html)
**Blink guide**: [learn.foundry.com/nuke/developers/15.1/BlinkUserGuide/QuickStart.html](https://learn.foundry.com/nuke/developers/15.1/BlinkUserGuide/QuickStart.html)
**Deep compositing**: [learn.foundry.com/nuke/content/comp_environment/deep/deep_compositing.html](https://learn.foundry.com/nuke/content/comp_environment/deep/deep_compositing.html)

---

### 2.3 DaVinci Resolve Fusion

#### Architecture

Fusion (originally eyeon Fusion, acquired by Blackmagic Design in 2014) is a node-based compositing system integrated into DaVinci Resolve. It provides hundreds of 2D and 3D tools connected via a flow-graph [28].

The execution model is request-driven: the viewer (or render output) requests a frame, and the graph evaluates backward from the request, computing only the nodes needed for the current output. Each node processes a tile or full frame depending on the operation [28].

#### GPU Acceleration

Blackmagic has been incrementally rewriting Fusion nodes for GPU acceleration -- as of Resolve 18+, many core operations (noise reduction, sharpening, lens blur, temporal effects, beauty tools) are GPU-accelerated. The architecture uses Metal on macOS, CUDA on NVIDIA, and OpenCL as a fallback. GPU-accelerated nodes operate on GPU memory directly, avoiding CPU round-trips for adjacent GPU nodes [28][29].

Unlike Nuke's BlinkScript, Fusion does not expose a user-programmable GPU kernel language. Custom nodes (Fuses) are written in Lua and execute on the CPU [28].

#### Relevance to Joon

Fusion's request-driven (pull) evaluation model is worth noting -- Joon currently uses push evaluation (starting from inputs, flowing to outputs). Pull evaluation naturally implements lazy evaluation and handles partial graph updates (only re-evaluate what changed upstream of the requested output). Joon's caching-based approach achieves a similar effect, but the conceptual model differs.

**Fusion features**: [blackmagicdesign.com/products/davinciresolve/fusion](https://www.blackmagicdesign.com/products/davinciresolve/fusion)

---

### 2.4 Natron

#### Architecture

Natron is an open-source (GPLv2) node-based compositor, similar to Nuke in workflow. The key architectural decision is building on the **OpenFX** plugin standard (OFX), supporting nearly all features of OpenFX v1.4 [30].

**OpenFX (OFX)** is a C API standard for image processing plugins. An OFX plugin declares its inputs, outputs, parameters, and supported pixel formats. The host (Natron) provides the execution environment: memory management, threading, GUI for parameters. Plugins operate on "clips" (image sequences) via a pull-based model where the plugin requests regions of interest from its inputs [30].

Natron's internal pipeline uses 32-bit floating-point linear color processing with OpenColorIO for color management, and supports image I/O via OpenImageIO and FFmpeg [30].

Community extensions ("PyPlugs") are node groups implemented as Python scripts -- Natron's equivalent of Nuke gizmos [30].

#### Relevance to Joon

Natron/OpenFX demonstrates the value of a well-defined plugin API with declared capabilities (supported formats, threading model, region of interest). Joon's node registry (`NodeRegistry`) serves a similar purpose -- each node type declares its inputs, outputs, and behavior. The OFX model of declared region-of-interest (ROI) is particularly relevant: knowing that a blur node needs NxN pixels around each output pixel enables the host to manage tiling and memory.

**Source code**: [github.com/NatronGitHub/Natron](https://github.com/NatronGitHub/Natron)
**OpenFX standard**: [openfx.readthedocs.io](https://openfx.readthedocs.io/)

---

### 2.5 ComfyUI

#### Architecture

ComfyUI is a node-graph interface for diffusion model inference (Stable Diffusion, Flux, etc.). Built in Python with PyTorch, it represents generation pipelines as DAGs where nodes handle model loading, conditioning, sampling, VAE encoding/decoding, and post-processing [31][32].

#### Execution Engine

The execution model was overhauled in PR #2666, inverting from back-to-front recursive evaluation to front-to-back topological sort [32]:

1. The user submits a workflow (JSON "prompt") describing nodes and connections
2. `ExecutionList` (extending `TopologicalSort`) orders nodes, with staging support
3. Nodes execute in order, with results cached per content-based cache key
4. **Lazy evaluation**: nodes can mark inputs as `lazy=True` -- the input is only evaluated on-demand if the node requests it during execution. This enables conditional branches (e.g., a switch node only evaluates the selected branch) [32]

**Caching strategies** [32]:
- **Classic**: aggressively clears cache entries after use
- **LRU**: keeps recently-used results with a memory budget
- **Dependency-aware**: tracks node dependency chains and only invalidates when upstream dependencies change

**Memory management**: Automatic model offloading between GPU VRAM and CPU RAM. Unused models move to CPU; active models load to GPU. This enables workflows with 5-10+ large models on 12GB VRAM GPUs [31].

#### Relevance to Joon

ComfyUI's execution model (topological sort with lazy evaluation and content-based caching) is remarkably similar to Joon's planned execution model. The caching-by-input-hash approach directly parallels Joon's "skip nodes whose inputs haven't changed" strategy. ComfyUI's lazy evaluation (only evaluate inputs when requested by the node) is more flexible than Joon's current caching approach -- Joon could benefit from allowing nodes to declare inputs as conditionally required.

**Source code**: [github.com/comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)
**Execution model docs**: [docs.comfy.org/development/comfyui-server/execution_model_inversion_guide](https://docs.comfy.org/development/comfyui-server/execution_model_inversion_guide)

---

## Part 3: GPU Compute DSLs and Functional Image Systems

### 3.1 Halide

#### Architecture

Halide was created by Jonathan Ragan-Kelley, Andrew Adams, et al. at MIT CSAIL and is the foundational work in separating algorithm from schedule in image processing pipelines. The key paper is "Halide: A Language and Compiler for Optimizing Parallelism, Locality, and Recomputation in Image Processing Pipelines" (PLDI 2013) [33][34].

The core insight: in stencil computation pipelines (where each stage reads a neighborhood of the previous stage's output), there is a fundamental three-way tradeoff between parallelism, locality, and redundant computation. The optimal strategy depends on the hardware, data sizes, and pipeline structure. Rather than forcing the programmer to bake this choice into the algorithm, Halide separates it [33][34]:

**Algorithm**: What is computed. Expressed as pure functions over integer coordinates:
```
Func blur_x, blur_y;
blur_x(x, y) = (input(x-1, y) + input(x, y) + input(x+1, y)) / 3;
blur_y(x, y) = (blur_x(x, y-1) + blur_x(x, y) + blur_x(x, y+1)) / 3;
```

**Schedule**: How and where it is computed. A set of directives that transform loop nests:
- `compute_root()` -- compute the entire function before any consumer reads it (maximizes locality, wastes memory)
- `compute_at(consumer, var)` -- compute just enough of this function inside the consumer's loop at the given level (fine-grained interleaving)
- `store_at(consumer, var)` -- allocate storage at a given loop level (controls memory lifetime)
- `vectorize(var, width)`, `parallel(var)`, `unroll(var, factor)` -- standard loop transformations
- `tile(x, y, xo, yo, xi, yi, tx, ty)` -- 2D tiling for cache locality
- `gpu_blocks(var)`, `gpu_threads(var)` -- map loop dimensions to GPU execution hierarchy [33][34][35]

#### GPU Compilation

For GPU targets (CUDA, OpenCL, Metal, Vulkan, Direct3D 12), the schedule maps loop variables to the GPU execution hierarchy [35]:

```
blur.gpu_tile(x, y, xi, yi, 16, 16);  // 16x16 thread blocks
```

This maps the outer loop iterations to GPU blocks and inner iterations to GPU threads. The Halide compiler then:

1. Lowers the scheduled pipeline into a loop-nest IR
2. Identifies GPU-mapped loops and extracts them into device kernels
3. Generates host code that allocates device memory, copies data, launches kernels, and synchronizes
4. Generates device code (CUDA PTX, OpenCL, SPIR-V, MSL, or HLSL) for the extracted kernels

Halide supports heterogeneous CPU+GPU execution where some pipeline stages run on CPU and others on GPU, with automatic data transfer between devices [35].

#### Autoscheduling

Because schedules are separate from algorithms, Halide supports automatic schedule search. The autoscheduler (Adams et al., SIGGRAPH 2019) uses beam search with a learned cost model to find high-performance schedules automatically [36].

#### Relevance to Joon

Halide's algorithm/schedule separation is **the most directly relevant concept** for Joon's compiled mode. Joon's DSL describes the algorithm (what nodes compute), and the compiler's optimizer/scheduler determines the execution strategy (how to fuse nodes, where to place barriers, how to tile). Joon's two execution modes (interpreter = compute_root everything; compiled = optimized schedule) mirror Halide's `compute_root` vs. `compute_at` distinction.

However, Joon operates at a coarser granularity than Halide: Joon nodes process whole images via GPU dispatches, while Halide schedules individual pixel computations within a fused kernel. Joon's node fusion (merging adjacent element-wise operations into a single dispatch) is a simplified version of Halide's `compute_at` -- it fuses nodes into one shader rather than scheduling them at a specific loop level.

**PLDI 2013 paper**: [people.csail.mit.edu/jrk/halide-pldi13.pdf](https://people.csail.mit.edu/jrk/halide-pldi13.pdf)
**CACM 2018 paper**: [andrew.adams.pub/halide_cacm.pdf](https://andrew.adams.pub/halide_cacm.pdf)
**Decoupling paper (2012)**: [people.csail.mit.edu/jrk/halide12/halide12.pdf](https://people.csail.mit.edu/jrk/halide12/halide12.pdf)
**GPU tutorial**: [halide-lang.org/tutorials/tutorial_lesson_12_using_the_gpu.html](https://halide-lang.org/tutorials/tutorial_lesson_12_using_the_gpu.html)
**Autoscheduling**: [graphics.cs.cmu.edu/projects/halidesched/](http://graphics.cs.cmu.edu/projects/halidesched/)
**Source code**: [github.com/halide/Halide](https://github.com/halide/Halide)

---

### 3.2 Futhark

#### Architecture

Futhark is a purely functional, data-parallel array language designed at DIKU (University of Copenhagen) by Troels Henriksen et al. It targets GPU execution via CUDA, OpenCL, or HIP backends, and multicore CPU via pthreads [37][38].

The language is ML-family with Hindley-Milner type inference, first-class functions (with restrictions for GPU compilation), and a **uniqueness type system** for in-place array updates that preserves referential transparency [37][38].

#### Core Parallel Primitives (SOACs)

Futhark programs are expressed using Second-Order Array Combinators [37]:

- `map f xs` -- apply f to each element (parallel)
- `reduce op ne xs` -- fold with associative operator and neutral element (parallel via tree reduction)
- `scan op ne xs` -- inclusive prefix sum (parallel)
- `scatter dest is vs` -- indexed write (parallel, handles conflicts by last-write-wins)
- `reduce_by_index dest f ne is vs` -- generalized histogram / segmented reduction

Nested parallelism is supported: `map (\row -> reduce (+) 0 row) matrix` expresses a parallel reduction of each row, with both levels of parallelism exploited.

#### Compilation Pipeline

The compiler performs aggressive transformations [38][39]:

1. **Defunctionalization and monomorphization**: Higher-order functions and polymorphism are eliminated
2. **Fusion**: Adjacent `map`s are fused into a single kernel. A `map` feeding a `reduce` can be fused. The compiler uses algebraic fusion rules based on the properties of SOACs
3. **Moderate flattening**: Nested parallelism is handled by a heuristic algorithm that attempts to exploit outer parallelism while sequentializing inner parallelism that would be expensive to flatten. This avoids the pathological blowup of full flattening while still exploiting parallelism across multiple levels [39]
4. **Kernel extraction**: After flattening and fusion, the compiler identifies GPU kernels -- each kernel is a fused sequence of parallel operations
5. **Memory management**: The compiler determines buffer lifetimes and inserts allocations/frees. GPU memory is managed explicitly
6. **Code generation**: Final emission to CUDA, OpenCL, or HIP. Each extracted kernel becomes a GPU kernel launch

#### FFI and Integration

Futhark compiles to a C library with a generated header. You call Futhark functions from C, Python, Rust, or Haskell via the FFI. The intended use case is that Futhark handles compute-intensive parallel kernels while the host language handles I/O, UI, and orchestration [37].

#### Relevance to Joon

Futhark's approach -- a purely functional language that compiles to GPU kernels via aggressive fusion -- validates Joon's approach of compiling a functional DSL to GPU compute. The key lesson is the fusion strategy: Futhark's algebraic fusion rules (two adjacent maps always fuse; map-reduce fuses into a single kernel) directly apply to Joon's node fusion optimization. Joon's "adjacent element-wise operations merged into a single GPU dispatch" is essentially Futhark's map-map fusion.

Futhark's uniqueness type system for in-place updates is also interesting for Joon's `state` bindings -- it provides a way to have mutable state in a pure language with compile-time safety guarantees.

**PLDI 2017 paper**: [futhark-lang.org/publications/pldi17.pdf](https://futhark-lang.org/publications/pldi17.pdf)
**Website**: [futhark-lang.org](https://futhark-lang.org/)
**Source code**: [github.com/diku-dk/futhark](https://github.com/diku-dk/futhark)
**Incremental flattening**: [futhark-lang.org/blog/2019-02-18-futhark-at-ppopp.html](https://futhark-lang.org/blog/2019-02-18-futhark-at-ppopp.html)

---

### 3.3 Taichi

#### Architecture

Taichi is a Python-embedded DSL for parallel programming, created by Yuanming Hu at MIT CSAIL. It uses JIT compilation to transform Python functions into GPU/CPU kernels targeting CUDA, Vulkan (SPIR-V), Metal, OpenGL, and LLVM-based CPU backends [40][41].

#### Compilation Pipeline

The "Life of a Taichi Kernel" pipeline [42]:

1. **Python AST capture**: When a `@ti.kernel` function is first called, Taichi's `ASTTransformer` captures the Python AST of the function body
2. **Frontend AST emission**: The captured AST is transformed into a Taichi-specific frontend AST, which is then lowered to **CHI IR** (Taichi's custom hierarchical SSA-form IR)
3. **IR optimization passes on CHI IR**:
   - Common subexpression elimination (CSE)
   - Dead instruction elimination (DIE)
   - Constant folding
   - Store forwarding
   - **Access lowering**: translates high-level field accesses into pointer arithmetic based on the data structure layout
   - **Atomic demotion**: converts unnecessary atomic operations to regular operations when safe
   - Pointer analysis
4. **Backend code generation**: Optimized CHI IR is fed to a backend:
   - LLVM backend: for CPU, CUDA (PTX)
   - SPIR-V codegen: for Vulkan
   - Metal backend: for macOS/iOS
   - OpenGL backend: for legacy GPU support [42]

Compilation is JIT: the first invocation of a kernel instance triggers compilation; subsequent calls with the same types reuse the compiled kernel [42].

#### Data Structures (SNodes)

Taichi's unique feature is its **Structural Nodes (SNodes)** system -- a way to declare hierarchical, potentially sparse data layouts that the compiler compiles access patterns for. Dense fields are simple arrays; sparse fields (pointer, bitmasked, dynamic) only allocate memory for active regions [41].

The compiler's access lowering pass resolves SNode accesses into concrete memory operations based on the declared layout. This means changing the data layout (e.g., from array-of-structs to struct-of-arrays) requires only changing the SNode declaration, not the kernel code [41].

#### Vulkan/SPIR-V Backend

As of Taichi v0.8.0, the Vulkan backend generates SPIR-V. CHI IR's SSA form maps naturally to SPIR-V's SSA structure. The backend currently supports dense data structures only; sparse SNode types require additional work for Vulkan translation. The SPIR-V codegen eliminated ~1000 lines of backend-dependent code compared to the previous approach [43].

#### Relevance to Joon

Taichi's compilation pipeline (Python AST -> custom IR -> optimization passes -> SPIR-V for Vulkan) is a close parallel to Joon's pipeline (DSL text -> IR Graph -> optimizer -> Vulkan compute). The key differences: Taichi embeds in Python and captures ASTs at runtime; Joon has a standalone parser. Taichi's SNode system for data layout abstraction is more sophisticated than Joon needs for images but hints at how Joon could handle voxel data structures in the future.

Taichi's approach of JIT-compiling on first use and caching compiled kernels matches Joon's planned compiled-mode behavior of background compilation with hot-swap.

**Website**: [taichi-lang.org](https://www.taichi-lang.org/)
**Source code**: [github.com/taichi-dev/taichi](https://github.com/taichi-dev/taichi)
**Compiler pipeline docs**: [docs.taichi-lang.org/docs/compilation](https://docs.taichi-lang.org/docs/compilation)
**Internal design docs**: [docs.taichi-lang.org/docs/internal](https://docs.taichi-lang.org/docs/internal)
**Berkeley tech report**: [www2.eecs.berkeley.edu/Pubs/TechRpts/2022/EECS-2022-112.pdf](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2022/EECS-2022-112.pdf)

---

### 3.4 ISPC (Intel SPMD Program Compiler)

#### Architecture

ISPC was created by Matt Pharr at Intel. It compiles a C-variant language using an "implicit SPMD" model -- the programmer writes scalar-looking code, and the compiler maps it to SIMD hardware (SSE, AVX, NEON) or GPU (Intel Xe via SPIR-V) [44][45].

#### Execution Model

The SPMD model has two key abstractions [44][45]:

- **Program instance**: One execution of the shader-like function operating on one data element
- **Gang**: A group of program instances executing in lockstep. The gang width equals the target SIMD width (4 for SSE, 8 for AVX, 16 for AVX-512)

The programmer writes code as if it operates on a single element. The compiler vectorizes across the gang: `float x = input[programIndex]` loads a different element for each program instance, arithmetic operates on the full SIMD register, and control flow is handled via masking (inactive lanes are masked off during divergent branches) [44][45].

ISPC uses LLVM for code generation. The compiler front-end translates ISPC source into LLVM IR with SIMD-width vector types, then LLVM's optimizer and code generator produce the final machine code. For GPU targets (Intel Xe), ISPC emits SPIR-V [44][46].

#### Performance

ISPC typically achieves 3x speedup on 4-wide SSE, 5-6x on 8-wide AVX, approaching the theoretical maximum for the SIMD width. The "implicit" nature means the programmer avoids writing explicit intrinsics -- the compiler handles vector register allocation, masking, and scatter/gather [44].

#### Relevance to Joon

ISPC's SPMD model is essentially what happens inside a Vulkan compute shader: each invocation is a "program instance," each workgroup is a "gang," and divergent branches are masked. ISPC proves that the SPMD abstraction can be compiled efficiently from C-like source, which validates Joon's approach of writing per-pixel node kernels that compile to compute shaders. The key insight is that the "one program, many data" model works well for image processing where every pixel runs the same code.

**Website**: [ispc.github.io](https://ispc.github.io/)
**Source code**: [github.com/ispc/ispc](https://github.com/ispc/ispc)
**Technical paper**: [pharr.org/matt/assets/ispc.pdf](https://pharr.org/matt/assets/ispc.pdf)
**LLVM publication**: [llvm.org/pubs/2012-05-13-InPar-ispc.html](https://llvm.org/pubs/2012-05-13-InPar-ispc.html)
**User guide**: [ispc.github.io/ispc.html](https://ispc.github.io/ispc.html)

---

### 3.5 Conal Elliott's Pan / Functional Images

#### Theoretical Foundation

Conal Elliott's work at Microsoft Research (2001-2003) established the theoretical foundation for treating images as functions. The core idea is denotational: an image is a function from continuous 2D space to color values [47][48]:

```haskell
type Image a = Point2 -> a
type Region = Image Bool
type ColorImage = Image Color
```

This means all image operations are function compositions. A blur is a function that takes an image (function) and returns a new image (function) that averages over a neighborhood. A translation is a function that takes an image and returns a new image with transformed coordinates. Composition is just function composition [47][48].

#### Pan Language and Compiler

Pan is an experimental embedded language in Haskell for image synthesis. The compilation pipeline [49]:

1. **Inline all function definitions** -- since images are functions, this fully expands the expression
2. **Apply algebraic laws** of primitive operations to simplify composites
3. **Recover sharing** via a code-motion pass (inlining loses sharing; this reclaims it by detecting common subexpressions)
4. **Generate intermediate code** for a JIT compiler

Elliott also created **Vertigo**, which compiled functional GPU programs from Haskell -- reportedly the first compilation of Haskell to GPU code [49].

#### Key Papers

- "Functional Image Synthesis" (Bridges 2001) -- illustrates the approach with Pan examples [47]
- "Functional Images" (The Fun of Programming, Palgrave 2003) -- extended treatment with more examples and the mathematical model [48]
- "Efficient Image Manipulation via Run-time Compilation" (MSR Tech Report TR-99-82) -- describes the Pan compiler's runtime compilation strategy [49]
- "Programming Graphics Processors Functionally" (Vertigo) -- Haskell to GPU compilation [49]

#### Relevance to Joon

Elliott's "image as function" model is the theoretical basis for Joon's DSL semantics. In Joon, `(def n (noise :scale 4.0))` creates a node that is conceptually a function from pixel coordinates to float values. `(def blended (* base n))` is function composition -- element-wise multiplication of two coordinate-to-value functions. The entire Joon graph is a composed function from coordinates (and parameters) to output pixel values.

The Pan compiler's pipeline (inline -> algebraic simplification -> recover sharing -> codegen) maps directly to Joon's compiled mode (inline node implementations -> constant fold -> detect shared subexpressions -> emit fused compute shaders). Elliott's work provides the mathematical justification for why this approach works: because images are pure functions, all equational transformations preserve semantics.

**Functional Image Synthesis**: [conal.net/papers/bridges2001/](http://conal.net/papers/bridges2001/)
**Functional Images**: [conal.net/papers/functional-images/](http://conal.net/papers/functional-images/)
**Pan home page**: [conal.net/pan/](http://conal.net/pan/)
**Efficient Image Manipulation (TR-99-82)**: [microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-99-82.pdf](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-99-82.pdf)
**Vertigo (GPU programming)**: [conal.net/papers/Vertigo/](http://conal.net/papers/Vertigo/)
**All publications**: [conal.net/papers/](http://conal.net/papers/)

---

### 3.6 FrameGraph / Render Graphs

#### Origin

The FrameGraph concept was presented by Yuriy O'Donnell at GDC 2017, describing Frostbite engine's (EA DICE) rendering architecture. It has since become standard practice in AAA game engines including Unreal Engine (RDG), Ubisoft's Anvil, and many open-source engines [50][51].

#### Architecture

A render graph is a DAG where [50][51][52]:

- **Nodes** are render passes (compute dispatches, draw calls, copies, resolves)
- **Edges** are resource dependencies (images, buffers) that passes read from or write to

The lifecycle of a frame [50][51]:

1. **Declaration phase**: Rendering code declares all passes and their resource requirements (inputs, outputs, resource descriptions). No GPU work is submitted. Passes declare resources as "created" (transient -- exists only for this frame), "imported" (persistent -- back buffer, GBuffer), "read," or "written."
2. **Compile phase**: The graph is analyzed:
   - **Topological sort** establishes execution order
   - **Lifetime analysis** determines first-use and last-use of each transient resource
   - **Dead pass culling** removes passes whose outputs are never consumed
   - **Barrier insertion** automatically places pipeline barriers between passes based on resource usage transitions (e.g., image layout transitions, read-after-write synchronization)
   - **Memory aliasing** assigns transient resources with non-overlapping lifetimes to the same physical memory allocation -- critical for reducing VRAM usage
3. **Execution phase**: Passes execute in order, with the graph runtime binding resources, inserting barriers, and managing transient allocations

#### Vulkan-Specific Considerations

In Vulkan, the render graph must manage [52]:

- **Image layout transitions**: `VK_IMAGE_LAYOUT_UNDEFINED` -> `VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL` -> `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` as an image transitions from render target to texture input
- **Pipeline barriers**: `vkCmdPipelineBarrier` with `srcStageMask`, `dstStageMask`, `srcAccessMask`, `dstAccessMask` specifying exactly which pipeline stages and memory operations to synchronize
- **Render pass merging**: Adjacent passes that use compatible attachments (same dimensions, compatible formats) can be merged into a single `VkRenderPass` with multiple subpasses, enabling tile-based GPUs to keep data on-chip
- **Queue management**: Passes on different queue families (graphics, compute, transfer) require semaphore-based synchronization instead of pipeline barriers
- **Memory aliasing**: `VK_MEMORY_PROPERTY_LAZILY_ALLOCATED_BIT` for transient attachments that may never be backed by physical memory on tile-based GPUs

#### Relevance to Joon

**Joon's scheduler is a render graph.** The Joon spec describes exactly this pattern: "GPU nodes grouped into Vulkan command buffer submissions with automatic barrier/layout transition insertion." Joon's graph compiler should implement the full render-graph lifecycle:

- Declaration: Joon's IR graph with typed resource requirements per node
- Compile: Topological sort, dead node elimination (already planned), barrier insertion, transient resource aliasing from the resource pool
- Execution: Command buffer recording and submission

The resource pool with recycling (already in Joon's design) maps to render graph transient resources. The key optimization Joon should adopt from render graphs is **memory aliasing** -- intermediate images whose lifetimes don't overlap can share the same `VkImage` allocation, significantly reducing VRAM usage for complex graphs.

**GDC 2017 slides**: [slideshare.net/slideshow/framegraph-extensible-rendering-architecture-in-frostbite/72795495](https://www.slideshare.net/slideshow/framegraph-extensible-rendering-architecture-in-frostbite/72795495)
**GDC Vault**: [gdcvault.com/play/1024612/FrameGraph-Extensible-Rendering-Architecture-in](https://www.gdcvault.com/play/1024612/FrameGraph-Extensible-Rendering-Architecture-in)
**Render Graphs overview**: [logins.github.io/graphics/2021/05/31/RenderGraphs.html](https://logins.github.io/graphics/2021/05/31/RenderGraphs.html)
**Render graphs and Vulkan deep dive**: [themaister.net/blog/2017/08/15/render-graphs-and-vulkan-a-deep-dive/](https://themaister.net/blog/2017/08/15/render-graphs-and-vulkan-a-deep-dive/)
**AMD RPS SDK**: [gpuopen.com/learn/rps-tutorial/rps-tutorial-intro/](https://gpuopen.com/learn/rps-tutorial/rps-tutorial-intro/)
**skaarj1989 FrameGraph library**: [github.com/skaarj1989/FrameGraph](https://github.com/skaarj1989/FrameGraph)
**Our Machinery blog on render graphs**: [ruby0x1.github.io/machinery_blog_archive/post/high-level-rendering-using-render-graphs/](https://ruby0x1.github.io/machinery_blog_archive/post/high-level-rendering-using-render-graphs/index.html)

---

## Summary: Mapping to Joon's Architecture

| System | Joon Parallel | Key Lesson |
|--------|--------------|------------|
| **OSL** | Shader group = node graph; LLVM JIT = compiled mode | Whole-network optimization: constant fold and dead-code-eliminate across node boundaries, not just within nodes |
| **MaterialX** | Declarative node graph schema | Four-tier node implementation (inline, function, subgraph, codegen) and monolithic shader output from graph |
| **MDL** | Compilable material description -> GPU code | DAG optimization -> GLSL/SPIR-V backend proves declarative-to-Vulkan-compute pipeline is viable |
| **RSL** | Historical: defined the shader type system | Separation of shader types by pipeline stage -> Joon's GPU/CPU node tiers |
| **Slang** | Modern shader compiler with SPIR-V output | IR at SPIR-V abstraction level; module system for imports; differentiability as future extension |
| **WGSL** | Safety-first shader language | No-UB guarantee and explicit resource binding align with Joon's compile-time validation |
| **Substance Designer** | Two-tier graph (compositing + per-pixel) | Compositing graph = Joon's node graph; Pixel Processor = compute shader kernel; atomic vs library nodes |
| **Nuke** | Multi-channel pipeline + BlinkScript | Declared access patterns (point vs neighborhood) enable tiling; write-once run-on-GPU-or-CPU kernels |
| **Fusion** | Request-driven (pull) evaluation | Pull evaluation as alternative to Joon's push+cache model |
| **ComfyUI** | Topological sort + lazy eval + caching | Content-based cache keys; lazy input evaluation; multi-tier caching strategies |
| **Halide** | Algorithm/schedule separation | **Most relevant**: Joon's interpreter = compute_root; compiled = optimized schedule; node fusion = compute_at |
| **Futhark** | Functional array language -> GPU kernels | Algebraic fusion rules for SOACs; moderate flattening heuristics; uniqueness types for in-place state |
| **Taichi** | Python DSL -> CHI IR -> SPIR-V | JIT compilation pipeline with CHI IR optimization passes; SNode data layout abstraction |
| **ISPC** | Implicit SPMD -> SIMD/GPU | SPMD model = compute shader invocations; validates per-pixel kernel approach |
| **Pan (Elliott)** | Images as functions + compiler optimizations | Theoretical foundation: inline -> simplify -> recover sharing -> codegen = Joon's compiled mode pipeline |
| **FrameGraph** | Render graph = Joon's scheduler | **Directly applicable**: barrier insertion, transient resource aliasing, dead pass culling, memory management |

---

## References

[1] OSL GitHub repository and README: https://github.com/AcademySoftwareFoundation/OpenShadingLanguage
[2] OSL LLVM Integration (DeepWiki): https://deepwiki.com/AcademySoftwareFoundation/OpenShadingLanguage/3.1-llvm-integration-and-jit-compilation
[3] LLVM for Open Shading Language (LLVM Dev Meeting 2010, PDF): https://llvm.org/devmtg/2010-11/Gritz-OpenShadingLang.pdf
[4] OSL Data Types documentation: https://open-shading-language.readthedocs.io/en/main/datatypes.html
[5] OSL Introduction: https://open-shading-language.readthedocs.io/en/latest/intro.html
[6] MaterialX home page: https://materialx.org/
[7] MaterialX Shader Generation documentation: https://github.com/AcademySoftwareFoundation/MaterialX/blob/main/documents/DeveloperGuide/ShaderGeneration.md
[8] NVIDIA blog -- OpenUSD, MaterialX, and OpenPBR: https://developer.nvidia.com/blog/unlock-seamless-material-interchange-for-virtual-worlds-with-openusd-materialx-and-openpbr/
[9] NVIDIA MDL overview: https://www.nvidia.com/en-us/design-visualization/technologies/material-definition-language/
[10] MDL SDK GitHub: https://github.com/NVIDIA/MDL-SDK
[11] MDL compiled distribution functions -- Vulkan/GLSL example: https://raytracing-docs.nvidia.com/mdl/api/mi_neuray_example_df_vulkan.html
[12] RenderMan Shading Language Wikipedia: https://en.wikipedia.org/wiki/RenderMan_Shading_Language
[13] Shading language Wikipedia: https://en.wikipedia.org/wiki/Shading_language
[14] Slang GitHub repository: https://github.com/shader-slang/slang
[15] Slang website: http://shader-slang.org/
[16] Slang IR design: http://shader-slang.org/slang/design/ir.html
[17] Slang compiler overview: http://shader-slang.org/slang/design/overview.html
[18] SLANG.D paper (SIGGRAPH Asia 2023): https://dl.acm.org/doi/10.1145/3618353
[19] WGSL specification: https://www.w3.org/TR/WGSL/
[20] From GLSL to WGSL (Damien Seguin): https://dmnsgn.me/blog/from-glsl-to-wgsl-the-future-of-shaders-on-the-web/
[21] Substance Designer Pixel Processor docs: https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/atomic-nodes/pixel-processor.html
[22] Substance Designer function graph docs: https://helpx.adobe.com/substance-3d-designer/function-graphs/the-function-graph.html
[23] Substance Designer SBS/SBSAR file format: https://stylizedtextures.com/blog/what-are-sbs-sbsar-files
[24] Substance Designer performance optimization: https://helpx.adobe.com/substance-3d-designer/best-practices/performance-optimization-guidelines.html
[25] Nuke features: https://www.foundry.com/products/nuke-family/nuke/features
[26] Nuke compositing introduction: https://learn.foundry.com/nuke/content/comp_environment/nuke/nuke_intro.html
[27] BlinkScript reference: https://learn.foundry.com/nuke/content/reference_guide/other_nodes/blinkscript.html
[28] DaVinci Resolve Fusion: https://www.blackmagicdesign.com/products/davinciresolve/fusion
[29] Fusion GPU-accelerated nodes list: https://jayaretv.com/fusion/list-of-fusion-nodes-that-are-gpu-accelerated/
[30] Natron GitHub: https://github.com/NatronGitHub/Natron
[31] ComfyUI GitHub: https://github.com/comfyanonymous/ComfyUI
[32] ComfyUI execution model (DeepWiki): https://deepwiki.com/hiddenswitch/ComfyUI/4.2-graph-execution-and-caching
[33] Halide PLDI 2013 paper: https://people.csail.mit.edu/jrk/halide-pldi13.pdf
[34] Halide CACM 2018 paper: https://andrew.adams.pub/halide_cacm.pdf
[35] Halide GPU tutorial: https://halide-lang.org/tutorials/tutorial_lesson_12_using_the_gpu.html
[36] Halide autoscheduler: http://graphics.cs.cmu.edu/projects/halidesched/
[37] Futhark website: https://futhark-lang.org/
[38] Futhark PLDI 2017 paper: https://futhark-lang.org/publications/pldi17.pdf
[39] Futhark incremental flattening: https://futhark-lang.org/blog/2019-02-18-futhark-at-ppopp.html
[40] Taichi website: https://www.taichi-lang.org/
[41] Taichi GitHub: https://github.com/taichi-dev/taichi
[42] Life of a Taichi Kernel: https://docs.taichi-lang.org/docs/compilation
[43] Berkeley tech report on Taichi portability: https://www2.eecs.berkeley.edu/Pubs/TechRpts/2022/EECS-2022-112.pdf
[44] ISPC website: https://ispc.github.io/
[45] ISPC user guide: https://ispc.github.io/ispc.html
[46] ISPC paper (Pharr): https://pharr.org/matt/assets/ispc.pdf
[47] Conal Elliott -- Functional Image Synthesis (Bridges 2001): http://conal.net/papers/bridges2001/
[48] Conal Elliott -- Functional Images (Fun of Programming, 2003): http://conal.net/papers/functional-images/
[49] Conal Elliott -- Efficient Image Manipulation via Run-time Compilation: https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-99-82.pdf
[50] Frostbite FrameGraph GDC 2017 slides: https://www.slideshare.net/slideshow/framegraph-extensible-rendering-architecture-in-frostbite/72795495
[51] Render Graphs overview (Riccardo Loggini): https://logins.github.io/graphics/2021/05/31/RenderGraphs.html
[52] Render graphs and Vulkan deep dive (Maister): https://themaister.net/blog/2017/08/15/render-graphs-and-vulkan-a-deep-dive/
