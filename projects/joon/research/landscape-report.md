# Joon Landscape Report: Node Graphs, GPU DSLs, and Procedural Generation

*Exhaustive survey for informing the design of joon — a Lisp-like graphics DSL that compiles to Vulkan compute shaders.*

**Date:** 2026-04-04

---

## Table of Contents

- [Part I: Survey of Relevant Projects](#part-i-survey-of-relevant-projects)
  - [1. Game Engines](#1-game-engines)
    - [1.1 Godot Visual Shaders](#11-godot-visual-shaders)
    - [1.2 Unreal Engine Material Editor](#12-unreal-engine-material-editor)
    - [1.3 Unity Shader Graph](#13-unity-shader-graph)
  - [2. Digital Content Creation (DCC) Tools](#2-digital-content-creation-dcc-tools)
    - [2.1 Blender Shader Nodes & Geometry Nodes](#21-blender-shader-nodes--geometry-nodes)
    - [2.2 Houdini VEX / VOPs / SOPs](#22-houdini-vex--vops--sops)
    - [2.3 Substance Designer](#23-substance-designer)
    - [2.4 Maya Hypershade & Bifrost](#24-maya-hypershade--bifrost)
    - [2.5 Adobe Photoshop](#25-adobe-photoshop)
    - [2.6 GIMP & GEGL](#26-gimp--gegl)
    - [2.7 Terragen](#27-terragen)
  - [3. GIS Applications](#3-gis-applications)
    - [3.1 QGIS Processing Framework](#31-qgis-processing-framework)
    - [3.2 ArcGIS ModelBuilder & Raster Functions](#32-arcgis-modelbuilder--raster-functions)
    - [3.3 GRASS GIS](#33-grass-gis)
    - [3.4 Google Earth Engine](#34-google-earth-engine)
    - [3.5 Other GIS Systems](#35-other-gis-systems)
  - [4. Image Processing DSLs & Scheduling Languages](#4-image-processing-dsls--scheduling-languages)
    - [4.1 Halide](#41-halide)
    - [4.2 Apache TVM](#42-apache-tvm)
    - [4.3 Taichi](#43-taichi)
    - [4.4 Futhark](#44-futhark)
    - [4.5 Other DSLs (ISPC, OSL, MaterialX, Slang, MDL, WGSL)](#45-other-dsls)
  - [5. Shader Graphs, Procedural Generation & Creative Tools](#5-shader-graphs-procedural-generation--creative-tools)
    - [5.1 Shadertoy](#51-shadertoy)
    - [5.2 ISF (Interactive Shader Format)](#52-isf-interactive-shader-format)
    - [5.3 Other Shader Editors](#53-other-shader-editors)
    - [5.4 Procedural Generation Systems](#54-procedural-generation-systems)
    - [5.5 Signed Distance Functions (SDFs)](#55-signed-distance-functions-sdfs)
  - [6. Demoscene & Real-Time Visual Tools](#6-demoscene--real-time-visual-tools)
    - [6.1 Werkkzeug / .kkrieger](#61-werkkzeug--kkrieger)
    - [6.2 Tooll3 / TiXL](#62-tooll3--tixl)
    - [6.3 cables.gl](#63-cablesgl)
    - [6.4 vvvv](#64-vvvv)
    - [6.5 TouchDesigner](#65-touchdesigner)
    - [6.6 Notch](#66-notch)
  - [7. ComfyUI & Compositing Node Graphs](#7-comfyui--compositing-node-graphs)
    - [7.1 ComfyUI](#71-comfyui)
    - [7.2 InvokeAI](#72-invokeai)
    - [7.3 Nuke](#73-nuke)
    - [7.4 DaVinci Resolve Fusion](#74-davinci-resolve-fusion)
    - [7.5 Natron](#75-natron)
    - [7.6 Blender Compositor](#76-blender-compositor)
  - [8. Creative Coding Frameworks](#8-creative-coding-frameworks)
    - [8.1 Processing / p5.js](#81-processing--p5js)
    - [8.2 Nannou (Rust)](#82-nannou-rust)
    - [8.3 Three.js TSL](#83-threejs-tsl)
  - [9. Lisp-Adjacent & Functional Shader Projects](#9-lisp-adjacent--functional-shader-projects)
- [Part II: Single-Source GPU/CPU Programming](#part-ii-single-source-gpucpu-programming)
  - [10. SYCL](#10-sycl)
  - [11. rust-gpu](#11-rust-gpu)
  - [12. CUDA Unified Programming](#12-cuda-unified-programming)
  - [13. Other Single-Source Approaches](#13-other-single-source-approaches)
  - [14. Implications for Joon](#14-implications-for-joon)
- [Part III: Feature Deep-Dives](#part-iii-feature-deep-dives)
  - [15. Polymorphic Nodes & Type Systems](#15-polymorphic-nodes--type-systems)
  - [16. Type Coercion & Implicit Conversion](#16-type-coercion--implicit-conversion)
  - [17. Color Spaces & Color Management](#17-color-spaces--color-management)
  - [18. Node Resolution & Tiling](#18-node-resolution--tiling)
  - [19. Evaluation Order & Caching](#19-evaluation-order--caching)
  - [20. Graph Serialization & File Formats](#20-graph-serialization--file-formats)
  - [21. Node Groups / Subgraphs / Encapsulation](#21-node-groups--subgraphs--encapsulation)
  - [22. Animation & Time](#22-animation--time)
  - [23. Debugging & Inspection](#23-debugging--inspection)
  - [24. Extensibility & Plugin Systems](#24-extensibility--plugin-systems)
  - [25. Expression Languages Within Node Graphs](#25-expression-languages-within-node-graphs)
  - [26. Parameter Ranges & Validation](#26-parameter-ranges--validation)
  - [27. Configurable Nodes with Variable Inputs](#27-configurable-nodes-with-variable-inputs)
  - [28. Multi-Output Nodes & Data Routing](#28-multi-output-nodes--data-routing)
  - [29. LOD & Progressive Rendering](#29-lod--progressive-rendering)
  - [30. Collaboration & Version Control](#30-collaboration--version-control)

---

# Part I: Survey of Relevant Projects

## 1. Game Engines

### 1.1 Godot Visual Shaders

#### Editor Architecture

Godot's Visual Shader System provides a graph-based editor where the architecture centers on `VisualShader` (the resource holding the full graph) and `VisualShaderNode` (individual operations). The graph forms a DAG where edges represent typed data connections. Each shader type (vertex, fragment, light, etc.) maintains its own independent sub-graph, compiled separately and combined into a single shader with multiple functions. Node ID 0 is always the output node, ID 1 is reserved, and user nodes start at ID 2. A dirty flag mechanism via `_update_shader()` orchestrates recompilation only when the graph changes, and a recursive `_dump_node_code()` traverses the DAG to emit GLSL.

[DeepWiki: Visual Shader System](https://deepwiki.com/godotengine/godot/10-visual-shader-system) | [Godot Docs: Using VisualShaders](https://docs.godotengine.org/en/stable/tutorials/shaders/visual_shaders.html)

#### Port Type System

The `VisualShaderNode::PortType` enum defines:

| Port Type | GLSL Type |
|-----------|-----------|
| `PORT_TYPE_SCALAR` | `float` |
| `PORT_TYPE_SCALAR_INT` | `int` |
| `PORT_TYPE_SCALAR_UINT` | `uint` |
| `PORT_TYPE_VECTOR_2D` | `vec2` |
| `PORT_TYPE_VECTOR_3D` | `vec3` |
| `PORT_TYPE_VECTOR_4D` | `vec4` |
| `PORT_TYPE_BOOLEAN` | `bool` |
| `PORT_TYPE_TRANSFORM` | `mat4` |
| `PORT_TYPE_SAMPLER` | `sampler2D` |

Type compatibility is enforced by `is_port_types_compatible()` (around line 1232-1280 of `visual_shader.cpp`). The system supports automatic scalar-to-vector promotion. Incompatible connections produce "Incompatible port types" errors.

[Source: visual_shader.cpp](https://github.com/godotengine/godot/blob/master/scene/resources/visual_shader.cpp) | [Source: visual_shader_nodes.cpp](https://github.com/godotengine/godot/blob/master/scene/resources/visual_shader_nodes.cpp) | [VisualShaderNode Docs](https://docs.godotengine.org/en/stable/classes/class_visualshadernode.html)

#### Expression Nodes & Code Injection

`VisualShaderNodeExpression` allows writing raw Godot Shading Language (GLSL-like) code inside the visual graph. The code is directly injected into the matching shader function. Supports arbitrary input/output ports with configurable names and types, enabling loops, `discard`, and extended types. `VisualShaderNodeGlobalExpression` injects code at the top of the shader file for functions, varyings, uniforms, and constants.

[Godot 3.2 Visual Shader Update](https://godotengine.org/article/major-update-for-visual-shader-in-godot-3-2/) | [PR #28838](https://github.com/godotengine/godot/pull/28838)

#### Custom Nodes via GDScript

`VisualShaderNodeCustom` provides a bridge: custom nodes written as GDScript `@tool` scripts can define ports and generate shader code strings. A saved script with a `class_name` auto-registers without requiring a `plugin.cfg`.

[Visual Shader Plugins](https://docs.godotengine.org/en/stable/tutorials/plugins/editor/visual_shader_plugins.html)

#### Special Shader Modes

Godot supports five shader modes with visual shader support: **Spatial** (3D), **CanvasItem** (2D), **Particles**, **Sky** (procedural sky rendering per-pixel for the radiance cubemap), and **Fog** (volumetric fog froxel processing).

[Godot Docs: Shader Reference](https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/index.html)

#### Compilation Pipeline

Three stages: lexical analysis/parsing, semantic analysis, and GLSL code generation. Uniform buffer layouts use std140 packing. Shaders compile into multiple variants based on feature requirements and render modes. There is no separate IR -- the graph is traversed directly to produce GLSL text.

[DeepWiki: Shader Language and Compilation](https://deepwiki.com/godotengine/godot/4.2-resource-saver-and-serialization)

---

### 1.2 Unreal Engine Material Editor

#### Material Expression Architecture

Every node is a `UMaterialExpression` subclass. Each implements a `Compile()` method taking an `FMaterialCompiler` interface and returning an index into a code chunk array. The compiler, `FHLSLMaterialTranslator`, walks the graph starting from material output pins, recursively calling `Compile()`. The result is multiple HLSL shaders per material.

[Epic KB: Material Graph to HLSL](https://dev.epicgames.com/community/learning/knowledge-base/0qGY/how-the-unreal-engine-translates-a-material-graph-to-hlsl) | [Shestakova: Materials Compilation](https://kseniia-shestakova.medium.com/materials-compilation-in-unreal-engine-nuts-and-bolts-bba28abeb789)

#### Type System

Unreal uses `EMaterialValueType`: `MCT_Float`, `MCT_Float2`, `MCT_Float3`, `MCT_Float4`. A float4 Vector Parameter connected to a float3 input (like Base Color) silently discards the alpha channel. However, arithmetic between inequivalent float types (e.g., float2 and float3) produces a **compile error** -- no auto-promotion. The generated HLSL can be inspected via Window > Shader Code > HLSL Code.

[Epic Docs: Material Data Types](https://dev.epicgames.com/documentation/en-us/unreal-engine/material-data-types-in-unreal-engine) | [HLSLMaterialTranslator.h](https://github.com/chendi-YU/UnrealEngine/blob/master/Engine/Source/Runtime/Engine/Private/Materials/HLSLMaterialTranslator.h)

#### Custom Expressions (HLSL Injection)

The Custom expression node allows injecting raw HLSL with multiple named inputs and outputs. The HLSLMaterial plugin by Phyronnaz provides enhanced external HLSL file authoring.

[Epic Docs: Custom Material Expressions](https://dev.epicgames.com/documentation/en-us/unreal-engine/custom-material-expressions-in-unreal-engine) | [HLSLMaterial Plugin](https://github.com/Phyronnaz/HLSLMaterial)

#### Material Functions & Layers

**Material Functions** are reusable sub-graphs stored as separate assets, nestable. **Material Layers** extend this: each layer is a Material Function representing a surface archetype (steel, leather), composed via Material Layer Blend nodes. `Make/Break Material Attributes` nodes allow wiring entire material outputs as single bundles.

[Epic Docs: Material Layers](https://docs.unrealengine.com/4.26/en-US/RenderingAndGraphics/Materials/MaterialLayers) | [Epic Docs: Layered Materials](https://dev.epicgames.com/documentation/en-us/unreal-engine/layered-materials-in-unreal-engine)

#### Material Parameter Collections

MPCs store up to 1024 scalar and 1024 vector parameters accessible from any material and modifiable from Blueprints at runtime. Updating an MPC value changes it globally across all referencing materials, far more efficiently than setting parameters on individual Material Instances.

[Epic Docs: Material Parameter Collections](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-material-parameter-collections-in-unreal-engine)

#### Substrate (Strata) Material System

Introduced with UE 5.x, Substrate replaces fixed shading models with a modular multi-lobe BSDF framework. Enables multi-layered material looks (dust on clear coat over car paint). Performance scales with material complexity. Artists compose BSDF slabs instead of connecting to fixed pins.

[Epic Docs: Substrate Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-substrate-materials-in-unreal-engine) | [Siggraph 2023: Substrate](https://advances.realtimerendering.com/s2023/2023%20Siggraph%20-%20Substrate.pdf)

#### Blueprints vs Material Graphs

Both share the same `UEdGraph` framework. The key difference: Blueprints handle **gameplay logic** with execution flow (white "exec" wires), while Material Graphs are **pure data-flow** with no execution ordering -- every node is a stateless expression.

#### Compilation Pipeline

Material Graph -> `FHLSLMaterialTranslator` walks the graph -> code chunks accumulated as HLSL strings -> assembled with `MaterialTemplate.usf` into complete HLSL -> compiled by platform shader compiler (DXC, FXC). No explicit IR between graph and HLSL; the "intermediate" is an array of HLSL code chunk strings.

[MaterialTemplate.usf source](https://github.com/chendi-YU/UnrealEngine/blob/master/Engine/Shaders/MaterialTemplate.usf)

---

### 1.3 Unity Shader Graph

#### Node Architecture & Port System

Nodes have typed input and output ports. Data types: Float (Vector1), Vector2, Vector3, Vector4, Color, Boolean, Matrix2, Matrix3, Matrix4, and Texture types. Some ports are **Dynamic Vector** -- their concrete type adapts to whatever is connected.

[Unity Docs: Create Node Menu](https://docs.unity3d.com/Packages/com.unity.shadergraph@17.5/manual/Create-Node-Menu.html)

#### Type Coercion

All Vector types can be promoted or truncated. When truncating, excess channels are removed. When promoting, extra channels are filled with defaults `(0, 0, 0, 1)`. Example: Vector2 to Vector4 yields `(x, y, 0, 1)`. Invalid connections between fundamentally incompatible types produce errors.

[Unity Docs: Data Types](https://docs.unity3d.com/Packages/com.unity.shadergraph@6.9/manual/Data-Types.html)

#### Master Stack & Targets

Since Shader Graph 10.0, the **Master Stack** contains Vertex and Fragment contexts. Each contains **Block nodes** representing specific shader outputs (Base Color, Normal, Alpha). Different render pipelines (URP, HDRP) expose different Block sets.

[Unity Blog: Master Stack](https://blog.unity.com/engine-platform/introducing-shader-graphs-new-master-stack)

#### Custom Function Nodes (HLSL Injection)

Two modes: **String mode** (inline HLSL with `$precision` token replacement) and **File mode** (external `.hlsl` includes with `_half`/`_float` function suffixes).

[Unity Docs: Custom Function Node](https://docs.unity3d.com/Packages/com.unity.shadergraph@17.0/manual/Custom-Function-Node.html)

#### Precision Handling

Explicit precision control at node level: `float` (32-bit), `half` (16-bit), or `Inherit`. Critical for mobile GPUs where `half` is genuinely faster.

#### Keyword Nodes & Shader Variants

Three types: **Boolean** (2 variants), **Enum** (N states), **Built-in** (pipeline-controlled). Definition modes: Multi Compile (all variants), Shader Feature (only used variants), Predefined (pipeline-controlled).

[Unity Docs: Keywords](https://docs.unity3d.com/Packages/com.unity.shadergraph@12.0/manual/Keywords.html) | [Cyanilux: Intro to Shader Graph](https://www.cyanilux.com/tutorials/intro-to-shader-graph/)

#### VFX Graph vs Shader Graph

Shader Graph defines surface appearance; VFX Graph defines particle simulation. A Shader Graph with Visual Effects output target can be assigned to VFX Graph Output Contexts. Exposed properties become per-particle parameters.

[Unity Docs: VFX + Shader Graph](https://docs.unity3d.com/Packages/com.unity.visualeffectgraph@17.0/manual/sg-working-with.html)

#### Game Engine Summary Tables

**Type Mismatch Handling:**

| Engine | Scalar->Vector | Vector Truncation | Incompatible Types |
|--------|---------------|-------------------|-------------------|
| Godot | Auto-promoted via `is_port_types_compatible()` | Supported with port expansion | Connection refused |
| Unreal | Float1 promoted to Float3/4 | Float4->Float3 silently drops alpha | Arithmetic mismatch errors |
| Unity | Promoted with defaults (0,0,0,1) | Excess channels removed | Connection refused |

**Compilation Pipeline:**

| Engine | IR | Target Language | Template System |
|--------|-----|----------------|-----------------|
| Godot | None (direct DAG->code) | GLSL ES 3.0 variant | Godot shader processor |
| Unreal | Code chunk string array | HLSL | MaterialTemplate.usf |
| Unity | None (direct DAG->code) | HLSL/GLSL per platform | Render pipeline templates |

---

## 2. Digital Content Creation (DCC) Tools

### 2.1 Blender Shader Nodes & Geometry Nodes

#### Core Architecture

Blender's node system is built on four structures: `bNodeTree`, `bNode`, `bNodeSocket`, and `bNodeLink`. These bridge DNA (serialized data), BKE (runtime kernel), RNA/UI (user interface), and evaluation engines. A runtime layer (`bNodeTreeRuntime`) maintains topology caches and transient evaluation data rebuilt on file load.

Key source files: `source/blender/makesdna/DNA_node_types.h`, `source/blender/blenkernel/BKE_node.h`, `source/blender/nodes/NOD_static_types.h`, `source/blender/nodes/shader/node_shader_tree.cc`.

[DeepWiki: Node Tree Core](https://deepwiki.com/blender/blender/2.1-node-tree-management-and-versioning) | [Blender GitHub: node_shader_tree.cc](https://github.com/blender/blender/blob/main/source/blender/nodes/shader/node_shader_tree.cc)

#### Type System & Implicit Conversions

Socket types: value sockets (float, integer, vector, color, boolean) and data sockets (image, geometry, shader, material, node tree). Implicit conversions:

| From | To | Method |
|------|-----|--------|
| Color | Vector | `(r,g,b)` -> `(x,y,z)` |
| Color | Float | Luminance: `0.2126729*r + 0.7151522*g + 0.0721750*b` |
| Vector | Float | Average: `(x+y+z)/3` |
| Float/Color/Vector | Shader | Wraps in emission shader |

These are lossy and one-directional.

[Blender Shaders: Sockets](https://wannesmalfait.github.io/Blender-shaders/mnode/sockets.html) | [Blender Manual: Node Parts](https://docs.blender.org/manual/en/2.92/interface/controls/nodes/parts.html)

#### SVM vs OSL Compilation

**SVM (Shader Virtual Machine)**: Bytecode interpreter with shaders encoded as sequential `uint4` instruction lists in a 1D texture. All stack data is floats in GPU local memory. DFS traversal clusterizes nodes to minimize stack size. Key source: `intern/cycles/kernel/svm/svm.h`.

**OSL (Open Shading Language)**: Compiles `.osl` to `.oso` bytecode. Historically CPU-only, now supports GPU via OptiX backend. Every built-in shader node has both SVM and OSL implementations.

[Fossies: svm.h](https://fossies.org/linux/blender/intern/cycles/kernel/svm/svm.h) | [DeepWiki: Cycles](https://deepwiki.com/blender/cycles) | [Blender Manual: OSL](https://docs.blender.org/manual/en/latest/render/cycles/osl/index.html)

#### Geometry Nodes & the Fields System

Two key abstractions:

- **Multi-Function (`FN::MultiFunction`)**: Encapsulates a function computed over many elements simultaneously. `MFNetwork` is a finalized graph; `MF_EvaluateNetwork` splits data into chunks for thread parallelism.
- **Lazy-Function system**: Compute only what is necessary. Each geometry node group converts to a lazy-function graph. Execution starts from the output node and traces backwards.

**Fields** are the central abstraction -- deferred computations (functions with variables like attribute names) that evaluate over a geometry domain (point, edge, face, corner, curve, instance). Fields compose into new fields and are only materialized when a data-flow node (like Set Position) demands the result. This is essentially lazy evaluation of pure functions over geometric domains.

**Relevance to joon**: Fields are conceptually identical to joon's deferred expression trees that compile to GPU compute shaders -- both represent unevaluated computation graphs materialized on demand.

[Blender Blog: Attributes and Fields](https://code.blender.org/2021/08/attributes-and-fields/) | [Blender Manual: Fields](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/fields.html)

---

### 2.2 Houdini VEX / VOPs / SOPs

#### VEX Language

VEX (Vector Expression Language) is a high-performance shading and geometry manipulation language with C-like syntax. Type system: `int`, `float`, `vector2`, `vector` (3-component), `vector4`, `matrix2`, `matrix3`, `matrix` (4x4), `string`, `dict` (since 18.5), and array variants. Attribute access uses sigil prefixes: `f@` (float), `i@` (int), `s@` (string), `v@` (vector), `u@` (vector2), `p@` (vector4).

VEX dispatches functions based on both argument types AND return type, which is unusual among shading languages. Performance close to compiled C/C++.

[SideFX: VEX Language Reference](https://www.sidefx.com/docs/houdini/vex/lang.html) | [SideFX: VEX Snippets](https://www.sidefx.com/docs/houdini/vex/snippets.html)

#### VOPs: Visual VEX

VOPs (VEX Operators) provide a visual node graph that maps one-to-one to VEX. Houdini linearizes the VOP graph into a single VEX code snippet at cook time. The compilation is essentially a topological sort and code emission -- the VOP graph serves as a visual abstract syntax tree.

**Wrangle nodes** provide the inverse path: inline VEX code embedded directly in the SOP/DOP/COP graph.

[Artivoxa: Power of VOPs](https://www.artivoxa.com/the-power-of-vops-a-visual-guide-to-houdinis-node-system/) | [Medium: VEX and VOP](https://medium.com/@jxu33/vex-and-vop-in-houdini-d8771b5b9618)

#### Contexts & Attribute Flow

Operator network organized by context: SOP (geometry), DOP (dynamics), COP (compositing), SHOP (shaders, legacy), LOP (USD), TOP (tasks), CHOP (channels). **CVEX** is a generic low-level context used for geometry manipulation. Geometry attributes flow at four levels: point, vertex, primitive, detail. Promotion between levels handled by Attribute Promote nodes.

[SideFX: Geometry Attributes](https://www.sidefx.com/docs/houdini/model/attributes.html) | [SideFX: CVEX Context](https://www.sidefx.com/docs/houdini/vex/contexts/cvex.html)

#### Compiled Blocks & PDG

**Compiled blocks**: Chains of compilable SOPs execute much faster, particularly for multithreaded for-each loops.

**PDG (Procedural Dependency Graph)**: Task-based parallel execution via TOPs (Task Operators). TOP nodes generate work items with named attributes. PDG distributes them across local cores, render farms, or cloud compute.

[SideFX: Compiled Blocks](https://www.sidefx.com/docs/houdini/model/compile.html) | [SideFX: PDG](https://www.sidefx.com/products/houdini/pdg/)

#### OpenCL GPU Acceleration

The **OpenCL SOP** provides a general interface for running OpenCL kernels on geometry. It binds attributes, volumes, and topology to kernel parameters. The `@`-prefixed macros mirror VEX wrangle conventions. With **Copernicus** (Houdini 20.5's refreshed COP network), OpenCL is more accessible to everyday artists.

[SideFX: OpenCL SOP](https://www.sidefx.com/docs/houdini/nodes/sop/opencl.html) | [SideFX: OpenCL for VEX Users](https://www.sidefx.com/docs/houdini/vex/ocl.html)

#### HDAs (Houdini Digital Assets)

HDAs encapsulate node networks into reusable custom operators with defined inputs/outputs, versioned and lockable interfaces.

**Relevance to joon**: Houdini's dual paradigm -- visual VOP graphs and textual VEX code, both compiling to the same execution target -- is the closest industry analogue to joon's approach.

---

### 2.3 Substance Designer

#### Two-Level Graph Architecture

1. **Compositing graphs** (main material graph): Nodes process full images. Types: **atomic nodes** (26 built-in primitives like Blend, Uniform Color, Levels) and **graph instances** (references to other graphs as reusable subgraphs).

2. **Function graphs**: Operate on single values (int, float, float2, float3, float4, bool). Drive the **Pixel Processor** and **Value Processor** atomic nodes.

[Adobe: Atomic Nodes](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/atomic-nodes.html) | [Adobe: Function Graph](https://helpx.adobe.com/substance-3d-designer/function-graphs/the-function-graph.html)

#### Pixel Processor

The most versatile atomic node: evaluates a function graph for every pixel. System variables:

| Variable | Type | Description |
|----------|------|-------------|
| `$pos` | float2 | Normalized pixel position (UV, 0 to 1) |
| `$size` | float2 | Raw pixel resolution (e.g., 1024, 512) |
| `$sizelog2` | float2 | Log2 of resolution (e.g., 10, 9) |

This per-pixel evaluation is conceptually identical to a GPU compute shader dispatch. The key difference: Substance abstracts parallelism entirely, while joon exposes it through explicit GPU dispatch.

[Adobe: Pixel Processor](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/atomic-nodes/pixel-processor.html) | [Adobe: System Variables](https://helpx.adobe.com/substance-3d-designer/function-graphs/variables/system-variables.html)

#### Data Types & Conversion

Compositing graphs handle grayscale (single channel) and color (RGBA). Explicit conversion nodes required -- no implicit coercion. Color operations take ~4x longer than grayscale.

Function graphs use: integer, float, float2, float3, float4, boolean with explicit cast nodes.

#### FX-Map

A special atomic node implementing a Markov chain: repeatedly replicates and subdivides an image with dynamic functions controlling rotation, scale, offset, and color. Inherently resolution-independent.

[Adobe: FX-Map](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/atomic-nodes/fx-map.html)

#### SBSAR Format

`.sbs` is the editable XML source. Publishing produces `.sbsar` -- compressed, standalone binary with all dependencies. Exposed parameters adjustable at runtime with no quality loss. The engine caches each node's output for incremental re-cooking.

[Adobe: Publishing SBSAR](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/publishing-substance-3d-asset-files-sbsar.html) | [Pysbs Python API](https://helpx.adobe.com/substance-3d-sat/pysbs-python-api.html)

---

### 2.4 Maya Hypershade & Bifrost

#### Hypershade

Maya's shader node editor built on the Dependency Graph (DG). The DG is a two-stage evaluation system: **dirty propagation** marks stale attributes via `MPxNode::attributeAffects`, then **attribute computation** pulls values on demand. This is fundamentally **demand-driven (lazy) evaluation**. When types mismatch, Maya inserts automatic conversion nodes (e.g., `timeToUnitConversion1`).

Arnold integrates via OSL: `.osl` source compiled by `oslc` to `.oso` bytecode, JIT-compiled at render time. OSL nodes evaluate lazily -- output computed only when "pulled" by downstream. Surface shaders produce **closures** (symbolic descriptions of light scattering) rather than final colors.

[Maya SDK: Dependency Graph](https://help.autodesk.com/cloudhelp/2022/ENU/Maya-SDK/Dependency-graph-plug-ins/About-the-dependency-graph.html) | [OSL Shaders - Arnold](https://help.autodesk.com/view/ARNOL/ENU/?guid=arnold_for_maya_shaders_am_OSL_Shaders_html)

#### Bifrost

Architecturally standalone from Maya. Pure data-flow graph with rich types: `bool`, `char`, `uchar`, `short`, `ushort`, `int`, `uint`, `long`, `ulong`, `float`, `double`, plus all matrix variants. Type promotion is automatic. Ports can be declared `auto` -- concrete type inferred from connections. Arrays are first-class: `array<float>`, `array<array<int>>`. Compounds act as reusable subgraphs.

[Bifrost data types](https://help.autodesk.com/view/BIFROST/ENU/?guid=Bifrost_Common_build_a_graph_about_data_types_html) | [Bifrost on fxguide](https://www.fxguide.com/fxfeatured/bifrost-the-return-of-the-naiad-team-with-a-bridge-to-ice/)

---

### 2.5 Adobe Photoshop

#### Implicit DAG

No node graph UI, but processing is structured as an implicit DAG. Adjustment layers apply non-destructive transforms. Smart Objects encapsulate embedded documents, Smart Filters form a reversible pipeline chain. GPU acceleration via the Mercury Graphics Engine (OpenCL, D3D12, Metal). Since 2022, native OpenColorIO support enables ACES workflows in 32-bit mode.

[Nondestructive editing](https://helpx.adobe.com/photoshop/using/nondestructive-editing.html) | [OpenColorIO in Photoshop](https://helpx.adobe.com/photoshop/using/opencolorio-transform.html)

---

### 2.6 GIMP & GEGL

#### GEGL Architecture

GEGL (Generic Graphics Library) is the computational backbone of GIMP, modeled as a **DAG** of image operations. Provides floating-point processing, non-destructive editing, and handles buffers **larger than RAM** through tiled, sparse, pyramidal storage.

**Evaluation**: Demand-driven (lazy) with cached results. On parameter edit, only the affected subgraph recomputes for the visible region at preview resolution. Full resolution re-evaluation happens in the background.

**Operation type hierarchy:**

| Type | Description |
|------|-------------|
| `GeglOperationFilter` | Single input/output, multi-threaded tiled |
| `GeglOperationPointFilter` | Pixel-independent 1:1 (color transforms) |
| `GeglOperationAreaFilter` | Neighborhood-dependent (convolutions, blurs) |
| `GeglOperationComposer` | Two inputs for blend/composite |
| `GeglOperationSource` | No inputs, generates data |
| `GeglOperationSink` | No outputs, consumes data |

This taxonomy maps cleanly to joon's operation categories.

[GEGL website](https://www.gegl.org/) | [GEGL operations](https://www.gegl.org/operations/) | [GEGL on GNOME GitLab](https://gitlab.gnome.org/GNOME/gegl)

#### babl: Pixel Format Type System

The **babl** library handles pixel format conversion as a structural type system. Formats are combinations of color model (RGB, CMYK, CIE Lab, etc.), component order, data type (u8, u16, float, double), and transfer curve (linear, sRGB TRC). Conversion between any two formats is handled by requesting a "fish" -- babl finds an optimal conversion path, potentially through intermediates. Format strings like `"R'G'B'A float"` (perceptual sRGB) or `"CIE Lab u16"` describe encodings precisely.

[babl documentation](https://gegl.org/babl/) | [babl ColorManagement](https://gegl.org/babl/ColorManagement.html)

#### Script-Fu: The Lisp Connection

GIMP's built-in scripting language is based on **TinyScheme**, an R5RS Scheme interpreter -- a direct member of the Lisp family. Syntax: `(gimp-image-flatten image)` -- structurally identical to joon's S-expression syntax. This validates joon's choice of S-expressions for a graphics DSL.

[Script-Fu Programmer's Reference](https://developer.gimp.org/resource/script-fu/programmers-reference/) | [GIMP Basic Scheme tutorial](https://www.gimp.org/tutorials/Basic_Scheme/)

---

### 2.7 Terragen

#### Node-Based Procedural Terrain

Terragen is organized as a node network with three primary data types: **Scalar** (float), **Vector** (XYZ triple), **Color** (RGB triple). Explicit conversion nodes mediate between types: `Scalar to Vector`, `Luminance to Scalar`, `X/Y/Z to Scalar`, etc. Arithmetic nodes like `Add Scalar` perform implicit coercion (color to scalar via luminance).

Shader categories: Surface shaders (Surface Layer), Atmosphere shaders (Rayleigh/Mie scattering), Cloud shaders (volumetric v3 with physically-based voxel ray-marching), Function nodes (Power Fractal with Voronoi).

Evaluation at render time via micropolygon rasterization. Displacement applied by procedural functions modifying the planet sphere from continent-scale to sand-grain detail. The **Micro Exporter** captures micropolygons as OBJ/FBX for game engine use.

[Terragen Network View Guide](https://planetside.co.uk/wiki/index.php?title=Terragen_Network_View_Guide) | [Procedural Data](https://planetside.co.uk/wiki/index.php?title=Procedural_Data) | [Cloud Layer v3](https://planetside.co.uk/wiki/index.php?title=Cloud_Layer_v3)

#### DCC Tools Summary Table

| Aspect | Blender | Houdini | Substance | Maya/Bifrost | GIMP/GEGL | Terragen |
|--------|---------|---------|-----------|-------------|-----------|----------|
| **IR** | SVM bytecode / OSL | VEX source | SBSAR binary | DG pull / Bifrost dataflow | GEGL DAG | Direct per-pixel eval |
| **Type coercion** | Implicit (lossy) | Dispatch on arg+return | Explicit nodes | Auto conversion nodes | babl fish | Explicit conversion nodes |
| **Lazy eval** | Fields (demand-driven) | Not inherent | Node caching | DG dirty propagation | Demand-driven, tiled | At render time |
| **GPU path** | SVM/OptiX | OpenCL SOP | GPU engine | Arnold GPU | OpenCL (experimental) | CPU micropolygon |
| **FP influence** | Strong (fields) | Moderate | Moderate (dataflow) | Closures (OSL) | Strong (GEGL DAG) | Moderate |
| **Lisp connection** | None | None | None | MEL (imperative) | **Script-Fu (Scheme!)** | None |

---

## 3. GIS Applications

### 3.1 QGIS Processing Framework

The Processing toolbox chains algorithms as a DAG with strongly-typed parameters (`QgsProcessingParameterRasterLayer`, etc.), evaluating eagerly with intermediate files on disk. The Graphical Modeler provides visual workflow composition. QGIS expressions form a full AST-parsed language with math, geometry, and aggregate functions. OpenCL GPU support exists but covers only hillshade/slope.

[QGIS Processing](https://docs.qgis.org/latest/en/docs/user_manual/processing/index.html)

### 3.2 ArcGIS ModelBuilder & Raster Functions

Two distinct graph models coexist. **ModelBuilder** is an eager visual DAG of tool invocations with variable substitution and iterators. **Raster Function Chains** are the interesting one: they evaluate **lazily**, processing only visible/requested pixels on the fly with no intermediate files. The Raster Function Editor produces `.rft.xml` templates. GPU support via CUDA for Spatial Analyst tools.

[ArcGIS Raster Functions](https://pro.arcgis.com/en/pro-app/latest/help/analysis/raster-functions/raster-functions.htm)

### 3.3 GRASS GIS

`r.mapcalc` is the richest expression language surveyed: C-like infix syntax with a **neighborhood modifier** (`map[row, col]`) permitting convolution-style filters directly in the algebra, plus NULL propagation, 3 numeric types, and a `graph()` function. Eager evaluation, region-aligned.

[GRASS r.mapcalc](https://grass.osgeo.org/grass-stable/manuals/r.mapcalc.html)

### 3.4 Google Earth Engine

The closest architectural analog to joon. A client-side API builds proxy objects forming a **JSON DAG** sent to the server only on `.getInfo()` or export. Fully **lazy**, **functional** (map/filter/reduce, no side effects), and **resolution-independent** (scale/CRS resolved at evaluation time, not definition time). This deferred-evaluation + resolution-independence pattern maps directly to joon's design.

[Google Earth Engine Guides](https://developers.google.com/earth-engine/guides)

### 3.5 Other GIS Systems

- **GDAL 3.11**: New raster pipeline with `.gdalg.json` serialization and streaming evaluation -- a lightweight lazy processing chain.
- **ESA SNAP**: XML-defined DAGs with tile-by-tile streaming.
- **Orfeo ToolBox**: Chains applications via in-memory ITK pipelines.

GPU acceleration across GIS remains fragmented -- no system offers a unified GPU compute graph like joon's Vulkan pipeline.

---

## 4. Image Processing DSLs & Scheduling Languages

### 4.1 Halide

#### Algorithm/Schedule Separation

Halide's central innovation: the algorithm specifies *what* is computed as pure functions over an infinite integer domain. The schedule specifies *when and where* -- loop ordering, tiling, parallelism, storage. This decoupling allows exploring different optimization strategies without touching algorithmic code.

[Halide PLDI'13 Paper](https://people.csail.mit.edu/jrk/halide-pldi13.pdf) | [Halide Homepage](https://halide-lang.org/)

#### Type System

Core types: `Expr` (scalar/symbolic expression), `Func` (function over integer domain), `Var` (loop dimension variable), `Buffer` (runtime data storage), `RDom` (reduction domain). Scalar types: int8-int64, uint8-uint64, float16/32/64, bfloat16.

#### Scheduling Primitives

| Primitive | Description |
|-----------|-------------|
| `tile(x,y,xi,yi,tw,th)` | Split dimensions into outer+inner tiles |
| `vectorize(dim,width)` | Generate SIMD instructions along dimension |
| `parallel(dim)` | Parallelize loop dimension across threads |
| `compute_at(f,var)` | Specify compute location in another Func's schedule |
| `store_at(f,var)` | Control intermediate storage placement |
| `unroll(dim,factor)` | Unroll loop by factor |
| `fuse(outer,inner)` | Merge two dimensions into one |

#### Boundary Conditions

Five built-in: `constant_exterior`, `repeat_edge`, `repeat_image`, `mirror_image`, `mirror_interior` -- mapping directly to GL texture wrap modes.

[BoundaryConditions Reference](https://halide-lang.org/docs/namespace_halide_1_1_boundary_conditions.html)

#### Code Example

```cpp
Func blur_3x3(Func input) {
  Func blur_x, blur_y;
  Var x, y, xi, yi;
  // Algorithm
  blur_x(x, y) = (input(x-1, y) + input(x, y) + input(x+1, y)) / 3;
  blur_y(x, y) = (blur_x(x, y-1) + blur_x(x, y) + blur_x(x, y+1)) / 3;
  // Schedule
  blur_y.tile(x, y, xi, yi, 256, 32)
        .vectorize(xi, 8).parallel(y);
  blur_x.compute_at(blur_y, x).vectorize(x, 8);
  return blur_y;
}
```

#### Autoschedulers

- **Mullapudi2016**: Greedy heuristic, single-level tiling.
- **Adams2019**: Beam search with learned cost model, ~2.3x over Mullapudi2016. [Paper](https://halide-lang.org/papers/halide_autoscheduler_2019.pdf)
- **Li2018**: Only GPU-targeting autoscheduler. [Paper](https://cseweb.ucsd.edu/~tzli/gpu_autoscheduler.pdf)

#### Vulkan & WebGPU Backends

The Vulkan backend compiles directly to binary SPIR-V. Beta quality as of 2025. WebGPU backend under active development.

[Halide Vulkan Documentation](https://github.com/halide/Halide/blob/main/doc/Vulkan.md)

**Relevance to joon**: Halide's algorithm/schedule separation is the most directly applicable pattern. Joon's DSL defining image operations is analogous to Halide's algorithm layer; joon could benefit from scheduling annotations to control tiling, memory layout, and workgroup dispatch.

---

### 4.2 Apache TVM

Two-level IR: high-level **Relay** (functional, supports let-bindings, closures, ADTs, pattern matching) for whole-model optimization, and low-level **TensorIR (TIR)** for per-operator scheduling. Three generations of auto-tuning: AutoTVM (manual templates), AutoScheduler/Ansor (automatic search space generation), and Meta Schedule (unified DSL).

Pipeline: Model import -> Relay IR -> graph optimizations -> TIR -> operator optimizations -> target code (LLVM/CUDA/OpenCL/Vulkan/Metal).

[TVM Architecture](https://tvm.apache.org/docs/arch/index.html) | [Ansor Paper](https://arxiv.org/pdf/2006.06762)

**Relevance to joon**: TVM's two-level IR maps to joon's architecture: graph-level node connections + per-node shader compilation.

---

### 4.3 Taichi

Python-embedded DSL for high-performance numerical computation. Key innovations:

- **SNode** data layout: composable hierarchical containers (dense, pointer, dynamic, bitmasked) for automatic sparse storage optimization.
- **Compilation pipeline**: Python AST capture -> Frontend IR (auto-parallelized) -> Chi-IR (SSA-form, domain-specific optimizations) -> Backend IR -> SPIR-V/PTX/Metal/LLVM.
- **Megakernels**: Fuses multiple small kernels into single dispatches, reducing launch overhead.
- **Differentiable programming**: Native auto-diff support.
- **Backends**: CUDA, Vulkan, Metal, OpenGL, DirectX 11, CPU (LLVM), WebAssembly.

[Taichi Overview](https://docs.taichi-lang.org/docs/overview) | [Taichi SIGGRAPH'19](https://dl.acm.org/doi/10.1145/3355089.3356506) | [GitHub](https://github.com/taichi-dev/taichi)

**Relevance to joon**: Taichi's Chi-IR as an intermediate optimization layer between DSL and SPIR-V is a pattern joon could adopt. Megakernel fusion is directly applicable to multi-node graph evaluation.

---

### 4.4 Futhark

Statically typed, purely functional, data-parallel array language in the ML family. **Uniqueness type system** enables in-place array updates while preserving referential transparency. Array types carry shape information: `[n][m]f32`. Parallelism via SOACs: `map`, `reduce`, `scan`, `filter`, `scatter`, `reduce_by_index`. Compiler aggressively fuses map chains, eliminates intermediate arrays, and applies **flattening** (nested parallelism -> flat GPU parallelism). Targets: OpenCL, CUDA, HIP, multicore CPU.

[Futhark Homepage](https://futhark-lang.org/) | [Futhark PLDI'17](https://futhark-lang.org/publications/pldi17.pdf) | [GitHub](https://github.com/diku-dk/futhark)

**Relevance to joon**: Futhark's purely functional semantics and aggressive fusion are directly applicable -- consecutive joon image operations could be fused into single GPU dispatches.

---

### 4.5 Other DSLs

#### ISPC (Intel SPMD Program Compiler)
SPMD (Single Program Multiple Data) for CPU SIMD units and Intel GPUs. Scalar-looking code maps across SIMD lanes. Demonstrates that the GPU programming model works on CPUs too. [ISPC Homepage](https://ispc.github.io/) | [ISPC Paper](https://pharr.org/matt/assets/ispc.pdf)

#### OSL (Open Shading Language)
C-like language for materials/lights/displacement, compiled via LLVM JIT with full knowledge of runtime parameters. Used by Arnold, Cycles, V-Ray, 3Delight, Redshift. CPU-primary with JIT specialization. [GitHub](https://github.com/AcademySoftwareFoundation/OpenShadingLanguage)

#### MaterialX
Open standard (ASWF) for materials as DAGs of pattern generation/processing nodes. Typed data streams, XML format (.mtlx), code generation to GLSL/OSL/MDL. Standard node library (noise, blend, PBR models). If joon wanted DCC interop, MaterialX import/export is the natural path. [MaterialX](https://materialx.org/) | [Specification](https://github.com/AcademySoftwareFoundation/MaterialX/blob/main/documents/Specification/MaterialX.Specification.md)

#### Slang
Extends HLSL with generics, interfaces, modules, and automatic differentiation. Compiles to SPIR-V, DXIL, Metal, CUDA, C++. Generics resolved via monomorphization. Hosted by Khronos Group since 2024. **Differentiable Slang** auto-generates forward/backward derivative propagation. [Slang Homepage](http://shader-slang.org/) | [GitHub](https://github.com/shader-slang/slang)

#### MDL (NVIDIA Material Definition Language)
Declarative material language defining light behavior at a high level. Compiled to PTX/LLVM IR. Portable across renderers (Iray, V-Ray, Omniverse). [MDL Technical Introduction](https://raytracing-docs.nvidia.com/mdl/introduction/index.html)

#### WGSL (WebGPU Shading Language)
Safety, determinism, portability for browsers. Rust-influenced syntax, no implicit conversions, explicit address spaces, no preprocessor. Strict static validation prevents undefined behavior. [W3C WGSL Specification](https://www.w3.org/TR/WGSL/)

#### DSL Compilation Pipeline Summary

| DSL | Source Form | IR | GPU Backend | Key Innovation |
|-----|-------------|-----|-------------|----------------|
| Halide | C++ embedded | Halide IR -> LLVM | SPIR-V, PTX, OpenCL, Metal, WebGPU | Algorithm/schedule separation |
| TVM | Python | Relay -> TIR | CUDA, OpenCL, Vulkan, Metal | Two-level IR + autotuning |
| Taichi | Python decorators | Chi-IR (SSA) | SPIR-V, PTX, Metal, OpenGL | Megakernel fusion, SNode layout |
| Futhark | Standalone functional | SOACs -> kernels | OpenCL, CUDA, HIP | Purely functional + flattening |
| Slang | HLSL-extended | Slang IR | SPIR-V, DXIL, Metal, CUDA, C++ | Generics + auto-diff |
| OSL | C-like standalone | LLVM JIT | CPU only | Runtime specialization |
| ISPC | C-like SPMD | LLVM | CPU SIMD, Intel GPU | SPMD-on-SIMD model |

---

## 5. Shader Graphs, Procedural Generation & Creative Tools

### 5.1 Shadertoy

Structures shaders around `mainImage(out vec4 fragColor, in vec2 fragCoord)`. Built-in uniforms: `iResolution`, `iTime`, `iMouse`, `iChannel0-3`. Multipass via four named buffers (A-D), each running independent fragment shaders with self-referencing channels for feedback effects. Shared `Common` tab for code reuse. Fragment-shader-only, no compute stage.

[Shadertoy How-To](https://www.shadertoy.com/howto) | [Tutorial: Channels/Buffers](https://inspirnathan.com/posts/62-shadertoy-tutorial-part-15/)

**Relevance to joon**: The buffer system is a simple precedent for multipass compute. The uniform convention (`iTime`, `iResolution`) is worth adopting as standard implicit inputs.

### 5.2 ISF (Interactive Shader Format)

GLSL + JSON metadata header declaring inputs, passes, and persistent buffers. Input types: `float`, `bool`, `color`, `point2D`, `image`, `audio`, `audioFFT`. Multipass via `PASSES` array, `PASSINDEX` uniform increments per pass. Natively supported in VDMX, Resolume, MadMapper.

[ISF spec](https://docs.isf.video/) | [GitHub](https://github.com/Vidvox/isf)

**Relevance to joon**: ISF's typed parameter declarations alongside shader code is a clean model for joon node metadata.

### 5.3 Other Shader Editors

- **ShaderFrog 2.0**: "Hybrid Graph" -- nodes can be visual blocks OR editable GLSL source in the same graph. Validates that text+graph hybrid works. [GitHub](https://github.com/AndrewRayCode/shaderfrog-2.0-hybrid-graph-demo)
- **NodeToy**: 150+ nodes, exports to Three.js/React Three Fiber/raw GLSL. [nodetoy.co](https://nodetoy.co/)
- **Shader Park**: JavaScript AST that compiles to GLSL SDF raymarching. Architecturally identical to joon's Lisp-to-compute pipeline. [shaderpark.com](https://shaderpark.com/)
- **KodeLife**: Real-time GPU shader editor supporting GLSL, Metal, HLSL. Compute shader support. [hexler.net/kodelife](https://hexler.net/kodelife)
- **Bonzomatic**: Live-coding shader tool for demoscene competitions. Compute shader fork exists. [GitHub](https://github.com/Gargaj/Bonzomatic)

### 5.4 Procedural Generation Systems

#### Wave Function Collapse (WFC)
Constraint-solving: propagate adjacency constraints from a sample. Two models: Overlapping (scan NxN patterns) and Simple Tiled (explicit adjacency rules). Maintains superposition per cell, collapses lowest-entropy cell, propagates. Used in Bad North, Townscaper, Caves of Qud. [GitHub](https://github.com/mxgmn/WaveFunctionCollapse) | [Boris the Brave: WFC Explained](https://www.boristhebrave.com/2020/04/13/wave-function-collapse-explained/)

#### L-Systems
Parallel rewriting grammars: alphabet, production rules, axiom. Turtle graphics interpretation maps symbols to drawing commands. Houdini has a built-in L-System SOP node. Graph grammars extend to polygon edges/vertices. [Wikipedia](https://en.wikipedia.org/wiki/L-system) | [Houdini L-System SOP](https://www.sidefx.com/docs/houdini/nodes/sop/lsystem.html)

#### Noise Functions
- **Perlin** (1983): Gradient noise, grid of random gradients, smoothstep interpolation.
- **Simplex** (2001): Simplicial grids, O(n^2) vs O(2^n), no directional artifacts.
- **Worley/Cellular** (1996): Distance to nearest feature point, cell-like patterns.
- **Value**: Random values at grid points with interpolation.
- All compose via octave summation (fBm) for multi-scale detail.

[Survey of Procedural Noise Functions (PDF)](https://www.cs.umd.edu/~zwicker/publications/SurveyProceduralNoise-CGF10.pdf) | [Book of Shaders: Noise](https://thebookofshaders.com/11/)

- **FastNoiseLite**: Portable library in C/C++/C#/Java/HLSL/GLSL/JS/Rust/Go. GLSL port suffers from branching that hurts shader performance. [GitHub](https://github.com/Auburn/FastNoiseLite)

### 5.5 Signed Distance Functions (SDFs)

Inigo Quilez's canonical reference: 50+ primitive distance functions, combination operators including smooth union (`smin`), smooth subtraction, smooth intersection with parameterized blending radius k. Polynomial kernels (quadratic, cubic, quartic, circular) clamp blend to finite radius. Domain repetition via `mod`, symmetry via `abs()`.

SDF operations map naturally to node graphs: primitives are leaf nodes, boolean/smooth ops are combining nodes, domain transforms are modifier nodes.

[iquilez.org: Distance Functions](https://iquilezles.org/articles/distfunctions/) | [iquilez.org: Smooth Minimum](https://iquilezles.org/articles/smin/)

**Relevance to joon**: `(smooth-union 0.3 (sphere 0.5) (box 1 1 1))` maps directly to an SDF combination. Each S-expression node compiles to a GLSL function call.

---

## 6. Demoscene & Real-Time Visual Tools

### 6.1 Werkkzeug / .kkrieger

Farbrausch's content creation system uses an **operator stack** architecture. KOps have a calling convention encoded as a 32-bit integer defining inputs, links, parameters, and string count. Categories: texture generators/filters/combiners, mesh generators/modifiers, scene operators. .kkrieger (2004) packed a full FPS into 96KB by storing assets as creation history (~2000:1 compression).

[farbrausch/fr_public](https://github.com/farbrausch/fr_public) | [GenThree Overview](https://fgiesen.wordpress.com/2012/04/15/genthree-overview/) | [DynamicSubspace: .kkrieger](https://dynamicsubspace.net/2024/07/30/kkrieger-a-demoscene-first-person-shooter-thats-only-96k/)

**Relevance to joon**: The operator stack is a postfix/concatenative evaluation -- the dual of joon's prefix Lisp. A joon graph file IS the creation history, with assets derived on demand.

### 6.2 Tooll3 / TiXL

Open-source real-time motion graphics. **Symbol/Instance** architecture: a Symbol defines an operator type (`.t3` graph + `.t3ui` visual + `.cs` C# implementation), Instances are runtime instantiations. Pull-based evaluation: outputs request updates via dirty flags; `EvaluationContext` propagates shared state (time, camera, resolution).

[GitHub](https://github.com/tixl3d/tixl) | [TiXL DeepWiki](https://deepwiki.com/tixl3d/tixl)

### 6.3 cables.gl

Web-based visual programming for WebGL/WebGPU. Typed ports: numbers, strings, booleans, textures, objects, arrays, and **trigger** signals. Trigger ports define execution order explicitly (like Unreal's exec pins). Data ports propagate changes automatically. Both WebGL and WebGPU backends.

[cables.gl](https://cables.gl) | [DeepWiki: Operators and Ports](https://deepwiki.com/cables-gl/cables/2.2-operators-and-ports)

### 6.4 vvvv

Two versions. **vvvv beta**: Single-threaded dataflow with automatic "spreading" (implicit iteration). **vvvv gamma** (2020): C#/.NET with VL (dataflow + functional + OOP with loops, if-regions, recursion, generics, interfaces). Multi-threaded. **VL.Fuse** -- visually programming on GPU: SDF, raymarching, particles, procedural geometry, textures, materials, GPGPU compute without writing shader code.

[visualprogramming.net](https://visualprogramming.net/) | [VL.Fuse](https://github.com/TheFuseLab/VL.Fuse)

**Relevance to joon**: VL.Fuse is the closest existing system to what joon aims to be. VL's evolution from implicit spreading (beta) to explicit loops (gamma) is a cautionary tale about implicit iteration semantics.

### 6.5 TouchDesigner

Six operator families handling different data domains:

| Family | Data Type | Example |
|--------|-----------|---------|
| **TOP** | 2D textures/images | Blur, Composite, GLSL |
| **CHOP** | Channels (floats over time) | Audio, LFO, Math |
| **SOP** | 3D geometry | Sphere, Transform, Noise |
| **DAT** | Text/tables | Script, Table, MIDI |
| **MAT** | Materials/shaders | Phong, PBR, GLSL |
| **COMP** | Containers/3D objects/UI | Geometry, Window |

Demand-based cooking (pull): operators only cook when something downstream needs their data AND inputs have changed. GLSL integration via Text DATs referenced by GLSL TOPs or GLSL Materials.

[Operator Families](https://docs.derivative.ca/Operator) | [Cook docs](https://docs.derivative.ca/Cook)

**Relevance to joon**: TouchDesigner's family-based type system is the most mature example of typed data flow.

### 6.6 Notch

Proprietary real-time VFX tool, natively GPU-accelerated. All rendering, simulation, compositing, and playback in real-time. [notch.one](https://www.notch.one/)

---

## 7. ComfyUI & Compositing Node Graphs

### 7.1 ComfyUI

#### Execution Model

PR #2666 inverted from pull-based to **front-to-back topological sort**. `ExecutionList` determines evaluation order. Three-tier caching: Classic, LRU, Dependency-aware. Nodes implement `IS_CHANGED` for cache invalidation. The inversion enables lazy evaluation -- e.g., a Mix node with factor 0.0 skips evaluating its second input.

[ComfyUI Execution Model Inversion](https://docs.comfy.org/development/comfyui-server/execution_model_inversion_guide)

#### Type System

Types: MODEL, CLIP, VAE, CONDITIONING, LATENT, IMAGE, MASK. Custom nodes declare types via:

```python
class MyNode:
    INPUT_TYPES = classmethod -> {"required": {"image": ("IMAGE",), "value": ("FLOAT", {"default": 1.0})}}
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("output",)
    FUNCTION = "process"
    CATEGORY = "custom"
```

Wildcard type (`"*"`) allows any connection but sacrifices safety. Dynamic Typing RFC (PR #5293) proposes improvement.

[ComfyUI Custom Nodes Guide](https://docs.comfy.org/custom-nodes/walkthrough) | [PR #5293](https://github.com/comfyanonymous/ComfyUI/pull/5293)

#### VRAM Management

Dynamic VRAM with fault-in tensors and VRAMState enumeration. GPU memory managed across the graph with automatic offloading.

#### Serialization

Dual JSON formats: workflow (includes visual layout, node positions) and API/prompt (minimal, for execution). Workflow spec at [docs.comfy.org/specs/workflow_json](https://docs.comfy.org/specs/workflow_json).

### 7.2 InvokeAI

`BaseInvocation`/`InputField`/`OutputField` system with Pydantic-to-OpenAPI-to-TypeScript type safety chain. [GitHub](https://github.com/invoke-ai/InvokeAI)

### 7.3 Nuke

Pull-based scanline/Row architecture. TCL expression language. **BlinkScript**: GPU compute kernels -- the most relevant Nuke feature for joon. Nuke 13.2 introduced top-down rendering for 20-200% speedup. Multiple cache layers: Viewer, Buffer, Disk.

[Foundry: Top-down Rendering](https://www.foundry.com/nuke-newsletter/top-down-rendering)

### 7.4 DaVinci Resolve Fusion

Fuse scripting with LuaJIT and OpenCL kernels. [Blackmagic Forum](https://forum.blackmagicdesign.com/)

### 7.5 Natron

OpenFX v1.4 host. C-based plugin API: host sends "actions" (C strings), plugins respond via "suites" (C struct function pointers). RAM/Disk cache. [OpenFX docs](https://openfx.readthedocs.io/en/main/)

### 7.6 Blender Compositor

Operation Domain concept. GPU real-time compositor since 4.2. Viewer node debugging. Write-once buffer semantics. ReadsOptimizer counts buffer reads, freeing memory when all readers finish.

---

## 8. Creative Coding Frameworks

### 8.1 Processing / p5.js

**p5.strands** lets you write shaders in JavaScript: functions build a graph of math operations that compiles to GLSL. The p5 team found that wrapping GLSL in visual nodes was "too verbose" and that a programmatic API was better. This validates joon's core thesis -- a text-based DSL can be more expressive than visual nodes.

[p5.strands blog](https://www.davepagurek.com/blog/writing-shaders-in-js/) | [p5.js strands tutorial](https://beta.p5js.org/tutorials/intro-to-p5-strands/)

### 8.2 Nannou (Rust)

Rust creative coding via WebGPU (wgpu-rs). Shader hot-loading, ISF pipeline support, SPIR-V compilation. [nannou.cc](https://nannou.cc/)

### 8.3 Three.js TSL (Three Shading Language)

JavaScript API building shaders as node graphs, compiling to WGSL (WebGPU) and GLSL (WebGL2). Automatic type coercion, temporary variable generation, dead code elimination. Two backends: `WGSLNodeBuilder` and `GLSLNodeBuilder`.

[TSL specification](https://threejs.org/docs/TSL.html) | [Three.js wiki: TSL](https://github.com/mrdoob/three.js/wiki/Three.js-Shading-Language)

**Relevance to joon**: TSL's architecture is the closest web-side analog. Both build node graphs from a high-level language, perform type inference, compile to GPU shader code. TSL's dual-backend shows joon could target multiple backends from one AST.

---

## 9. Lisp-Adjacent & Functional Shader Projects

Three projects bridge toward joon's Lisp-like approach:

- **Coollab**: Open-source generative art tool where links between nodes represent **passing functions, not data**. Enables higher-order operations like building fractal noise by passing a base noise function to a layering node. [Coollab](https://coollab-art.com/Articles/Alpaca) | [Alpaca Paper](https://alpaca.pubpub.org/pub/0iv3m8dt)

- **Shadergarden** (Tonari): Explicitly uses **Lisp/S-expressions** to represent GPU compute pipelines. The closest existing precedent to joon. [LISP.md](https://github.com/tonarino/shadergarden/blob/master/LISP.md) | [Blog](https://blog.tonari.no/shadergarden)

- **unconed/shadergraph**: "Functional GLSL Linker" treating shader snippets as composable functions. [GitHub](https://github.com/unconed/shadergraph)

---

# Part II: Single-Source GPU/CPU Programming

## 10. SYCL

SYCL (Khronos Group, current spec: SYCL 2020 rev 6) embeds heterogeneous device programming in ISO C++17. No separate shader language: kernels are C++ lambdas. The DPC++ compiler (Intel LLVM-based) performs split compilation: device compiler outlines kernel code, enforces restrictions (no exceptions, no virtual calls, no RTTI), emits LLVM IR lowered to SPIR-V. A `sycl-post-link` tool splits SYCL and ESIMD entry points.

**Two memory models**: Buffer/accessor (runtime manages dependency graph and data migration) and USM (raw pointers via `malloc_shared`/`malloc_device`, programmer manages dependencies). CPU fallback supported.

[Khronos SYCL](https://www.khronos.org/sycl/) | [DPC++ Architecture](https://intel.github.io/llvm/design/CompilerAndRuntimeDesign.html) | [AdaptiveCpp](https://github.com/AdaptiveCpp/AdaptiveCpp)

---

## 11. rust-gpu

Compiles standard Rust (`no_std`) to SPIR-V. `spirv-builder` crate invokes `rustc` with `rustc_codegen_spirv` backend. A shared crate can define structs imported on both CPU and GPU sides. Entry points annotated with `#[spirv(compute(threads(64)))]`, parameters with `#[spirv(push_constant)]` or `#[spirv(storage_buffer)]`. GPU crates must be `no_std`/`no_alloc`.

Transitioned to community ownership after Embark Studios archived (Oct 2025). Focus shifting toward GPGPU/compute.

[GitHub](https://github.com/Rust-GPU/rust-gpu) | [Sharing types](https://dev.to/bardt/sharing-types-between-wgpu-code-and-rust-gpu-shaders-17c4) | [Transition announcement](https://rust-gpu.github.io/blog/transition-announcement/)

**Relevance to joon**: The shared-types-in-one-workspace model could allow joon's node types to be defined once and compiled to both SPIR-V and native code. The SPIR-V output is directly consumable by joon's Vulkan pipeline.

---

## 12. CUDA Unified Programming

Functions annotated `__host__ __device__` compile for both CPU and GPU. NVCC splits `.cu` files into host and device streams. Unified Memory (`cudaMallocManaged()`) provides pointers valid on both sides with fault-and-migrate on Pascal+ GPUs. Cooperative Groups enable flexible thread synchronization. Dynamic Parallelism allows GPU kernels to launch child kernels.

[NVIDIA: Unified Memory](https://developer.nvidia.com/blog/unified-memory-cuda-beginners/) | [Cooperative Groups](https://developer.nvidia.com/blog/cooperative-groups/)

---

## 13. Other Single-Source Approaches

| Approach | Model | Key Feature |
|----------|-------|-------------|
| **Futhark** | Purely functional array language | Compiler manages CPU/GPU boundary, aggressive fusion |
| **Julia GPU** | `@cuda` kernels via LLVM JIT | `KernelAbstractions.jl` for portable GPU code |
| **Numba** | `@cuda.jit` Python decorator | JIT Python to PTX |
| **Chapel** | `on here.gpus[0]` locale model | `forall` loops compile to GPU kernels |
| **Kokkos** | `parallel_for` with `KOKKOS_LAMBDA` | Execution spaces + memory spaces abstraction |
| **RAJA** | Compute abstractions + Umpire/CHAI | Similar to Kokkos, HPC focus |
| **Metal/MSL** | C++-based shader language | Metal 4 adds tensor types, ML command encoders |
| **WebGPU/WGSL** | Shaders as strings to `createShaderModule()` | Minimal, safe, strict type checking |

---

## 14. Implications for Joon

Three viable evolutionary paths:

1. **Stay with separate GLSL shaders** (current). Simple, maintainable. Cost: parallel type definitions in C++ and GLSL.

2. **Direct SPIR-V generation**. Joon's compiler emits SPIR-V directly instead of GLSL text + `glslc`. Enables operation fusion, memory access optimization, specialization constants without text manipulation. Libraries: SPIRV-Tools, SPIRV-Cross.

3. **Embed a single-source model**. For CPU fallback/preview, rust-gpu's shared types or Futhark's compiler-managed boundary would be the natural fit. SYCL/Kokkos add too much toolchain complexity.

**Strongest recommendation**: Futhark's compiler-managed boundary and automatic fusion are the most relevant architectural precedent. rust-gpu's shared-type model is the most relevant implementation technique if cross-compilation is considered.

| Concern | SYCL | rust-gpu | CUDA | Futhark | Kokkos |
|---------|------|----------|------|---------|--------|
| Type sharing | Same C++ types | Shared Rust crate | `__host__ __device__` structs | Compiler-managed opaque | `Kokkos::View` |
| Memory mgmt | Buffer/accessor or USM | Host via wgpu/ash | `cudaMallocManaged` | Fully automatic | Memory spaces |
| Vendor portability | Intel, NVIDIA, AMD | Any Vulkan GPU | NVIDIA only | OpenCL/CUDA/multicore | CUDA, HIP, SYCL, OpenMP |
| CPU fallback | Host device | Software rasterizer | None | Multicore C backend | OpenMP/threads |

---

# Part III: Feature Deep-Dives

## 15. Polymorphic Nodes & Type Systems

### How Different Systems Handle Polymorphism

**Blender**: Separates scalar and vector math into distinct node types. Vector Math node has a dropdown selecting operation; output socket type changes accordingly. Compile-time resolution via enum.

**Unity Shader Graph**: **Dynamic Vector** ports adapt to connected type. All connected Dynamic Vector ports truncate to the lowest dimension (unless dimension is 1, then scalar is promoted). The Multiply node is a special case allowing both Dynamic Matrix and Dynamic Vector.

[Unity Docs: Data Types](https://docs.unity3d.com/Packages/com.unity.shadergraph@6.9/manual/Data-Types.html)

**Houdini VOPs**: Explicitly typed. VEX requires the programmer to set expected types. Conversion nodes for dimension changes. No inference.

**Unreal Engine**: Blueprint system supports **wildcard pins** that resolve on connection. Once resolved, siblings update to same type. Material editor: float4->float3 implicit on specific inputs.

[UE5 Wildcard Pins](https://www.pome.cc/en/posts/wildcardinput/)

**Godot**: Port expansion: Boolean becomes `0`/`1` as scalar or `(0,0,0)`/`(1,1,1)` as vector.

**ComfyUI**: Wildcard type `"*"` allows any connection but produces runtime errors on mismatch. V3 API adds type-safe wrappers. Dynamic Typing RFC (PR #5293) in progress.

**TouchDesigner**: Family-level type enforcement. Same-family only wires. Cross-family via explicit conversion operators.

**vvvv gamma/VL**: Static typing with inference, generics, interfaces. Smaller integer types auto-promote to larger.

---

## 16. Type Coercion & Implicit Conversion

### GLSL vs HLSL Rules

**GLSL**: Strict. `x + 1` is illegal if x is float (must be `x + 1.0`). Scalar-vector multiplication works. Signed->unsigned, int->float, int/float->double implicit. No cross-dimension vector promotion.

**HLSL**: Permissive. Scalar-to-vector promotion implicit. Per-component math is the default.

This distinction is critical for joon's code generation -- targeting GLSL compute requires emitting explicit casts.

[GLSL Operators](http://learnwebgl.brown37.net/12_shader_language/glsl_mathematical_operations.html) | [HLSL Per-Component Math](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-per-component-math)

### Conversion Rules Across Implementations

| System | Float->Vector | Vector->Float | Color->Float | Missing Dims |
|--------|--------------|---------------|--------------|--------------|
| Blender | Fill all components | Average (x+y+z)/3 | Luminance weighted | N/A |
| Unity | Fill with (0,0,0,1) | Truncate | N/A | (0,0,0,1) |
| Houdini VEX | Component-wise | First component only | N/A | N/A |
| Substance | Explicit node required | Explicit node required | N/A | N/A |
| Unreal | Error (arithmetic) | N/A | N/A | Float4->Float3 drops alpha |
| Godot | Scalar expansion | Port expansion | N/A | N/A |

---

## 17. Color Spaces & Color Management

### The sRGB/Linear Fundamental

All mathematical operations on pixel data produce physically correct results **only in linear space**. The sRGB transfer function (IEC 61966-2-1) is piecewise: linear below 0.04045, then `((x + 0.055) / 1.055)^2.4` above. In GLSL:

```glsl
vec3 srgbToLinear(vec3 s) {
    return mix(s / 12.92,
               pow((s + 0.055) / 1.055, vec3(2.4)),
               step(vec3(0.04045), s));
}
```

Rule: Color textures (diffuse/albedo) stored in sRGB. Data textures (normal, roughness) always linear.

[NVIDIA GPU Gems 3, Ch. 24](https://developer.nvidia.com/gpugems/gpugems3/part-iv-image-effects/chapter-24-importance-being-linear) | [LearnOpenGL: Gamma Correction](https://learnopengl.com/Advanced-Lighting/Gamma-Correction)

### ACES & ACEScg

**ACEScg**: Scene-linear with AP1 wide-gamut primaries, gamma 1.0, using half-float EXR. AP1 primaries are all non-negative, unlike ACES2065-1's imaginary blue. The VFX industry standard working space.

[ACEScg Docs](https://docs.acescentral.com/encodings/acescg/) | [Frame.io Guide to ACES](https://blog.frame.io/2019/09/09/guide-to-aces/)

### OpenColorIO (OCIO)

YAML config defining named color spaces, roles, file rules, view transforms. OCIO v2 generates GPU shader code (GLSL/HLSL) implementing transforms with 1D/3D LUT textures at runtime.

[OCIO Config Syntax](https://opencolorio.readthedocs.io/en/latest/guides/authoring/overview.html) | [OCIO Shaders API](https://opencolorio.readthedocs.io/en/latest/api/shaders.html)

### How Major Tools Handle Color

| Tool | Working Space | Color/Data Distinction | OCIO | View Transform |
|------|--------------|----------------------|------|---------------|
| **Blender** | Linear BT.709 (or XYZ with AgX) | "Color" vs "Non-Color" sockets | Yes | AgX (16.5 stops), ACES 1.3/2.0 |
| **Nuke** | `scene_linear` role | Colorspace knob per Read node | Yes (primary) | Per output |
| **Substance** | Linear RGB (with OCIO) | Color vs Data outputs | Yes (since 2021) | sRGB default |
| **Houdini** | ACES 1.0 config | File COP auto-linearize | Yes | COPs output limited |
| **Photoshop** | ICC profile (sRGB/AdobeRGB/ProPhoto) | Bit-depth modes | OCIO (since 2022) | ICC based |
| **GIMP/babl** | Linear sRGB (via babl) | Format strings encode TRC | Via babl formats | sRGB display |
| **Unreal** | sRGB Linear (or ACEScg) | sRGB checkbox on textures | Since 4.26 | ACES Filmic |
| **Resolve** | DaVinci Wide Gamut | CST nodes | Via ACES mode | Per output |

### Color Models Beyond RGB

- **HSV/HSL**: Intuitive but flawed -- changing saturation alters perceptual lightness, interpolation produces hue shifts.
- **Oklab/OKLCH** (Bjorn Ottosson, 2020): Perceptually uniform, CSS standard for color interpolation and gamut mapping. Smooth gradients without muddy midpoints. [Oklab Wikipedia](https://en.wikipedia.org/wiki/Oklab_color_space)
- **CIE Lab**: Perceptually uniform, supported natively by babl.
- **YCbCr/YUV**: Luma/chroma separation. BT.601/709/2020 use different coefficient matrices (3x3 multiply in shader).
- **Spectral**: RGB is fundamentally a tristimulus approximation. Mitsuba 3 supports spectral rendering.

### HDR & Extended Range

Float pixel data allows values outside [0,1]. OpenEXR (half/float) is the standard interchange. Tone mapping compresses HDR to displayable range -- must be the last step, never applied to intermediates.

### Color in Vulkan Compute Shaders

**Critical**: `VK_FORMAT_*_SRGB` formats do NOT support `VK_IMAGE_USAGE_STORAGE_BIT` on most hardware. Workaround: create `_UNORM` image for storage, do sRGB conversion manually in shader, reinterpret as `_SRGB` for sampling.

**Precision**: fp16 halves register usage and doubles throughput. ~3 decimal digits, max 65504. Use fp16 for bandwidth-bound color ops, fp32 for accumulation.

[AMD GPUOpen: FP16](https://gpuopen.com/learn/first-steps-implementing-fp16/) | [Vulkan 16-bit Arithmetic](https://docs.vulkan.org/samples/latest/samples/performance/16bit_arithmetic/README.html)

### Recommendations for Joon

1. **Adopt a single linear working space.** Linear sRGB (BT.709, D65) as default. Matches Nuke, Blender, Vulkan common formats.
2. **Linearize on input, encode on output.** `load-image` converts; `save-image`/display converts back.
3. **Distinguish color from data.** Tag images as "color" (apply transfer function on load) or "data" (passthrough).
4. **Color literals as sRGB stored linear.** `(color 0.8 0.2 0.1)` interpreted as sRGB, stored linear internally.
5. **Manual sRGB conversion in compute shaders.** Compiler emits piecewise conversion automatically for sRGB-tagged textures.
6. **Start simple, add OCIO later.** Hardcode sRGB transfer function + a few 3x3 matrices (sRGB-to-XYZ, XYZ-to-ACEScg).

---

## 18. Node Resolution & Tiling

### Substance Designer

Three inheritance methods: **Relative to Parent** (from parent graph), **Relative to Input** (from connected input), **Absolute** (fixed). Logarithmic modifier (-12 to +12, each step doubles/halves). Performance: lowest resolution needed for desired result.

[Adobe: Output Size](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/output-size.html)

### Nuke

Merge node bbox options: Union, Intersection, A, B. Best practice: Reformat inputs after Read nodes.

### Blender Compositor

Most nodes produce output matching first input's size. Mixing sizes requires explicit Scale nodes.

### Houdini COPs

Default to first input's resolution. Masks optionally scaled via parameter.

### Tiling for GPU

Divide images into fixed tiles (16x16 or 32x32), dispatch one workgroup per tile. Bounds intermediate memory to tile size, critical for large textures exceeding VRAM.

---

## 19. Evaluation Order & Caching

### Topological Sort

All DAG systems use topological ordering. Kahn's algorithm (remove zero in-degree nodes) or DFS-based (post-order + reverse).

### Dirty Propagation

When an input changes, mark downstream nodes for recomputation via transitive dirty propagation.

[Game Programming Patterns: Dirty Flag](https://gameprogrammingpatterns.com/dirty-flag.html)

### Pull-Based vs Push-Based

| System | Model | Notes |
|--------|-------|-------|
| Houdini | Pull | UI expresses interest; dirtied nodes notify consumers |
| TouchDesigner | Pull | Only cook when downstream needs data |
| Nuke (13.2+) | Push (top-down) | 20-200% speedup over scanline pull |
| ComfyUI | Push (front-to-back) | Topological sort, lazy evaluation |
| Blender | Pull (lazy-function) | Compute only necessary data |
| TiXL | Pull | Dirty flags + UpdateAction |

### Cycle Prevention

All systems enforce DAG structure. Cycles rejected at connection time.

---

## 20. Graph Serialization & File Formats

| Tool | Format | Human-Readable | Diffable |
|------|--------|---------------|----------|
| Blender .blend | Binary (MemFile) | No | No |
| Houdini .hip | Binary (text export available) | Partially | With effort |
| Substance .sbs | XML | Yes | Verbose |
| ComfyUI | JSON | Yes | Yes |
| MaterialX .mtlx | XML | Yes | Yes |
| OSL .osl | Text (C-like) | Yes | Yes |
| USD | Binary or ASCII | ASCII option | With ASCII |
| **Joon .jn** | **S-expressions** | **Yes** | **Yes** |

Joon's S-expression format is a significant advantage: human-readable, diffable, version-control friendly. The source IS the graph definition.

[ComfyUI Workflow JSON](https://docs.comfy.org/specs/workflow_json) | [MaterialX Specification](https://github.com/AcademySoftwareFoundation/MaterialX/blob/main/documents/Specification/MaterialX.Specification.md)

---

## 21. Node Groups / Subgraphs / Encapsulation

| Tool | Mechanism | Semantics | Distribution |
|------|-----------|-----------|-------------|
| Blender | Group Nodes | Ctrl+G creates group with exposed I/O | Within .blend |
| Houdini | HDAs | Locked, versioned (e.g., `mynode::2.0`) | .hda files |
| Substance | Graph Instances | Subgraphs as reusable nodes | Within .sbs/.sbsar |
| Unreal | Material Functions | Assets with FunctionInput/Output nodes | Asset references |
| ComfyUI | N/A (flat graphs) | No native subgraphs | N/A |

**Mapping to joon**: Subgraphs = function definitions:
```lisp
(defn my-filter (input:IMAGE threshold:FLOAT)
  (threshold (blur input 2.0) threshold))
```

Key design choices: inline vs reference semantics, recursive nesting (all tools support it), parameter exposure.

---

## 22. Animation & Time

**Houdini**: `$F` (frame), `$FF` (fractional frame), `$T` (time seconds). Any parameter can reference these. CHOPs handle animation channels.

**Blender**: F-Curves (Constant/Linear/Bezier interpolation). Drivers: expression-based animation referencing other properties.

**After Effects**: JavaScript expressions. `time`, `wiggle(freq,amp)`, `loopOut()`, `valueAtTime(t)`.

**Relevance to joon**: Expose `$t` (seconds) and `$frame` (integer) as built-in variables. Keyframes could use:
```lisp
(def opacity (keyframes :bezier [0 0.0] [30 1.0] [60 0.0]))
(threshold input (at opacity $frame))
```

Temporal operations (frame differencing, motion blur) require the evaluator to request multiple time samples, with significant pipeline implications.

---

## 23. Debugging & Inspection

| Tool | Mechanism | Notes |
|------|-----------|-------|
| Blender | Viewer Node (Shift+Ctrl+Click) | Socket values shown inline |
| Substance | 2D preview on every node | Click for full-size |
| Nuke | Viewer + wipe (A/B comparison) | Split-screen, 10 inputs |
| Houdini | Geometry Spreadsheet | Tabular attribute inspection |
| TouchDesigner | Per-operator preview | Family-specific visualization |

**Recommendations for joon**:
1. Click-to-preview on any node (display IMAGE in viewport)
2. Value inspection on non-image sockets (show float/vec inline)
3. Per-node compute timing via Vulkan timestamp queries
4. Split-screen comparison mode

---

## 24. Extensibility & Plugin Systems

| Tool | API | Language | Registration |
|------|-----|----------|-------------|
| Blender | `bpy.types.Node` subclass | Python | `class_name` auto-register |
| Houdini | HDAs (version-controlled, lockable) | VEX/Python/C++ | .hda files |
| OpenFX (Nuke/Natron/Resolve) | C suites | C | Actions/suites |
| ComfyUI | Python class with INPUT_TYPES/RETURN_TYPES | Python | NODE_CLASS_MAPPINGS dict |

**Recommendations for joon**: Three tiers:
1. `.jn` functions (simplest -- a file IS a plugin)
2. `.comp` shaders with metadata (I/O declarations)
3. C++ compiled plugins with C API (like OpenFX, for performance)

---

## 25. Expression Languages Within Node Graphs

| Tool | Language | Pattern |
|------|----------|---------|
| Houdini | VEX wrangle nodes | `@P.y += sin(@Frame * 0.1);` per-element |
| Nuke | TCL expressions | `nodename.knobname`, `frame`, conditional |
| Blender | Driver expressions | Reference other properties, frame |
| Substance | Pixel Processor functions | Per-pixel, `$pos`/`$size` variables |
| After Effects | JavaScript | `time`, `wiggle()`, `loopOut()` |

Joon IS an expression language, so the "escape hatch" is built in. A `(pixel-fn ...)` form could compile to inline GLSL:
```lisp
(pixel-fn input (fn [pos color]
  (vec4 (- 1.0 (.r color)) (- 1.0 (.g color)) (- 1.0 (.b color)) (.a color))))
```

---

## 26. Parameter Ranges & Validation

All major systems converge on a two-tier model:

| System | Soft Limits | Hard Limits |
|--------|------------|-------------|
| Blender | `soft_min`/`soft_max` (slider range) | `hard_min`/`hard_max` (absolute, clamped) |
| Substance | Soft Range (cosmetic) | Hard Range (clamped) |
| Houdini | `PRM_Range` UI-limited | Hard-limited ranges |

---

## 27. Configurable Nodes with Variable Inputs

- **Blender**: Vector Math dropdown changes output socket type. Built-in nodes support dynamic socket counts.
- **Substance**: Blend mode dropdown. Inputs switch grayscale/color based on connections.
- **XOD**: Variadic nodes: users add/remove similar input pins dynamically.
- **Houdini APEX**: Variadic ports create subports as connections are made.

---

## 28. Multi-Output Nodes & Data Routing

- **Multi-output**: Separate RGB (1 IMAGE -> 3 FLOATs), Separate XYZ (1 VEC3 -> 3 FLOATs)
- **Switch/mux**: ComfyUI `ImpactSwitch`, selector-based routing
- **Reroute/relay**: Blender reroute node (visual redirect, no data change)
- **Frame/backdrop**: Visual containers for organization
- **Fan-out**: Universal. Source evaluated once, result shared.

In joon: `(let [r g b] (separate-rgb img))`. Switch: `(switch condition a b)`.

---

## 29. LOD & Progressive Rendering

**Substance**: "Relative to Parent" with logarithmic modifier (-12 to +12). Changing document resolution propagates without information loss.

**Progressive refinement**: Evaluate at 1/4 or 1/8 for interactive preview, full resolution on demand. Mipmap generation can be a graph operation node.

**Recommendation for joon**: Resolution context propagates through graph. GUI "preview quality" slider sets base resolution. Evaluator invalidates cached results on resolution change.

---

## 30. Collaboration & Version Control

**The binary format problem**: Blender `.blend` and Houdini `.hip` make git diffs meaningless and merges impossible.

**Text-based advantage**: Joon's S-expression files produce clean diffs, support merge tools, and can be reviewed in PRs.

**NodeGit** (Rinaldi et al., ACM TOG 2023): Algorithm for diffing and merging node graphs directly -- computing graph edit distance. [ACM Paper](https://dl.acm.org/doi/10.1145/3618343) | [GitHub](https://github.com/edu-rinaldi/NodeGit)

**Houdini Takes**: Parameter overrides as named layers. A "take" records only differing parameters.

**Recommendations for joon**:
1. Stable node ordering in DSL (avoid spurious diffs)
2. Separate GUI layout metadata from semantic graph data (e.g., `.jn.layout` companion file)
3. Consider a "take"-like override system for parameter variations

---

# Appendix: Key Academic Papers

| Paper | Venue | Relevance |
|-------|-------|-----------|
| Ragan-Kelley et al., "Halide: Optimizing Parallelism, Locality, and Recomputation" | PLDI 2013 | Algorithm/schedule separation |
| Adams et al., "Learning to Optimize Halide with Tree Search" | 2019 | Autoscheduling for GPU |
| Chen et al., "TVM: End-to-End Optimizing Compiler for Deep Learning" | OSDI 2018 | Two-level IR + autotuning |
| Zheng et al., "Ansor: Generating High-Performance Tensor Programs" | OSDI 2020 | Automatic search space generation |
| Hu et al., "Taichi: High-Performance Computation on Sparse Data" | SIGGRAPH 2019 | Megakernel fusion, SNode layout |
| Henriksen et al., "Futhark: Purely Functional GPU-Programming" | PLDI 2017 | Functional GPU + flattening |
| He et al., "Slang: Language Mechanisms for Extensible Shading" | SIGGRAPH 2018 | Generics + interfaces in shaders |
| Pharr & Mark, "ispc: A SPMD Compiler for CPU Programming" | InPar 2012 | SPMD-on-SIMD model |
| Rinaldi et al., "NodeGit: Diffing and Merging Node Graphs" | ACM TOG 2023 | Version control for node graphs |
