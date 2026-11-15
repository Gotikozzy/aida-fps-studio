"""Presentation references only. Never supplied to the cadence detector."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass

from dg_fps.analyzers.cadence import CadenceAnalysisResult, content_cadence_readings

REFERENCE_VERSION = "1.0.0"


def capture_target_limit(rate: float | None) -> float | None:
    """Resolve the presentation ceiling from the encoded capture rate."""
    if rate is None or not math.isfinite(rate) or rate <= 0:
        return None
    for minimum, nominal in ((28, 30), (58, 60), (118, 120)):
        if minimum < rate <= nominal:
            return float(nominal)
    for nominal in (24, 240):
        if abs(rate - nominal * 1000 / 1001) <= 0.005:
            return float(nominal)
    return rate


def capture_supports_target(rate: float | None, target: float) -> bool:
    limit = capture_target_limit(rate)
    return (
        rate is not None and limit is not None and target <= limit and (target != 40 or rate > 58)
    )


def nearby_target(fps: float | None, capture_fps: float | None) -> int | None:
    if fps is None or not math.isfinite(fps) or fps <= 0:
        return None
    for minimum, target in ((27, 30), (37, 40), (57, 60)):
        if minimum <= fps <= target * 1.01:
            return target
    if fps >= 65 and capture_fps is not None and capture_fps > 60.6:
        return 120
    return None


@dataclass(frozen=True, slots=True)
class ContentReference:
    target_fps: float | None
    origin: str
    status: str
    observed_seconds: float = 0.0
    qualifying_seconds: float = 0.0
    candidates: tuple[int, ...] = ()

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "version": REFERENCE_VERSION,
            "lower_bounds": {"30": 27, "40": 37, "60": 57, "120": 65},
            "scope": "presentation_only_not_engine_telemetry",
        }


def content_references(
    result: CadenceAnalysisResult,
    default_target: float | None = None,
    overrides: dict[str, float | None] | None = None,
) -> dict[str, ContentReference]:
    """Freeze one reference per selected range; ambiguous modes need manual selection.

    Use non-overlapping time buckets to avoid weighting 120 Hz more than 30 Hz.
    Require three consecutive qualifying one-second buckets, 70% support, and
    reject a second sustained mode. Black/static/hold windows cannot vote.
    """
    choices = overrides or {}
    for value in (default_target, *choices.values()):
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError("Content target must be finite and positive")
    readings = content_cadence_readings(result.samples)
    references = {}
    for segment in result.segment_summaries:
        manual = choices.get(segment, default_target)
        if manual is not None:
            references[segment] = ContentReference(manual, "manual", "user_reference")
            continue
        samples = [sample for sample in result.samples if sample.segment == segment]
        buckets: dict[int, list] = defaultdict(list)
        if samples:
            start = samples[0].timestamp_seconds
            for sample in samples:
                buckets[int(sample.timestamp_seconds - start)].append(sample)
        votes: dict[int, float] = defaultdict(float)
        runs: dict[int, int] = defaultdict(int)
        previous_target, run, previous_bucket = None, 0, -2
        observable = 0.0
        for bucket, items in sorted(buckets.items()):
            duration = items[-1].timestamp_seconds - items[0].timestamp_seconds
            valid = [
                sample
                for sample in items
                if sample.timestamp_valid and sample.signal_state == "observable"
            ]
            target = None
            if duration >= 0.8 and len(valid) / len(items) >= 0.9:
                reading = readings[items[-1].frame_index]
                if reading.status == "observable_cadence":
                    observable += duration
                    if reading.complete_update_intervals >= 6:
                        target = nearby_target(reading.content_fps, reading.capture_fps)
            run = run + 1 if target == previous_target and bucket == previous_bucket + 1 else 1
            if target is not None:
                votes[target] += duration
                runs[target] = max(runs[target], run)
            previous_target, previous_bucket = target, bucket
        sustained = tuple(sorted(target for target in votes if runs[target] >= 3))
        winner = max(votes, key=votes.get) if votes else None
        accepted = (
            len(sustained) == 1
            and winner in sustained
            and observable >= 2.4
            and votes[winner] / observable >= 0.7
        )
        references[segment] = ContentReference(
            float(winner) if accepted else None,
            "inferred",
            "dominant_observed_cadence"
            if accepted
            else "mixed_modes"
            if len(sustained) > 1
            else "insufficient_stable_evidence",
            observable,
            votes[winner] if winner else 0.0,
            sustained,
        )
    return references


def reference_state(
    fps: float | None, reference: ContentReference, capture_fps: float | None = None
) -> str:
    if fps is None:
        return "inconclusive"
    target = reference.target_fps
    if target is None:
        return "no_reference"
    if capture_fps is not None and target > capture_fps * 1.02:
        return "capture_limited"
    # Proximity describes the displayed target; it never changes the measured value.
    minimum = {30: 27, 40: 37, 60: 57, 120: 65}.get(target, target * 0.97)
    if minimum <= fps <= target * 1.01:
        return "near_reference"
    return "below_reference" if fps < minimum else "above_reference"


def resolve_references(
    automatic: dict[str, ContentReference],
    default_target: float | None,
    overrides: dict[str, float | None],
) -> dict[str, ContentReference]:
    references = {}
    for label, reference in automatic.items():
        value = overrides.get(label, default_target)
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError("Content target must be finite and positive")
        references[label] = (
            ContentReference(value, "manual", "user_reference") if value is not None else reference
        )
    return references
