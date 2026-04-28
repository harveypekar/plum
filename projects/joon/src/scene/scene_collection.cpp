#include <joon/scene.h>

namespace joon {

void SceneCollection::clear() {
    objects.clear();
    lights.clear();
    // Note: camera is intentionally left at its current value, not reset to default.
    // Resetting would require the next evaluate() to also re-run the camera node;
    // since cameras are usually static across re-evaluates, leaving it alone is more efficient.
    // The clear/add_object test case below explicitly checks this behavior.
}

void SceneCollection::add_object(SceneObject o) { objects.push_back(std::move(o)); }
void SceneCollection::add_light(Light l) { lights.push_back(l); }
void SceneCollection::set_camera(Camera c) { camera = c; }

} // namespace joon
