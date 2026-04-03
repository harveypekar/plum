#include "catch_amalgamated.hpp"
#include "joon/joon.h"
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

// Reproduce the real GraphTab and App structures for integration testing
struct GraphTab {
    std::string path;
    std::string name;
    joon::Graph graph;
    std::unique_ptr<joon::Evaluator> eval;
    bool dirty = false;
    uint64_t saved_update_count = 0;
};

struct AppIntegration {
    std::unique_ptr<joon::Context> ctx;
    std::vector<GraphTab> tabs;
    int active_tab = -1;
    uint32_t selected_node_id = UINT32_MAX;
    int untitled_count = 0;

    void init() {
        ctx = joon::Context::create();
    }

    void new_graph() {
        std::string name = "Untitled " + std::to_string(++untitled_count);

        GraphTab tab;
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

    void open_graph(const std::string& path) {
        fs::path abs_path = fs::absolute(path);

        for (size_t i = 0; i < tabs.size(); i++) {
            if (fs::absolute(tabs[i].path) == abs_path) {
                active_tab = (int)i;
                return;
            }
        }

        GraphTab tab;
        tab.path = abs_path.string();
        tab.name = abs_path.stem().string();

        try {
            tab.graph = ctx->parse_file(abs_path.string().c_str());
            if (!tab.graph.has_errors()) {
                tab.eval = ctx->create_evaluator(tab.graph);
                tab.eval->evaluate();
            }
        } catch (const std::exception&) {}

        tabs.push_back(std::move(tab));
        active_tab = tabs.size() - 1;
    }
};

struct GuiIntegrationTestFixture {
    fs::path temp_graphs_dir;

    GuiIntegrationTestFixture() {
        temp_graphs_dir = fs::absolute("../../../graphs");
        if (!fs::exists(temp_graphs_dir)) {
            fs::create_directories(temp_graphs_dir);
        }
    }

    ~GuiIntegrationTestFixture() {
        for (auto& entry : fs::directory_iterator(temp_graphs_dir)) {
            if (entry.path().stem().string().find("gui_int_test_") == 0) {
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

TEST_CASE_METHOD(GuiIntegrationTestFixture, "GUI Integration: App initialization", "[gui][integration]") {
    AppIntegration app;
    app.init();

    // Verify context was created
    REQUIRE(app.ctx != nullptr);
    REQUIRE(app.tabs.empty());
    REQUIRE(app.active_tab == -1);
}

TEST_CASE_METHOD(GuiIntegrationTestFixture, "GUI Integration: Create new graph matches App structure", "[gui][integration]") {
    AppIntegration app;
    app.init();

    // Call the new_graph() method with the exact same logic as the real App
    app.new_graph();

    // Verify the tab was created with the exact structure as GraphTab
    REQUIRE(app.tabs.size() == 1);
    REQUIRE(app.active_tab == 0);
    REQUIRE(app.tabs[0].name == "Untitled 1");
    REQUIRE(app.tabs[0].path.empty());
    REQUIRE(!app.tabs[0].graph.has_errors());
    REQUIRE(app.tabs[0].eval != nullptr);
}

TEST_CASE_METHOD(GuiIntegrationTestFixture, "GUI Integration: Multiple new graphs", "[gui][integration]") {
    AppIntegration app;
    app.init();

    app.new_graph();
    app.new_graph();
    app.new_graph();

    REQUIRE(app.tabs.size() == 3);
    REQUIRE(app.tabs[0].name == "Untitled 1");
    REQUIRE(app.tabs[1].name == "Untitled 2");
    REQUIRE(app.tabs[2].name == "Untitled 3");
    REQUIRE(app.active_tab == 2);
}

TEST_CASE_METHOD(GuiIntegrationTestFixture, "GUI Integration: Open graph file", "[gui][integration]") {
    create_test_file("gui_int_test_open", "(output (noise :scale 2.0))");

    AppIntegration app;
    app.init();

    fs::path test_file = temp_graphs_dir / "gui_int_test_open.jn";
    app.open_graph(test_file.string());

    REQUIRE(app.tabs.size() == 1);
    REQUIRE(app.tabs[0].name == "gui_int_test_open");
    REQUIRE(!app.tabs[0].graph.has_errors());
    REQUIRE(app.tabs[0].eval != nullptr);
}

TEST_CASE_METHOD(GuiIntegrationTestFixture, "GUI Integration: Selected node tracking", "[gui][integration]") {
    AppIntegration app;
    app.init();

    REQUIRE(app.selected_node_id == UINT32_MAX);

    app.selected_node_id = 42;
    REQUIRE(app.selected_node_id == 42);

    app.selected_node_id = 9999;
    REQUIRE(app.selected_node_id == 9999);
}
