from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from functools import cached_property
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, cast

import av
import cv2
import numpy as np
from numpy.typing import NDArray

from dg_fps.analyzers.base import (
    AnalysisContext,
    AnalysisFrameRange,
    AnalysisRequirements,
    Analyzer,
)
from dg_fps.analyzers.local_motion import (
    motion_luma,
    motion_occupancy,
    textured_luma,
    validate_luma_motion,
)
from dg_fps.core.enums import Classification
from dg_fps.core.errors import MediaOpenError
from dg_fps.core.finding import (
    AnalyzerIdentity,
    Finding,
    Interpretation,
    Observation,
    TimeRange,
)
from dg_fps.media.frame_provider import DecodedFrame, FrameProvider
from dg_fps.media.timestamp_index import frame_timestamp_from_av
from dg_fps.vision.optical_flow.base import OpticalFlowBackend

SCOPE_POLICY = {
    "version": "1.2.0",
    "grid": [8, 6],
    "distributed_minimum_cells": 6,
    "distributed_minimum_columns": 3,
    "distributed_minimum_rows": 2,
    "legacy_dense_support": 0.15,
    "distributed_changed_pixel_ratio": 0.20,
    "localized_maximum_cells_floor": 2,
    "minimum_anchor_overlap": 0.15,
    "localized_maximum_anchor_fraction": 0.25,
    "persistent_local_updates": 3,
    "local_window_seconds": 0.5,
    "local_minimum_span_seconds": 0.1,
    "decision_basis": "validated_motion_occupancy_not_fps",
}

RETENTION_POLICY = {
    "version": "1.0.0",
    "reference_seconds": 0.1,
    "source_roi_minimum_displacement_px": 0.5,
    "source_roi_minimum_confidence": 0.30,
    "decision_basis": "source_identity_or_bracketed_observable_motion",
}


@dataclass(frozen=True, slots=True)
class CadenceParameters:
    similarity_threshold: float = 0.995
    analysis_width: int = 640
    analysis_height: int = 360
    refinement_regions: int = 2
    refinement_size: int = 160

    def __post_init__(self) -> None:
        if not 0.0 < self.similarity_threshold <= 1.0:
            raise ValueError("Similarity threshold must be in (0, 1]")
        if self.analysis_width < 1 or self.analysis_height < 1:
            raise ValueError("Analysis dimensions must be positive")
        if not 0 <= self.refinement_regions <= 4 or self.refinement_size < 32:
            raise ValueError("Refinement requires 0–4 regions and a size of at least 32 pixels")


@dataclass(frozen=True, slots=True)
class CadenceSample:
    segment: str
    frame_index: int
    timestamp_seconds: float
    similarity_to_previous: float | None
    mean_absolute_difference: float | None
    normalized_difference: float | None
    changed_block_ratio: float | None
    edge_change_ratio: float | None
    flow_magnitude_px: float | None
    flow_support_ratio: float | None
    flow_confidence: float | None
    repeated: bool
    timestamp_valid: bool = True
    pts: int | None = None
    time_base: str | None = None
    signal_state: str = "observable"
    flow_backend: str = "not_recorded"
    flow_backend_version: str = ""
    flow_parameters: dict[str, Any] | None = None
    cadence_repeated: bool | None = None

    @property
    def presentation_repeated(self) -> bool:
        return self.repeated if self.cadence_repeated is None else self.cadence_repeated

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RepeatedFrameEvent:
    segment: str
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    repeated_frames: int
    mean_similarity: float
    cadence_role: str = "unclassified_hold"
    observed_duration_seconds: float = 0.0
    closed: bool = False
    cause: str = "undetermined"
    reference_hold_ms: float | None = None
    held_since_seconds: float | None = None
    resumed_at_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CadenceSummary:
    total_frames: int
    unique_frames: int
    repeated_frames: int
    repeated_ratio: float
    container_fps: float
    estimated_unique_fps: float | None
    temporal_irregularity: float
    duration_seconds: float
    timing_status: str = "observed_intervals"
    observed_intervals: int = 0
    content_fps: float | None = None
    content_status: str = "insufficient_updates"
    observed_capture_fps: float | None = None
    observable_window_ratio: float = 0.0
    measurable_seconds: float = 0.0
    ambiguous_seconds: float = 0.0
    retained_seconds: float = 0.0
    complete_period_seconds: float = 0.0
    complete_period_count: int = 0
    prolonged_retention_seconds: float = 0.0
    measurement_scope: str = "captured_visual_cadence_including_observed_holds"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CadenceAnalysisResult:
    analyzer_id: str
    analyzer_version: str
    source_path: Path
    parameters: CadenceParameters
    summary: CadenceSummary
    samples: tuple[CadenceSample, ...]
    events: tuple[RepeatedFrameEvent, ...]
    findings: tuple[Finding, ...]
    limitations: tuple[str, ...]
    frame_ranges: tuple[AnalysisFrameRange, ...]
    segment_summaries: dict[str, CadenceSummary]

    @property
    def unavailable_frame_count(self) -> int:
        return max(0, sum(r.frame_count for r in self.frame_ranges) - len(self.samples))


@dataclass(frozen=True, slots=True)
class VisualAdvanceMeasurement:
    similarity: float
    raw_difference: float
    normalized_difference: float
    changed_block_ratio: float
    edge_change_ratio: float
    flow_magnitude_px: float
    flow_support_ratio: float
    flow_confidence: float
    repeated: bool
    signal_state: str = "observable"
    flow_backend: str = "opencv_farneback"
    flow_backend_version: str = "local"
    flow_parameters: dict[str, Any] | None = None


@dataclass(frozen=True)
class _PreparedFrame:
    original: NDArray[np.uint8]
    rgb: NDArray[np.uint8]

    @cached_property
    def luma(self) -> NDArray[np.uint8]:
        return motion_luma(self.rgb)

    @cached_property
    def enhanced_luma(self) -> NDArray[np.uint8]:
        return _enhance_denoised(self.luma)

    @cached_property
    def edges(self) -> NDArray[np.bool_]:
        return cv2.Canny(self.enhanced_luma, 45, 110) > 0

    def signal_state(self) -> str:
        return textured_luma(self.luma)


def measure_visual_advance(
    previous_rgb: NDArray[np.uint8],
    current_rgb: NDArray[np.uint8],
    *,
    similarity_threshold: float = 0.995,
    backend: OpticalFlowBackend | None = None,
) -> VisualAdvanceMeasurement:
    return _measure_prepared_advance(
        _PreparedFrame(previous_rgb, previous_rgb),
        _PreparedFrame(current_rgb, current_rgb),
        similarity_threshold=similarity_threshold,
        backend=backend,
    )


def _measure_prepared_advance(
    a: _PreparedFrame,
    b: _PreparedFrame,
    *,
    similarity_threshold: float,
    backend: OpticalFlowBackend | None,
) -> VisualAdvanceMeasurement:
    previous_rgb, current_rgb = a.rgb, b.rgb
    if previous_rgb.shape != current_rgb.shape:
        raise ValueError("Cadence frames must have the same shape")
    signal_state = b.signal_state()
    if np.array_equal(previous_rgb, current_rgb):
        return VisualAdvanceMeasurement(
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            True,
            signal_state,
            "exact_pixel_comparison",
            "1.0",
            {},
        )
    raw = np.abs(current_rgb.astype(np.int16) - previous_rgb.astype(np.int16))
    raw_difference = float(raw.mean() / 255.0)
    similarity = max(0.0, 1.0 - raw_difference)
    previous, current = a.enhanced_luma, b.enhanced_luma
    normalized_delta = np.abs(current.astype(np.int16) - previous.astype(np.int16))
    normalized_difference = float(normalized_delta.mean() / 255.0)
    changed_blocks = _changed_block_ratio(normalized_delta)
    edge_change = float(np.logical_xor(a.edges, b.edges).mean())
    field = backend.compute(previous_rgb, current_rgb) if backend is not None else None
    flow = _farneback(previous, current) if field is None else field.vectors
    reverse_field = backend.compute(current_rgb, previous_rgb) if backend is not None else None
    backward = _farneback(current, previous) if reverse_field is None else reverse_field.vectors
    evidence = validate_luma_motion(a.luma, b.luma, flow, backward)
    supported = evidence.supported
    flow_support = float(supported.mean())
    flow_magnitude = evidence.magnitude
    flow_confidence = evidence.confidence
    alignment_gain = evidence.alignment_gain
    coherent_flow = bool(evidence.regions)
    # Large brightness changes/cuts remain observed changes, but cannot alone establish FPS.
    appearance_change = raw_difference >= max(0.008, 1.0 - similarity_threshold)
    structural_change = (
        changed_blocks >= 0.015
        and edge_change >= 0.002
        and normalized_difference >= 0.004
        and raw_difference >= 0.003
    )
    visible_change = coherent_flow or appearance_change or structural_change
    if visible_change and not coherent_flow and signal_state == "observable":
        signal_state = (
            "scene_transition"
            if raw_difference > 0.12 and edge_change > 0.08
            else "uncertain_change"
        )
    repeated = not visible_change
    return VisualAdvanceMeasurement(
        similarity,
        raw_difference,
        normalized_difference,
        changed_blocks,
        edge_change,
        flow_magnitude,
        flow_support,
        flow_confidence,
        repeated,
        signal_state,
        "opencv_farneback" if field is None else field.backend_id,
        "local" if field is None else field.backend_version,
        {
            **({} if field is None else field.parameters),
            "cadence_alignment_gain": alignment_gain,
            "validation": "local_forward_backward_and_photometric_alignment",
            "validation_parameters": {
                "tile_size": 16,
                "minimum_support": 12,
                "fb_tolerance_px": 0.35,
                "minimum_alignment_gain": 0.12,
                "minimum_displacement_px": 0.08,
                "minimum_local_coherence": 0.65,
                "maximum_noise_floor_luma": 2.0,
                "photometric_warp": "symmetric_midpoint",
            },
            "noise_floor_luma": evidence.noise_floor,
            "changed_pixel_ratio": float(
                (raw.mean(axis=2) > max(2.0, evidence.noise_floor * 2)).mean()
            ),
            "analysis_size": [previous_rgb.shape[1], previous_rgb.shape[0]],
            "active_regions": evidence.regions,
            "active_region_count": evidence.total_regions,
            "active_region_policy": "uniform_spatial_sample_max_32",
            "motion_occupancy": motion_occupancy(supported),
            "backward_backend": "opencv_farneback"
            if reverse_field is None
            else reverse_field.backend_id,
            "backward_version": "local" if reverse_field is None else reverse_field.backend_version,
            "backward_parameters": {} if reverse_field is None else reverse_field.parameters,
            "scope": "localized_visual_change"
            if flow_support < 0.05
            else "distributed_visual_change",
        },
    )


def _motion_alignment_gain(
    previous_rgb: NDArray[np.uint8],
    current_rgb: NDArray[np.uint8],
    flow: NDArray[np.float32],
    supported: NDArray[np.bool_],
) -> float:
    previous = cv2.GaussianBlur(cv2.cvtColor(previous_rgb, cv2.COLOR_RGB2GRAY), (3, 3), 0.7).astype(
        np.float32
    )
    current = cv2.GaussianBlur(cv2.cvtColor(current_rgb, cv2.COLOR_RGB2GRAY), (3, 3), 0.7).astype(
        np.float32
    )
    yy, xx = np.indices(previous.shape, dtype=np.float32)
    mx, my = xx + flow[:, :, 0], yy + flow[:, :, 1]
    valid = (
        supported
        & (mx >= 0)
        & (mx < previous.shape[1] - 1)
        & (my >= 0)
        & (my < previous.shape[0] - 1)
    )
    if np.count_nonzero(valid) < 12:
        return 0.0
    warped = cv2.remap(current, mx, my, cv2.INTER_LINEAR)
    baseline = float(np.abs(current - previous)[valid].mean())
    residual = float(np.abs(warped - previous)[valid].mean())
    return max(0.0, (baseline - residual) / max(baseline, 1e-6))


def cadence_advance_map(
    previous_rgb: NDArray[np.uint8],
    current_rgb: NDArray[np.uint8],
    *,
    max_width: int = 480,
    evidence: dict[str, Any] | None = None,
) -> NDArray[np.uint8]:
    if previous_rgb.shape != current_rgb.shape:
        raise ValueError("Cadence frames must have the same shape")
    if previous_rgb.shape[1] > max_width:
        scale = max_width / previous_rgb.shape[1]
        size = (max_width, max(1, round(previous_rgb.shape[0] * scale)))
        previous_rgb = cast(
            NDArray[np.uint8], cv2.resize(previous_rgb, size, interpolation=cv2.INTER_AREA)
        )
        current_rgb = cast(
            NDArray[np.uint8], cv2.resize(current_rgb, size, interpolation=cv2.INTER_AREA)
        )
    previous = _enhanced_luma(previous_rgb)
    current = _enhanced_luma(current_rgb)
    previous_edges = cv2.Canny(previous, 45, 110) > 0
    current_edges = cv2.Canny(current, 45, 110) > 0
    canvas = np.full((*previous.shape, 3), (4, 8, 12), np.uint8)
    overlap = previous_edges & current_edges
    canvas[previous_edges] = (196, 90, 230)
    canvas[current_edges] = (34, 211, 238)
    canvas[overlap] = (226, 232, 240)
    # Draw only the motion evidence actually used by the analyzer. A fresh,
    # unvalidated flow here could otherwise contradict the measured decision.
    evidence = evidence or {}
    source_width, source_height = evidence.get("analysis_size", [canvas.shape[1], canvas.shape[0]])
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


def _enhanced_luma(rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
    return _enhance_denoised(motion_luma(rgb))


def _enhance_denoised(denoised: NDArray[np.uint8]) -> NDArray[np.uint8]:
    return cast(
        NDArray[np.uint8],
        cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(denoised),
    )


def _farneback(previous: NDArray[np.uint8], current: NDArray[np.uint8]) -> NDArray[np.float32]:
    initial = np.empty((*previous.shape, 2), np.float32)
    return cast(
        NDArray[np.float32],
        cv2.calcOpticalFlowFarneback(previous, current, initial, 0.5, 4, 21, 4, 7, 1.5, 0),
    )


def _changed_block_ratio(delta: NDArray[np.int16]) -> float:
    height, width = delta.shape
    block = max(8, round(width / 20))
    changed = total = 0
    for top in range(0, height, block):
        for left in range(0, width, block):
            patch = delta[top : top + block, left : left + block]
            if patch.size:
                total += 1
                changed += float(patch.mean()) >= 4.0
    return changed / total if total else 0.0


class CadenceAnalyzer(Analyzer[CadenceAnalysisResult]):
    analyzer_id = "frame_cadence"
    analyzer_version = "0.9.0"

    def __init__(
        self,
        parameters: CadenceParameters | None = None,
        *,
        backend: OpticalFlowBackend | None = None,
    ) -> None:
        self._parameters = parameters or CadenceParameters()
        self._backend = backend

    def requirements(self) -> AnalysisRequirements:
        return AnalysisRequirements()

    def analyze(self, context: AnalysisContext) -> CadenceAnalysisResult:
        samples = _mark_scope_changes(self._decode_samples(context))
        events = _build_repeated_events(samples)
        summary = _summarize_decoded_runs(samples, context.container_fps)
        ranges = context.frame_ranges or (
            AnalysisFrameRange(0, max(0, len(samples) - 1), "Vídeo completo"),
        )
        segment_summaries = {
            frame_range.label: _summarize_decoded_runs(
                [sample for sample in samples if sample.segment == frame_range.label],
                context.container_fps,
            )
            for frame_range in ranges
        }
        findings = tuple(
            self._event_to_finding(event)
            for event in events
            if event.cadence_role == "extended_hold"
        )
        return CadenceAnalysisResult(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            source_path=context.source_path.resolve(),
            parameters=self._parameters,
            summary=summary,
            samples=tuple(samples),
            events=tuple(events),
            findings=findings,
            limitations=(
                "A análise mede frames decodificados de vídeo comprimido, não GPU frame time.",
                "Cena visualmente estática pode ser compatível com frame repetido.",
                "A taxa de frames únicos combina mudança estrutural e movimento visual coerente.",
                "Optical Flow confirma avanço visual, mas não identifica sozinho um novo frame.",
            ),
            frame_ranges=ranges,
            segment_summaries=segment_summaries,
        )

    def _analysis_pixels(self, pixels: NDArray[np.uint8]) -> NDArray[np.uint8]:
        height, width = pixels.shape[:2]
        scale = min(
            self._parameters.analysis_width / width, self._parameters.analysis_height / height, 1.0
        )
        return (
            pixels
            if scale == 1
            else cv2.resize(
                pixels,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        )

    def _measure_pair(
        self, previous: NDArray[np.uint8], current: NDArray[np.uint8]
    ) -> VisualAdvanceMeasurement:
        return self._measure_prepared_pair(
            self._prepare_frame(previous), self._prepare_frame(current)
        )

    def _prepare_frame(self, original: NDArray[np.uint8]) -> _PreparedFrame:
        return _PreparedFrame(original, self._analysis_pixels(original))

    def _measure_prepared_pair(
        self, first: _PreparedFrame, second: _PreparedFrame
    ) -> VisualAdvanceMeasurement:
        previous, current = first.original, second.original
        a, b = first.rgb, second.rgb
        result = _measure_prepared_advance(
            first,
            second,
            similarity_threshold=self._parameters.similarity_threshold,
            backend=self._backend,
        )
        if result.flow_backend == "exact_pixel_comparison":
            result = replace(result, flow_parameters={
                **(result.flow_parameters or {}),
                "pixel_identity_scope": "decoded_source"
                if a.shape == previous.shape or np.array_equal(previous, current)
                else "analysis_resolution_only",
            })
        if (
            a.shape == previous.shape
            or (not result.repeated and result.signal_state == "observable")
            or np.array_equal(previous, current)
        ):
            return result
        # Select by texture and change evidence, never by whether a measured FPS is low.
        delta = np.abs(b.astype(np.float32) - a.astype(np.float32)).mean(axis=2)
        if float(delta.max()) < 0.25:
            return result
        scores = cv2.GaussianBlur(delta, (17, 17), 0)
        regions = []
        height, width = previous.shape[:2]
        size = min(self._parameters.refinement_size, height, width)
        for _ in range(self._parameters.refinement_regions):
            y, x = np.unravel_index(np.argmax(scores), scores.shape)
            if scores[y, x] <= 0.1:
                break
            left = max(0, min(width - size, round(x * width / a.shape[1]) - size // 2))
            top = max(0, min(height - size, round(y * height / a.shape[0]) - size // 2))
            refined = measure_visual_advance(
                previous[top : top + size, left : left + size],
                current[top : top + size, left : left + size],
                backend=self._backend,
                similarity_threshold=self._parameters.similarity_threshold,
            )
            roi = {
                "x": left,
                "y": top,
                "width": size,
                "height": size,
                "source_size": [width, height],
                "evidence": refined.flow_parameters,
                "backend": refined.flow_backend,
                "version": refined.flow_backend_version,
            }
            regions.append(roi)
            if not refined.repeated and refined.signal_state == "observable":
                # Local evidence must stay local in the scene witness coordinates.
                # A crop's support fraction cannot represent whole-frame motion.
                sx, sy = a.shape[1] / width, a.shape[0] / height
                mapped_regions = [
                    {
                        **region,
                        "x": (left + region["x"]) * sx,
                        "y": (top + region["y"]) * sy,
                        "width": region["width"] * sx,
                        "height": region["height"] * sy,
                    }
                    for region in (refined.flow_parameters or {}).get("active_regions", [])
                ]
                return replace(
                    result,
                    repeated=False,
                    signal_state="observable",
                    flow_magnitude_px=refined.flow_magnitude_px,
                    flow_support_ratio=refined.flow_support_ratio * size * size / (width * height),
                    flow_confidence=refined.flow_confidence,
                    flow_backend=refined.flow_backend,
                    flow_backend_version=refined.flow_backend_version,
                    flow_parameters={
                        **(result.flow_parameters or {}),
                        "refinement_regions": regions,
                        "active_regions": mapped_regions,
                        "scope": "source_roi_visual_change",
                        "flow_units": "source_pixels",
                        "motion_occupancy": _region_occupancy(
                            mapped_regions, a.shape[1], a.shape[0]
                        ),
                    },
                )
            scores[max(0, y - 24) : y + 25, max(0, x - 24) : x + 25] = 0
        return replace(
            result,
            flow_parameters={**(result.flow_parameters or {}), "refinement_regions": regions},
        )

    def _decode_samples(self, context: AnalysisContext) -> list[CadenceSample]:
        if context.frame_ranges:
            return self._decode_selected_ranges(context)
        samples: list[CadenceSample] = []
        previous: _PreparedFrame | None = None
        source = context.source_path.resolve()
        try:
            with av.open(str(source), mode="r") as container:
                stream = container.streams.video[0]
                expected = int(stream.frames or 0)
                for index, frame in enumerate(container.decode(video=0)):
                    context.check_cancelled()
                    timestamp = frame_timestamp_from_av(
                        index, stream.index, frame, frame.time_base or stream.time_base
                    )
                    analysis_frame = frame.reformat(format="rgb24")
                    current = self._prepare_frame(
                        cast(NDArray[np.uint8], analysis_frame.to_ndarray())
                    )
                    measurement = (
                        None if previous is None else self._measure_prepared_pair(previous, current)
                    )
                    samples.append(
                        CadenceSample(
                            segment="Vídeo completo",
                            frame_index=index,
                            timestamp_seconds=timestamp.seconds,
                            timestamp_valid=timestamp.pts is not None
                            and timestamp.time_base is not None,
                            pts=timestamp.pts,
                            time_base=timestamp.time_base,
                            similarity_to_previous=(
                                None if measurement is None else measurement.similarity
                            ),
                            mean_absolute_difference=(
                                None if measurement is None else measurement.raw_difference
                            ),
                            normalized_difference=(
                                None if measurement is None else measurement.normalized_difference
                            ),
                            changed_block_ratio=(
                                None if measurement is None else measurement.changed_block_ratio
                            ),
                            edge_change_ratio=(
                                None if measurement is None else measurement.edge_change_ratio
                            ),
                            flow_magnitude_px=(
                                None if measurement is None else measurement.flow_magnitude_px
                            ),
                            flow_support_ratio=(
                                None if measurement is None else measurement.flow_support_ratio
                            ),
                            flow_confidence=(
                                None if measurement is None else measurement.flow_confidence
                            ),
                            repeated=False if measurement is None else measurement.repeated,
                            signal_state=current.signal_state()
                            if measurement is None
                            else measurement.signal_state,
                            flow_backend="not_compared"
                            if measurement is None
                            else measurement.flow_backend,
                            flow_backend_version=""
                            if measurement is None
                            else measurement.flow_backend_version,
                            flow_parameters=None
                            if measurement is None
                            else measurement.flow_parameters,
                        )
                    )
                    previous = current
                    if index % 10 == 0:
                        progress = min(99, round(((index + 1) / expected) * 100)) if expected else 0
                        context.report_progress(progress, f"Comparando frame {index + 1}")
        except (av.error.FFmpegError, OSError, ValueError, IndexError) as exc:
            raise RuntimeError(f"Não foi possível analisar a cadência de {source.name}") from exc
        context.report_progress(100, f"Cadência concluída: {len(samples)} frames")
        return samples

    def _decode_selected_ranges(self, context: AnalysisContext) -> list[CadenceSample]:
        if context.timestamp_index is None:
            raise ValueError("Selected ranges require a timestamp index")
        provider = FrameProvider(context.source_path, timestamp_index=context.timestamp_index)
        threaded = None
        if context.timestamp_index.has_unambiguous_pts and all(
            frame.time_base is not None and not frame.is_corrupt
            for frame in context.timestamp_index
        ):
            threaded = FrameProvider(
                context.source_path, timestamp_index=context.timestamp_index, threaded_decode=True
            )
        expected = sum(frame_range.frame_count for frame_range in context.frame_ranges)
        processed = 0
        samples: list[CadenceSample] = []
        for frame_range in context.frame_ranges:
            previous: _PreparedFrame | None = None
            expected_index = frame_range.start_frame
            decoded_frames = _indexed_frames(
                provider, threaded, frame_range, context.check_cancelled
            )
            for decoded in decoded_frames:
                if decoded.timestamp.index != expected_index:
                    previous = None
                expected_index = decoded.timestamp.index + 1
                current = self._prepare_frame(decoded.rgb)
                measurement = (
                    None if previous is None else self._measure_prepared_pair(previous, current)
                )
                samples.append(
                    CadenceSample(
                        segment=frame_range.label,
                        frame_index=decoded.timestamp.index,
                        timestamp_seconds=decoded.timestamp.seconds,
                        timestamp_valid=decoded.timestamp.pts is not None
                        and decoded.timestamp.time_base is not None,
                        pts=decoded.timestamp.pts,
                        time_base=decoded.timestamp.time_base,
                        similarity_to_previous=(
                            None if measurement is None else measurement.similarity
                        ),
                        mean_absolute_difference=(
                            None if measurement is None else measurement.raw_difference
                        ),
                        normalized_difference=(
                            None if measurement is None else measurement.normalized_difference
                        ),
                        changed_block_ratio=(
                            None if measurement is None else measurement.changed_block_ratio
                        ),
                        edge_change_ratio=(
                            None if measurement is None else measurement.edge_change_ratio
                        ),
                        flow_magnitude_px=(
                            None if measurement is None else measurement.flow_magnitude_px
                        ),
                        flow_support_ratio=(
                            None if measurement is None else measurement.flow_support_ratio
                        ),
                        flow_confidence=(
                            None if measurement is None else measurement.flow_confidence
                        ),
                        repeated=False if measurement is None else measurement.repeated,
                        signal_state=current.signal_state()
                        if measurement is None
                        else measurement.signal_state,
                        flow_backend="not_compared"
                        if measurement is None
                        else measurement.flow_backend,
                        flow_backend_version=""
                        if measurement is None
                        else measurement.flow_backend_version,
                        flow_parameters=None
                        if measurement is None
                        else measurement.flow_parameters,
                    )
                )
                previous = current
                processed += 1
                if processed % 10 == 0:
                    progress = min(99, round((processed / expected) * 100))
                    context.report_progress(
                        progress,
                        f"Analisando {frame_range.label}: frame {decoded.timestamp.index}",
                    )
        context.report_progress(100, f"Cadência concluída: {len(samples)} frames selecionados")
        return samples

    def _event_to_finding(self, event: RepeatedFrameEvent) -> Finding:
        confidence = min(1.0, max(0.0, event.mean_similarity))
        return Finding(
            analyzer=AnalyzerIdentity(self.analyzer_id, self.analyzer_version),
            category="temporal_cadence",
            type="repeated_frame_event",
            classification=Classification.HEURISTIC,
            range=TimeRange(
                event.start_time,
                event.end_time,
                event.start_frame,
                event.end_frame,
            ),
            confidence=confidence,
            observations=(
                Observation("mean_frame_similarity", event.mean_similarity, "ratio"),
                Observation("repeated_frames", event.repeated_frames, "frames"),
                Observation("analysis_segment", event.segment),
                Observation("observed_hold_duration", event.observed_duration_seconds, "seconds"),
                Observation("cause", "undetermined"),
            ),
            interpretations=(
                Interpretation(
                    "Imagem retida além da cadência recente; causa não identificada.", confidence
                ),
            ),
            audience_explanation=(
                "A imagem permaneceu sem atualização por mais tempo que o padrão recente do trecho."
            ),
            limitations=(
                "Pode representar uma cena estática em vez de repetição na apresentação.",
                "A medição ocorre após compressão e decodificação do vídeo.",
            ),
        )


def _indexed_frames(
    provider: FrameProvider,
    threaded: FrameProvider | None,
    selection: AnalysisFrameRange,
    check_cancelled: Callable[[], None],
) -> Iterator[DecodedFrame]:
    start, end = selection.start_frame, selection.end_frame
    if threaded is not None:
        try:
            with closing(
                threaded.frames_in_range(start, end, check_cancelled=check_cancelled)
            ) as frames:
                for frame in frames:
                    start = frame.timestamp.index + 1
                    yield frame
            return
        except MediaOpenError:
            # Retry before accepting a hole from the accelerated reader.
            check_cancelled()
    if start <= end:
        yield from provider.frames_in_range(
            start, end, check_cancelled=check_cancelled, allow_incomplete=True
        )


def _region_occupancy(regions: list[dict], width: int, height: int) -> dict:
    cells = {
        (
            min(7, max(0, int(float(r["x"]) * 8 / width))),
            min(5, max(0, int(float(r["y"]) * 6 / height))),
        )
        for r in regions
    }
    return {
        "grid": [8, 6],
        "cells": [list(c) for c in sorted(cells)],
        "origin": "mapped_local_or_legacy_witnesses",
        "version": "1.0.0",
    }


def _scope_cells(params: dict) -> set[tuple[int, int]]:
    occupancy = params.get("motion_occupancy")
    if occupancy is None:
        width, height = params.get("analysis_size", [640, 360])
        occupancy = _region_occupancy(params.get("active_regions", []), width, height)
    return {tuple(c) for c in occupancy["cells"]}


def _distributed_scope(regions: set[tuple[int, int]]) -> bool:
    return (
        len(regions) >= SCOPE_POLICY["distributed_minimum_cells"]
        and len({x for x, _ in regions}) >= SCOPE_POLICY["distributed_minimum_columns"]
        and len({y for _, y in regions}) >= SCOPE_POLICY["distributed_minimum_rows"]
    )


def _mark_scope_changes(samples: list[CadenceSample]) -> list[CadenceSample]:
    """Guard isolated overlays; also qualify spatial evidence accumulated in source time."""
    result: list[CadenceSample] = []
    anchors: set[tuple[int, int]] = set()
    established = 0
    candidate_start: int | None = None
    candidate_count = 0
    candidate_regions: set[tuple[int, int]] = set()
    partial_episode = False
    local_window: deque[tuple[int, CadenceSample, set[tuple[int, int]]]] = deque()
    previous: CadenceSample | None = None
    for sample in samples:
        if (
            previous is None
            or sample.segment != previous.segment
            or sample.frame_index != previous.frame_index + 1
            or not sample.timestamp_valid
            or sample.timestamp_seconds <= previous.timestamp_seconds
            or sample.signal_state in {"dark_unobservable", "low_texture", "scene_transition"}
        ):
            anchors, established, partial_episode = set(), 0, False
            candidate_start, candidate_count, candidate_regions = None, 0, set()
            local_window.clear()
        if sample.signal_state != "observable":
            local_window.clear()
        params = sample.flow_parameters or {}
        regions = _scope_cells(params)
        params = {**params, "scope_policy": SCOPE_POLICY, "scope_cell_count": len(regions)}
        sample = replace(sample, flow_parameters=params)
        raw_sample = sample
        while local_window and (
            sample.timestamp_seconds - local_window[0][1].timestamp_seconds
            > SCOPE_POLICY["local_window_seconds"]
        ):
            local_window.popleft()
        distributed = _distributed_scope(regions)
        support = sample.flow_support_ratio or 0.0
        broad_evidence = (
            distributed
            or (support >= SCOPE_POLICY["legacy_dense_support"] and len(regions) >= 4)
            or (
                params.get("changed_pixel_ratio", 0.0)
                >= SCOPE_POLICY["distributed_changed_pixel_ratio"]
                and bool(regions)
            )
        )
        if not sample.repeated and sample.signal_state == "observable":
            if broad_evidence:
                if not anchors or len(regions) >= len(anchors) / 2:
                    anchors = regions
                established += 1
                partial_episode = False
                candidate_start, candidate_count, candidate_regions = None, 0, set()
                # A preceding camera pan cannot qualify a subsequently animated HUD.
                local_window.clear()
            elif (
                established >= 3
                and anchors
                and regions
                and (
                    len(regions & anchors) / len(anchors) < SCOPE_POLICY["minimum_anchor_overlap"]
                    or len(regions)
                    <= len(anchors) * SCOPE_POLICY["localized_maximum_anchor_fraction"]
                )
                and len(regions)
                <= max(
                    SCOPE_POLICY["localized_maximum_cells_floor"],
                    int(len(anchors) * SCOPE_POLICY["localized_maximum_anchor_fraction"]),
                )
            ):
                if candidate_start is None or not regions & candidate_regions:
                    candidate_start, candidate_count, candidate_regions = len(result), 0, regions
                candidate_count += 1
                sample = replace(
                    sample,
                    cadence_repeated=True,
                    flow_parameters={
                        **params,
                        "cadence_witness": "previously_distributed_scene_regions",
                        "raw_local_visual_advance": True,
                        "scope_warning": "local_only_change_requires_persistent_confirmation",
                    },
                )
                candidate_regions |= regions
                if candidate_count == SCOPE_POLICY["persistent_local_updates"]:
                    partial_episode = True
                    for index in range(candidate_start, len(result)):
                        old = result[index]
                        result[index] = replace(
                            old,
                            cadence_repeated=True,
                            signal_state="partial_hold",
                            flow_parameters={
                                **(old.flow_parameters or {}),
                                "scope_warning": "persistent_local_only_motion_after_scene_motion",
                                "reference_region_count": len(anchors),
                            },
                        )
            else:
                candidate_start, candidate_count, candidate_regions = None, 0, set()
        if (
            raw_sample.signal_state == "observable"
            and raw_sample.timestamp_valid
            and not (broad_evidence and not raw_sample.repeated)
        ):
            # Retain repetitions too: confirmation restores their raw state, never
            # promotes them to advances, and does not leave holes between updates.
            local_window.append(
                (len(result), raw_sample, regions if not raw_sample.repeated else set())
            )
            advances = [entry for entry in local_window if entry[2]]
            footprint = set().union(*(cells for _, _, cells in advances))
            span = (
                advances[-1][1].timestamp_seconds - advances[0][1].timestamp_seconds
                if advances else 0.0
            )
            if (
                not raw_sample.repeated
                and regions
                and len(advances) >= SCOPE_POLICY["persistent_local_updates"]
                and span >= SCOPE_POLICY["local_minimum_span_seconds"]
                and _distributed_scope(footprint)
            ):
                confirmation = {
                    "classification": "heuristic",
                    "basis": "temporally_distributed_validated_motion",
                    "start_seconds": advances[0][1].timestamp_seconds,
                    "confirmed_at_seconds": raw_sample.timestamp_seconds,
                    "validated_updates": len(advances),
                    "cells": [list(cell) for cell in sorted(footprint)],
                }
                for index, original, _ in local_window:
                    restored = replace(
                        original,
                        flow_parameters={
                            **(original.flow_parameters or {}),
                            "scope_confirmation": confirmation,
                        },
                    )
                    if index < len(result):
                        result[index] = restored
                    else:
                        sample = restored
                partial_episode = False
                candidate_start, candidate_count, candidate_regions = None, 0, set()
        if partial_episode and sample.signal_state == "observable":
            sample = replace(
                sample,
                cadence_repeated=True,
                signal_state="partial_hold",
                flow_parameters={
                    **params,
                    "scope_warning": "persistent_local_only_motion_after_scene_motion",
                    "reference_region_count": len(anchors),
                },
            )
        result.append(sample)
        previous = sample
    # Provisional rejection is uncertainty, never a confirmed repeated period.
    pending = [
        replace(sample, signal_state="scope_pending")
        if sample.signal_state == "observable"
        and (sample.flow_parameters or {}).get("scope_warning")
        == "local_only_change_requires_persistent_confirmation"
        else sample
        for sample in result
    ]
    return _qualify_retention_evidence(pending)


def _retention_motion_anchor(sample: CadenceSample) -> str | None:
    if sample.signal_state != "observable" or sample.repeated or not sample.timestamp_valid:
        return None
    params = sample.flow_parameters or {}
    if _distributed_scope(_scope_cells(params)):
        return "distributed_validated_motion"
    if (
        params.get("scope") == "source_roi_visual_change"
        and (sample.flow_magnitude_px or 0.0)
        >= RETENTION_POLICY["source_roi_minimum_displacement_px"]
        and (sample.flow_confidence or 0.0)
        >= RETENTION_POLICY["source_roi_minimum_confidence"]
        and any((roi.get("evidence") or {}).get("active_regions")
                for roi in params.get("refinement_regions", []))
    ):
        return "source_resolution_validated_motion"
    return None


def _qualify_retention_evidence(samples: list[CadenceSample]) -> list[CadenceSample]:
    """Keep raw no-advance flags; qualify their use in measured periods separately."""
    before: list[int | None] = [None] * len(samples)
    after: list[int | None] = [None] * len(samples)
    anchors = [_retention_motion_anchor(s) for s in samples]

    def continuous(a: CadenceSample, b: CadenceSample) -> bool:
        return (
            a.segment == b.segment and b.frame_index == a.frame_index + 1
            and a.timestamp_valid and b.timestamp_valid
            and np.isfinite(a.timestamp_seconds) and np.isfinite(b.timestamp_seconds)
            and b.timestamp_seconds > a.timestamp_seconds
            and a.signal_state in {"observable", "scope_pending"}
            and b.signal_state in {"observable", "scope_pending"}
        )

    last = None
    for i, sample in enumerate(samples):
        if i == 0 or not continuous(samples[i - 1], sample):
            last = None
        before[i] = last
        if anchors[i]:
            last = i
    following = None
    for i in range(len(samples) - 1, -1, -1):
        if i == len(samples) - 1 or not continuous(samples[i], samples[i + 1]):
            following = None
        after[i] = following
        if anchors[i]:
            following = i
    result = []
    for i, sample in enumerate(samples):
        pending_scope = sample.signal_state == "scope_pending"
        if not sample.presentation_repeated or sample.signal_state not in {
            "observable", "scope_pending"
        }:
            result.append(sample)
            continue
        params = sample.flow_parameters or {}
        # Older imported evidence without photometry cannot be newly certified.
        if sample.mean_absolute_difference is None:
            result.append(sample)
            continue
        exact = (
            sample.repeated and sample.mean_absolute_difference == 0.0
            and sample.similarity_to_previous == 1.0
            and params.get("pixel_identity_scope") != "analysis_resolution_only"
        )
        left, right = before[i], after[i]
        bracketed = (
            left is not None and right is not None
            and sample.timestamp_seconds - samples[left].timestamp_seconds
            <= RETENTION_POLICY["reference_seconds"] + 1e-9
            and samples[right].timestamp_seconds - sample.timestamp_seconds
            <= RETENTION_POLICY["reference_seconds"] + 1e-9
        )
        evidence = {
            "classification": "observed" if exact else "heuristic",
            "status": "qualified" if exact or bracketed else "unresolved",
            "basis": "exact_source_pixels" if exact else "bracketed_motion"
            if bracketed else "insufficient_motion_reference",
            "before_frame": samples[left].frame_index if left is not None else None,
            "after_frame": samples[right].frame_index if right is not None else None,
            "before_basis": anchors[left] if left is not None else None,
            "after_basis": anchors[right] if right is not None else None,
        }
        if pending_scope and bracketed:
            evidence["provisional_warning"] = params.get("scope_warning")
            params = {k: v for k, v in params.items() if k != "scope_warning"}
        result.append(replace(
            sample,
            signal_state="observable" if exact or bracketed else "scope_pending"
            if pending_scope else "motion_unresolved",
            flow_parameters={**params, "retention_policy": RETENTION_POLICY,
                             "retention_evidence": evidence},
        ))
    return result


def _build_repeated_events(samples: list[CadenceSample]) -> list[RepeatedFrameEvent]:
    events: list[RepeatedFrameEvent] = []
    run: list[CadenceSample] = []
    before: CadenceSample | None = None
    recent_updates: deque[float] = deque(maxlen=12)
    reference: float | None = None

    def finish(after: CadenceSample | None) -> None:
        if not run:
            return
        same = after is not None and after.segment == run[-1].segment
        closed = bool(
            same and after.signal_state == "observable" and not after.presentation_repeated
        )
        start = before.timestamp_seconds if before is not None else run[0].timestamp_seconds
        end = after.timestamp_seconds if closed else run[-1].timestamp_seconds
        duration = max(0.0, end - start)
        if any(item.signal_state == "partial_hold" for item in run):
            role = "partial_scene_hold"
        elif any(item.signal_state != "observable" for item in run):
            role = "unobservable_hold"
        elif reference is not None and duration > 1.5 * reference:
            role = "extended_hold"
        elif reference is not None and closed:
            role = "regular_cadence_hold"
        else:
            role = "unclassified_hold"
        events.append(
            RepeatedFrameEvent(
                run[0].segment,
                run[0].frame_index,
                run[-1].frame_index,
                run[0].timestamp_seconds,
                run[-1].timestamp_seconds,
                sum(item.presentation_repeated for item in run),
                fmean(item.similarity_to_previous or 0.0 for item in run),
                role,
                duration,
                closed,
                "undetermined",
                None if reference is None else reference * 1000,
                start,
                end if closed else None,
            )
        )

    previous: CadenceSample | None = None
    for sample in samples:
        boundary = previous is not None and (
            sample.segment != previous.segment
            or sample.frame_index != previous.frame_index + 1
            or not sample.timestamp_valid
            or sample.timestamp_seconds <= previous.timestamp_seconds
        )
        if boundary:
            finish(None)
            run = []
            recent_updates.clear()
            reference = None
            previous = None
        retained = sample.presentation_repeated or sample.signal_state == "partial_hold"
        if retained:
            if not run:
                before = previous
                if len(recent_updates) >= 3:
                    reference = float(np.median(np.diff(recent_updates)))
            run.append(sample)
        else:
            finish(sample)
            run = []
            if sample.signal_state == "observable":
                recent_updates.append(sample.timestamp_seconds)
            else:
                recent_updates.clear()
                reference = None
        previous = sample
    finish(None)
    return events


def _complete_periods(samples: list[CadenceSample]) -> list[float]:
    """All closed observable periods, including long holds; never average selected FPS values."""
    periods = []
    anchor: CadenceSample | None = None
    previous: CadenceSample | None = None
    for sample in samples:
        if (
            previous is None
            or sample.segment != previous.segment
            or sample.frame_index != previous.frame_index + 1
            or not sample.timestamp_valid
            or sample.timestamp_seconds <= previous.timestamp_seconds
            or sample.signal_state != "observable"
        ):
            anchor = None
        elif not sample.presentation_repeated:
            if anchor is not None:
                periods.append(sample.timestamp_seconds - anchor.timestamp_seconds)
            anchor = sample
        previous = sample
    return periods


def _summarize_decoded_runs(samples: list[CadenceSample], container_fps: float) -> CadenceSummary:
    if not any(
        b.segment == a.segment and b.frame_index != a.frame_index + 1
        for a, b in zip(samples, samples[1:], strict=False)
    ):
        return _build_summary(samples, container_fps)
    # Use the existing summary on separate contiguous runs. The stored samples
    # retain their original segment labels and source frame identities.
    runs = []
    previous = None
    run = 0
    for sample in samples:
        if previous is not None and (
            sample.segment != previous.segment or sample.frame_index != previous.frame_index + 1
        ):
            run += 1
        runs.append(replace(sample, segment=str(run)))
        previous = sample
    return _build_summary(runs, container_fps)


def _build_summary(samples: list[CadenceSample], container_fps: float) -> CadenceSummary:
    total = len(samples)
    repeated = sum(sample.repeated for sample in samples)
    unique = total - repeated
    repeated_ratio = repeated / total if total else 0.0
    intervals = [
        current.timestamp_seconds - previous.timestamp_seconds
        for previous, current in zip(samples, samples[1:], strict=False)
        if current.segment == previous.segment
    ]
    positive_intervals = [interval for interval in intervals if interval > 0]
    mean_interval = fmean(positive_intervals) if positive_intervals else 0.0
    irregularity = (
        pstdev(positive_intervals) / mean_interval
        if len(positive_intervals) > 1 and mean_interval > 0
        else 0.0
    )
    duration = sum(positive_intervals)
    advances = sum(
        not current.repeated
        for previous, current in zip(samples, samples[1:], strict=False)
        if current.segment == previous.segment
        and current.timestamp_seconds > previous.timestamp_seconds
    )
    timing_valid = (
        bool(positive_intervals)
        and len(positive_intervals) == len(intervals)
        and all(sample.timestamp_valid for sample in samples)
        and all(np.isfinite(sample.timestamp_seconds) for sample in samples)
    )
    estimated_unique_fps = advances / duration if timing_valid else None
    readings = content_cadence_readings(samples)
    periods = _complete_periods(samples)
    period_seconds = sum(periods)
    measurable = sum(
        current.timestamp_seconds - previous.timestamp_seconds
        for previous, current in zip(samples, samples[1:], strict=False)
        if current.segment == previous.segment
        and current.timestamp_valid
        and previous.timestamp_valid
        and current.timestamp_seconds > previous.timestamp_seconds
        and readings[current.frame_index].content_fps is not None
    )
    retained = sum(
        current.timestamp_seconds - previous.timestamp_seconds
        for previous, current in zip(samples, samples[1:], strict=False)
        if current.segment == previous.segment
        and current.presentation_repeated
        and current.timestamp_seconds > previous.timestamp_seconds
    )
    events = _build_repeated_events(samples)
    prolonged = sum(
        event.observed_duration_seconds
        for event in events
        if event.cadence_role in {"extended_hold", "partial_scene_hold"}
    )
    return CadenceSummary(
        total_frames=total,
        unique_frames=unique,
        repeated_frames=repeated,
        repeated_ratio=repeated_ratio,
        container_fps=container_fps,
        estimated_unique_fps=estimated_unique_fps,
        temporal_irregularity=irregularity,
        duration_seconds=duration,
        timing_status="observed_intervals" if timing_valid else "insufficient_or_ambiguous_timing",
        observed_intervals=len(positive_intervals),
        content_fps=len(periods) / period_seconds if periods and timing_valid else None,
        content_status="complete_observed_periods_including_retention"
        if periods
        else (next(reversed(readings.values())).status if readings else "insufficient_updates"),
        observed_capture_fps=len(positive_intervals) / duration if timing_valid else None,
        observable_window_ratio=measurable / duration if duration and timing_valid else 0.0,
        measurable_seconds=measurable,
        ambiguous_seconds=max(0.0, duration - measurable),
        retained_seconds=retained,
        complete_period_seconds=period_seconds,
        complete_period_count=len(periods),
        prolonged_retention_seconds=prolonged,
    )


@dataclass(frozen=True, slots=True)
class ContentCadenceReading:
    content_fps: float | None
    capture_fps: float | None
    status: str
    complete_update_intervals: int
    median_hold_ms: float | None
    longest_hold_ms: float | None
    pending_hold_ms: float = 0.0
    reference_fps: float | None = None


def content_cadence_readings(
    samples: list[CadenceSample] | tuple[CadenceSample, ...],
) -> dict[int, ContentCadenceReading]:
    """Causal window, plus persistent retention evidence outside the rolling window."""
    readings: dict[int, ContentCadenceReading] = {}
    window: deque[CadenceSample] = deque()
    updates: deque[float] = deque(maxlen=12)
    previous: CadenceSample | None = None
    for sample in samples:
        boundary = previous is not None and (
            sample.segment != previous.segment
            or sample.frame_index != previous.frame_index + 1
            or not sample.timestamp_valid
            or sample.timestamp_seconds <= previous.timestamp_seconds
        )
        if boundary:
            window.clear()
            updates.clear()
        window.append(sample)
        if (
            sample.signal_state == "observable"
            and not sample.presentation_repeated
            and previous is not None
            and not boundary
        ):
            updates.append(sample.timestamp_seconds)
        while len(window) > 2 and sample.timestamp_seconds - window[1].timestamp_seconds >= 1.0:
            window.popleft()
        reading = _content_reading(list(window))
        if sample.signal_state == "observable" and len(updates) >= 3:
            median = float(np.median(np.diff(updates)))
            age = sample.timestamp_seconds - updates[-1]
            if age > 1.5 * median:
                reading = ContentCadenceReading(
                    None,
                    reading.capture_fps,
                    "extended_hold",
                    reading.complete_update_intervals,
                    median * 1000,
                    age * 1000,
                    age * 1000,
                    1 / median,
                )
        readings[sample.frame_index] = reading
        if sample.signal_state != "observable" or not sample.timestamp_valid:
            window.clear()
            updates.clear()
        previous = sample
    return readings


def _content_reading(window: list[CadenceSample]) -> ContentCadenceReading:
    current = window[-1]

    def unknown(status: str, capture: float | None = None) -> ContentCadenceReading:
        return ContentCadenceReading(None, capture, status, 0, None, None)

    if not current.timestamp_valid or not np.isfinite(current.timestamp_seconds):
        return unknown("invalid_timing")
    if current.signal_state != "observable":
        return unknown(current.signal_state)
    intervals = [
        b.timestamp_seconds - a.timestamp_seconds for a, b in zip(window, window[1:], strict=False)
    ]
    if not intervals or any(value <= 0 or not np.isfinite(value) for value in intervals):
        return unknown("insufficient_timing")
    capture = len(intervals) / sum(intervals)
    updates = [
        sample.timestamp_seconds
        for sample in window[1:]
        if not sample.presentation_repeated and sample.signal_state == "observable"
    ]
    if len(updates) < 3:
        return unknown("insufficient_updates", capture)
    holds = np.diff(updates)
    median = float(np.median(holds))
    elapsed = float(holds.sum())
    return ContentCadenceReading(
        min(capture, len(holds) / elapsed),
        capture,
        "observable_cadence",
        len(holds),
        median * 1000,
        float(holds.max()) * 1000,
        0.0,
        1 / median,
    )
