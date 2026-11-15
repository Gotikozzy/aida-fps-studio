from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from dg_fps.analyzers.cadence import CadenceSample
from dg_fps.presentation.cadence_video import CadenceVideoExporter
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.presentation.fps_display import capture_nominal_text, fps_display
from dg_fps.presentation.second_timeline import PresentationSecond


@pytest.mark.parametrize(
    "measured,capture,expected,nominal",
    [
        (59.94, 59.94, "60", True),
        (59.86168004813477, 59.939690067768694, "60", True),
        (58.4, 58.4, "60", True),
        (58.4, 59.94, "58.40", False),
        (58.94, 59.94, "58.94", False),
        (58, 58, "58.00", False),
        (28, 28, "28.00", False),
        (28.5, 28.5, "30", True),
        (29.97, 59.94, "30", True),
        (39.96, 58, "39.96", False),
        (39.96, 59.94, "40", True),
        (39.96, 119.88, "40", True),
        (39.8, 119.88, "39.80", False),
        (59.94, 119.88, "60", True),
        (90, 119.88, "90.00", False),
        (118, 118, "118.00", False),
        (118.5, 118.5, "120", True),
        (119.88, 119.88, "120", True),
        (None, 59.94, "—", False),
    ],
)
def test_display_normalizes_encoded_families_without_hiding_drops(
    measured, capture, expected, nominal
):
    display = fps_display(measured, capture)
    assert display.text == expected and display.nominal == nominal


@pytest.mark.parametrize(
    "rate,text",
    [(58.01, "60"), (28.01, "30"), (118.01, "120"), (58, "58.00"), (75, "75.00")],
)
def test_capture_label_does_not_change_rate(rate, text):
    assert capture_nominal_text(rate) == text


@pytest.mark.parametrize(
    "language,fps,title,measurement,label",
    [
        ("pt", 59.94, "FPS MEDIDO", "60", "Cadência visual"),
        ("en", 59.94, "MEASURED FPS", "60", "Visual cadence"),
        ("pt", 58.86, "FPS MEDIDO", "58.86", "Cadência visual"),
        ("en", 58.86, "MEASURED FPS", "58.86", "Visual cadence"),
    ],
)
def test_video_prioritizes_the_per_second_measurement(
    qapp, language, fps, title, measurement, label
):
    card = []

    class Painter(QPainter):
        def drawText(self, *args):
            if isinstance(args[0], QRectF) and args[0].left() >= 1480:
                card.append((args[-1], self.font().pointSize()))
            return super().drawText(*args)

    image = QImage(1920, 1080, QImage.Format.Format_RGB888)
    painter = Painter(image)
    reference = ContentReference(60, "inferred", "dominant_observed_cadence")
    sample = CadenceSample("A", 60, 1.001, None, None, None, None, None, None, None, None, False)
    exporter = CadenceVideoExporter(language, {"A": reference})
    exporter._active_second = PresentationSecond(
        "A", 1, 1, 2, 1, 1, fps, fps, 60 if fps == 59.94 else fps, 60, "measured", "test"
    )
    exporter._draw_header(painter, "A", sample, 59.94, None)
    painter.end()
    assert title in dict(card) and label in dict(card)
    sizes = [size for text, size in card if text == measurement]
    assert len(sizes) == 2 and sizes[0] > sizes[1]
    assert all("NOMINAL" not in text for text, _ in card)
