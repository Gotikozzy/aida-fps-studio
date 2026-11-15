"""Frame-resolution export projection of existing cadence measurements."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace

from dg_fps.analyzers.cadence import CadenceAnalysisResult, CadenceSample, content_cadence_readings
from dg_fps.presentation.content_targets import (
    ContentReference,
    capture_supports_target,
    capture_target_limit,
    content_references,
)

FRAME_GRAPH_POLICY = {
    "version": "1.5.0",
    "scope": "export_presentation_only",
    "resolution": "one_point_per_source_frame",
    "fps": "existing_content_cadence_reading",
    "update_decision": "contextual_presentation_repeated",
    "frame_time": "closed_observable_update_interval_ms",
    "unknown": "dotted_offline_visual_projection_not_measurement",
    "projection": "source_pts_bounded_smoothstep_up_to_1s_otherwise_linear",
    "projection_edges": "hold_only_available_measured_endpoint_no_extrapolation",
    "projection_boundaries": "never_cross_cut_invalid_timestamp_missing_frame_or_segment",
    "fps_transition_join": "continuous_dotted_curve_display_only_no_measured_interpolation",
    "axis": "source_pts_seconds_continuous_six_second_window",
    "scroll": "newest_at_right_history_moves_left_from_first_frame",
    "frame_time_card": "separate_compact_above_fps_left",
    "headline": "independent_one_second_aggregation",
    "spatial_uncertainty": "hold_previous_trusted_fps_dotted_not_measurement",
    "confidence_recovery_seconds": 1.0,
}


@dataclass(frozen=True, slots=True)
class PresentationFrame:
    segment: str
    frame_index: int
    seconds: float
    measured_fps: float | None
    displayed_fps: float | None
    origin: str
    frame_time_ms: float | None
    frame_time_origin: str
    graph_fps: float | None = None
    graph_origin: str = "legacy"
    projection_method: str = ""
    projection_support: tuple[int, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def export_references(
    result: CadenceAnalysisResult,
    references: dict[str, ContentReference] | None = None,
) -> dict[str, ContentReference]:
    """Resolve display defaults without changing the original inferred references."""
    resolved = dict(content_references(result) if references is None else references)
    capture = result.summary.container_fps
    target = capture_target_limit(capture)
    if target is not None and not capture_supports_target(capture, target):
        target = None
    for label in result.segment_summaries:
        original = resolved.get(label)
        if (
            original is None
            or original.target_fps is None
            or not capture_supports_target(capture, original.target_fps)
        ):
            resolved[label] = ContentReference(
                target, "presentation_capture_reference", "nominal_capture_fallback"
            )
    return resolved


def build_frame_timeline(
    result: CadenceAnalysisResult,
    references: dict[str, ContentReference],
    check_cancelled: Callable[[], None] = lambda: None,
) -> dict[str, tuple[PresentationFrame, ...]]:
    readings = content_cadence_readings(result.samples)
    groups = {}
    for label in result.segment_summaries:
        check_cancelled()
        items = [s for s in result.samples if s.segment == label]
        durations: dict[int, float] = {}
        anchor = None
        pending = []
        previous = None
        for sample in items:
            continuous = (
                previous is not None
                and previous.frame_index + 1 == sample.frame_index
                and previous.timestamp_valid
                and sample.timestamp_valid
                and previous.signal_state == sample.signal_state == "observable"
                and sample.timestamp_seconds > previous.timestamp_seconds
            )
            if not continuous:
                anchor, pending = None, []
            if sample.timestamp_valid and sample.signal_state == "observable":
                pending.append(sample.frame_index)
                if not sample.presentation_repeated:
                    if anchor is not None:
                        duration = (sample.timestamp_seconds - anchor) * 1000
                        durations.update((number, duration) for number in pending)
                    anchor, pending = sample.timestamp_seconds, []
            previous = sample
        target = references[label].target_fps
        points = []
        for number, sample in enumerate(items):
            if number % 1024 == 0:
                check_cancelled()
            reading = readings[sample.frame_index]
            measured = reading.content_fps
            frame_time = durations.get(sample.frame_index)
            points.append(
                PresentationFrame(
                    label,
                    sample.frame_index,
                    sample.timestamp_seconds,
                    measured,
                    measured if measured is not None else target,
                    "measured" if measured is not None else "reference",
                    frame_time if frame_time is not None else 1000 / target if target else None,
                    "measured" if frame_time is not None else "reference",
                )
            )
        groups[label] = project_inconclusive_fps(tuple(points), tuple(items), check_cancelled)
    return groups


def project_inconclusive_fps(
    points: tuple[PresentationFrame, ...],
    samples: tuple[CadenceSample, ...],
    check_cancelled: Callable[[], None] = lambda: None,
) -> tuple[PresentationFrame, ...]:
    """Offline drawing only. Original measurement and presentation fields stay intact."""
    if len(points) != len(samples):
        raise ValueError("Projection requires matching source samples")
    output = [
        replace(
            p,
            graph_fps=p.measured_fps,
            graph_origin="measured" if p.measured_fps is not None else "unavailable",
        )
        for p in points
    ]
    # Confidence is independent of the measured FPS value: a genuine low rate
    # remains eligible. Only loss of visual evidence starts this recovery period.
    guarded: set[int] = set()
    last_loss = None
    for i, sample in enumerate(samples):
        if i and (
            sample.segment != samples[i - 1].segment
            or sample.frame_index != samples[i - 1].frame_index + 1
            or sample.timestamp_seconds <= samples[i - 1].timestamp_seconds
        ):
            last_loss = None
        if not sample.timestamp_valid or sample.signal_state == "scene_transition":
            last_loss = None
            continue
        if sample.signal_state in {
            "partial_hold",
            "scope_pending",
            "motion_unresolved",
            "dark_unobservable",
            "low_texture",
            "uncertain_change",
        }:
            last_loss = sample.timestamp_seconds
            # A trailing reading can already include pending local-only
            # rejections. Guard that evidence window, not just the null point.
            j, entrance = i - 1, i
            while j >= 0 and (
                samples[j].segment == sample.segment
                and samples[j].timestamp_valid
                and samples[j].signal_state != "scene_transition"
                and samples[j].frame_index + 1 == samples[j + 1].frame_index
                and 0 < sample.timestamp_seconds - samples[j].timestamp_seconds <= 1.0
            ):
                if (samples[j].flow_parameters or {}).get("scope_warning") == (
                    "local_only_change_requires_persistent_confirmation"
                ):
                    entrance = j
                j -= 1
            for j in range(entrance, i):
                guarded.add(j)
                output[j] = replace(output[j], graph_fps=None, graph_origin="unavailable")
        if (
            last_loss is not None
            and sample.timestamp_seconds - last_loss
            < FRAME_GRAPH_POLICY["confidence_recovery_seconds"]
        ):
            guarded.add(i)
            output[i] = replace(output[i], graph_fps=None, graph_origin="unavailable")

    def fill(start: int, end: int) -> None:
        valid = [
            i for i in range(start, end) if points[i].measured_fps is not None and i not in guarded
        ]
        if not valid:
            return
        previous = None
        next_position = 0
        for i in range(start, end):
            if i % 1024 == 0:
                check_cancelled()
            if points[i].measured_fps is not None and i not in guarded:
                previous = i
                while next_position < len(valid) and valid[next_position] <= i:
                    next_position += 1
                continue
            following = valid[next_position] if next_position < len(valid) else None
            # Hold a known rate throughout an evidence-loss episode, including
            # short recovery readings; do not turn missing evidence into a ramp.
            if previous is not None and i in guarded:
                value = points[previous].measured_fps
                method = "hold_trusted_before_spatial_uncertainty"
                support = (points[previous].frame_index,)
            elif previous is not None and following is not None:
                a, b = points[previous], points[following]
                duration = b.seconds - a.seconds
                weight = (points[i].seconds - a.seconds) / duration
                if duration <= 1:
                    weight = weight * weight * (3 - 2 * weight)
                    method = "bounded_smoothstep"
                else:
                    method = "linear"
                value = a.measured_fps + weight * (b.measured_fps - a.measured_fps)
                support = (a.frame_index, b.frame_index)
            else:
                endpoint = points[previous if previous is not None else following]
                value = endpoint.measured_fps
                method = "hold_previous" if previous is not None else "hold_following"
                support = (endpoint.frame_index,)
            output[i] = replace(
                output[i],
                graph_fps=value,
                graph_origin="projected",
                projection_method=method,
                projection_support=support,
            )

    start = 0
    for i, sample in enumerate(samples):
        check_cancelled()
        invalid = (
            not sample.timestamp_valid
            or not math.isfinite(sample.timestamp_seconds)
            or sample.signal_state == "scene_transition"
        )
        if invalid:
            fill(start, i)
            output[i] = replace(output[i], graph_fps=None, graph_origin="unavailable")
            start = i + 1
        elif i > start and (
            sample.segment != samples[i - 1].segment
            or sample.frame_index != samples[i - 1].frame_index + 1
            or sample.timestamp_seconds <= samples[i - 1].timestamp_seconds
        ):
            fill(start, i)
            start = i
    fill(start, len(points))
    return tuple(output)
