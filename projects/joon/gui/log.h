#pragma once

// Log to three destinations:
//   1. Console window (stderr)
//   2. Visual Studio Output window (OutputDebugStringA)
//   3. File (joon.log, appended)
//
// Usage: jlog("format string %d %s", 42, "hello");

void jlog(const char* fmt, ...);
