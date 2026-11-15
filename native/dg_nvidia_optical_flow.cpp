#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <exception>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <cuda.h>
#include "NvOFCuda.h"

namespace {
thread_local std::string g_last_error;
thread_local int g_device_index = 0;

void cuda_check(CUresult result, const char* operation) {
    if (result == CUDA_SUCCESS) {
        return;
    }
    const char* name = nullptr;
    const char* description = nullptr;
    cuGetErrorName(result, &name);
    cuGetErrorString(result, &description);
    std::ostringstream message;
    message << operation << " failed: " << (name ? name : "CUDA_ERROR")
            << " - " << (description ? description : "unknown error");
    throw std::runtime_error(message.str());
}

class CudaContext final {
public:
    CudaContext() {
        cuda_check(cuInit(0), "cuInit");
        CUdevice device{};
        cuda_check(cuDeviceGet(&device, g_device_index), "cuDeviceGet");
        cuda_check(cuCtxCreate(&context_, CU_CTX_SCHED_AUTO, device), "cuCtxCreate");
    }

    ~CudaContext() {
        if (context_ != nullptr) {
            cuCtxDestroy(context_);
        }
    }

    CUcontext get() const { return context_; }

private:
    CUcontext context_ = nullptr;
};

// Every entry point restores the caller's context, including on worker-thread handoff.
class CurrentContext final {
public:
    explicit CurrentContext(CUcontext context) : context_(context) {
        cuda_check(cuCtxGetCurrent(&previous_), "cuCtxGetCurrent");
        cuda_check(cuCtxPushCurrent(context), "cuCtxPushCurrent");
    }
    ~CurrentContext() {
        // SDK transfers also push this context; unwind them if a transfer throws.
        CUcontext popped{}, current{};
        do {
            if (cuCtxPopCurrent(&popped) != CUDA_SUCCESS ||
                cuCtxGetCurrent(&current) != CUDA_SUCCESS) break;
        } while (current == context_ && current != previous_);
    }
private:
    CUcontext context_ = nullptr, previous_ = nullptr;
};

struct Session final {
    std::uint32_t width, height, grid = 4;
    NvOFObj flow;
    std::vector<NvOFBufferObj> inputs, outputs;
    std::vector<NV_OF_FLOW_VECTOR> fixed;
    std::vector<std::uint8_t> images[2];

    Session(CUcontext context, std::uint32_t w, std::uint32_t h) : width(w), height(h) {
        flow = NvOFCuda::Create(context, w, h, NV_OF_BUFFER_FORMAT_GRAYSCALE8,
            NV_OF_CUDA_BUFFER_TYPE_CUDEVICEPTR, NV_OF_CUDA_BUFFER_TYPE_CUDEVICEPTR,
            NV_OF_MODE_OPTICALFLOW, NV_OF_PERF_LEVEL_SLOW);
        if (!flow->CheckGridSize(grid)) {
            std::uint32_t supported = 0;
            if (!flow->GetNextMinGridSize(grid, supported)) {
                throw std::runtime_error("GPU does not expose a supported output grid");
            }
            grid = supported;
        }
        flow->Init(grid);
        inputs = flow->CreateBuffers(NV_OF_BUFFER_USAGE_INPUT, 2);
        outputs = flow->CreateBuffers(NV_OF_BUFFER_USAGE_OUTPUT, 1);
        fixed.resize(static_cast<std::size_t>(outputs[0]->getWidth()) * outputs[0]->getHeight());
    }
};

class Engine final {
public:
    CUcontext context = nullptr;
    std::mutex mutex;
    std::vector<std::unique_ptr<Session>> sessions;
    std::uint64_t creations = 0, uploads = 0, executions = 0;

    explicit Engine(int index) {
        cuda_check(cuInit(0), "cuInit");
        CUdevice device{};
        cuda_check(cuDeviceGet(&device, index), "cuDeviceGet");
        cuda_check(cuCtxCreate(&context, CU_CTX_SCHED_AUTO, device), "cuCtxCreate");
        CUcontext created{};
        cuCtxPopCurrent(&created);
    }
    ~Engine() noexcept {
        if (context) {
            // Driver loss must not throw across the C ABI while falling back to CPU.
            const auto status = cuCtxPushCurrent(context);
            sessions.clear();
            if (status == CUDA_SUCCESS) {
                CUcontext popped{};
                cuCtxPopCurrent(&popped);
            }
            cuCtxDestroy(context);
        }
    }
    Session& session(std::uint32_t w, std::uint32_t h) {
        for (std::size_t i = 0; i < sessions.size(); ++i) {
            if (sessions[i]->width == w && sessions[i]->height == h) {
                auto found = std::move(sessions[i]);
                sessions.erase(sessions.begin() + i);
                sessions.push_back(std::move(found));
                return *sessions.back();
            }
        }
        // Bound VRAM even when successive ranges use different ROI dimensions.
        if (sessions.size() == 2) sessions.erase(sessions.begin());
        sessions.push_back(std::make_unique<Session>(context, w, h));
        ++creations;
        return *sessions.back();
    }
};
}

extern "C" __declspec(dllexport) void* dg_nvof_engine_create(int index) {
    try { g_last_error.clear(); return new Engine(index); }
    catch (const std::exception& error) { g_last_error = error.what(); return nullptr; }
    catch (...) { g_last_error = "unknown NVIDIA initialization error"; return nullptr; }
}

extern "C" __declspec(dllexport) void dg_nvof_engine_destroy(void* handle) {
    delete static_cast<Engine*>(handle);
}

extern "C" __declspec(dllexport) int dg_nvof_engine_stats(void* handle, std::uint64_t* stats) {
    if (!handle || !stats) return -1;
    auto& engine = *static_cast<Engine*>(handle);
    std::lock_guard<std::mutex> lock(engine.mutex);
    stats[0] = engine.creations;
    stats[1] = engine.uploads;
    stats[2] = engine.executions;
    stats[3] = engine.sessions.size();
    return 0;
}

extern "C" __declspec(dllexport) int dg_nvof_engine_compute_gray8(
    void* handle, const std::uint8_t* previous, const std::uint8_t* current,
    std::uint32_t width, std::uint32_t height, float* output_xy,
    std::size_t output_capacity, std::uint32_t* output_width,
    std::uint32_t* output_height, std::uint32_t* output_grid
) {
    try {
        g_last_error.clear();
        if (!handle || !previous || !current || !output_xy || !output_width ||
            !output_height || !output_grid || !width || !height) {
            throw std::invalid_argument("invalid null pointer or image dimensions");
        }
        auto& engine = *static_cast<Engine*>(handle);
        std::lock_guard<std::mutex> lock(engine.mutex);
        CurrentContext active(engine.context);
        auto& session = engine.session(width, height);
        if (output_capacity < session.fixed.size() * 2) {
            throw std::length_error("output buffer is too small");
        }
        const std::size_t bytes = static_cast<std::size_t>(width) * height;
        auto match = [&](const std::uint8_t* data, int excluded) {
            for (int i = 0; i < 2; ++i) {
                if (i != excluded && session.images[i].size() == bytes &&
                    std::memcmp(session.images[i].data(), data, bytes) == 0) return i;
            }
            return -1;
        };
        int first = match(previous, -1);
        int second = match(current, first);
        if (first < 0) first = second == 0 ? 1 : 0;
        if (second < 0) second = 1 - first;
        auto upload = [&](int slot, const std::uint8_t* data) {
            if (session.images[slot].size() != bytes ||
                std::memcmp(session.images[slot].data(), data, bytes) != 0) {
                // Invalidate first: a failed transfer must never become a cache hit.
                session.images[slot].clear();
                session.inputs[slot]->UploadData(data);
                session.images[slot].assign(data, data + bytes);
                ++engine.uploads;
            }
        };
        upload(first, previous);
        upload(second, current);
        // Fresh-per-pair semantics: never carry temporal hints into another comparison.
        session.flow->Execute(session.inputs[first].get(), session.inputs[second].get(),
            session.outputs[0].get(), nullptr, nullptr, 0, nullptr, nullptr, 0, nullptr,
            NV_OF_TRUE);
        cuda_check(cuCtxSynchronize(), "cuCtxSynchronize");
        session.outputs[0]->DownloadData(session.fixed.data());
        cuda_check(cuCtxSynchronize(), "output download");
        ++engine.executions;
        for (std::size_t i = 0; i < session.fixed.size(); ++i) {
            output_xy[i * 2] = static_cast<float>(session.fixed[i].flowx) / 32.0f;
            output_xy[i * 2 + 1] = static_cast<float>(session.fixed[i].flowy) / 32.0f;
        }
        *output_width = session.outputs[0]->getWidth();
        *output_height = session.outputs[0]->getHeight();
        *output_grid = session.grid;
        return 0;
    } catch (const std::exception& error) { g_last_error = error.what(); return -1; }
    catch (...) { g_last_error = "unknown NVIDIA execution error"; return -1; }
}

extern "C" __declspec(dllexport) void dg_nvof_set_device(int index) {
    g_device_index = index;
}

extern "C" __declspec(dllexport) int dg_nvof_device_count() {
    try {
        cuda_check(cuInit(0), "cuInit");
        int count = 0;
        cuda_check(cuDeviceGetCount(&count), "cuDeviceGetCount");
        return count;
    } catch (const std::exception& error) {
        g_last_error = error.what();
        return -1;
    }
}

extern "C" __declspec(dllexport) const char* dg_nvof_last_error() {
    return g_last_error.c_str();
}

extern "C" __declspec(dllexport) int dg_nvof_probe(char* gpu_name, std::size_t capacity) {
    try {
        g_last_error.clear();
        cuda_check(cuInit(0), "cuInit");
        CUdevice device{};
        cuda_check(cuDeviceGet(&device, g_device_index), "cuDeviceGet");
        char name[256]{};
        cuda_check(cuDeviceGetName(name, sizeof(name), device), "cuDeviceGetName");
        if (gpu_name != nullptr && capacity > 0) {
            const auto length = std::min(capacity - 1, std::char_traits<char>::length(name));
            std::copy_n(name, length, gpu_name);
            gpu_name[length] = '\0';
        }
        return 0;
    } catch (const std::exception& error) {
        g_last_error = error.what();
        return -1;
    }
}

extern "C" __declspec(dllexport) int dg_nvof_compute_gray8(
    const std::uint8_t* previous,
    const std::uint8_t* current,
    std::uint32_t width,
    std::uint32_t height,
    float* output_xy,
    std::size_t output_capacity,
    std::uint32_t* output_width,
    std::uint32_t* output_height,
    std::uint32_t* output_grid
) {
    try {
        g_last_error.clear();
        if (!previous || !current || !output_xy || !output_width || !output_height ||
            !output_grid || width == 0 || height == 0) {
            throw std::invalid_argument("invalid null pointer or image dimensions");
        }

        CudaContext cuda;
        auto optical_flow = NvOFCuda::Create(
            cuda.get(), width, height, NV_OF_BUFFER_FORMAT_GRAYSCALE8,
            NV_OF_CUDA_BUFFER_TYPE_CUDEVICEPTR,
            NV_OF_CUDA_BUFFER_TYPE_CUDEVICEPTR,
            NV_OF_MODE_OPTICALFLOW, NV_OF_PERF_LEVEL_SLOW
        );

        std::uint32_t grid = 4;
        if (!optical_flow->CheckGridSize(grid)) {
            std::uint32_t supported_grid = 0;
            if (!optical_flow->GetNextMinGridSize(grid, supported_grid)) {
                throw std::runtime_error("GPU does not expose a supported output grid");
            }
            grid = supported_grid;
        }
        optical_flow->Init(grid);

        auto inputs = optical_flow->CreateBuffers(NV_OF_BUFFER_USAGE_INPUT, 2);
        auto outputs = optical_flow->CreateBuffers(NV_OF_BUFFER_USAGE_OUTPUT, 1);
        inputs[0]->UploadData(previous);
        inputs[1]->UploadData(current);
        optical_flow->Execute(inputs[0].get(), inputs[1].get(), outputs[0].get());
        cuda_check(cuCtxSynchronize(), "cuCtxSynchronize");

        const auto out_width = outputs[0]->getWidth();
        const auto out_height = outputs[0]->getHeight();
        const std::size_t vector_count = static_cast<std::size_t>(out_width) * out_height;
        if (output_capacity < vector_count * 2) {
            throw std::length_error("output buffer is too small");
        }
        std::vector<NV_OF_FLOW_VECTOR> fixed_flow(vector_count);
        outputs[0]->DownloadData(fixed_flow.data());
        cuda_check(cuCtxSynchronize(), "output download");
        for (std::size_t index = 0; index < vector_count; ++index) {
            output_xy[index * 2] = static_cast<float>(fixed_flow[index].flowx) / 32.0f;
            output_xy[index * 2 + 1] = static_cast<float>(fixed_flow[index].flowy) / 32.0f;
        }
        *output_width = out_width;
        *output_height = out_height;
        *output_grid = grid;
        return 0;
    } catch (const std::exception& error) {
        g_last_error = error.what();
        return -1;
    } catch (...) {
        g_last_error = "unknown native NVIDIA Optical Flow error";
        return -1;
    }
}
