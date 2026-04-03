#include "catch_amalgamated.hpp"
#include <windows.h>
#include <thread>
#include <chrono>
#include <filesystem>
#include <string>

namespace fs = std::filesystem;

struct WindowSearchInfo {
    DWORD target_pid;
    HWND found_window;
};

static BOOL CALLBACK EnumWindowsProc(HWND hwnd, LPARAM lParam) {
    WindowSearchInfo* info = reinterpret_cast<WindowSearchInfo*>(lParam);
    DWORD process_id;
    GetWindowThreadProcessId(hwnd, &process_id);

    if (process_id == info->target_pid) {
        info->found_window = hwnd;
        return FALSE;  // Stop enumeration
    }
    return TRUE;  // Continue
}

struct BlackBoxGuiTestFixture {
    fs::path gui_exe;

    BlackBoxGuiTestFixture() {
        // Try multiple relative paths from different potential working directories
        std::vector<std::string> possible_paths = {
            "../build/bin/Debug/joon-gui.exe",
            "build/bin/Debug/joon-gui.exe",
            "../../build/bin/Debug/joon-gui.exe",
            "../../../build/bin/Debug/joon-gui.exe",
            "projects/joon/build/bin/Debug/joon-gui.exe"
        };

        for (const auto& path : possible_paths) {
            gui_exe = fs::absolute(path);
            if (fs::exists(gui_exe)) {
                return;
            }
        }

        SKIP("joon-gui.exe not found - test requires built GUI application");
    }
};

TEST_CASE_METHOD(BlackBoxGuiTestFixture, "Black Box: GUI launches without crashing", "[gui][blackbox]") {
    STARTUPINFOA si = {};
    PROCESS_INFORMATION pi = {};
    si.cb = sizeof(si);

    // Launch the GUI
    BOOL created = CreateProcessA(
        gui_exe.string().c_str(),
        nullptr,
        nullptr, nullptr, FALSE,
        CREATE_NEW_CONSOLE,
        nullptr, nullptr,
        &si, &pi
    );

    REQUIRE(created);
    REQUIRE(pi.hProcess != nullptr);

    // Wait for window to appear
    std::this_thread::sleep_for(std::chrono::milliseconds(2000));

    // Check if process is still running
    DWORD exit_code = 0;
    BOOL got_exit = GetExitCodeProcess(pi.hProcess, &exit_code);
    REQUIRE(got_exit);
    REQUIRE(exit_code == STILL_ACTIVE);  // Should still be running

    // Clean shutdown
    TerminateProcess(pi.hProcess, 0);
    WaitForSingleObject(pi.hProcess, 5000);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}

TEST_CASE_METHOD(BlackBoxGuiTestFixture, "Black Box: GUI stays stable for 5 seconds", "[gui][blackbox]") {
    STARTUPINFOA si = {};
    PROCESS_INFORMATION pi = {};
    si.cb = sizeof(si);

    BOOL created = CreateProcessA(
        gui_exe.string().c_str(),
        nullptr,
        nullptr, nullptr, FALSE,
        CREATE_NEW_CONSOLE,
        nullptr, nullptr,
        &si, &pi
    );

    REQUIRE(created);

    // Sample process status repeatedly over 5 seconds to catch any crashes
    int samples = 10;
    int sample_interval_ms = 500;

    for (int i = 0; i < samples; i++) {
        std::this_thread::sleep_for(std::chrono::milliseconds(sample_interval_ms));

        DWORD exit_code = 0;
        GetExitCodeProcess(pi.hProcess, &exit_code);

        if (exit_code != STILL_ACTIVE) {
            FAIL("GUI crashed at sample " + std::to_string(i) +
                 " after " + std::to_string(i * sample_interval_ms) + "ms. Exit code: " +
                 std::to_string(exit_code));
        }
    }

    TerminateProcess(pi.hProcess, 0);
    WaitForSingleObject(pi.hProcess, 5000);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}

TEST_CASE_METHOD(BlackBoxGuiTestFixture, "Black Box: GUI survives modifier keys", "[gui][blackbox]") {
    STARTUPINFOA si = {};
    PROCESS_INFORMATION pi = {};
    si.cb = sizeof(si);

    BOOL created = CreateProcessA(
        gui_exe.string().c_str(),
        nullptr,
        nullptr, nullptr, FALSE,
        CREATE_NEW_CONSOLE,
        nullptr, nullptr,
        &si, &pi
    );

    REQUIRE(created);

    // Wait for initialization
    std::this_thread::sleep_for(std::chrono::milliseconds(2000));

    DWORD exit_code = 0;
    GetExitCodeProcess(pi.hProcess, &exit_code);
    REQUIRE(exit_code == STILL_ACTIVE);

    // Find and focus the window
    WindowSearchInfo search{ pi.dwProcessId, nullptr };
    EnumWindows(EnumWindowsProc, reinterpret_cast<LPARAM>(&search));

    if (search.found_window) {
        SetForegroundWindow(search.found_window);
        std::this_thread::sleep_for(std::chrono::milliseconds(200));

        // Send Ctrl press/release (this was crashing the app)
        INPUT inputs[2] = {};
        inputs[0].type = INPUT_KEYBOARD;
        inputs[0].ki.wVk = VK_CONTROL;
        inputs[0].ki.dwFlags = 0;

        inputs[1].type = INPUT_KEYBOARD;
        inputs[1].ki.wVk = VK_CONTROL;
        inputs[1].ki.dwFlags = KEYEVENTF_KEYUP;

        SendInput(2, inputs, sizeof(INPUT));
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        // Send Ctrl+A (select all — common operation)
        INPUT ctrl_a[4] = {};
        ctrl_a[0].type = INPUT_KEYBOARD;
        ctrl_a[0].ki.wVk = VK_CONTROL;
        ctrl_a[1].type = INPUT_KEYBOARD;
        ctrl_a[1].ki.wVk = 'A';
        ctrl_a[2].type = INPUT_KEYBOARD;
        ctrl_a[2].ki.wVk = 'A';
        ctrl_a[2].ki.dwFlags = KEYEVENTF_KEYUP;
        ctrl_a[3].type = INPUT_KEYBOARD;
        ctrl_a[3].ki.wVk = VK_CONTROL;
        ctrl_a[3].ki.dwFlags = KEYEVENTF_KEYUP;

        SendInput(4, ctrl_a, sizeof(INPUT));
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        // Send Shift, Alt
        INPUT mods[4] = {};
        mods[0].type = INPUT_KEYBOARD;
        mods[0].ki.wVk = VK_SHIFT;
        mods[1].type = INPUT_KEYBOARD;
        mods[1].ki.wVk = VK_SHIFT;
        mods[1].ki.dwFlags = KEYEVENTF_KEYUP;
        mods[2].type = INPUT_KEYBOARD;
        mods[2].ki.wVk = VK_MENU;
        mods[3].type = INPUT_KEYBOARD;
        mods[3].ki.wVk = VK_MENU;
        mods[3].ki.dwFlags = KEYEVENTF_KEYUP;

        SendInput(4, mods, sizeof(INPUT));
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    // Verify still running after all modifier key inputs
    GetExitCodeProcess(pi.hProcess, &exit_code);
    REQUIRE(exit_code == STILL_ACTIVE);

    TerminateProcess(pi.hProcess, 0);
    WaitForSingleObject(pi.hProcess, 5000);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}

TEST_CASE_METHOD(BlackBoxGuiTestFixture, "Black Box: GUI responds to close command", "[gui][blackbox]") {
    STARTUPINFOA si = {};
    PROCESS_INFORMATION pi = {};
    si.cb = sizeof(si);

    BOOL created = CreateProcessA(
        gui_exe.string().c_str(),
        nullptr,
        nullptr, nullptr, FALSE,
        CREATE_NEW_CONSOLE,
        nullptr, nullptr,
        &si, &pi
    );

    REQUIRE(created);

    // Wait for initialization
    std::this_thread::sleep_for(std::chrono::milliseconds(2000));

    // Verify running
    DWORD exit_code = 0;
    GetExitCodeProcess(pi.hProcess, &exit_code);
    REQUIRE(exit_code == STILL_ACTIVE);

    // Send Alt+F4 to close
    INPUT inputs[4] = {};
    inputs[0].type = INPUT_KEYBOARD;
    inputs[0].ki.wVk = VK_MENU;
    inputs[0].ki.dwFlags = 0;

    inputs[1].type = INPUT_KEYBOARD;
    inputs[1].ki.wVk = VK_F4;
    inputs[1].ki.dwFlags = 0;

    inputs[2].type = INPUT_KEYBOARD;
    inputs[2].ki.wVk = VK_F4;
    inputs[2].ki.dwFlags = KEYEVENTF_KEYUP;

    inputs[3].type = INPUT_KEYBOARD;
    inputs[3].ki.wVk = VK_MENU;
    inputs[3].ki.dwFlags = KEYEVENTF_KEYUP;

    SendInput(4, inputs, sizeof(INPUT));

    // Wait for graceful shutdown
    DWORD wait_result = WaitForSingleObject(pi.hProcess, 5000);
    REQUIRE(wait_result == WAIT_OBJECT_0);  // Process exited

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}
