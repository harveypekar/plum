# Node-Based and Graph-Based Processing Systems in GIS

**Date:** 2026-04-04
**Context:** Research for Joon -- a Lisp-style DSL that compiles to a Vulkan compute node graph for image processing. This survey examines how Geographic Information Systems represent and execute processing graphs, with attention to evaluation models, type systems, expression languages, and GPU acceleration.

---

## 1. QGIS Processing Framework and Graphical Modeler

### Processing Architecture

The QGIS Processing Framework is a geoprocessing pipeline that unifies algorithms from multiple backends -- QGIS native, GDAL/OGR, GRASS GIS, and SAGA -- behind a single API [1][2]. Each algorithm is a class inheriting from `QgsProcessingAlgorithm` with a rigid lifecycle: `initAlgorithm()` declares typed inputs and outputs, and `processAlgorithm()` executes the computation [3]. Algorithms are registered in providers (e.g., `QgsNativeAlgorithms`, the GDAL provider) and exposed through the Processing Toolbox.

The Graphical Modeler (called "Model Designer" from QGIS 3.14+) allows users to visually chain algorithms into a directed acyclic graph. Each node in the model is either an input parameter or an algorithm invocation. Edges are implicit: when an algorithm's input is set to "the output of algorithm X," a dependency edge is created. The model enforces DAG semantics -- circular dependencies are rejected. Execution proceeds by topological traversal; each algorithm runs only after all its upstream dependencies have completed [1][4].

Models are serializable as `.model3` files (an XML-based format) and can be nested: a saved model appears in the algorithm tree and can be used as a sub-node inside a larger model, enabling hierarchical composition [1].

### Type System

Processing parameters are strongly typed. The API defines parameter types including `QgsProcessingParameterRasterLayer`, `QgsProcessingParameterFeatureSource` (vector), `QgsProcessingParameterNumber`, `QgsProcessingParameterCrs`, `QgsProcessingParameterExtent`, and `QgsProcessingParameterFeatureSink`. Inside `processAlgorithm()`, typed accessors like `parameterAsRasterLayer()`, `parameterAsDouble()`, and `parameterAsSource()` convert raw parameter values to QGIS classes [3]. This parameter type system is what constrains which outputs can legally connect to which inputs in the graphical modeler.

### QGIS Expressions Language

Separate from the raster calculator, QGIS has a general-purpose expression language used in labeling, symbology, field calculation, and now in processing filters. It supports three primitive types (number, string, boolean), plus geometry and date/time types. The function library is extensive: math (`sqrt`, `sin`, `cos`, `ln`), string manipulation (`concat`, `regexp_match`), geometry operations (`buffer`, `transform`, `$area`, `intersection`), aggregate functions (`sum`, `mean` over features), conditionals (`if(condition, then, else)`, `CASE WHEN`), and array/map operations [5][6]. Custom functions can be registered in Python. Expressions are parsed into an AST and evaluated per-feature or per-pixel depending on context.

### Raster Calculator

The QGIS Raster Calculator implements a simple map algebra language. Raster bands are referenced as `layer_name@band_number` (e.g., `DEM@1`). Supported operators: arithmetic (`+`, `-`, `*`, `/`, `^`), comparison (`=`, `!=`, `<`, `>`, `<=`, `>=`), logical (`AND`, `OR`), and functions (`sin`, `cos`, `tan`, `atan2`, `ln`, `log10`, `abs`, `min`, `max`). Conditionals use `IF(condition, then, else)` syntax. The calculator evaluates eagerly, producing a new raster file on disk [7][8]. There is also a virtual raster provider approach (QEP, not yet standard) that would allow lazy/on-the-fly evaluation of raster expressions without writing intermediate files [9].

### GPU Acceleration

QGIS has an optional OpenCL acceleration framework introduced in QGIS 3.2 via QEP-121 [10][11]. The initial implementation ported the hillshade and slope algorithms to OpenCL kernels, demonstrating approximately 4x speedup. The framework is opt-in (activated in settings) and supports AMD, NVIDIA, and Intel GPUs via their OpenCL drivers. A third-party plugin, CUDA Raster, provides NVIDIA-specific GPU raster calculations [12]. Coverage remains limited compared to the full algorithm library.

---

## 2. ArcGIS ModelBuilder and Raster Function Chains

### ModelBuilder as a Directed Graph

ModelBuilder is Esri's visual programming environment for geoprocessing workflows in ArcGIS Pro [13][14]. A model is a diagram of *processes*, where each process is a triple: input data (blue oval), tool (yellow rectangle), and output data (green oval). Outputs from one process feed as inputs to the next, forming a directed graph. The diagram is not merely documentation -- it is the executable representation. Models can be saved as `.atbx` toolbox items and called from Python via `arcpy` [14].

### Variables, Iterators, and Branching

ModelBuilder supports inline variable substitution: `%VariableName%` syntax interpolates variable values into tool parameter strings [15]. System variables include `%n%` (iteration counter) and `%t%` (timestamp). Iterators allow looping over feature classes, rasters, field values, or numeric ranges within a model -- though only one iterator is permitted per model level. Branching uses if-then-else logic: a `Calculate Value` tool produces a boolean, and downstream processes have preconditions gating their execution on that boolean [15][16].

### Raster Function Chains (Lazy Evaluation)

ArcGIS raster functions are a fundamentally different processing paradigm from geoprocessing tools. Raster functions apply processing *on the fly*: calculations execute only on the pixels currently being displayed or exported, with no intermediate datasets written to disk [17][18]. This is a form of lazy evaluation -- the processing is deferred until pixels are actually requested by the renderer or an export operation.

The **Raster Function Editor** is a visual graph editor for building function chains. Functions are nodes; connecting the output of one function to the input of another wires the internal processing pipeline. Chains are saved as **Raster Function Templates** (`.rft.xml`) and can be applied to mosaic datasets, image services, or individual rasters [18][19]. Esri maintains a public repository of community-contributed function chains [20].

Custom raster functions can be implemented in Python by extending the raster function framework, with `NumPy` arrays as the pixel data interchange format [20].

### GPU Processing

ArcGIS Pro's Spatial Analyst supports GPU-accelerated execution for specific tools, requiring NVIDIA GPUs with CUDA compute capability 5.2 or higher [21]. The GPU path divides the raster into tiles, dispatches them to the GPU for parallel computation, and reassembles results. Supported tools include focal statistics, distance accumulation, viewshed, and several interpolation methods. The acceleration is transparent: the same tool parameters apply whether executing on CPU or GPU [21].

### Cloud Raster Format (CRF)

Esri's Cloud Raster Format is a tiled, distributed-storage raster format optimized for multidimensional data (time series of satellite imagery, for example). CRF stores processing templates alongside the data, enabling published image services to apply raster function chains on the fly without pre-computing results [22]. This makes CRF a vehicle for deferred computation in cloud-hosted geospatial workflows.

---

## 3. GRASS GIS

### Module System

GRASS GIS follows a Unix philosophy: each operation is a standalone module (executable) that reads from and writes to the GRASS mapset database. Modules are prefixed by data type -- `r.` for raster, `v.` for vector, `i.` for imagery, `t.` for temporal. Chaining modules together happens at the shell level or via Python scripting with `grass.script` [23].

### r.mapcalc: The Raster Expression Language

`r.mapcalc` is GRASS's raster map calculator and one of the oldest map algebra implementations, directly descended from Dana Tomlin's Map Analysis Package (MAP) developed at Yale in the late 1970s [24][25]. It implements a small but complete expression language.

**Data types**: `int` (32-bit, with -2,147,483,648 reserved for NULL), `float` (32-bit IEEE 754), and `double` (64-bit IEEE 754). Type promotion follows C conventions [24].

**Operators**: arithmetic (`+`, `-`, `*`, `/`, `%`), comparison (`==`, `!=`, `>`, `>=`, `<`, `<=`), logical (`&&`, `||`), bitwise (`<<<`, `>>>`, `&&&`, `|||`), ternary conditional (`condition ? true_expr : false_expr`), and unary negation [24].

**Functions**: `abs()`, `exp()`, `log()`, `sqrt()`, `sin()`, `cos()`, `tan()`, `asin()`, `acos()`, `atan()`, `int()`, `float()`, `double()`, `round()`, `if(condition, then, else)`, `isnull()`, `null()`, `max()`, `min()`, `median()`, `mode()`, `nmax()`, `nmin()`, `rand()`, `graph()`, `eval()` [24].

**Neighborhood modifier**: The syntax `map[row_offset, col_offset]` accesses relative pixel positions. For instance, `elevation[0,1]` reads the cell one column to the right. This permits convolution-style neighborhood filters to be expressed directly in the map algebra language, without a separate filtering module [24][26]. This is a notable feature -- most other raster calculators operate strictly per-pixel and require separate tools for neighborhood operations.

**NULL handling**: `isnull(map)` tests for NULL; `null()` produces a NULL value. All arithmetic with NULL propagates NULL [24].

**Evaluation**: `r.mapcalc` evaluates eagerly. It reads input rasters, applies the expression cell-by-cell (respecting the current computational region), and writes a new output raster. The computational region -- a rectangular extent and resolution set by `g.region` -- controls alignment, ensuring all inputs are resampled to the same grid before the expression evaluates [23][24].

### 3D Extension

`r3.mapcalc` extends the same expression language to 3D raster (voxel) data, with a third depth index in the neighborhood modifier: `map[row, col, depth]` [27].

### Temporal Framework

The temporal framework (`t.*` modules) manages space-time datasets -- collections of rasters registered with timestamps. `t.rast.mapcalc` applies r.mapcalc-style expressions across temporal datasets, with additional temporal variables: `td()` (time interval size in days) and `start_time()` (offset from dataset start). It supports parallel execution via the `nprocs` parameter [28][29].

### Python Scripting

The `grass.script` module provides Python bindings: `grass.script.run_command()` calls any GRASS module, `grass.script.raster.mapcalc()` wraps r.mapcalc, and `grass.script.array` provides NumPy interop for direct raster data manipulation [23].

---

## 4. Google Earth Engine

### Server-Side DAG and Lazy Evaluation

Google Earth Engine (GEE) is the most thoroughgoing implementation of lazy evaluation in the GIS domain [30][31]. When a user writes Python or JavaScript code using the `ee` library, no computation happens locally. Every `ee.*` object is a **proxy** -- a lightweight client-side handle representing a node in a server-side computation graph. For example, `ee.Image('LANDSAT/LC08/...')` does not fetch any pixels; it creates a JSON description of a data access node [32][33].

The client library encodes the entire script as a directed acyclic graph of `Invocation` objects, each specifying a function name and named arguments. This JSON DAG is sent to Google's servers only when the user explicitly requests a result via `.getInfo()` (synchronous), `Map.addLayer()` (display), or `Export.*` (batch) [32][33]. Until that point, the computation is purely symbolic.

This is deferred execution in the precise functional programming sense. GEE's documentation explicitly states that it leverages referential transparency and lazy evaluation for optimization: the server can reorder operations, eliminate dead branches, cache intermediate results across users, and only compute the tiles actually needed for the requested output extent and resolution [30][33].

### Functional Programming Paradigm

GEE's API enforces a functional paradigm [34]. Collections are transformed via `map()`, `filter()`, and `reduce()` -- higher-order functions that return new collections. Side effects are impossible because all `ee` objects are immutable server-side descriptions. The recommended pattern is to avoid for-loops entirely: instead of iterating and mutating, users compose transformations functionally [34][35].

**Reducers** are first-class objects that aggregate data across dimensions: `imageCollection.reduce()` collapses time, `image.reduceRegion()` collapses space, `image.reduceNeighborhood()` applies focal operations, and `image.reduce()` collapses bands. A single reducer (e.g., `ee.Reducer.mean()`) is automatically replicated across bands when applied to a multi-band image [36].

### Scale and Projection Handling

GEE handles scale and projection lazily. Composite images (results of reducing a collection) have no fixed projection; they default to WGS-84 at 1-degree resolution as a placeholder. When the computation is actually triggered -- by display, export, or `reduceRegion()` -- the system reprojects and resamples to whatever output CRS and scale the request demands [35][36]. This means the same computation graph can produce results at different resolutions without modification, a property that directly parallels how Joon's resolution-independent node graph could work.

### Relevance to Joon

GEE's architecture is the closest existing system to what Joon implements: a client-side DSL that builds a symbolic computation graph, evaluated lazily by a backend runtime. The key differences are that GEE's backend is a cloud cluster (not a local GPU), GEE's DAG is serialized as JSON (not compiled to SPIR-V), and GEE has no user-visible compilation step. But the conceptual model -- proxy objects, deferred evaluation, functional composition, resolution-independent computation -- maps almost directly.

---

## 5. Other GIS-Relevant Systems

### GDAL Virtual Raster (VRT) and Raster Pipelines

GDAL's Virtual Raster format (VRT) is an XML document describing a virtual mosaic or transformation of source rasters, evaluated lazily when pixels are read [37]. VRTs can be nested: a VRT can reference other VRTs as sources, creating implicit processing chains.

Starting with GDAL 3.9, a **VRT Processed Dataset** variant supports explicit processing chains defined in XML. Steps are applied sequentially to all bands simultaneously, with four built-in algorithms: `LocalScaleOffset`, `BandAffineCombination`, `Trimming`, and `LUT` [38].

GDAL 3.11 (May 2025) introduced the **raster pipeline** command, a major step toward graph-based processing. Pipelines chain steps separated by `!`, starting with `read` and ending with `write`: `gdal raster pipeline ! read in.tif ! reproject --dst-crs=EPSG:32632 ! write out.tif` [39]. Pipelines can be serialized as `.gdalg.json` files with `"type": "gdal_streamed_alg"`, which the GDALG driver opens and evaluates in a streaming/on-the-fly fashion without materializing intermediate rasters [40][41]. This is essentially a serialized lazy processing graph -- conceptually similar to Joon's serialized node graph, though expressed as a linear pipeline rather than an arbitrary DAG.

### Map Algebra: Historical Context

Map Algebra was formalized by Dana Tomlin and Joseph K. Berry at Yale University in the early 1980s [42][43]. Tomlin's framework categorizes raster operations into four classes: **local** (per-pixel), **focal** (neighborhood), **zonal** (region-based), and **incremental** (iterative/spreading). This taxonomy remains the standard vocabulary. Tomlin's Map Analysis Package (MAP) directly influenced GRASS's r.mapcalc, IDRISI (now TerrSet), and ARC/INFO's GRID module, which became ArcGIS Spatial Analyst [42][43]. Every raster expression language discussed in this report is a descendant of Tomlin's original algebra.

### ESA SNAP Toolbox (Graph Processing Framework)

The Sentinel Application Platform (SNAP), developed by ESA for Sentinel satellite data processing, has a Graph Processing Framework (GPF) at its core [44][45]. Operators (calibration, terrain correction, speckle filtering, etc.) can be composed into a directed acyclic graph represented as an XML document. The command-line tool `gpt` (Graph Processing Tool) executes these graphs. SNAP's operator chaining supports streaming: data flows through the graph tile-by-tile without fully materializing intermediate products [44].

### Orfeo ToolBox (OTB)

OTB is a C++ library for remote sensing image processing developed by CNES (French Space Agency), built on top of ITK's pipeline architecture [46][47]. Since OTB 5.8, applications can be chained in-memory: the output image parameter of one application connects directly to the input of the next, wiring their internal ITK streaming pipelines together. No temporary images are written; only the final application in the chain writes to disk [47]. The pipeline supports multi-threading and streaming (tile-by-tile processing of arbitrarily large images). This in-memory chaining model is architecturally similar to Joon's approach of building a connected compute pipeline that only materializes the final output.

### GPU-Accelerated GIS Processing

Beyond the QGIS and ArcGIS GPU support noted above, several projects bring GPU acceleration to geospatial raster processing:

- **NVIDIA RAPIDS cuSpatial**: A CUDA-accelerated library for vector geospatial operations (point-in-polygon, distances, spatial joins) and coordinate transformations via cuProj. Focused on vector rather than raster [48].
- **Xarray-Spatial**: A raster analysis library from Makepath that experiments with GPU backends for operations like hillshade, viewshed, and zonal statistics [49].
- **GRASS GIS OpenCL modules**: Research implementations that port GRASS raster modules to OpenCL, enabling GPU-accelerated focal and interpolation operations [11].
- **Academic CUDA implementations**: Research has demonstrated 13-33x speedups for IDW interpolation and 28-925x for viewshed analysis when ported to CUDA [50][51].

The GIS ecosystem's GPU acceleration remains fragmented and tool-specific, with no unified GPU compute graph equivalent to what Joon provides through its Vulkan compute pipeline.

---

## Summary Table

| System | Graph Model | Evaluation | Expression Language | GPU Support |
|--------|------------|------------|-------------------|-------------|
| QGIS Modeler | Visual DAG of algorithms | Eager (writes intermediate files) | QGIS Expressions + Raster Calculator | OpenCL (limited algorithms) |
| ArcGIS ModelBuilder | Visual directed graph of tools | Eager | ArcPy / Arcade | CUDA (Spatial Analyst subset) |
| ArcGIS Raster Functions | Visual function chain (Function Editor) | Lazy (on-the-fly pixels) | Raster function template XML | Implicit via display pipeline |
| GRASS r.mapcalc | Expression-defined per-cell computation | Eager | r.mapcalc (C-like infix with neighborhood access) | Experimental OpenCL |
| Google Earth Engine | Server-side JSON DAG | Fully lazy (deferred to server) | Python/JS API building proxy DAG | Server-side (opaque) |
| GDAL VRT/Pipeline | XML/JSON processing chain | Lazy (streaming) | Pipeline DSL (`! read ! reproject ! write`) | None |
| ESA SNAP GPF | XML operator DAG | Streaming (tile-by-tile) | XML graph definition | None |
| OTB | In-memory ITK pipeline chain | Streaming | C++/Python application chaining | None |

---

## References

[1] https://docs.qgis.org/3.44/en/docs/user_manual/processing/modeler.html -- QGIS Model Designer documentation
[2] https://docs.qgis.org/3.44/en/docs/user_manual/processing/intro.html -- QGIS Processing Framework introduction
[3] https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/processing.html -- Writing a Processing plugin (QgsProcessingAlgorithm)
[4] https://www.qgistutorials.com/en/docs/3/processing_graphical_modeler.html -- QGIS Tutorials: Processing Modeler
[5] https://docs.qgis.org/3.44/en/docs/user_manual/expressions/expression.html -- QGIS Expressions documentation
[6] https://docs.qgis.org/3.40/en/docs/user_manual/expressions/functions_list.html -- QGIS Expressions function list
[7] https://mapscaping.com/mastering-qgis-raster-calculator/ -- Mastering QGIS Raster Calculator (Mapscaping)
[8] https://docs.qgis.org/3.40/en/docs/user_manual/working_with_raster/raster_analysis.html -- QGIS Raster Analysis documentation
[9] https://wiki.osgeo.org/wiki/New_Virtual_Raster_Data_Provider_for_Raster_Calculator_in_QGIS -- Virtual Raster Data Provider QEP (OSGeo Wiki)
[10] https://github.com/qgis/QGIS-Enhancement-Proposals/issues/121 -- QEP-121: OpenCL support for processing core algorithms
[11] https://www.itopen.it/opencl-acceleration-now-available-in-qgis/ -- OpenCL acceleration in QGIS (itopen.it)
[12] https://plugins.qgis.org/plugins/CUDARaster/ -- CUDA Raster plugin for QGIS
[13] https://pro.arcgis.com/en/pro-app/latest/help/analysis/geoprocessing/modelbuilder/what-is-modelbuilder-.htm -- What is ModelBuilder (Esri)
[14] https://pro.arcgis.com/en/pro-app/latest/help/analysis/geoprocessing/modelbuilder/modelbuilder-quick-tour.htm -- Use ModelBuilder (Esri)
[15] https://pro.arcgis.com/en/pro-app/3.4/help/analysis/geoprocessing/modelbuilder/inline-variable-substitution.htm -- Inline variable substitution in ModelBuilder
[16] https://pro.arcgis.com/en/pro-app/latest/help/analysis/geoprocessing/modelbuilder/iterators-for-looping.htm -- Iterators in ModelBuilder (Esri)
[17] https://pro.arcgis.com/en/pro-app/latest/help/analysis/raster-functions/raster-functions.htm -- Raster functions overview (Esri)
[18] https://pro.arcgis.com/en/pro-app/latest/help/analysis/raster-functions/raster-function-template.htm -- Raster function templates (Esri)
[19] https://enterprise.arcgis.com/en/portal/11.4/use/raster-function-editor.htm -- Raster Function Editor (ArcGIS Enterprise)
[20] https://github.com/Esri/raster-functions -- Esri raster-functions repository (GitHub)
[21] https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/gpu-processing-with-spatial-analyst.htm -- GPU processing with Spatial Analyst (Esri)
[22] https://pro.arcgis.com/en/pro-app/latest/help/data/imagery/working-with-a-multidimensional-raster-layer.htm -- Multidimensional raster data and CRF (Esri)
[23] https://grass.osgeo.org/grass83/manuals/temporalintro.html -- GRASS GIS temporal data processing introduction
[24] https://grass.osgeo.org/grass-stable/manuals/r.mapcalc.html -- r.mapcalc manual (GRASS GIS)
[25] https://grass.osgeo.org/history_docs/mapcalc.pdf -- Performing Map Calculations on GRASS Data (historical tutorial)
[26] http://ncsu-geoforall-lab.github.io/geospatial-modeling-course/grass/map_algebra.html -- NCSU Geospatial Modeling: Map Algebra in GRASS GIS
[27] https://grass.osgeo.org/grass-stable/manuals/r3.mapcalc.html -- r3.mapcalc manual (GRASS GIS)
[28] https://grass.osgeo.org/grass78/manuals/t.rast.mapcalc.html -- t.rast.mapcalc manual (GRASS GIS)
[29] https://grass.osgeo.org/grass85/manuals/temporalintro.html -- Temporal data processing in GRASS GIS
[30] https://www.sciencedirect.com/science/article/pii/S0034425717302900 -- Google Earth Engine: Planetary-scale geospatial analysis for everyone (Gorelick et al., 2017)
[31] https://link.springer.com/chapter/10.1007/978-3-031-26588-4_29 -- Scaling up in Earth Engine (Springer)
[32] https://developers.google.com/earth-engine/guides/client_server -- Client vs. Server (GEE documentation)
[33] https://developers.google.com/earth-engine/guides/deferred_execution -- Deferred Execution (GEE documentation)
[34] https://developers.google.com/earth-engine/tutorials/tutorial_js_03 -- Functional Programming Concepts (GEE tutorial)
[35] https://developers.google.com/earth-engine/guides/best_practices -- Coding Best Practices (GEE documentation)
[36] https://developers.google.com/earth-engine/guides/reducers_intro -- Reducer Overview (GEE documentation)
[37] https://gdal.org/en/stable/drivers/raster/vrt.html -- VRT: GDAL Virtual Format documentation
[38] https://gdal.org/en/stable/drivers/raster/vrt_processed_dataset.html -- VRT processed dataset documentation
[39] https://gdal.org/en/stable/programs/gdal_raster_pipeline.html -- gdal raster pipeline command documentation
[40] https://gdal.org/en/stable/drivers/raster/gdalg.html -- GDALG: GDAL Streamed Algorithm driver
[41] https://gis.utah.gov/blog/2026-02-09-streaming-down-gdal-pipeline/ -- Streaming Down the GDAL Pipeline (UGRC blog, 2026)
[42] https://en.wikipedia.org/wiki/Map_algebra -- Map algebra (Wikipedia)
[43] https://en.wikipedia.org/wiki/Dana_Tomlin -- Dana Tomlin (Wikipedia)
[44] https://step.esa.int/main/wp-content/help/?version=9.0.0&helpid=gpf.overview -- SNAP Graph Processing Framework overview (ESA)
[45] https://docs.terrabyte.lrz.de/software/modules/snap/ -- ESA SNAP Toolbox (terrabyte documentation)
[46] https://link.springer.com/article/10.1186/s40965-017-0031-6 -- Orfeo ToolBox: open source processing of remote sensing images (Springer)
[47] https://www.orfeo-toolbox.org/CookBook-6.2/OTB-Applications.html -- OTB Applications and chaining (OTB CookBook)
[48] https://github.com/rapidsai/cuspatial -- cuSpatial: CUDA-accelerated GIS (GitHub)
[49] https://makepath.com/gpu-enhanced-geospatial-analysis/ -- GPU-Enhanced Geospatial Analysis (Makepath)
[50] https://link.springer.com/article/10.1631/jzus.C1100051 -- Accelerating geospatial analysis on GPUs using CUDA (Springer)
[51] https://www.researchgate.net/publication/256938188_Accelerating_batch_processing_of_spatial_raster_analysis_using_GPU -- Accelerating batch processing of spatial raster analysis using GPU (ResearchGate)
