from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from dg_fps.vision.optical_flow.base import (
    OpticalFlowBackend,
    OpticalFlowField,
    OpticalFlowRequirements,
)


@dataclass(frozen=True, slots=True)
class FarnebackParameters:
    pyr_scale: float = 0.5
    levels: int = 4
    winsize: int = 21
    iterations: int = 4
    poly_n: int = 7
    poly_sigma: float = 1.5
    flags: int = 0


class OpenCVFarnebackBackend(OpticalFlowBackend):
    backend_id = "opencv_farneback_cpu"
    backend_version = "1.0.0"

    def __init__(self, parameters: FarnebackParameters | None = None) -> None:
        self._parameters = parameters or FarnebackParameters()

    def requirements(self) -> OpticalFlowRequirements:
        return OpticalFlowRequirements(needs_gpu=False, supported=True)

    def compute(
        self,
        previous_rgb: NDArray[np.uint8],
        current_rgb: NDArray[np.uint8],
    ) -> OpticalFlowField:
        _validate_pair(previous_rgb, current_rgb)
        previous_gray = cv2.cvtColor(previous_rgb, cv2.COLOR_RGB2GRAY)
        current_gray = cv2.cvtColor(current_rgb, cv2.COLOR_RGB2GRAY)
        params = self._parameters
        initial = np.empty((*previous_gray.shape, 2), dtype=np.float32)
        vectors = cast(
            NDArray[np.float32],
            cv2.calcOpticalFlowFarneback(
                previous_gray,
                current_gray,
                initial,
                params.pyr_scale,
                params.levels,
                params.winsize,
                params.iterations,
                params.poly_n,
                params.poly_sigma,
                params.flags,
            ),
        ).astype(np.float32, copy=False)
        magnitude = np.linalg.norm(vectors, axis=2).astype(np.float32, copy=False)
        return OpticalFlowField(
            self.backend_id,
            self.backend_version,
            vectors,
            magnitude,
            asdict(params),
        )


def _validate_pair(previous_rgb: NDArray[np.uint8], current_rgb: NDArray[np.uint8]) -> None:
    for frame in (previous_rgb, current_rgb):
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("Optical flow expects HxWx3 uint8 RGB frames")
    if previous_rgb.shape != current_rgb.shape:
        raise ValueError("Optical-flow frame dimensions must match")
