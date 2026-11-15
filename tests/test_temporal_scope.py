"""Global scene evidence: source-time confirmation without FPS-specific tuning."""
from dataclasses import replace

import pytest
from test_observable_cadence import sample

from dg_fps.analyzers.cadence import SCOPE_POLICY, _mark_scope_changes, content_cadence_readings

BROAD = [[x, y] for x in range(8) for y in range(6)]
LOCAL = (
    [[2, 2], [3, 2]], [[3, 2], [4, 2]], [[2, 3], [3, 3]], [[3, 3], [4, 3]],
)


def scene(capture=60.0, cadence=60.0, seconds=3):
    step = round(capture / cadence)
    frames = []
    for i in range(round(capture * seconds)):
        repeated = i >= 6 and i % step != 0
        cells = BROAD if i < 6 else LOCAL[(i // step) % len(LOCAL)]
        frames.append(replace(
            sample(i, repeated), timestamp_seconds=i / capture,
            flow_support_ratio=0.001,
            flow_parameters={"motion_occupancy": {"grid": [8, 6], "cells": cells}},
        ))
    return frames


@pytest.mark.parametrize("capture,cadence", [
    (30, 30), (60, 30), (120, 40), (60, 60), (120, 120), (59.94, 29.97),
])
def test_local_scene_updates_preserve_real_cadence_and_raw_repetitions(capture, cadence):
    raw = scene(capture, cadence)
    marked = _mark_scope_changes(raw)
    assert [s.repeated for s in marked] == [s.repeated for s in raw]
    assert [s.presentation_repeated for s in marked] == [s.repeated for s in raw]
    assert all(s.signal_state == "observable" for s in marked)
    assert content_cadence_readings(marked)[len(raw) - 1].content_fps == pytest.approx(cadence)
    assert any((s.flow_parameters or {}).get("scope_confirmation") for s in marked)
    assert all(s.flow_parameters.get("scope_confirmation") is None for s in raw)


def test_confirmation_requires_elapsed_source_time_not_three_quick_updates():
    marked = _mark_scope_changes(scene(120, 120)[:16])
    assert not any((s.flow_parameters or {}).get("scope_confirmation") for s in marked)


@pytest.mark.parametrize("cells", [[[0, 0]], [[3, 3]], [[2, 2], [3, 2]]])
def test_stationary_small_overlay_is_not_qualified_even_in_screen_center(cells):
    raw = scene()
    raw[6:] = [replace(s, flow_parameters={"motion_occupancy": {"cells": cells}}) for s in raw[6:]]
    marked = _mark_scope_changes(raw)
    assert marked[-1].signal_state == "partial_hold"
    assert not any((s.flow_parameters or {}).get("scope_confirmation") for s in marked)
    assert content_cadence_readings(marked)[179].content_fps is None


def test_local_confirmation_expires_instead_of_permanently_unlocking_overlay():
    raw = scene()
    raw[60:] = [replace(s, flow_parameters={"motion_occupancy": {"cells": [[0, 0]]}})
                for s in raw[60:]]
    marked = _mark_scope_changes(raw)
    assert (marked[50].flow_parameters or {}).get("scope_confirmation")
    assert marked[100].signal_state == "partial_hold"
    assert content_cadence_readings(marked)[179].content_fps is None


@pytest.mark.parametrize("boundary", ["cut", "uncertain", "gap", "segment", "time", "invalid"])
def test_temporal_confirmation_never_bridges_evidence_boundaries(boundary):
    raw = scene()[:17]
    # Each side contains fewer than 0.1 source seconds of local evidence.
    middle = raw[11]
    if boundary == "cut":
        raw[11] = replace(middle, signal_state="scene_transition")
    elif boundary == "uncertain":
        raw[11] = replace(middle, signal_state="uncertain_change")
    elif boundary == "invalid":
        raw[11] = replace(middle, timestamp_valid=False)
    elif boundary == "gap":
        raw[11:] = [replace(s, frame_index=s.frame_index + 1) for s in raw[11:]]
    elif boundary == "segment":
        raw[11:] = [replace(s, segment="B") for s in raw[11:]]
    else:
        raw[11:] = [replace(s, timestamp_seconds=(s.frame_index - 11) / 60) for s in raw[11:]]
    marked = _mark_scope_changes(raw)
    assert not any((s.flow_parameters or {}).get("scope_confirmation") for s in marked)


def test_confirmed_local_motion_cannot_erase_subsequent_repeated_frames():
    raw = scene(seconds=4)
    raw[90:150] = [replace(s, repeated=True) for s in raw[90:150]]
    marked = _mark_scope_changes(raw)
    assert all(s.repeated and s.presentation_repeated for s in marked[90:150])
    assert content_cadence_readings(marked)[140].content_fps is None


def test_timing_and_pixel_evidence_are_unchanged_and_confirmation_is_bounded():
    raw = scene()
    marked = _mark_scope_changes(raw)
    for a, b in zip(raw, marked, strict=True):
        assert (a.frame_index, a.timestamp_seconds, a.pts, a.time_base, a.repeated,
                a.similarity_to_previous, a.flow_support_ratio) == (
                    b.frame_index, b.timestamp_seconds, b.pts, b.time_base, b.repeated,
                    b.similarity_to_previous, b.flow_support_ratio)
        confirmation = (b.flow_parameters or {}).get("scope_confirmation")
        if confirmation:
            assert confirmation["classification"] == "heuristic"
            assert confirmation["confirmed_at_seconds"] - confirmation["start_seconds"] <= (
                SCOPE_POLICY["local_window_seconds"] + 1e-9)
