from __future__ import annotations

from dataclasses import replace

import cv2
import numpy as np
import pytest

from dg_fps.analyzers.cadence import (
    CadenceAnalyzer,
    CadenceParameters,
    CadenceSample,
    _build_repeated_events,
    _build_summary,
    _mark_scope_changes,
    content_cadence_readings,
    measure_visual_advance,
)
from dg_fps.vision.optical_flow.opencv_cpu import OpenCVFarnebackBackend


def sample(index: int, repeated: bool = False) -> CadenceSample:
    return CadenceSample(
        "A", index, index / 60, None, None, None, None, None, None, None, None, repeated
    )


def texture(height: int, width: int) -> np.ndarray:
    return np.random.default_rng(910).integers(30, 220, (height, width, 3), np.uint8)


def test_tiny_moving_region_on_black_is_observable():
    a = np.zeros((360, 640, 3), np.uint8)
    a[164:196, 304:336] = texture(32, 32)
    b = a.copy()
    b[164:196, 304:336] = np.roll(a[164:196, 304:336], 2, axis=1)
    result = measure_visual_advance(a, b, backend=OpenCVFarnebackBackend())
    assert result.signal_state == "observable"
    assert not result.repeated
    assert result.flow_parameters["active_regions"]
    assert result.flow_parameters["scope"] == "localized_visual_change"


def test_opposing_motion_does_not_require_global_direction():
    a = texture(192, 320)
    b = np.concatenate((np.roll(a[:96], 3, axis=1), np.roll(a[96:], -3, axis=1)))
    result = measure_visual_advance(a, b, backend=OpenCVFarnebackBackend())
    assert not result.repeated and result.signal_state == "observable"
    assert result.flow_confidence > 0.6
    assert result.flow_parameters["backward_backend"] == "opencv_farneback_cpu"


def test_slow_subpixel_motion_is_observable():
    a = texture(192, 320)
    b = cv2.warpAffine(
        a, np.float32([[1, 0, 0.25], [0, 1, 0]]), (320, 192), borderMode=cv2.BORDER_REFLECT
    )
    result = measure_visual_advance(a, b, backend=OpenCVFarnebackBackend())
    assert not result.repeated and result.signal_state == "observable"


def test_brightness_pumping_does_not_prove_motion():
    a = texture(192, 320)
    b = np.clip(a.astype(np.int16) + 5, 0, 255).astype(np.uint8)
    result = measure_visual_advance(a, b)
    assert result.signal_state != "observable"
    samples = [replace(sample(i), signal_state=result.signal_state) for i in range(120)]
    assert _build_summary(samples, 60).content_fps is None


def test_different_compression_of_same_image_does_not_prove_cadence():
    a = texture(192, 320)
    images = [
        cv2.imdecode(
            cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, quality])[1], cv2.IMREAD_COLOR
        )
        for quality in (92, 65)
    ]
    result = measure_visual_advance(*images, backend=OpenCVFarnebackBackend())
    assert result.signal_state != "observable" or result.repeated


def test_source_resolution_refinement_preserves_roi():
    a = np.zeros((1080, 1920, 3), np.uint8)
    a[510:534, 944:968] = texture(24, 24)
    b = a.copy()
    b[510:534, 944:968] = np.roll(a[510:534, 944:968], 2, axis=1)
    analyzer = CadenceAnalyzer(
        CadenceParameters(analysis_width=160, analysis_height=90), backend=OpenCVFarnebackBackend()
    )
    result = analyzer._measure_pair(a, b)
    assert not result.repeated and result.signal_state == "observable"
    assert result.flow_parameters["refinement_regions"]
    assert result.flow_parameters["flow_units"] == "source_pixels"
    assert result.flow_support_ratio < 0.01
    assert result.flow_parameters["active_regions"]
    assert result.flow_parameters["refinement_regions"][0]["source_size"] == [1920, 1080]


def test_long_retention_survives_window_and_is_not_zero_fps():
    samples = [sample(i, i % 2 != 0 if i < 60 or i >= 210 else True) for i in range(300)]
    readings = content_cadence_readings(samples)
    assert readings[200].status == "extended_hold"
    assert readings[200].content_fps is None
    assert readings[200].pending_hold_ms > 2000
    events = _build_repeated_events(samples)
    event = max(events, key=lambda value: value.observed_duration_seconds)
    assert event.cadence_role == "extended_hold" and event.closed
    assert event.observed_duration_seconds == pytest.approx((210 - 58) / 60)
    assert event.cause == "undetermined"
    summary = _build_summary(samples, 60)
    assert summary.prolonged_retention_seconds > 2.5
    assert summary.content_fps < 20  # the complete hold is not erased from the denominator
    assert summary.ambiguous_seconds > 2.0


def test_pause_and_freeze_with_identical_pixels_have_identical_results():
    pause = [sample(i, i % 2 != 0 if i < 60 else True) for i in range(240)]
    freeze = [replace(value) for value in pause]
    assert _build_summary(pause, 60) == _build_summary(freeze, 60)
    assert _build_repeated_events(pause) == _build_repeated_events(freeze)
    event = _build_repeated_events(pause)[-1]
    assert event.cause == "undetermined" and not event.closed
    assert event.observed_duration_seconds > 2.9


def test_weighted_complete_periods_do_not_average_fast_and_slow_rates():
    samples = [sample(i, repeated=i > 60 and i % 3 != 0) for i in range(241)]
    summary = _build_summary(samples, 60)
    assert summary.content_fps == pytest.approx(30, abs=0.3)
    assert summary.content_fps == pytest.approx(
        summary.complete_period_count / summary.complete_period_seconds
    )
    assert summary.measurable_seconds + summary.ambiguous_seconds == pytest.approx(4.0)


def test_motion_of_small_overlay_cannot_hide_loss_of_scene_evidence():
    distributed = [{"x": x * 32, "y": y * 32} for x in range(8) for y in range(4)]
    localized = [{"x": 0, "y": 0}]
    samples = [
        replace(
            sample(i),
            flow_support_ratio=0.5 if i < 6 else 0.01,
            flow_parameters={"active_regions": distributed if i < 6 else localized},
        )
        for i in range(120)
    ]
    marked = _mark_scope_changes(samples)
    assert marked[-1].signal_state == "partial_hold"
    assert not marked[-1].repeated  # actual local visual changes remain recorded
    assert content_cadence_readings(marked)[119].content_fps is None
    assert any(
        event.cadence_role == "partial_scene_hold" for event in _build_repeated_events(marked)
    )


def test_weak_flow_cannot_hide_distributed_subpixel_change():
    distributed = [{"x": x * 16, "y": y * 16} for x in range(8) for y in range(4)]
    samples = [
        replace(
            sample(i),
            flow_support_ratio=0.5 if i < 6 else 0.01,
            flow_parameters={
                "active_regions": distributed if i < 6 else distributed[:2],
                "changed_pixel_ratio": 0.9,
            },
        )
        for i in range(120)
    ]
    marked = _mark_scope_changes(samples)
    assert all(not value.presentation_repeated for value in marked)
    assert _build_summary(marked, 60).content_fps == pytest.approx(60)


def test_refinement_does_not_promote_compression_noise():
    source = texture(360, 640)
    images = [
        cv2.imdecode(
            cv2.imencode(".jpg", source, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR
        )
        for q in (92, 65)
    ]
    result = CadenceAnalyzer(
        CadenceParameters(analysis_width=160, analysis_height=90), backend=OpenCVFarnebackBackend()
    )._measure_pair(*images)
    assert result.signal_state != "observable" or result.repeated


def test_initial_static_logo_has_no_invented_fps():
    image = np.zeros((192, 320, 3), np.uint8)
    cv2.putText(image, "LOGO", (60, 110), cv2.FONT_HERSHEY_SIMPLEX, 2, (240, 240, 240), 3)
    result = measure_visual_advance(image, image)
    assert result.repeated
    summary = _build_summary([sample(i, repeated=True) for i in range(120)], 60)
    assert summary.content_fps is None and summary.ambiguous_seconds > 1.9
