"""Presentation-only reuse of the exact cadence advance-map preprocessing."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from dg_fps.analyzers.cadence import _enhanced_luma


class AdvanceMapRenderer:
    def __init__(self, max_width: int = 480) -> None:
        self.max_width = max_width
        self._previous_edges: NDArray[np.bool_] | None = None
        self._source_shape: tuple[int, ...] | None = None

    def render(
        self, rgb: NDArray[np.uint8], evidence: dict[str, Any] | None
    ) -> NDArray[np.uint8] | None:
        if self._source_shape is not None and rgb.shape != self._source_shape:
            raise ValueError("Cadence frames must have the same shape")
        self._source_shape = rgb.shape
        if rgb.shape[1] > self.max_width:
            scale = self.max_width / rgb.shape[1]
            rgb = cv2.resize(
                rgb,
                (self.max_width, max(1, round(rgb.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )
        current_edges = cv2.Canny(_enhanced_luma(rgb), 45, 110) > 0
        previous_edges = self._previous_edges
        self._previous_edges = current_edges
        if previous_edges is None:
            return None
        canvas = np.full((*previous_edges.shape, 3), (4, 8, 12), np.uint8)
        overlap = previous_edges & current_edges
        canvas[previous_edges] = (196, 90, 230)
        canvas[current_edges] = (34, 211, 238)
        canvas[overlap] = (226, 232, 240)
        # Draw only the motion evidence actually used by the analyzer. A fresh,
        # unvalidated flow here could otherwise contradict the measured decision.
        evidence = evidence or {}
        source_width, source_height = evidence.get(
            "analysis_size", [canvas.shape[1], canvas.shape[0]]
        )
        sx, sy = canvas.shape[1] / source_width, canvas.shape[0] / source_height
        for region in evidence.get("active_regions", []):
            cv2.rectangle(
                canvas,
                (round(region["x"] * sx), round(region["y"] * sy)),
                (
                    round((region["x"] + region["width"]) * sx),
                    round((region["y"] + region["height"]) * sy),
                ),
                (34, 211, 238),
                1,
            )
        for roi in evidence.get("refinement_regions", []):
            width, height = roi["source_size"]
            sx, sy = canvas.shape[1] / width, canvas.shape[0] / height
            for region in (roi.get("evidence") or {}).get("active_regions", []):
                left, top = roi["x"] + region["x"], roi["y"] + region["y"]
                cv2.rectangle(
                    canvas,
                    (round(left * sx), round(top * sy)),
                    (round((left + region["width"]) * sx), round((top + region["height"]) * sy)),
                    (251, 191, 36),
                    1,
                )
        return canvas
