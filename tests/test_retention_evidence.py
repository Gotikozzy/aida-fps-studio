from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from test_graph_projection import project
from test_observable_cadence import sample
from test_second_presentation import timeline

from dg_fps.analyzers.cadence import (
    CadenceAnalyzer,
    CadenceParameters,
    _qualify_retention_evidence,
    content_cadence_readings,
)

BROAD = [[x, y] for x in range(8) for y in range(6)]


def evidence(i, repeated=False, cells=None):
    return replace(
        sample(i, repeated), mean_absolute_difference=0.0005 if repeated else 0.02,
        similarity_to_previous=0.9995 if repeated else 0.98,
        flow_magnitude_px=0.0 if repeated else 2.0,
        flow_confidence=0.0 if repeated else 0.7,
        flow_parameters={"motion_occupancy": {"cells": BROAD if cells is None else cells}},
    )


@pytest.mark.parametrize("capture,cadence", [(60, 30), (120, 40), (120, 60), (59.94, 29.97)])
def test_compressed_repetitions_keep_their_real_cadence(capture, cadence):
    step = round(capture / cadence)
    raw = [replace(evidence(i, i % step != 0), timestamp_seconds=i / capture)
           for i in range(round(capture * 3))]
    qualified = _qualify_retention_evidence(raw)
    assert all(s.signal_state == "observable" for s in qualified[step:-step])
    assert content_cadence_readings(qualified)[len(raw) - step - 1].content_fps == (
        pytest.approx(cadence))
    assert [s.repeated for s in qualified] == [s.repeated for s in raw]


def test_weak_local_movement_does_not_prove_a_retained_frame():
    raw = [evidence(i, i % 2 != 0, [[3, 3]]) for i in range(180)]
    qualified = _qualify_retention_evidence(raw)
    assert qualified[91].signal_state == "motion_unresolved"
    assert qualified[91].repeated  # auxiliary no-advance observation is preserved
    assert content_cadence_readings(qualified)[91].content_fps is None
    seconds = timeline(SimpleNamespace(samples=tuple(qualified)))["A"]
    assert seconds[1].origin == "reference" and seconds[1].measured_fps is None


def test_pending_rejection_is_unknown_without_independent_references():
    raw = [evidence(0, cells=[[3, 3]]), replace(
        evidence(1, cells=[[3, 3]]), cadence_repeated=True, signal_state="scope_pending",
        flow_parameters={"scope_warning": "local_only_change_requires_persistent_confirmation"},
    ), evidence(2, cells=[[3, 3]])]
    qualified = _qualify_retention_evidence(raw)
    assert qualified[1].signal_state == "scope_pending" and not qualified[1].repeated
    assert qualified[1].flow_parameters["retention_evidence"]["status"] == "unresolved"


def test_pending_overlay_rejection_can_be_corroborated_by_scene_motion():
    raw = [evidence(0), replace(
        evidence(1, cells=[[0, 0]]), cadence_repeated=True, signal_state="scope_pending",
        flow_parameters={"scope_warning": "local_only_change_requires_persistent_confirmation"},
    ), evidence(2)]
    qualified = _qualify_retention_evidence(raw)
    assert qualified[1].signal_state == "observable" and qualified[1].presentation_repeated
    assert not qualified[1].repeated
    assert "scope_warning" not in qualified[1].flow_parameters
    assert qualified[1].flow_parameters["retention_evidence"]["status"] == "qualified"


@pytest.mark.parametrize("basis", ["scene_transition", "uncertain_change", "partial_hold"])
def test_retention_references_do_not_cross_unknown_signal(basis):
    raw = [evidence(0), replace(evidence(1), signal_state=basis), evidence(2, True), evidence(3)]
    assert _qualify_retention_evidence(raw)[2].signal_state == "motion_unresolved"


@pytest.mark.parametrize("kind", ["segment", "gap", "invalid", "time", "age"])
def test_retention_references_respect_source_continuity(kind):
    raw = [evidence(0), evidence(1, True), evidence(2)]
    if kind == "segment":
        raw[2] = replace(raw[2], segment="B")
    elif kind == "gap":
        raw[2] = replace(raw[2], frame_index=3)
    elif kind == "invalid":
        raw[2] = replace(raw[2], timestamp_valid=False)
    elif kind == "time":
        raw[2] = replace(raw[2], timestamp_seconds=0.0)
    else:
        raw[2] = replace(raw[2], timestamp_seconds=0.2)
    assert _qualify_retention_evidence(raw)[1].signal_state == "motion_unresolved"


def test_strong_source_resolution_roi_remains_a_valid_reference():
    anchor = evidence(0, cells=[[3, 3]])
    anchor = replace(anchor, flow_parameters={
        **anchor.flow_parameters, "scope": "source_roi_visual_change",
        "refinement_regions": [{"evidence": {"active_regions": [{"support": 20}]}}],
    })
    raw = [anchor, evidence(1, True), replace(anchor, frame_index=2, timestamp_seconds=2 / 60)]
    assert _qualify_retention_evidence(raw)[1].signal_state == "observable"
    weak = replace(anchor, flow_confidence=0.1)
    raw[0] = weak
    assert _qualify_retention_evidence(raw)[1].signal_state == "motion_unresolved"


@pytest.mark.parametrize("scope,expected", [
    ("decoded_source", "observable"), ("analysis_resolution_only", "motion_unresolved"),
])
def test_exact_source_identity_is_distinct_from_downscaled_identity(scope, expected):
    raw = replace(evidence(0, True), similarity_to_previous=1.0, mean_absolute_difference=0.0,
                  flow_parameters={"pixel_identity_scope": scope})
    assert _qualify_retention_evidence([raw])[0].signal_state == expected


def test_pair_identity_records_when_a_small_source_change_disappears_in_downscaling():
    a = np.random.default_rng(46).integers(30, 180, (64, 64, 3), dtype=np.uint8)
    b = a.copy()
    b[1, 1, 0] += 1
    result = CadenceAnalyzer(CadenceParameters(
        analysis_width=8, analysis_height=8, refinement_regions=0,
    ))._measure_pair(a, b)
    assert result.flow_backend == "exact_pixel_comparison"
    assert result.flow_parameters["pixel_identity_scope"] == "analysis_resolution_only"


@pytest.mark.parametrize("state", ["scope_pending", "motion_unresolved"])
def test_graph_projects_uncertainty_without_turning_it_into_a_drop(state):
    samples = [sample(i) for i in range(7)]
    samples[2] = replace(samples[2], signal_state=state)
    points = project([60, 60, None, 25, 30, 60, 60],
                     [0, 0.1, 0.2, 0.3, 0.4, 1.4, 1.5], samples)
    assert all(p.graph_fps == 60 for p in points)
    assert points[3].measured_fps == 25  # original reading retained separately
    assert points[2].graph_origin == "projected"
