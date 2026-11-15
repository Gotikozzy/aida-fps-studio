import json
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from dg_fps.analyzers.base import AnalysisContext, AnalysisFrameRange
from dg_fps.analyzers.cadence import (
    CadenceAnalyzer,
    cadence_advance_map,
    measure_visual_advance,
)
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.reports.cadence_json import CadenceJsonWriter


def _make_repeated_video(path: Path) -> Path:
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("mpeg4", rate=Fraction(10, 1))
        stream.width = 64
        stream.height = 48
        stream.pix_fmt = "yuv420p"
        for index, value in enumerate((0, 0, 50, 50, 100, 150)):
            image = np.full((48, 64, 3), value, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(image, format="rgb24")
            frame.pts = index
            frame.time_base = Fraction(1, 10)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def test_cadence_analyzer_detects_controlled_repeated_frames(tmp_path: Path) -> None:
    source = _make_repeated_video(tmp_path / "repeated.mp4")

    result = CadenceAnalyzer().analyze(AnalysisContext(source, container_fps=10.0))

    assert result.summary.total_frames == 6
    assert result.summary.repeated_frames == 2
    assert result.summary.unique_frames == 4
    assert result.summary.estimated_unique_fps == 3 / 0.5
    assert [(event.start_frame, event.end_frame) for event in result.events] == [
        (1, 1),
        (3, 3),
    ]
    assert len(result.findings) == 0


def test_cadence_detects_coherent_motion_in_a_dark_scene() -> None:
    rng = np.random.default_rng(7)
    previous = np.full((180, 320, 3), 4, np.uint8)
    current = previous.copy()
    texture = rng.integers(7, 28, (70, 90, 1), dtype=np.uint8)
    texture = np.repeat(texture, 3, axis=2)
    previous[55:125, 80:170] = texture
    current[55:125, 84:174] = texture

    measurement = measure_visual_advance(previous, current)
    advance_map = cadence_advance_map(previous, current)

    assert measurement.repeated is False
    assert measurement.flow_magnitude_px > 1.0
    assert measurement.flow_confidence > 0.5
    assert measurement.changed_block_ratio > 0
    assert np.any((advance_map[:, :, 1] > 150) & (advance_map[:, :, 2] > 150))


def test_cadence_keeps_identical_dark_frames_repeated() -> None:
    frame = np.full((180, 320, 3), 5, np.uint8)

    measurement = measure_visual_advance(frame, frame.copy())

    assert measurement.repeated is True
    assert measurement.flow_support_ratio == 0


def test_cadence_writer_generates_full_and_compact_json(tmp_path: Path) -> None:
    source = _make_repeated_video(tmp_path / "repeated.mp4")
    result = CadenceAnalyzer().analyze(AnalysisContext(source, container_fps=10.0))
    paths = CadenceJsonWriter(app_name="DG Graphics Analyzer", app_version="0.1.0").write(
        result,
        source_metadata={"codec": "ffv1"},
        projects_root=tmp_path / "projects",
    )

    analysis = json.loads(paths.analysis_json.read_text(encoding="utf-8"))
    report = json.loads(paths.report_json.read_text(encoding="utf-8"))

    assert analysis["schema_version"] == "1.4"
    assert len(analysis["frames"]) == 6
    assert analysis["summary"]["repeated_frames"] == 2
    assert report["schema_version"] == "1.4"
    assert "frames" not in report
    assert report["analysis_summary"]["repeated_frame_events"] == 2
    assert len(report["findings"]) == 0


def test_cadence_analyzer_limits_comparison_to_multiple_ranges(tmp_path: Path) -> None:
    source = _make_repeated_video(tmp_path / "repeated.mp4")
    index = TimestampIndex.build(source)
    ranges = (
        AnalysisFrameRange(0, 1, "Jogabilidade A"),
        AnalysisFrameRange(4, 5, "Jogabilidade B"),
    )

    result = CadenceAnalyzer().analyze(
        AnalysisContext(
            source,
            container_fps=10.0,
            frame_ranges=ranges,
            timestamp_index=index,
        )
    )

    assert result.summary.total_frames == 4
    assert result.summary.repeated_frames == 1
    assert [sample.frame_index for sample in result.samples] == [0, 1, 4, 5]
    assert [event.segment for event in result.events] == ["Jogabilidade A"]
    assert result.segment_summaries["Jogabilidade B"].repeated_frames == 0


def test_cadence_rate_uses_observed_time_not_container_rate(tmp_path: Path) -> None:
    source = _make_repeated_video(tmp_path / "timing.mp4")
    first = CadenceAnalyzer().analyze(AnalysisContext(source, container_fps=10.0))
    wrong_metadata = CadenceAnalyzer().analyze(AnalysisContext(source, container_fps=120.0))
    assert first.summary.estimated_unique_fps == wrong_metadata.summary.estimated_unique_fps
    assert first.summary.observed_intervals == 5


def test_single_frame_has_no_observed_rate() -> None:
    from dg_fps.analyzers.cadence import CadenceSample, _build_summary

    sample = CadenceSample("a", 0, 0.0, None, None, None, None, None, None, None, None, False)
    assert _build_summary([sample], 60.0).estimated_unique_fps is None


def test_exported_samples_match_declared_schema_fields(tmp_path: Path) -> None:
    from dataclasses import fields

    from dg_fps.analyzers.cadence import (
        CadenceSample,
        CadenceSummary,
        ContentCadenceReading,
    )

    schema = json.loads(
        (Path(__file__).parents[1] / "schemas/analysis.schema.json").read_text(encoding="utf-8")
    )
    assert {field.name for field in fields(CadenceSample)} <= set(
        schema["properties"]["frames"]["items"]["properties"]
    )
    assert {field.name for field in fields(CadenceSummary)} <= set(
        schema["$defs"]["cadenceSummary"]["properties"]
    )
    assert {field.name for field in fields(ContentCadenceReading)} == set(
        schema["properties"]["content_cadence"]["additionalProperties"]["properties"]
    )
