#pragma once

#include <cstdio>
#include <cstdarg>

namespace joon_log {

inline FILE* g_file = nullptr;

inline void init(const char* path) {
    g_file = std::fopen(path, "w");
    if (g_file) std::setvbuf(g_file, nullptr, _IONBF, 0);
}

inline void close() {
    if (g_file) { std::fclose(g_file); g_file = nullptr; }
}

inline void write(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    va_list args2;
    va_copy(args2, args);
    std::vfprintf(stderr, fmt, args);
    if (g_file) std::vfprintf(g_file, fmt, args2);
    va_end(args2);
    va_end(args);
}

} // namespace joon_log
