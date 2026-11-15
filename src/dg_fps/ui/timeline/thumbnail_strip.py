from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from dg_fps.media.frame_provider import VideoThumbnail
from dg_fps.ui.i18n import localize


class ThumbnailStrip(QWidget):
    frame_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("timelineThumbnailStrip")
        self.setAccessibleName(localize("Miniaturas da timeline"))
        self.setToolTip(localize("Clique para navegar até um ponto do vídeo"))
        self.setMinimumHeight(44)
        self.setMaximumHeight(60)
        self._frame_count = 0
        self._current_frame = 0
        self._images: list[tuple[int, QImage]] = []

    @property
    def thumbnail_count(self) -> int:
        return sum(not image.isNull() for _, image in self._images)

    def set_frame_count(self, frame_count: int) -> None:
        self._frame_count = max(0, frame_count)
        self.update()

    def set_current_frame(self, frame_index: int) -> None:
        self._current_frame = frame_index
        self.update()

    def set_thumbnails(self, thumbnails: list[VideoThumbnail]) -> None:
        images: list[tuple[int, QImage]] = []
        for thumbnail in thumbnails:
            rgb = thumbnail.rgb
            if rgb is None:
                images.append((thumbnail.timestamp.index, QImage()))
                continue
            height, width, _ = rgb.shape
            image = QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
            images.append((thumbnail.timestamp.index, image))
        self._images = images
        self.update()

    def clear(self) -> None:
        self._images.clear()
        self._frame_count = 0
        self._current_frame = 0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101318"))
        if not self._images:
            painter.setPen(QColor("#788394"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                localize("Gerando miniaturas…" if self._frame_count else "Miniaturas"),
            )
            return
        count = len(self._images)
        for position, (_, image) in enumerate(self._images):
            left = round(position * self.width() / count)
            right = round((position + 1) * self.width() / count)
            target = QRect(left, 0, max(1, right - left), self.height())
            painter.drawImage(target, image)
            painter.setPen(QPen(QColor("#171a1f"), 1))
            painter.drawRect(target.adjusted(0, 0, -1, -1))
        if self._frame_count > 1:
            ratio = self._current_frame / (self._frame_count - 1)
            x = round(ratio * (self.width() - 1))
            painter.setPen(QPen(QColor("#38bdf8"), 3))
            painter.drawLine(x, 0, x, self.height())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._frame_count > 0:
            denominator = max(1, self.width() - 1)
            ratio = min(1.0, max(0.0, event.position().x() / denominator))
            frame_index = round(ratio * (self._frame_count - 1))
            self.frame_selected.emit(frame_index)
            event.accept()
            return
        super().mousePressEvent(event)
