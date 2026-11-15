from __future__ import annotations

import ctypes
import math
import weakref
from pathlib import Path
from threading import RLock
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from dg_fps.vision.optical_flow.base import (
    OpticalFlowBackend,
    OpticalFlowField,
    OpticalFlowRequirements,
)


class NvidiaOpticalFlowError(RuntimeError):
    """Raised when the optional native NVIDIA bridge cannot execute."""


class NvidiaNativeBackend(OpticalFlowBackend):
    backend_id = "nvidia_optical_flow_cuda"
    backend_version = "1.2.1"

    def __init__(self, library_path: Path, device_index: int = 0) -> None:
        self._library_path = library_path.resolve()
        self._library = _load_library(self._library_path)
        self.device_index = device_index
        self._library.dg_nvof_set_device(device_index)
        self._gpu_name = _probe(self._library)
        self._lock = RLock()
        self._engine: int | None = None
        self._cleanup: weakref.finalize | None = None
        self._closed = False
        self._gray_inputs: list[
            tuple[weakref.ReferenceType, NDArray[np.uint8], NDArray[np.uint8]]
        ] = []

    def close(self) -> None:
        """Release resources on success, cancellation or fallback; safe to repeat."""
        with self._lock:
            self._closed = True
            if self._cleanup is not None:
                self._cleanup()
            self._engine = None
            self._gray_inputs.clear()

    def resource_stats(self) -> dict[str, int]:
        with self._lock:
            values = (ctypes.c_uint64 * 4)()
            if (
                self._engine is not None
                and self._library.dg_nvof_engine_stats(self._engine, values) != 0
            ):
                raise NvidiaOpticalFlowError(_last_error(self._library))
            return dict(
                zip(
                    ("sessions_created", "uploads", "executions", "cached_sessions"),
                    values,
                    strict=True,
                )
            )

    def verify(self) -> None:
        """Exercise the complete API, buffers, execution and vector download."""
        frame = np.random.default_rng(1701).integers(20, 235, (192, 320, 3), dtype=np.uint8)
        field = self.compute(frame, np.roll(frame, 4, axis=1))
        if (
            field.vectors.shape != (192, 320, 2)
            or not np.isfinite(field.vectors).all()
            or float(np.percentile(field.magnitude[16:-16, 16:-16], 75)) < 0.05
        ):
            raise NvidiaOpticalFlowError("Optical Flow self-test returned invalid or empty motion")

    @property
    def gpu_name(self) -> str:
        return self._gpu_name

    def requirements(self) -> OpticalFlowRequirements:
        return OpticalFlowRequirements(
            needs_gpu=True,
            supported=True,
            reason=f"Ponte CUDA ativa em {self._gpu_name}",
        )

    def compute(
        self,
        previous_rgb: NDArray[np.uint8],
        current_rgb: NDArray[np.uint8],
    ) -> OpticalFlowField:
        with self._lock:
            if self._closed:
                raise NvidiaOpticalFlowError("NVIDIA backend is closed")
            return self._compute(previous_rgb, current_rgb)

    def _compute(
        self, previous_rgb: NDArray[np.uint8], current_rgb: NDArray[np.uint8]
    ) -> OpticalFlowField:
        _validate_pair(previous_rgb, current_rgb)
        if self._engine is None:
            self._engine = self._library.dg_nvof_engine_create(self.device_index)
            if not self._engine:
                raise NvidiaOpticalFlowError(_last_error(self._library))
            self._cleanup = weakref.finalize(
                self, self._library.dg_nvof_engine_destroy, self._engine
            )
        previous_gray = self._gray_input(previous_rgb)
        current_gray = self._gray_input(current_rgb)
        height, width = previous_gray.shape
        max_grid_width = math.ceil(width / 4)
        max_grid_height = math.ceil(height / 4)
        raw = np.empty((max_grid_height, max_grid_width, 2), dtype=np.float32)
        output_width = ctypes.c_uint32()
        output_height = ctypes.c_uint32()
        output_grid = ctypes.c_uint32()
        status = self._library.dg_nvof_engine_compute_gray8(
            self._engine,
            previous_gray.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            current_gray.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            width,
            height,
            raw.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            raw.size,
            ctypes.byref(output_width),
            ctypes.byref(output_height),
            ctypes.byref(output_grid),
        )
        if status != 0:
            raise NvidiaOpticalFlowError(_last_error(self._library))
        grid_vectors = raw[: output_height.value, : output_width.value]
        vectors = np.empty((height, width, 2), dtype=np.float32)
        for component in range(2):
            vectors[:, :, component] = cv2.resize(
                grid_vectors[:, :, component],
                (width, height),
                interpolation=cv2.INTER_LINEAR,
            )
        magnitude = np.linalg.norm(vectors, axis=2).astype(np.float32, copy=False)
        parameters: dict[str, Any] = {
            "gpu": self._gpu_name,
            "device_index": self.device_index,
            "input_format": "grayscale8",
            "performance_preset": "slow_quality",
            "hardware_grid": output_grid.value,
            "hardware_grid_width": output_width.value,
            "hardware_grid_height": output_height.value,
            "fixed_point_precision": "S10.5 (1/32 pixel)",
            "dense_interpolation": "bilinear",
            "native_library": str(self._library_path),
        }
        return OpticalFlowField(
            self.backend_id,
            self.backend_version,
            vectors,
            magnitude,
            parameters,
        )

    def _gray_input(self, rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
        # Identity only locates a candidate; compare every byte on mutable inputs.
        for position, (owner, snapshot, gray) in enumerate(self._gray_inputs):
            if owner() is rgb:
                self._gray_inputs.pop(position)
                if np.array_equal(snapshot, rgb):
                    self._gray_inputs.append((owner, snapshot, gray))
                    return gray
                break
        gray = np.ascontiguousarray(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
        self._gray_inputs.append((weakref.ref(rgb), rgb.copy(), gray))
        del self._gray_inputs[:-2]
        return gray


def default_library_path(project_root: Path) -> Path:
    return project_root / "native" / "nvidia_optical_flow" / "bin" / "dg_nvidia_optical_flow.dll"


def _load_library(path: Path) -> ctypes.CDLL:
    if not path.is_file():
        raise NvidiaOpticalFlowError(f"Ponte NVIDIA não compilada: {path}")
    try:
        library = ctypes.WinDLL(str(path))
    except OSError as exc:
        raise NvidiaOpticalFlowError(f"Falha ao carregar a ponte NVIDIA: {exc}") from exc
    library.dg_nvof_probe.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    library.dg_nvof_probe.restype = ctypes.c_int
    library.dg_nvof_last_error.argtypes = []
    library.dg_nvof_last_error.restype = ctypes.c_char_p
    library.dg_nvof_compute_gray8.argtypes = [
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    library.dg_nvof_compute_gray8.restype = ctypes.c_int
    library.dg_nvof_engine_create.argtypes = [ctypes.c_int]
    library.dg_nvof_engine_create.restype = ctypes.c_void_p
    library.dg_nvof_engine_destroy.argtypes = [ctypes.c_void_p]
    library.dg_nvof_engine_destroy.restype = None
    library.dg_nvof_engine_compute_gray8.argtypes = [
        ctypes.c_void_p,
        *library.dg_nvof_compute_gray8.argtypes,
    ]
    library.dg_nvof_engine_compute_gray8.restype = ctypes.c_int
    library.dg_nvof_engine_stats.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
    library.dg_nvof_engine_stats.restype = ctypes.c_int
    library.dg_nvof_set_device.argtypes = [ctypes.c_int]
    library.dg_nvof_set_device.restype = None
    library.dg_nvof_device_count.argtypes = []
    library.dg_nvof_device_count.restype = ctypes.c_int
    return cast(ctypes.CDLL, library)


def device_count(path: Path) -> int:
    library = _load_library(path)
    count = library.dg_nvof_device_count()
    if count < 0:
        raise NvidiaOpticalFlowError(_last_error(library))
    return count


def _probe(library: ctypes.CDLL) -> str:
    name = ctypes.create_string_buffer(256)
    if library.dg_nvof_probe(name, len(name)) != 0:
        raise NvidiaOpticalFlowError(_last_error(library))
    return name.value.decode("utf-8", errors="replace")


def _last_error(library: ctypes.CDLL) -> str:
    value = library.dg_nvof_last_error()
    return value.decode("utf-8", errors="replace") if value else "erro NVIDIA desconhecido"


def _validate_pair(previous_rgb: NDArray[np.uint8], current_rgb: NDArray[np.uint8]) -> None:
    for frame in (previous_rgb, current_rgb):
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("Optical flow expects HxWx3 uint8 RGB frames")
    if previous_rgb.shape != current_rgb.shape:
        raise ValueError("Optical-flow frame dimensions must match")
