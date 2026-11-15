from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class OpticalFlowRequirements:
    needs_gpu: bool
    supported: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class OpticalFlowField:
    backend_id: str
    backend_version: str
    vectors: NDArray[np.float32]
    magnitude: NDArray[np.float32]
    parameters: dict[str, Any]


class OpticalFlowBackend(ABC):
    backend_id: str
    backend_version: str

    @abstractmethod
    def requirements(self) -> OpticalFlowRequirements:
        raise NotImplementedError

    @abstractmethod
    def compute(
        self,
        previous_rgb: NDArray[np.uint8],
        current_rgb: NDArray[np.uint8],
    ) -> OpticalFlowField:
        raise NotImplementedError
