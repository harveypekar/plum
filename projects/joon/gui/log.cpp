#define NOMINMAX
#include "log.h"
#include <cstdio>
#include <cstdarg>
#include <windows.h>

static FILE* s_logFile = nullptr;

static FILE* get_log_file() {
    if (!s_logFile) {
        s_logFile = fopen("joon.log", "w");
    }
    return s_logFile;
}

void jlog(const char* fmt, ...) {
    char buf[1024];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    // 1. Console
    fprintf(stderr, "%s\n", buf);

    // 2. VS Output window
    OutputDebugStringA(buf);
    OutputDebugStringA("\n");

    // 3. File
    FILE* f = get_log_file();
    if (f) {
        fprintf(f, "%s\n", buf);
        fflush(f);
    }
}
