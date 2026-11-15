from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from dg_fps.analyzers.base import AnalysisContext
from dg_fps.analyzers.cadence import (
    CadenceAnalyzer,
    CadenceSample,
    content_cadence_readings,
    measure_visual_advance,
)
from dg_fps.vision.optical_flow.opencv_cpu import OpenCVFarnebackBackend


def captured_video(
    path: Path,
    capture_rate: int,
    content_rate: int,
    *,
    dark: bool = False,
    compressed: bool = False,
) -> Path:
    rng = np.random.default_rng(814)
    texture = rng.integers(5 if dark else 30, 30 if dark else 225, (64, 96, 1), dtype=np.uint8)
    texture = np.repeat(texture, 3, axis=2)
    with av.open(str(path), mode="w") as output:
        stream = output.add_stream("mpeg4" if compressed else "ffv1", rate=capture_rate)
        stream.width, stream.height, stream.pix_fmt = 96, 64, "yuv420p" if compressed else "bgr0"
        for index in range(2 * capture_rate + 1):
            update = index * content_rate // capture_rate
            rgb = np.roll(texture, update * 2, axis=1)
            frame = av.VideoFrame.from_ndarray(rgb, format="rgb24")
            frame.pts, frame.time_base = index, Fraction(1, capture_rate)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return path


@pytest.mark.parametrize(
    "capture,content",
    [
        (120, 120),
        (120, 60),
        (120, 40),
        (120, 30),
        (120, 24),
        (120, 20),
        (120, 15),
        (120, 10),
        (120, 47),
        (60, 30),
        (60, 60),
    ],
)
@pytest.mark.parametrize("use_explicit_cpu", [False, True])
def test_real_encoded_capture_recovers_content_fps(
    tmp_path: Path, capture: int, content: int, use_explicit_cpu: bool
) -> None:
    source = captured_video(tmp_path / "reference.mkv", capture, content)
    backend = OpenCVFarnebackBackend() if use_explicit_cpu else None
    result = CadenceAnalyzer(backend=backend).analyze(
        AnalysisContext(source, container_fps=float(capture))
    )
    reading = content_cadence_readings(result.samples)[result.samples[-1].frame_index]
    assert reading.capture_fps == pytest.approx(capture, rel=0.05)
    assert reading.content_fps == pytest.approx(content, abs=0.6)
    assert result.summary.content_fps == pytest.approx(content, abs=0.6)
    assert result.summary.observable_window_ratio > 0.75


@pytest.mark.parametrize("use_explicit_cpu", [False, True])
def test_dark_motion_remains_measurable(tmp_path: Path, use_explicit_cpu: bool) -> None:
    source = captured_video(tmp_path / "dark.mkv", 120, 40, dark=True)
    backend = OpenCVFarnebackBackend() if use_explicit_cpu else None
    result = CadenceAnalyzer(backend=backend).analyze(AnalysisContext(source, container_fps=120))
    assert result.summary.content_fps == pytest.approx(40, abs=0.6)


def sample(index: int, *, repeated: bool = False) -> CadenceSample:
    return CadenceSample(
        "a", index, index / 120, None, None, None, None, None, None, None, None, repeated
    )


def test_long_static_period_is_not_reported_as_zero_fps() -> None:
    samples = [sample(i, repeated=i % 4 != 0 if i < 120 else True) for i in range(300)]
    readings = content_cadence_readings(samples)
    assert readings[100].content_fps == pytest.approx(30)
    assert readings[299].content_fps is None
    assert readings[299].status == "extended_hold"
    assert any(reading.status == "extended_hold" for reading in readings.values())


def test_no_inference_bridges_blackout_or_segment_boundaries() -> None:
    samples = [sample(i, repeated=i % 4 != 0) for i in range(200)]
    samples[120] = replace(samples[120], signal_state="dark_unobservable")
    readings = content_cadence_readings(samples)
    assert readings[120].content_fps is None
    assert readings[121].content_fps is None
    assert readings[160].content_fps == pytest.approx(30)
    samples[160] = replace(samples[160], segment="b")
    assert content_cadence_readings(samples)[160].content_fps is None


def test_rate_change_is_resolved_without_snapping_to_standard_rates() -> None:
    samples = [sample(i, repeated=i % (4 if i < 240 else 3) != 0) for i in range(480)]
    readings = content_cadence_readings(samples)
    assert readings[200].content_fps == pytest.approx(30)
    assert readings[479].content_fps == pytest.approx(40)


@pytest.mark.parametrize("value", [0, 5, 80, 255])
def test_uniform_frames_are_unobservable_not_low_fps(value: int) -> None:
    rgb = np.full((64, 96, 3), value, dtype=np.uint8)
    measurement = measure_visual_advance(rgb, rgb)
    assert measurement.repeated
    assert measurement.signal_state != "observable"


def test_selected_flow_backend_is_used_and_recorded() -> None:
    class CountingBackend(OpenCVFarnebackBackend):
        count = 0

        def compute(self, previous_rgb, current_rgb):
            self.count += 1
            return super().compute(previous_rgb, current_rgb)

    backend = CountingBackend()
    rng = np.random.default_rng(7)
    rgb = rng.integers(0, 255, (64, 96, 3), dtype=np.uint8)
    measurement = measure_visual_advance(rgb, np.roll(rgb, 2, axis=1), backend=backend)
    assert backend.count == 2
    assert measurement.flow_backend == backend.backend_id
    assert not measurement.repeated
    measure_visual_advance(rgb, rgb, backend=backend)
    assert backend.count == 2


@pytest.mark.parametrize("content", [30, 40, 60, 120])
def test_compressed_capture_recovers_content_fps(tmp_path: Path, content: int) -> None:
    source = captured_video(tmp_path / "compressed.mkv", 120, content, compressed=True)
    result = CadenceAnalyzer().analyze(AnalysisContext(source, container_fps=120))
    assert result.summary.content_fps == pytest.approx(content, abs=0.8)


def test_small_noise_does_not_turn_repeated_texture_into_updates() -> None:
    rng = np.random.default_rng(29)
    rgb = rng.integers(30, 220, (96, 160, 3), dtype=np.uint8)
    noisy = np.clip(rgb.astype(np.int16) + rng.integers(-1, 2, rgb.shape), 0, 255).astype(np.uint8)
    assert measure_visual_advance(rgb, noisy).repeated


def test_fractional_capture_rate_is_preserved() -> None:
    samples = [
        replace(sample(i, repeated=i % 3 != 0), timestamp_seconds=i * 1001 / 120000)
        for i in range(240)
    ]
    reading = content_cadence_readings(samples)[239]
    assert reading.content_fps == pytest.approx(40000 / 1001)
    assert reading.capture_fps == pytest.approx(120000 / 1001)


def test_expected_holds_are_not_performance_findings(tmp_path: Path) -> None:
    source = captured_video(tmp_path / "regular.mkv", 120, 30)
    result = CadenceAnalyzer().analyze(AnalysisContext(source, container_fps=120))
    assert not result.findings
    assert any(event.cadence_role == "regular_cadence_hold" for event in result.events)
    assert not any(event.cadence_role == "extended_hold" for event in result.events)


def test_bounded_stall_is_detected_without_calling_regular_holds_stalls() -> None:
    from dg_fps.analyzers.cadence import _build_repeated_events

    samples = [sample(i, repeated=i % 4 != 0 or 120 <= i < 144) for i in range(240)]
    events = _build_repeated_events(samples)
    assert any(
        event.cadence_role == "extended_hold" and event.start_frame == 117 for event in events
    )
