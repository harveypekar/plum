#pragma once
#include <joon/scene.h>
#include <string>

namespace joon {

// Parse an OBJ from an in-memory string. Throws std::runtime_error on parse failure.
Mesh load_obj_string(const std::string& obj_text);

// Parse an OBJ from a file path. Throws std::runtime_error on read or parse failure.
Mesh load_obj_file(const std::string& path);

} // namespace joon
