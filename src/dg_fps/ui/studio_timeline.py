"""PTS-aware visual timeline. Editing emits ranges; it never changes measurements."""

from __future__ import annotations

import math
from bisect import bisect_left

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QMenu, QWidget

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.frame_timeline import PresentationFrame
from dg_fps.ui.i18n import localize


class StudioTimeline(QWidget):
    seek_requested = Signal(int)
    range_created = Signal(int, int)
    range_edited = Signal(int, int, int)
    range_selected = Signal(int)
    interaction_started = Signal()
    viewport_changed = Signal()
    mark_start_requested = Signal(int)
    mark_end_requested = Signal(int)
    delete_requested = Signal()
    margin = 88

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(200)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(localize("Timeline visual de análise"))
        self.count = 0
        self.current = 0
        self.times: tuple[float, ...] = ()
        self.ranges: tuple[AnalysisFrameRange, ...] = ()
        self.points: tuple[PresentationFrame, ...] = ()
        self.images: dict[int, QImage] = {}
        self.selection_mode = False
        self.selected = -1
        self.zoom = 1.0
        self.offset = 0.0
        self.drag: tuple | None = None
        self.draft: tuple[int, int] | None = None
        self.pending_start: int | None = None

    def set_index(self, index: TimestampIndex | None) -> None:
        self.times = tuple(index[i].seconds for i in range(len(index))) if index else ()
        self.update()

    def duration(self) -> float:
        return max(0.001, self.time_at(max(0, self.count - 1)))

    def time_at(self, frame: int) -> float:
        if self.times:
            return self.times[min(max(0, frame), len(self.times) - 1)] - self.times[0]
        return max(0, frame) / 30

    def x_at(self, frame: int) -> float:
        return self.margin + (self.time_at(frame) - self.offset) / (
            self.duration() / self.zoom
        ) * max(1, self.width() - self.margin - 12)

    def frame_at(self, x: float) -> int:
        seconds = (
            self.offset
            + (x - self.margin)
            / max(1, self.width() - self.margin - 12)
            * self.duration()
            / self.zoom
        )
        if self.times:
            pos = bisect_left(self.times, seconds + self.times[0])
            pos = min(len(self.times) - 1, pos)
            if pos > 0 and abs(self.times[pos - 1] - seconds - self.times[0]) < abs(
                self.times[pos] - seconds - self.times[0]
            ):
                pos -= 1
            return pos
        return min(max(0, self.count - 1), max(0, round(seconds * 30)))

    def thumbnail_frames(self) -> tuple[int, ...]:
        if not self.count:
            return ()
        first = self.frame_at(self.margin)
        width = max(1, self.width() - self.margin - 12)
        last = self.frame_at(self.margin + width)
        count = min(12, last - first + 1)
        if count <= 1:
            return (first,)
        return tuple(self.frame_at(self.margin + i * width / (count - 1)) for i in range(count))

    def set_zoom(self, value: float) -> None:
        self.zoom = max(1, min(40, value))
        self.offset = min(self.offset, self.duration() * (1 - 1 / self.zoom))
        self.viewport_changed.emit()
        self.update()

    def paintEvent(self, event) -> None:
        del event
        key = (
            self.width(),
            self.height(),
            self.count,
            self.offset,
            self.zoom,
            id(self.points),
            id(self.ranges),
            id(self.images),
            self.selected,
            self.draft,
            self.pending_start,
            localize("Trechos"),
        )
        if getattr(self, "_cache_key", None) != key:
            self._cache_key = key
            self._cache = QImage(self.size(), QImage.Format.Format_RGB32)
            p = QPainter(self._cache)
            self._draw_content(p)
            p.end()
        p = QPainter(self)
        p.drawImage(0, 0, self._cache)
        x = self.x_at(self.current)
        if x >= self.margin:
            p.setPen(QPen(QColor("#ececec"), 1))
            p.drawLine(QPointF(x, 25), QPointF(x, self.height()))
        p.end()

    def _draw_content(self, p: QPainter) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#181818"))
        for y in (30, 87, 130, self.height() - 1):
            p.setPen(QColor("#383838"))
            p.drawLine(0, y, self.width(), y)
        p.setPen(QColor("#bdbdbd"))
        for label, y in (("Vídeo", 62), ("Trechos", 114), ("FPS", 169)):
            p.drawText(QRectF(12, y - 17, 70, 30), localize(label))
        p.save()
        p.setClipRect(QRectF(self.margin, 0, self.width() - self.margin, self.height()))
        visible = self.duration() / self.zoom
        step = max(0.1, 10 ** math.floor(math.log10(visible / 8)))
        step *= next(v for v in (1, 2, 5, 10) if v * step >= visible / 10)
        start = math.ceil(self.offset / step) * step
        for n in range(14):
            t = start + n * step
            x = self.margin + (t - self.offset) / visible * max(1, self.width() - self.margin - 12)
            p.setPen(QPen(QColor("#383838"), 1))
            p.drawLine(QPointF(x, 25), QPointF(x, self.height()))
            p.setPen(QColor("#aaaaaa"))
            p.drawText(QRectF(max(self.margin, x - 20), 3, 75, 22), f"{t:g} s")
        slots = self.thumbnail_frames()
        if slots:
            tile = max(1, self.width() - self.margin - 12) / len(slots)
            for slot, frame in enumerate(slots):
                image = self.images.get(frame)
                rect = QRectF(self.margin + slot * tile, 33, max(1, tile - 2), 50)
                if image is None or image.isNull():
                    p.fillRect(rect, QColor("#282828"))
                    p.setPen(QColor("#aaaaaa"))
                    label = "…" if image is None else localize("Indisponível")
                    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
                else:
                    p.drawImage(rect, image)
        if not self.ranges:
            p.setPen(QColor("#aaaaaa"))
            p.drawText(
                QRectF(self.margin + 12, 96, self.width() - self.margin - 24, 24),
                localize("Arraste aqui para selecionar um trecho"),
            )
        for row, value in enumerate(self.ranges):
            a, b = self.x_at(value.start_frame), self.x_at(value.end_frame)
            rect = QRectF(a, 96, max(3, b - a), 24)
            p.setBrush(QColor("#20383d" if row == self.selected else "#333333"))
            p.setPen(QPen(QColor("#20cfe3" if row == self.selected else "#777777"), 1.5))
            p.drawRoundedRect(rect, 3, 3)
            p.fillRect(QRectF(a, 97, 4, 22), QColor("#ececec"))
            p.fillRect(QRectF(b - 4, 97, 4, 22), QColor("#ececec"))
            p.setPen(QColor("#ececec"))
            p.drawText(
                rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignCenter, localize(value.label)
            )
        if self.draft:
            a, b = sorted(self.draft)
            p.fillRect(
                QRectF(self.x_at(a), 92, max(2, self.x_at(b) - self.x_at(a)), 33),
                QColor(34, 211, 238, 90),
            )
        if self.pending_start is not None:
            x = self.x_at(self.pending_start)
            p.setPen(QPen(QColor("#20cfe3"), 2, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, 30), QPointF(x, 130))
            p.drawText(QRectF(x + 6, 87, 150, 20), localize("Início do trecho"))
        top, bottom = 140, self.height() - 12
        ceiling = max((v.graph_fps or v.measured_fps or 0 for v in self.points), default=60)
        ceiling = max(30, math.ceil(ceiling / 10) * 10)
        for value in (0, ceiling / 2, ceiling):
            y = bottom - value / ceiling * (bottom - top)
            p.setPen(QPen(QColor("#383838"), 1))
            p.drawLine(QPointF(self.margin, y), QPointF(self.width(), y))
        for a, b in zip(self.points, self.points[1:], strict=False):
            if a.segment != b.segment or b.frame_index != a.frame_index + 1:
                continue
            av = a.graph_fps if a.graph_origin != "legacy" else a.measured_fps
            bv = b.graph_fps if b.graph_origin != "legacy" else b.measured_fps
            if (
                av is None
                or bv is None
                or self.x_at(b.frame_index) < self.margin
                or self.x_at(a.frame_index) > self.width()
            ):
                continue
            projected = a.graph_origin == "projected" or b.graph_origin == "projected"
            p.setPen(
                QPen(
                    QColor("#b9e5f5" if projected else "#20cfe3"),
                    1.6,
                    Qt.PenStyle.DotLine if projected else Qt.PenStyle.SolidLine,
                )
            )
            p.drawLine(
                QPointF(self.x_at(a.frame_index), bottom - av / ceiling * (bottom - top)),
                QPointF(self.x_at(b.frame_index), bottom - bv / ceiling * (bottom - top)),
            )
        p.restore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() != Qt.MouseButton.LeftButton
            or self.count < 2
            or event.position().x() < self.margin
        ):
            return
        self.interaction_started.emit()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        frame = self.frame_at(event.position().x())
        if 90 <= event.position().y() <= 129:
            for row, value in enumerate(self.ranges):
                a, b = self.x_at(value.start_frame), self.x_at(value.end_frame)
                if a - 6 <= event.position().x() <= b + 6:
                    self.selected = row
                    self.range_selected.emit(row)
                    mode = (
                        "left"
                        if abs(event.position().x() - a) < 8
                        else "right"
                        if abs(event.position().x() - b) < 8
                        else "move"
                    )
                    self.drag = (mode, row, frame, value.start_frame, value.end_frame)
                    self.seek_requested.emit(frame)
                    self.update()
                    return
            self.drag = ("new", frame)
            self.draft = (frame, frame)
        elif self.selection_mode:
            self.drag = ("new", frame)
            self.draft = (frame, frame)
        else:
            self.drag = ("seek",)
        self.seek_requested.emit(frame)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.drag:
            return
        frame = self.frame_at(event.position().x())
        mode = self.drag[0]
        if mode == "seek":
            self.seek_requested.emit(frame)
            return
        if mode == "new":
            self.draft = (self.drag[1], frame)
        else:
            _, row, initial, a, b = self.drag
            if mode == "left":
                a = min(frame, b - 1)
            elif mode == "right":
                b = max(frame, a + 1)
            else:
                shift = max(-a, min(self.count - 1 - b, frame - initial))
                a += shift
                b += shift
            self.draft = (max(0, a), min(self.count - 1, b))
        self.seek_requested.emit(frame)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self.drag:
            return
        self.mouseMoveEvent(event)
        drag, draft = self.drag, self.draft
        self.drag = self.draft = None
        if draft and abs(draft[1] - draft[0]) >= 1:
            a, b = sorted(draft)
            if drag[0] == "new":
                self.range_created.emit(a, b)
            elif (a, b) != (drag[3], drag[4]):
                self.range_edited.emit(drag[1], a, b)
        self.update()

    def contextMenuEvent(self, event) -> None:
        if self.count < 2 or event.pos().x() < self.margin:
            return
        frame = self.frame_at(event.pos().x())
        self.interaction_started.emit()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.seek_requested.emit(frame)
        for row, value in enumerate(self.ranges):
            if value.start_frame <= frame <= value.end_frame:
                self.selected = row
                self.range_selected.emit(row)
                break
        menu = self.context_menu(frame)
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(event.globalPos())
        event.accept()

    def context_menu(self, frame: int) -> QMenu:
        """Use the clicked PTS-indexed frame, independent of asynchronous decoding."""
        menu = QMenu(self)
        menu.addAction(
            localize("Iniciar trecho aqui") + "\tI", lambda: self.mark_start_requested.emit(frame)
        )
        end = menu.addAction(
            localize("Encerrar novo trecho aqui") + "\tO",
            lambda: self.mark_end_requested.emit(frame),
        )
        end.setEnabled(self.pending_start is not None)
        if 0 <= self.selected < len(self.ranges):
            row = self.selected
            selected = self.ranges[row]
            label = localize(selected.label)
            edit = menu.addAction(
                localize(f"Ajustar fim de “{label}” aqui"),
                lambda: self.range_edited.emit(row, selected.start_frame, frame),
            )
            edit.setEnabled(frame > selected.start_frame and frame != selected.end_frame)
        menu.addSeparator()
        remove = menu.addAction(localize("Apagar trecho"), self.delete_requested.emit)
        remove.setEnabled(0 <= self.selected < len(self.ranges))
        return menu

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom * (1.25 if event.angleDelta().y() > 0 else 0.8))
        else:
            self.offset = max(
                0,
                min(
                    self.duration() * (1 - 1 / self.zoom),
                    self.offset - event.angleDelta().y() / 120 * self.duration() / self.zoom / 6,
                ),
            )
            self.viewport_changed.emit()
            self.update()
        event.accept()
