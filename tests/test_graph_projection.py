from dataclasses import asdict, replace

import pytest
from test_content_targets import observations

from dg_fps.presentation.frame_timeline import PresentationFrame, project_inconclusive_fps


def project(values, times=None, samples=None):
    times = times or [i / 10 for i in range(len(values))]
    if samples is None:
        samples = observations(10, ((len(values) / 10, 10, "observable"),)).samples
    samples = tuple(replace(s, timestamp_seconds=t) for s, t in zip(samples, times, strict=True))
    points = tuple(
        PresentationFrame(
            s.segment,
            s.frame_index,
            s.timestamp_seconds,
            v,
            v if v is not None else 60,
            "measured" if v is not None else "reference",
            25,
            "measured",
        )
        for s, v in zip(samples, values, strict=True)
    )
    before = [asdict(p) for p in points]
    output = project_inconclusive_fps(points, samples)
    assert [asdict(p) for p in points] == before
    for old, new in zip(points, output, strict=True):
        a, b = asdict(old), asdict(new)
        for field in ("graph_fps", "graph_origin", "projection_method", "projection_support"):
            a.pop(field)
            b.pop(field)
        assert a == b
    return output


@pytest.mark.parametrize("left,right", [(45, 45), (45, 48), (48, 42)])
def test_short_projection_is_bounded_and_does_not_return_to_target(left, right):
    points = project([left, None, None, None, right])
    assert [p.graph_origin for p in points] == [
        "measured",
        "projected",
        "projected",
        "projected",
        "measured",
    ]
    assert all(min(left, right) <= p.graph_fps <= max(left, right) for p in points)
    assert points[1].graph_fps == pytest.approx(left + (right - left) * 0.15625)
    assert points[2].graph_fps == pytest.approx((left + right) / 2)
    assert points[1].projection_support == (0, 4)
    assert points[1].projection_method == "bounded_smoothstep"
    assert all(p.measured_fps is None and p.displayed_fps == 60 for p in points[1:4])


def test_projection_uses_real_pts_and_long_gaps_are_linear():
    points = project([40, None, None, 50], [0, 0.1, 1.5, 2])
    assert points[1].graph_fps == pytest.approx(40.5)
    assert points[2].graph_fps == pytest.approx(47.5)
    assert points[1].projection_method == "linear"


def test_leading_and_trailing_gaps_hold_the_only_measured_endpoint():
    points = project([None, None, 44, None, None])
    assert all(p.graph_fps == 44 for p in points)
    assert points[0].projection_method == "hold_following"
    assert points[-1].projection_method == "hold_previous"
    assert points[0].projection_support == (2,)


def test_no_measurement_does_not_invent_a_projection():
    assert all(
        p.graph_fps is None and p.graph_origin == "unavailable" for p in project([None, None, None])
    )


@pytest.mark.parametrize("boundary", ["cut", "invalid", "missing_frame", "segment", "backward_pts"])
def test_projection_never_crosses_a_boundary(boundary):
    samples = list(observations(10, ((0.5, 10, "observable"),)).samples)
    times = [0, 0.1, 0.2, 0.3, 0.4]
    if boundary == "cut":
        samples[2] = replace(samples[2], signal_state="scene_transition")
    elif boundary == "invalid":
        samples[2] = replace(samples[2], timestamp_valid=False)
    elif boundary == "missing_frame":
        samples[2:] = [replace(s, frame_index=s.frame_index + 1) for s in samples[2:]]
    elif boundary == "segment":
        samples[2:] = [replace(s, segment="B") for s in samples[2:]]
    else:
        times = [0, 0.1, 0.05, 0.15, 0.25]
    points = project([40, None, None, None, 50], times, samples)
    assert points[1].graph_fps == 40
    assert points[3].graph_fps == 50
    assert points[1].projection_support == (0,)
    assert points[3].projection_support == (samples[4].frame_index,)
