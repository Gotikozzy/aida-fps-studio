from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from dg_fps.analyzers.cadence import CadenceSample
from dg_fps.presentation.branding import BRAND_ACRONYM
from dg_fps.presentation.cadence_video import CadenceVideoExporter
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.presentation.second_timeline import PresentationSecond
from dg_fps.ui.i18n import set_language


def test_export_text_language_is_frozen_and_brand_is_aida(qapp):
    card = []

    class RecordingPainter(QPainter):
        def drawText(self, *args):
            texts.extend(value for value in args if isinstance(value, str))
            if isinstance(args[0], QRectF) and args[0].left() >= 1480 and args[0].top() < 252:
                card.append(args[-1])
            return super().drawText(*args)

    assert BRAND_ACRONYM == "AIDA"
    reference = ContentReference(60, "manual", "user_reference")
    exporter = CadenceVideoExporter(language="en", references={"Trecho 1": reference})
    exporter._active_second = PresentationSecond(
        "Trecho 1", 0, 0, 1, 0, 0, 0, None, 60, 60, "reference", "test"
    )
    set_language("pt")  # changing the UI must not change a running render
    image = QImage(1920, 1080, QImage.Format.Format_RGB888)
    image.fill(0)
    texts = []
    painter = RecordingPainter(image)
    sample = CadenceSample("Trecho 1", 5, 0.1, None, None, None, None, None, None, None, None, True)
    exporter._draw_header(painter, "Trecho 1", sample, 60.0, None, "extended_hold", 2.0)
    exporter._draw_graph(painter, (30.0, None), (False, True), 60.0, True, 0.8, 2.0)
    exporter._draw_advance_map(painter, None, True)
    painter.end()
    joined = "\n".join(texts)
    assert "AIDA" in texts and "DG FPS" not in joined
    assert "FRAME-BY-FRAME TRANSITIONS" in joined
    assert card == ["MEASURED FPS", "—", "Reference", "60", "Updated once per second"]
    assert "Dotted:" in joined and "Drop:" in joined and "Target:" in joined
    assert "Motion between frames" in joined
    assert "MAPA DE AVANÇO" not in joined and "NOMINAL CAPTURE" not in joined
    assert not any(
        value in joined
        for value in (
            "INCONCLUSIVE",
            "IMAGE HOLD",
            "Segment 1",
            "frame 5",
            "coverage:",
            "Waiting",
            "detonandogueek.com.br",
        )
    )
