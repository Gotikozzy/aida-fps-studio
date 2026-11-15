"""FPS labels shared by the analysis workspace and the export."""

from __future__ import annotations

import math
from dataclasses import dataclass

from dg_fps.presentation.content_targets import capture_supports_target, capture_target_limit

_DISPLAY_TOLERANCE_FPS = 0.1

DISPLAY_POLICY = {
    "version": "2.2.0",
    "scope": "studio_and_video_presentation_only",
    "main_value": "per_second_measured_or_dash",
    "measured_value": "preserved_in_analysis",
    "secondary_value": "visual_cadence_or_explicit_reference",
    "graph": "solid_measured_dotted_reference",
    "capture_families": {"30": [28, 30], "60": [58, 60], "120": [118, 120]},
    "capture_family_lower_bound_exclusive": True,
    "capture_rate_for_40_exclusive": 58,
    "measurement_display_tolerance_fps": _DISPLAY_TOLERANCE_FPS,
    "fractional_cadence_alias": "1000/1001_in_fractional_capture",
    "decimal_separator": ".",
}


@dataclass(frozen=True, slots=True)
class FPSDisplay:
    value: float | None
    nominal: bool = False

    @property
    def text(self) -> str:
        if self.value is None:
            return "—"
        return f"{self.value:g}" if self.nominal else f"{self.value:.2f}"


def fps_display(measured: float | None, capture: float | None) -> FPSDisplay:
    if measured is None or not math.isfinite(measured):
        return FPSDisplay(None)
    limit = capture_target_limit(capture)
    if (
        capture is not None and limit in (30, 60, 120)
        and abs(measured - capture) <= _DISPLAY_TOLERANCE_FPS
    ):
        return FPSDisplay(limit, nominal=True)
    fractional_capture = (
        capture is not None and limit in (30, 60, 120)
        and abs(capture - limit * 1000 / 1001) <= 0.005
    )
    for target in (30.0, 40.0, 60.0, 120.0):
        distance = abs(measured - target)
        if fractional_capture:
            distance = min(distance, abs(measured - target * 1000 / 1001))
        if distance <= _DISPLAY_TOLERANCE_FPS and capture_supports_target(capture, target):
            return FPSDisplay(target, nominal=True)
    return FPSDisplay(measured)


def capture_nominal_text(rate: float | None) -> str:
    limit = capture_target_limit(rate)
    if limit is None:
        return "—"
    return f"{limit:g}" if limit in (24, 30, 40, 60, 120, 240) else f"{limit:.2f}"
