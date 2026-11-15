from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.analyzers.cadence import CadenceSample, content_cadence_readings
from dg_fps.ui.i18n import localize


class CadenceTrack(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("cadenceTrack")
        self.setAccessibleName(localize("Cadência visual"))
        self.setToolTip(
            localize(
                "Azul: atualização; cinza: retenção regular ou sinal insuficiente; "
                "laranja: retenção prolongada"
            )
        )
        self.setFixedHeight(20)
        self._samples: tuple[CadenceSample, ...] = ()
        self._ranges: tuple[AnalysisFrameRange, ...] = ()
        self._frame_count = 0
        self._states: dict[int, str] = {}

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def set_samples(self, samples: tuple[CadenceSample, ...]) -> None:
        self._samples = samples
        self._states = {
            index: reading.status for index, reading in content_cadence_readings(samples).items()
        }
        self.update()

    def set_frame_count(self, frame_count: int) -> None:
        self._frame_count = max(0, frame_count)
        self.update()

    def set_ranges(self, ranges: tuple[AnalysisFrameRange, ...]) -> None:
        self._ranges = ranges
        self.update()

    def clear(self) -> None:
        self._samples = ()
        self._states = {}
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#252a33"))
        if self._frame_count > 1:
            for frame_range in self._ranges:
                left = round(frame_range.start_frame / (self._frame_count - 1) * self.width())
                right = round(frame_range.end_frame / (self._frame_count - 1) * self.width())
                painter.fillRect(left, 0, max(2, right - left), self.height(), QColor("#0e7490"))
        if not self._samples or self.width() < 1:
            return
        by_frame = {sample.frame_index: sample for sample in self._samples}
        unique_color = QColor("#3b82f6")
        repeated_color = QColor("#64748b")
        for x in range(self.width()):
            index = round(x / max(1, self.width() - 1) * max(0, self._frame_count - 1))
            sample = by_frame.get(index)
            if sample is None:
                continue
            status = self._states.get(sample.frame_index)
            color = (
                repeated_color
                if sample.presentation_repeated or status != "observable_cadence"
                else unique_color
            )
            if status == "extended_hold":
                color = QColor("#f59e0b")
            painter.setPen(color)
            painter.drawLine(x, 0, x, self.height())
