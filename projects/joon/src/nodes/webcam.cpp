#include "nodes/node_registry.h"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfreadwrite.h>

#pragma comment(lib, "mfplat.lib")
#pragma comment(lib, "mf.lib")
#pragma comment(lib, "mfreadwrite.lib")
#pragma comment(lib, "mfuuid.lib")
#pragma comment(lib, "ole32.lib")
#endif

#include <vector>

namespace joon {

namespace {

class WebcamCapture {
public:
    static WebcamCapture& instance() {
        static WebcamCapture cam;
        return cam;
    }

    ~WebcamCapture() { close(); }

    bool open() {
        if (m_open) return true;
#ifdef _WIN32
        HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        if (FAILED(hr) && hr != RPC_E_CHANGED_MODE && hr != S_FALSE)
            return false;
        m_com_init = (hr != RPC_E_CHANGED_MODE);

        hr = MFStartup(MF_VERSION);
        if (FAILED(hr)) { cleanup_com(); return false; }
        m_mf_init = true;

        IMFAttributes* attrs = nullptr;
        hr = MFCreateAttributes(&attrs, 1);
        if (FAILED(hr)) { close(); return false; }

        hr = attrs->SetGUID(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,
                            MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID);
        if (FAILED(hr)) { attrs->Release(); close(); return false; }

        IMFActivate** devices = nullptr;
        UINT32 count = 0;
        hr = MFEnumDeviceSources(attrs, &devices, &count);
        attrs->Release();
        if (FAILED(hr) || count == 0) { close(); return false; }

        IMFMediaSource* source = nullptr;
        hr = devices[0]->ActivateObject(__uuidof(IMFMediaSource),
                                        reinterpret_cast<void**>(&source));
        for (UINT32 i = 0; i < count; i++) devices[i]->Release();
        CoTaskMemFree(devices);
        if (FAILED(hr)) { close(); return false; }

        hr = MFCreateSourceReaderFromMediaSource(source, nullptr, &m_reader);
        source->Release();
        if (FAILED(hr)) { close(); return false; }

        IMFMediaType* type = nullptr;
        hr = MFCreateMediaType(&type);
        if (FAILED(hr)) { close(); return false; }

        type->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Video);
        type->SetGUID(MF_MT_SUBTYPE, MFVideoFormat_RGB32);
        hr = m_reader->SetCurrentMediaType(
            static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM), nullptr, type);
        type->Release();
        if (FAILED(hr)) { close(); return false; }

        IMFMediaType* actual = nullptr;
        hr = m_reader->GetCurrentMediaType(
            static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM), &actual);
        if (FAILED(hr)) { close(); return false; }

        UINT32 w = 0, h = 0;
        hr = MFGetAttributeSize(actual, MF_MT_FRAME_SIZE, &w, &h);
        actual->Release();
        if (FAILED(hr) || w == 0 || h == 0) { close(); return false; }

        m_width = w;
        m_height = h;
        m_open = true;
        return true;
#else
        return false;
#endif
    }

    void close() {
#ifdef _WIN32
        if (m_reader) { m_reader->Release(); m_reader = nullptr; }
        if (m_mf_init) { MFShutdown(); m_mf_init = false; }
        cleanup_com();
#endif
        m_open = false;
        m_width = 0;
        m_height = 0;
    }

    bool is_open() const { return m_open; }
    uint32_t width() const { return m_width; }
    uint32_t height() const { return m_height; }

    bool read_frame(std::vector<float>& rgba) {
        if (!m_open) return false;
#ifdef _WIN32
        DWORD flags = 0;
        IMFSample* sample = nullptr;
        HRESULT hr = m_reader->ReadSample(
            static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM),
            0, nullptr, &flags, nullptr, &sample);

        if (FAILED(hr) || !sample) return false;
        if (flags & MF_SOURCE_READERF_ENDOFSTREAM) {
            sample->Release();
            return false;
        }

        IMFMediaBuffer* buffer = nullptr;
        hr = sample->ConvertToContiguousBuffer(&buffer);
        if (FAILED(hr)) { sample->Release(); return false; }

        BYTE* data = nullptr;
        DWORD cur_len = 0;
        hr = buffer->Lock(&data, nullptr, &cur_len);
        if (FAILED(hr)) { buffer->Release(); sample->Release(); return false; }

        uint32_t stride = m_width * 4;
        size_t expected = static_cast<size_t>(stride) * m_height;
        if (cur_len < expected) {
            buffer->Unlock();
            buffer->Release();
            sample->Release();
            return false;
        }

        size_t pixels = static_cast<size_t>(m_width) * m_height;
        rgba.resize(pixels * 4);

        for (uint32_t y = 0; y < m_height; y++) {
            const BYTE* row = data + static_cast<size_t>(y) * stride;
            for (uint32_t x = 0; x < m_width; x++) {
                size_t src = static_cast<size_t>(x) * 4;
                size_t dst = (static_cast<size_t>(y) * m_width + x) * 4;
                rgba[dst + 0] = row[src + 2] / 255.0f;
                rgba[dst + 1] = row[src + 1] / 255.0f;
                rgba[dst + 2] = row[src + 0] / 255.0f;
                rgba[dst + 3] = 1.0f;
            }
        }

        buffer->Unlock();
        buffer->Release();
        sample->Release();
        return true;
#else
        (void)rgba;
        return false;
#endif
    }

private:
    WebcamCapture() = default;
    WebcamCapture(const WebcamCapture&) = delete;
    WebcamCapture& operator=(const WebcamCapture&) = delete;

#ifdef _WIN32
    void cleanup_com() {
        if (m_com_init) { CoUninitialize(); m_com_init = false; }
    }

    IMFSourceReader* m_reader = nullptr;
    bool m_com_init = false;
    bool m_mf_init = false;
#endif

    bool m_open = false;
    uint32_t m_width = 0;
    uint32_t m_height = 0;
};

void exec_webcam(const Node& node, EvalContext& ctx) {
    auto& cam = WebcamCapture::instance();
    if (!cam.is_open()) cam.open();

    std::vector<float> rgba;
    if (cam.is_open() && cam.read_frame(rgba)) {
        auto* img = ctx.pool.alloc_image(node.id, cam.width(), cam.height());
        ctx.pool.upload(img, rgba.data(), rgba.size() * sizeof(float));
    } else {
        auto* img = ctx.pool.alloc_image(node.id, ctx.default_width,
                                         ctx.default_height);
        std::vector<float> black(ctx.default_width * ctx.default_height * 4, 0.0f);
        ctx.pool.upload(img, black.data(), black.size() * sizeof(float));
    }
}

} // anonymous namespace

void register_webcam(NodeRegistry& reg) {
    reg.register_node("webcam", exec_webcam);
}

} // namespace joon
