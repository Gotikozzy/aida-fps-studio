"""Optional acceleration; importing or running DG FPS never requires NVIDIA."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from dg_fps.vision.optical_flow.base import OpticalFlowBackend, OpticalFlowField
from dg_fps.vision.optical_flow.opencv_cpu import OpenCVFarnebackBackend

LOGGER = logging.getLogger(__name__)


def bundled_library_path() -> Path:
    return Path(__file__).resolve().parent / "_native" / "dg_nvidia_optical_flow.dll"


class RecoveringBackend(OpenCVFarnebackBackend):
    backend_id = "automatic_nvidia_then_cpu"

    def __init__(self, primary: OpticalFlowBackend) -> None:
        super().__init__()
        self.primary = primary
        self.cpu = OpenCVFarnebackBackend()
        self.failure: str | None = None

    def close(self) -> None:
        close = getattr(self.primary, "close", None)
        if close is not None:
            close()

    def compute(
        self, previous_rgb: NDArray[np.uint8], current_rgb: NDArray[np.uint8]
    ) -> OpticalFlowField:
        if self.failure is None:
            try:
                return self.primary.compute(previous_rgb, current_rgb)
            except Exception as exc:
                self.failure = str(exc)
                self.close()
                LOGGER.warning("optical_flow_fallback", extra={"reason": self.failure})
        result = self.cpu.compute(previous_rgb, current_rgb)
        return OpticalFlowField(
            result.backend_id,
            result.backend_version,
            result.vectors,
            result.magnitude,
            {
                **result.parameters,
                "fallback_from": self.primary.backend_id,
                "fallback_reason": self.failure,
            },
        )


def select_backend(mode: str, library: Path | None = None) -> OpticalFlowBackend:
    if mode not in {"cpu", "auto", "nvidia"}:
        raise ValueError("Modo de análise inválido")
    if mode == "cpu":
        return OpenCVFarnebackBackend()
    library = library or bundled_library_path()
    if library.is_file():
        try:
            from dg_fps.vision.optical_flow.nvidia_native import NvidiaNativeBackend, device_count

            errors = []
            for index in range(device_count(library)):
                primary = None
                try:
                    primary = NvidiaNativeBackend(library, index)
                    primary.verify()
                    return RecoveringBackend(primary)
                except Exception as exc:
                    if primary is not None:
                        primary.close()
                    errors.append(str(exc))
            raise RuntimeError("; ".join(errors) or "No compatible NVIDIA GPU detected")
        except Exception as exc:
            if mode == "nvidia":
                raise RuntimeError(
                    f"NVIDIA indisponível: {exc}. Selecione CPU ou Automático."
                ) from exc
            LOGGER.warning("nvidia_unavailable", extra={"reason": str(exc)})
    elif mode == "nvidia":
        raise RuntimeError(
            "Ponte NVIDIA ausente no pacote. Reinstale o aplicativo ou selecione CPU."
        )
    return OpenCVFarnebackBackend()
