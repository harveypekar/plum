workspace "Joon"
    configurations { "Debug", "Release" }
    architecture "x86_64"
    language "C++"
    cppdialect "C++20"
    location "build"

    filter "configurations:Debug"
        defines { "DEBUG" }
        symbols "On"
        optimize "Off"

    filter "configurations:Release"
        defines { "NDEBUG" }
        optimize "Speed"

    filter "system:windows"
        systemversion "latest"

    filter {}

    local vulkan_sdk = os.getenv("VULKAN_SDK")
    if not vulkan_sdk then
        error("VULKAN_SDK environment variable not set")
    end

project "joon-lib"
    kind "StaticLib"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/lib"

    files {
        "include/**.h",
        "src/**.h",
        "src/**.cpp"
    }

    includedirs {
        "include",
        "src",
        "third_party",
        "third_party/imgui",
        "third_party/vma/include",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "vulkan-1" }

project "joon-cli"
    kind "ConsoleApp"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/cli"

    files { "cli/**.cpp" }

    includedirs {
        "include",
        "src",
        "third_party",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "joon-lib", "vulkan-1" }

project "joon-gui"
    kind "WindowedApp"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/gui"

    files {
        "gui/**.h",
        "gui/**.cpp",
        "third_party/imgui/*.cpp",
        "third_party/imgui/backends/imgui_impl_vulkan.cpp",
        "third_party/imgui/backends/imgui_impl_glfw.cpp"
    }

    includedirs {
        "include",
        "src",
        "third_party",
        "third_party/imgui",
        "third_party/imgui/backends",
        "third_party/vma/include",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "joon-lib", "vulkan-1", "glfw3" }

project "joon-tests"
    kind "ConsoleApp"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/tests"

    files {
        "tests/**.cpp",
        "third_party/catch2/extras/catch_amalgamated.cpp"
    }

    includedirs {
        "include",
        "src",
        "third_party",
        "third_party/catch2/extras",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "joon-lib", "vulkan-1" }
