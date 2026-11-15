from dataclasses import replace

import numpy as np
import pytest
from test_graph_projection import project
from test_observable_cadence import sample

from dg_fps.analyzers.cadence import _mark_scope_changes, content_cadence_readings
from dg_fps.analyzers.local_motion import motion_occupancy


def test_occupancy_retains_complete_validated_support_before_visual_subsampling():
    mask = np.zeros((360, 640), dtype=bool)
    for y in range(6):
        for x in range(8):
            mask[y * 60 + 10 : y * 60 + 14, x * 80 + 10 : x * 80 + 14] = True
    occupancy = motion_occupancy(mask)
    assert len(occupancy["cells"]) == 48
    assert occupancy["origin"] == "full_validated_motion_mask"
    assert mask.mean() < 0.01  # sparse yet spatially distributed validated motion


def test_sparse_distributed_motion_does_not_depend_on_exact_witness_coordinates():
    cells = [[x, y] for x in range(8) for y in range(6)]
    samples = [
        replace(
            sample(i, repeated=i % 2 == 1),
            flow_support_ratio=0.5 if i < 6 else 0.02,
            flow_parameters={
                "analysis_size": [640, 360],
                "active_regions": [{"x": 10 + i % 3, "y": 10}],
                "motion_occupancy": {"grid": [8, 6], "cells": cells},
            },
        )
        for i in range(180)
    ]
    marked = _mark_scope_changes(samples)
    assert [s.presentation_repeated for s in marked] == [s.repeated for s in samples]
    rates = content_cadence_readings(marked)
    assert rates[179].content_fps == pytest.approx(30)


def test_small_local_overlay_still_cannot_establish_scene_cadence():
    cells = [[x, y] for x in range(8) for y in range(6)]
    samples = [
        replace(
            sample(i),
            flow_support_ratio=0.5 if i < 6 else 0.01,
            flow_parameters={
                "motion_occupancy": {
                    "grid": [8, 6],
                    "cells": cells if i < 6 else [[0, 0]],
                }
            },
        )
        for i in range(100)
    ]
    marked = _mark_scope_changes(samples)
    assert marked[6].signal_state == "partial_hold"  # includes pending entrance
    assert content_cadence_readings(marked)[99].content_fps is None


def test_uncertain_graph_holds_before_suspect_drop_and_through_recovery():
    values = [30, 30, 12, None, None, 18, 20, 20]
    times = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.5]
    samples = [sample(i) for i in range(len(values))]
    samples[2] = replace(
        samples[2],
        flow_parameters={
            "scope_warning": "local_only_change_requires_persistent_confirmation",
        },
    )
    samples[3:5] = [replace(s, signal_state="partial_hold") for s in samples[3:5]]
    points = project(values, times, samples)
    assert [p.graph_fps for p in points] == [30, 30, 30, 30, 30, 30, 30, 20]
    assert points[2].measured_fps == 12  # immutable original evidence
    assert all(p.graph_origin == "projected" for p in points[2:7])
    assert points[7].graph_origin == "measured"  # real low FPS remains visible


def test_real_drop_without_evidence_loss_is_unchanged():
    points = project([30, 30, 24, 20, 15, 20, 30])
    assert [p.graph_fps for p in points] == [30, 30, 24, 20, 15, 20, 30]
    assert all(p.graph_origin == "measured" for p in points)


def test_entrance_uses_reading_before_the_pending_warning_contaminated_its_window():
    samples = [sample(i) for i in range(7)]
    samples[2] = replace(
        samples[2],
        flow_parameters={
            "scope_warning": "local_only_change_requires_persistent_confirmation",
        },
    )
    samples[4] = replace(samples[4], signal_state="partial_hold")
    points = project([30, 30, 25, 22, None, 18, 20], samples=samples)
    assert [p.graph_fps for p in points] == [30] * 7
    assert points[3].measured_fps == 22


def test_unqualified_recovery_cannot_invent_a_trusted_anchor():
    samples = [replace(sample(0), signal_state="partial_hold"), sample(1)]
    points = project([None, 15], [0, 0.1], samples)
    assert all(p.graph_fps is None for p in points)


def test_spatial_graph_hold_does_not_cross_a_cut():
    samples = [sample(i) for i in range(7)]
    samples[2] = replace(samples[2], signal_state="partial_hold")
    samples[3] = replace(samples[3], signal_state="scene_transition")
    points = project([30, 30, None, None, None, 20, 20], samples=samples)
    assert points[2].graph_fps == 30
    assert points[3].graph_fps is None
    assert points[4].graph_fps == 20
