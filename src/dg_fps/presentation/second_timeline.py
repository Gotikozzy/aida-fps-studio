"""Offline presentation buckets. Never overwrite frame measurements or conclusions."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from statistics import median

from dg_fps.analyzers.cadence import CadenceSample
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.presentation.fps_display import fps_display

SECOND_POLICY = {
    "version": "1.0.0",
    "scope": "export_presentation_only",
    "window_seconds": 1,
    "minimum_observable_coverage": 0.9,
    "aggregation": "closed_update_periods_split_by_overlap_duration",
    "unknown_gaps": "never_bridged",
    "fallback": "explicit_defined_reference_only",
    "graph": "solid_measured_dotted_reference",
}


@dataclass(frozen=True, slots=True)
class PresentationSecond:
    segment: str
    second: int
    start_seconds: float
    end_seconds: float
    observable_seconds: float
    period_seconds: float
    update_equivalents: float
    measured_fps: float | None
    displayed_fps: float | None
    reference_fps: float | None
    origin: str
    reason: str
    open_hold_seconds: float = 0.0

    @property
    def coverage(self) -> float:
        return self.observable_seconds / (self.end_seconds - self.start_seconds)

    def to_dict(self) -> dict:
        return {**asdict(self), "coverage": self.coverage}


def second_key(seconds: float) -> int:
    return math.floor(seconds + 1e-9)


def build_second_timeline(
    samples: tuple[CadenceSample, ...],
    index: TimestampIndex,
    references: dict[str, ContentReference],
    capture_fps: float,
    check_cancelled: Callable[[], None] = lambda: None,
    *,
    range_bounds: dict[str, tuple[float, float]] | None = None,
) -> dict[str, tuple[PresentationSecond, ...]]:
    groups: dict[str, list[CadenceSample]] = {}
    for sample in samples:
        groups.setdefault(sample.segment, []).append(sample)
    bounds = range_bounds or {}
    for label in bounds:
        groups.setdefault(label, [])
    timelines = {}
    for label, items in groups.items():
        check_cancelled()
        if label in bounds:
            start, end = bounds[label]
            if not math.isfinite(start) or not math.isfinite(end) or end <= start:
                timelines[label] = ()
                continue
        else:
            first, last = items[0], items[-1]
            if last.frame_index + 1 < len(index):
                duration = index[last.frame_index + 1].seconds - last.timestamp_seconds
            elif len(items) > 1:
                duration = last.timestamp_seconds - items[-2].timestamp_seconds
            else:
                duration = 1 / capture_fps
            start, end = first.timestamp_seconds, last.timestamp_seconds + duration
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError("Invalid presentation interval")
        buckets = {}
        for key in range(second_key(start), math.ceil(end - 1e-9)):
            a, b = max(start, key), min(end, key + 1)
            if b > a:
                buckets[key] = [a, b, 0.0, 0.0, 0.0, 0.0]

        def allocate(
            a: float,
            b: float,
            *,
            period: bool = False,
            open_hold: bool = False,
            _buckets=buckets,
        ) -> None:
            if b <= a:
                return
            for key in range(second_key(a), math.ceil(b - 1e-9)):
                bucket = _buckets.get(key)
                if bucket is None:
                    continue
                overlap = max(0.0, min(b, bucket[1]) - max(a, bucket[0]))
                if open_hold:
                    bucket[5] += overlap
                elif period:
                    bucket[3] += overlap
                    bucket[4] += overlap / (b - a)
                else:
                    bucket[2] += overlap

        previous = None
        anchor = None
        recent_periods = []
        for number, sample in enumerate(items):
            if number % 1024 == 0:
                check_cancelled()
            continuous = (
                previous is not None
                and sample.frame_index == previous.frame_index + 1
                and sample.timestamp_valid
                and previous.timestamp_valid
                and sample.timestamp_seconds > previous.timestamp_seconds
                and sample.signal_state == previous.signal_state == "observable"
            )
            if not continuous:
                anchor = None
                recent_periods.clear()
            else:
                allocate(previous.timestamp_seconds, sample.timestamp_seconds)
                if not sample.presentation_repeated:
                    if anchor is not None:
                        allocate(anchor, sample.timestamp_seconds, period=True)
                        recent_periods.append(sample.timestamp_seconds - anchor)
                        recent_periods = recent_periods[-12:]
                    anchor = sample.timestamp_seconds
            previous = sample
        # An unclosed hold is not evidence of a normal-rate window. Do not discard it
        # from the denominator and extrapolate the few earlier fast updates instead.
        if anchor is not None and recent_periods and end - anchor > 1.5 * median(recent_periods):
            allocate(anchor, end, open_hold=True)
        reference = references.get(label)
        target = reference.target_fps if reference is not None else None
        values = []
        for key, (a, b, observable, periods, updates, open_hold) in buckets.items():
            coverage = min(1.0, observable / (b - a))
            valid = coverage >= 0.9 - 1e-8 and periods > 0 and open_hold <= (b - a) * 0.1
            measured = min(capture_fps, updates / periods) if valid else None
            display = fps_display(measured, capture_fps)
            values.append(
                PresentationSecond(
                    label,
                    key,
                    a,
                    b,
                    observable,
                    periods,
                    updates,
                    measured,
                    display.value if measured is not None else target,
                    target,
                    "measured"
                    if measured is not None
                    else "reference"
                    if target is not None
                    else "none",
                    "closed_observed_periods"
                    if valid
                    else "open_hold"
                    if open_hold
                    else "insufficient_coverage"
                    if coverage < 0.9
                    else "no_closed_periods",
                    open_hold,
                )
            )
        timelines[label] = tuple(values)
    return timelines


def timecode(seconds: float) -> str:
    value = max(0, math.floor(seconds + 1e-9))
    return f"{value // 3600:02d}:{value // 60 % 60:02d}:{value % 60:02d}"
