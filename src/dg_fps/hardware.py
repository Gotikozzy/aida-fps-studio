"""Real capability checks. Never interpret a GPU name as proof of feature support."""

from __future__ import annotations

import ctypes
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dg_fps.backends import bundled_library_path
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.jobs.worker import ProgressReporter
from dg_fps.presentation.video_encoder import probe_nvenc


@dataclass(frozen=True, slots=True)
class GPUCheck:
    name: str
    device_index: int
    optical_flow: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class HardwareCheck:
    bridge_found: bool
    driver_available: bool
    gpus: tuple[GPUCheck, ...]
    nvenc: bool
    reason: str

    @property
    def optical_flow(self) -> bool:
        return any(gpu.optical_flow for gpu in self.gpus)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def driver_available() -> bool:
    if os.name != "nt":
        return False
    try:
        ctypes.WinDLL("nvcuda.dll", winmode=0x00000800)  # System32 only
        return True
    except OSError:
        return False


def check_hardware(
    token: CancellationToken,
    report: ProgressReporter,
    library: Path | None = None,
) -> HardwareCheck:
    library = library or bundled_library_path()
    found = library.is_file()
    driver = driver_available()
    gpus: list[GPUCheck] = []
    reason = ""
    token.raise_if_cancelled()
    report(5, "Verificando suporte NVIDIA…")
    if not found:
        reason = "bridge_missing"
    elif not driver:
        reason = "driver_missing"
    else:
        try:
            from dg_fps.vision.optical_flow.nvidia_native import NvidiaNativeBackend, device_count

            count = device_count(library)
            for index in range(count):
                token.raise_if_cancelled()
                name = f"NVIDIA #{index + 1}"
                backend = None
                try:
                    backend = NvidiaNativeBackend(library, index)
                    name = backend.gpu_name
                    report(20, f"Testando Optical Flow: {name}")
                    backend.verify()
                    gpus.append(GPUCheck(name, index, True))
                except Exception as exc:
                    gpus.append(GPUCheck(name, index, False, str(exc)))
                finally:
                    if backend is not None:
                        backend.close()
            if not count:
                reason = "no_devices"
        except Exception as exc:
            reason = str(exc)
    token.raise_if_cancelled()
    report(75, "Testando codificação NVIDIA…")
    nvenc = probe_nvenc(1920, 1080) if driver else False
    token.raise_if_cancelled()
    report(100, "Teste NVIDIA concluído")
    return HardwareCheck(found, driver, tuple(gpus), nvenc, reason)
