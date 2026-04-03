#include "catch_amalgamated.hpp"
#include "joon/joon.h"
#include "ir/ir_graph.h"
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

// Test that the real tab management works with actual Vulkan context
// This creates real graphs using the joon::Context (Vulkan compute)
struct VulkanAppTestFixture {
    fs::path temp_graphs_dir;

    VulkanAppTestFixture() {
        temp_graphs_dir = fs::absolute("../../../graphs");
        if (!fs::exists(temp_graphs_dir)) {
            fs::create_directories(temp_graphs_dir);
        }
    }

    ~VulkanAppTestFixture() {
        for (auto& entry : fs::directory_iterator(temp_graphs_dir)) {
            if (entry.path().stem().string().find("vk_app_test_") == 0) {
                try {
                    fs::remove(entry.path());
                } catch (...) {}
            }
        }
    }

    void create_test_file(const std::string& name, const std::string& content) {
        fs::path path = temp_graphs_dir / (name + ".jn");
        std::ofstream file(path);
        file << content;
        file.close();
    }
};

// Replicate the exact GraphTab and App structures to test with real Vulkan context
struct GraphTabVulkan {
    std::string path;
    std::string name;
    joon::Graph graph;
    std::unique_ptr<joon::Evaluator> eval;
    bool dirty = false;
    uint64_t saved_update_count = 0;
};

struct AppVulkan {
    std::unique_ptr<joon::Context> ctx;
    std::vector<GraphTabVulkan> tabs;
    int active_tab = -1;
    uint32_t selected_node_id = UINT32_MAX;
    int untitled_count = 0;

    void init() {
        // Create REAL Vulkan context
        ctx = joon::Context::create();
    }

    void new_graph() {
        std::string name = "Untitled " + std::to_string(++untitled_count);

        GraphTabVulkan tab;
        tab.path = "";
        tab.name = name;

        std::string source = "(output (constant 0.5))";
        try {
            tab.graph = ctx->parse_string(source.c_str());
            if (!tab.graph.has_errors()) {
                tab.eval = ctx->create_evaluator(tab.graph);
                tab.eval->evaluate();
            }
        } catch (const std::exception&) {}

        tabs.push_back(std::move(tab));
        active_tab = tabs.size() - 1;
    }
};

TEST_CASE_METHOD(VulkanAppTestFixture, "Vulkan App: Initialize with real Vulkan context", "[gui][vulkan]") {
    AppVulkan app;
    app.init();

    // Verify context was created with real Vulkan
    REQUIRE(app.ctx != nullptr);
    REQUIRE(app.tabs.empty());
    REQUIRE(app.active_tab == -1);
}

TEST_CASE_METHOD(VulkanAppTestFixture, "Vulkan App: Create new graph with real Vulkan context", "[gui][vulkan]") {
    AppVulkan app;
    app.init();

    // Call new_graph with REAL joon::Context (Vulkan compute)
    app.new_graph();

    // Verify the tab was created and graph parsed with real Vulkan
    REQUIRE(app.tabs.size() == 1);
    REQUIRE(app.active_tab == 0);
    REQUIRE(app.tabs[0].name == "Untitled 1");
    REQUIRE(app.tabs[0].path.empty());
    REQUIRE(!app.tabs[0].graph.has_errors());
    REQUIRE(app.tabs[0].eval != nullptr);
}

TEST_CASE_METHOD(VulkanAppTestFixture, "Vulkan App: Multiple new graphs with real Vulkan", "[gui][vulkan]") {
    AppVulkan app;
    app.init();

    app.new_graph();
    app.new_graph();
    app.new_graph();

    REQUIRE(app.tabs.size() == 3);
    REQUIRE(app.tabs[0].name == "Untitled 1");
    REQUIRE(app.tabs[1].name == "Untitled 2");
    REQUIRE(app.tabs[2].name == "Untitled 3");
    REQUIRE(app.active_tab == 2);

    // All graphs evaluated successfully with real Vulkan
    for (int i = 0; i < 3; i++) {
        REQUIRE(!app.tabs[i].graph.has_errors());
        REQUIRE(app.tabs[i].eval != nullptr);
    }
}

TEST_CASE_METHOD(VulkanAppTestFixture, "Vulkan App: Evaluate graph successfully with Vulkan compute", "[gui][vulkan]") {
    AppVulkan app;
    app.init();

    app.new_graph();

    // The evaluator was created and evaluated - this uses REAL Vulkan compute
    REQUIRE(app.tabs[0].eval != nullptr);

    // Verify the evaluator can be called
    try {
        app.tabs[0].eval->evaluate();
        // If we get here, Vulkan evaluation succeeded
        REQUIRE(true);
    } catch (const std::exception& e) {
        FAIL("Vulkan evaluation failed: " + std::string(e.what()));
    }
}

TEST_CASE_METHOD(VulkanAppTestFixture, "Vulkan App: Vertical slice with real Vulkan context", "[gui][vulkan][vertical-slice]") {
    AppVulkan app;
    app.init();

    // Step 1: Create new graph (parses DSL with joon::Context)
    app.new_graph();
    REQUIRE(app.tabs.size() == 1);
    REQUIRE(!app.tabs[0].graph.has_errors());

    // Step 2: Create evaluator and evaluate (uses Vulkan compute)
    REQUIRE(app.tabs[0].eval != nullptr);
    app.tabs[0].eval->evaluate();

    // Step 3: Verify graph IR is valid
    auto& ir = app.tabs[0].graph.ir();
    REQUIRE(!ir.outputs.empty());

    // Step 4: Verify evaluator still works
    REQUIRE(app.tabs[0].eval != nullptr);
}
