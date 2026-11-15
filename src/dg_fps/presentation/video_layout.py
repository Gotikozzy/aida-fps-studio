"""Viewer-facing legend, per-second readout and a time-scaled chart."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen

from dg_fps.presentation.branding import draw_video_branding
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.presentation.fps_display import fps_display
from dg_fps.presentation.frame_timeline import PresentationFrame
from dg_fps.presentation.second_timeline import PresentationSecond, timecode
from dg_fps.presentation.video_text import VideoText

_PROJECTION_COLOR = "#b9e5f5"


def draw_header(
    painter: QPainter,
    text: VideoText,
    capture: float,
    measured: float | None,
    reference: ContentReference | None,
    second: PresentationSecond | None,
) -> None:
    painter.fillRect(QRectF(42, 30, 820, 222), QColor(8, 12, 18, 225))
    painter.fillRect(QRectF(42, 30, 8, 222), QColor("#22d3ee"))
    draw_video_branding(painter, 1920, x=52, y=43, language=text.language, show_site=False)
    rows = (
        (104, "Pontilhado:", "projeção visual durante medição inconclusiva."),
        (154, "Queda:", "redução confirmada da cadência medida."),
        (204, "Meta:", "valor de referência para comparação."),
    )
    for position, (y, label, explanation) in enumerate(rows):
        if position == 0:
            painter.setPen(QPen(QColor(_PROJECTION_COLOR), 3, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(72, y + 12), QPointF(210, y + 12))
        elif position == 1:
            painter.setPen(QPen(QColor("#22d3ee"), 3))
            path = QPainterPath(QPointF(72, y + 3))
            path.cubicTo(115, y + 3, 155, y + 23, 210, y + 23)
            painter.drawPath(path)
        else:
            painter.setPen(QPen(QColor("#a8b3c4"), 1))
            painter.drawLine(QPointF(72, y + 12), QPointF(172, y + 12))
            painter.setFont(QFont("Segoe UI", 12))
            target = reference.target_fps if reference is not None else None
            painter.drawText(QRectF(180, y - 1, 48, 26), f"{target:g}" if target else "—")
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f8fafc"))
        translated = text(label)
        painter.drawText(QRectF(246, y - 4, 580, 32), translated)
        left = 246 + QFontMetricsF(font).horizontalAdvance(translated) + 9
        painter.setFont(QFont("Segoe UI", 14))
        painter.drawText(QRectF(left, y - 4, 840 - left, 32), text(explanation))

    target = reference.target_fps if reference is not None else None
    if second is not None:
        measured = second.measured_fps
        target = second.reference_fps
    display = fps_display(measured, capture)
    has_measurement = display.value is not None
    measured_text = display.text
    if has_measurement:
        secondary_label = "Cadência visual"
        secondary_text = measured_text
    else:
        secondary_label = "Referência"
        secondary_text = f"{target:g}" if target is not None else "—"
    color = QColor("#22d3ee" if has_measurement else "#b9e5f5")
    painter.fillRect(QRectF(1480, 38, 398, 214), QColor(8, 12, 18, 235))
    painter.fillRect(QRectF(1480, 38, 8, 214), color)
    painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
    painter.setPen(QColor("#dbe4f0"))
    painter.drawText(QRectF(1510, 54, 340, 28), text("FPS MEDIDO"))
    painter.setFont(QFont("Segoe UI", 49, QFont.Weight.Bold))
    painter.setPen(color)
    painter.drawText(QRectF(1510, 84, 340, 86), Qt.AlignmentFlag.AlignVCenter, measured_text)
    painter.setFont(QFont("Segoe UI", 12))
    painter.setPen(QColor("#a8b3c4"))
    painter.drawText(
        QRectF(1510, 177, 240, 28), Qt.AlignmentFlag.AlignVCenter, text(secondary_label)
    )
    painter.drawText(
        QRectF(1750, 177, 98, 28),
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        secondary_text,
    )
    painter.setFont(QFont("Segoe UI", 11))
    painter.drawText(QRectF(1510, 211, 340, 26), text("Apresentação por segundo"))


def draw_frame_graph(
    painter: QPainter,
    text: VideoText,
    seconds: tuple[PresentationSecond, ...],
    current: PresentationSecond | None,
    reference: ContentReference | None,
    capture: float,
    *,
    frames: tuple[PresentationFrame, ...] = (),
    segment_start: float = 0.0,
) -> None:
    # Seconds belong to the headline. Both curves below use source-frame PTS.
    del seconds, current
    panel = QRectF(42, 790, 1836, 246)
    timing_panel = QRectF(42, 600, 480, 170)
    timing = QRectF(102, 651, 400, 82)
    graph = QRectF(116, 852, 1714, 126)
    painter.fillRect(panel, QColor(8, 12, 18, 230))
    painter.fillRect(timing_panel, QColor(8, 12, 18, 230))
    painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    painter.setPen(QColor("#dbe4f0"))
    painter.drawText(QRectF(82, 805, 1500, 32), text("FPS • TRANSIÇÕES QUADRO A QUADRO"))
    painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    painter.drawText(QRectF(62, 611, 440, 28), text("TEMPO ENTRE QUADROS (ms)"))
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(QRectF(102, 741, 400, 23), text("Últimos 6 s"))
    target = reference.target_fps if reference is not None else None
    # Stable scales throughout the segment, rather than zooming with each sample.
    ceiling = max(capture, target or 0, 1)
    fps_step = max(1, math.ceil(ceiling / 4))
    fps_top = fps_step * 4 * 1.04
    time_step = 1000 / (target or capture or 60)
    time_top = time_step * 4 * 1.04
    now = frames[-1].seconds if frames else segment_start
    # The newest frame is always on the right, including the first six seconds.
    # Earlier samples move left continuously as each new source frame arrives.
    right = now
    left = right - 6

    def point(area: QRectF, t: float, value: float, maximum: float) -> QPointF:
        return QPointF(
            area.left() + (t - left) / 6 * area.width(),
            area.bottom() - value / maximum * area.height(),
        )

    painter.setFont(QFont("Segoe UI", 10))
    for area, maximum, step in ((graph, fps_top, fps_step), (timing, time_top, time_step)):
        painter.setFont(QFont("Segoe UI", 10))
        for n in range(5):
            value = n * step
            y = point(area, left, value, maximum).y()
            painter.setPen(QPen(QColor(148, 163, 184, 55), 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QColor("#c3cbd6"))
            label = f"{value:.0f}" if area == graph else f"{value:.1f}"
            painter.drawText(
                QRectF(area.left() - 58, y - 10, 46, 21), Qt.AlignmentFlag.AlignRight, label
            )
        for tick in range(max(0, math.ceil(left)), math.floor(right) + 1):
            x = point(area, tick, 0, maximum).x()
            painter.setPen(QPen(QColor(148, 163, 184, 35), 1))
            painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        painter.save()
        painter.setClipRect(area)
        ref_value = target if area == graph else 1000 / target if target else None
        if ref_value is not None:
            painter.setPen(QPen(QColor(180, 198, 210, 150), 1))
            painter.drawLine(
                point(area, left, ref_value, maximum), point(area, right, ref_value, maximum)
            )
        for a, b in zip(frames, frames[1:], strict=False):
            if area == graph and (
                a.segment != b.segment
                or b.frame_index != a.frame_index + 1
                or b.seconds <= a.seconds
            ):
                continue
            avalue = (
                (a.graph_fps if a.graph_origin != "legacy" else a.displayed_fps)
                if area == graph
                else a.frame_time_ms
            )
            bvalue = (
                (b.graph_fps if b.graph_origin != "legacy" else b.displayed_fps)
                if area == graph
                else b.frame_time_ms
            )
            if avalue is None or bvalue is None:
                continue
            aorigin = (
                (a.graph_origin if a.graph_origin != "legacy" else a.origin)
                if area == graph
                else a.frame_time_origin
            )
            borigin = (
                (b.graph_origin if b.graph_origin != "legacy" else b.origin)
                if area == graph
                else b.frame_time_origin
            )
            if area == timing and aorigin != borigin:
                continue
            measured = (
                aorigin == borigin == "measured"
                if area == graph
                else a.frame_time_origin == b.frame_time_origin == "measured"
            )
            painter.setPen(
                QPen(
                    QColor("#22d3ee" if measured else _PROJECTION_COLOR),
                    2.5,
                    Qt.PenStyle.SolidLine if measured else Qt.PenStyle.DotLine,
                )
            )
            p, q = (
                point(area, a.seconds, min(avalue, maximum * 0.97), maximum),
                point(area, b.seconds, min(bvalue, maximum * 0.97), maximum),
            )
            if measured:
                painter.drawLine(p, q)
            else:
                # Independent short strokes must share a continuous dash phase.
                # Otherwise Qt restarts a dash on every 60 Hz edge and it looks solid.
                pen = painter.pen()
                pen.setDashOffset((p.x() - area.left()) / pen.widthF())
                painter.setPen(pen)
                if area == graph and aorigin != borigin:
                    # A display-only join: endpoints and measurement origins stay intact.
                    middle = (p.x() + q.x()) / 2
                    path = QPainterPath(p)
                    path.cubicTo(middle, p.y(), middle, q.y(), q.x(), q.y())
                    painter.drawPath(path)
                else:
                    painter.drawLine(p, q)
            if area == timing and bvalue > maximum and avalue <= maximum:
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(min(q.x() + 3, area.right() - 100), area.top(), 100, 20),
                    f"↑ {bvalue:.1f} ms",
                )
        painter.restore()
    painter.setPen(QColor("#c3cbd6"))
    for tick in range(max(0, math.ceil(left)), math.floor(right) + 1):
        x = point(graph, tick, 0, fps_top).x()
        painter.drawText(QRectF(x - 59, 994, 118, 26), Qt.AlignmentFlag.AlignCenter, timecode(tick))
