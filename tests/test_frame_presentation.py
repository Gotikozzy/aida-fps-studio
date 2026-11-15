from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest
from test_content_targets import observations

from dg_fps.presentation.content_targets import ContentReference, content_references
from dg_fps.presentation.frame_timeline import build_frame_timeline, export_references


def test_export_reference_defaults_to_capture_family_without_changing_inference():
    result = observations(59.94, ((4, 0, "dark_unobservable"),))
    result.summary = SimpleNamespace(container_fps=59.94)
    original = content_references(result)
    resolved = export_references(result, original)
    assert original["A"].target_fps is None
    assert resolved["A"].target_fps == 60
    assert resolved["A"].origin == "presentation_capture_reference"
    frames = build_frame_timeline(result, resolved)["A"]
    assert all(p.measured_fps is None and p.displayed_fps == 60 for p in frames)


@pytest.mark.parametrize("origin", ["manual", "inferred"])
def test_30_fps_game_in_60_fps_capture_keeps_established_target(origin):
    result = observations()
    result.summary = SimpleNamespace(container_fps=60)
    reference = ContentReference(30, origin, "defined")
    assert export_references(result, {"A": reference})["A"] == reference


@pytest.mark.parametrize(
    ("capture", "limit"), [(28.1, 30), (58.1, 60), (75, 75), (118.1, 120)]
)
def test_effective_reference_cannot_exceed_capture(capture, limit):
    result = observations()
    result.summary = SimpleNamespace(container_fps=capture)
    original = {"A": ContentReference(240, "inferred", "defined")}
    assert export_references(result, original)["A"].target_fps == limit
    assert original["A"].target_fps == 240


def test_40_fps_reference_uses_the_encoded_capture_rate():
    result = observations()
    reference = ContentReference(40, "manual", "defined")
    result.summary = SimpleNamespace(container_fps=58, observed_capture_fps=60)
    assert export_references(result, {"A": reference})["A"].target_fps == 58
    result.summary.container_fps = 58.01
    assert export_references(result, {"A": reference})["A"] == reference


def test_chart_has_every_source_frame_and_within_second_variations():
    result = observations(60, ((2, 60, "observable"), (2, 30, "observable")))
    original = [asdict(s) for s in result.samples]
    frames = build_frame_timeline(result, {"A": ContentReference(60, "manual", "defined")})["A"]
    assert len(frames) == 240
    third_second = [p for p in frames if 2 <= p.seconds < 3]
    assert len(third_second) == 60
    assert len({round(p.measured_fps, 2) for p in third_second if p.measured_fps}) > 20
    assert any(p.frame_time_ms == pytest.approx(1000 / 30) for p in third_second)
    assert [(p.frame_index, p.seconds) for p in frames] == [
        (s.frame_index, s.timestamp_seconds) for s in result.samples
    ]
    assert [asdict(s) for s in result.samples] == original


def test_frame_time_does_not_bridge_an_ambiguous_interval_or_segment():
    result = observations(60, ((3, 60, "observable"),))
    result.samples = tuple(
        replace(s, signal_state="uncertain_change") if 60 <= s.frame_index < 120 else s
        for s in result.samples
    )
    frames = build_frame_timeline(result, {"A": ContentReference(60, "manual", "defined")})["A"]
    assert all(p.frame_time_origin == "reference" for p in frames[60:121])
    assert frames[121].frame_time_origin == "measured"
    assert frames[121].frame_time_ms == pytest.approx(1000 / 60)


def test_frame_time_and_fps_use_the_same_recorded_update_decision():
    result = observations(60, ((2, 60, "observable"),))
    result.samples = tuple(replace(s, cadence_repeated=True) for s in result.samples)
    frames = build_frame_timeline(result, {"A": ContentReference(60, "manual", "defined")})["A"]
    assert all(p.frame_time_origin == "reference" for p in frames)
    assert all(p.measured_fps is None for p in frames)
    assert all(s.cadence_repeated for s in result.samples)


def test_new_frames_enter_at_right_and_frame_time_has_its_own_card(qapp):
    from PySide6.QtGui import QImage, QPainter

    from dg_fps.presentation.frame_timeline import PresentationFrame
    from dg_fps.presentation.video_layout import draw_frame_graph
    from dg_fps.presentation.video_text import VideoText

    class RecordingPainter(QPainter):
        def fillRect(self, rect, color):
            panels.append(rect)
            return super().fillRect(rect, color)

        def drawLine(self, a, b):
            if self.pen().color().name() == "#22d3ee" and a.y() >= 852:
                curves.append((a, b))
            return super().drawLine(a, b)

    image = QImage(1920, 1080, QImage.Format.Format_RGB888)
    points = tuple(
        PresentationFrame("A", i, i / 60, 60, 60, "measured", 1000 / 60, "measured")
        for i in range(3)
    )
    first_positions = []
    for count in (2, 3):
        curves, panels = [], []
        painter = RecordingPainter(image)
        draw_frame_graph(
            painter,
            VideoText(),
            (),
            None,
            ContentReference(60, "manual", "defined"),
            60,
            frames=points[:count],
        )
        painter.end()
        assert curves[-1][1].x() == pytest.approx(1830)
        first_positions.append(curves[0][0].x())
        fps, timing = panels
        assert timing.bottom() < fps.top()
        assert timing.width() < fps.width() / 3
    assert first_positions[1] < first_positions[0]


def test_fps_curve_connects_both_sides_of_unknown_without_changing_values(qapp):
    from PySide6.QtGui import QImage, QPainter

    from dg_fps.presentation.frame_timeline import PresentationFrame
    from dg_fps.presentation.video_layout import draw_frame_graph
    from dg_fps.presentation.video_text import VideoText

    joins = []

    class RecordingPainter(QPainter):
        def drawPath(self, path):
            joins.append(
                (path.elementAt(0), path.currentPosition(), tuple(self.pen().dashPattern()))
            )
            return super().drawPath(path)

    points = (
        PresentationFrame("A", 0, 0, 40, 40, "measured", 25, "measured"),
        PresentationFrame("A", 1, 1 / 60, None, 60, "reference", 25, "measured"),
        PresentationFrame("A", 2, 2 / 60, 42, 42, "measured", 25, "measured"),
    )
    before = [asdict(p) for p in points]
    image = QImage(1920, 1080, QImage.Format.Format_RGB888)
    painter = RecordingPainter(image)
    draw_frame_graph(
        painter, VideoText(), (), None, ContentReference(60, "manual", "defined"), 60, frames=points
    )
    painter.end()
    assert len(joins) == 2
    assert all(pattern == (1.0, 2.0) for _, _, pattern in joins)
    assert joins[0][1].x() == pytest.approx(joins[1][0].x)
    assert joins[0][1].y() == pytest.approx(joins[1][0].y)
    assert joins[-1][1].x() == pytest.approx(1830)
    assert [asdict(p) for p in points] == before
