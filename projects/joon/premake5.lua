workspace "Joon"
    configurations { "Debug", "Release", "ANALYZE" }
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

    filter "configurations:ANALYZE"
        defines { "DEBUG", "JOON_ANALYZE" }
        symbols "On"
        optimize "Off"

        -- AddressSanitizer (ASan)
        buildoptions { "-fsanitize=address" }
        linkoptions { "-fsanitize=address" }

        -- UndefinedBehaviorSanitizer (UBSan)
        buildoptions { "-fsanitize=undefined" }
        linkoptions { "-fsanitize=undefined" }

        -- Additional sanitizer options
        buildoptions { "-fno-omit-frame-pointer" }
        linkoptions { "-fno-omit-frame-pointer" }

    filter "system:windows"
        systemversion "latest"

    filter {}

    local vulkan_sdk = os.getenv("VULKAN_SDK")
    if not vulkan_sdk then
        error("VULKAN_SDK environment variable not set")
    end

-- GLFW built from source
project "glfw"
    kind "StaticLib"
    language "C"
    targetdir "build/bin/%{cfg.buildcfg}"
    objdir "build/obj/%{cfg.buildcfg}/glfw"

    files {
        "third_party/glfw/src/context.c",
        "third_party/glfw/src/init.c",
        "third_party/glfw/src/input.c",
        "third_party/glfw/src/monitor.c",
        "third_party/glfw/src/platform.c",
        "third_party/glfw/src/vulkan.c",
        "third_party/glfw/src/window.c",
        "third_party/glfw/src/egl_context.c",
        "third_party/glfw/src/osmesa_context.c",
        "third_party/glfw/src/null_init.c",
        "third_party/glfw/src/null_monitor.c",
        "third_party/glfw/src/null_window.c",
        "third_party/glfw/src/null_joystick.c"
    }

    includedirs {
        "third_party/glfw/include",
        "third_party/glfw/src"
    }

    filter "system:windows"
        defines { "_GLFW_WIN32" }
        files {
            "third_party/glfw/src/win32_init.c",
            "third_party/glfw/src/win32_joystick.c",
            "third_party/glfw/src/win32_module.c",
            "third_party/glfw/src/win32_monitor.c",
            "third_party/glfw/src/win32_thread.c",
            "third_party/glfw/src/win32_time.c",
            "third_party/glfw/src/win32_window.c",
            "third_party/glfw/src/wgl_context.c"
        }

    filter "system:linux"
        defines { "_GLFW_X11" }
        files {
            "third_party/glfw/src/x11_init.c",
            "third_party/glfw/src/x11_monitor.c",
            "third_party/glfw/src/x11_window.c",
            "third_party/glfw/src/xkb_unicode.c",
            "third_party/glfw/src/posix_module.c",
            "third_party/glfw/src/posix_poll.c",
            "third_party/glfw/src/posix_thread.c",
            "third_party/glfw/src/posix_time.c",
            "third_party/glfw/src/glx_context.c",
            "third_party/glfw/src/linux_joystick.c"
        }

    filter "system:macosx"
        defines { "_GLFW_COCOA" }
        files {
            "third_party/glfw/src/cocoa_init.m",
            "third_party/glfw/src/cocoa_joystick.m",
            "third_party/glfw/src/cocoa_monitor.m",
            "third_party/glfw/src/cocoa_time.c",
            "third_party/glfw/src/cocoa_window.m",
            "third_party/glfw/src/nsgl_context.m",
            "third_party/glfw/src/posix_module.c",
            "third_party/glfw/src/posix_thread.c"
        }

    filter {}

-- Joon library
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

    -- Compile shaders before building (only if changed)
    prebuildcommands {
        "{CHDIR} %{wks.location}/../shaders",
        "compile_if_changed.bat"
    }

-- CLI
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

-- GUI
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
        "third_party/glfw/include",
        "third_party/vma/include",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "joon-lib", "glfw", "vulkan-1" }

    filter "system:windows"
        links { "gdi32", "shell32", "user32" }

    filter {}

-- Tests
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
        "third_party/vma/include",
        vulkan_sdk .. "/Include"
    }

    libdirs { vulkan_sdk .. "/Lib" }
    links { "joon-lib", "vulkan-1" }
