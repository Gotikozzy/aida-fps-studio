from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.ui.i18n import localize
from dg_fps.ui.timeline.timeline_widget import format_timecode


class CadencePanel(QWidget):
    mark_in_requested = Signal()
    mark_out_requested = Signal()
    analyze_requested = Signal(object)
    ranges_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName(localize("Seleção de trechos para FPS e cadência"))
        self._in_point: tuple[int, float] | None = None
        self._out_point: tuple[int, float] | None = None
        self._ranges: list[AnalysisFrameRange] = []
        self._next_range_number = 1
        self._points_label = QLabel(localize("Início: —   Fim: —"))
        self._status = QLabel(localize("Marque início e fim de um ou mais trechos."))
        self._status.setWordWrap(True)
        self._points_label.setWordWrap(True)
        self._range_list = QListWidget()
        self._range_list.setMinimumHeight(64)
        self._range_list.setMaximumHeight(110)
        self._range_list.setObjectName("cadenceRangeList")
        self._summary = QPlainTextEdit()
        self._summary.setReadOnly(True)
        self._summary.setPlaceholderText(localize("O resultado da análise aparecerá aqui."))
        mark_in = QPushButton(localize("Marcar início (I)"))
        mark_in.setObjectName("cadenceMarkStartButton")
        mark_in.clicked.connect(self.mark_in_requested)
        mark_out = QPushButton(localize("Marcar fim (O)"))
        mark_out.setObjectName("cadenceMarkEndButton")
        mark_out.clicked.connect(self.mark_out_requested)
        add = QPushButton(localize("Adicionar trecho"))
        add.setObjectName("addCadenceRangeButton")
        add.setToolTip(localize("Incluir o trecho marcado (Ctrl+Shift+A)"))
        add.clicked.connect(self._add_range)
        remove = QPushButton(localize("Remover trecho"))
        remove.clicked.connect(self._remove_selected)
        clear = QPushButton(localize("Limpar trechos"))
        clear.clicked.connect(self.clear_ranges)
        self._analyze = QPushButton(localize("Analisar FPS dos trechos"))
        self._analyze.setObjectName("analyzeCadenceRangesButton")
        self._analyze.clicked.connect(self.request_analysis)
        marks = QHBoxLayout()
        marks.addWidget(mark_in)
        marks.addWidget(mark_out)
        edit = QHBoxLayout()
        edit.addWidget(add)
        edit.addWidget(remove)
        edit.addWidget(clear)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(localize("Trechos incluídos na medição")))
        layout.addLayout(marks)
        layout.addWidget(self._points_label)
        layout.addLayout(edit)
        layout.addWidget(self._range_list)
        layout.addWidget(self._status)
        layout.addWidget(self._analyze)
        layout.addWidget(self._summary, 1)

    @property
    def ranges(self) -> tuple[AnalysisFrameRange, ...]:
        return tuple(self._ranges)

    @property
    def summary_text(self) -> str:
        return self._summary.toPlainText()

    def mark_in(self, frame_index: int, seconds: float) -> None:
        self._in_point = (frame_index, seconds)
        self._update_points_label()

    def mark_out(self, frame_index: int, seconds: float) -> None:
        self._out_point = (frame_index, seconds)
        self._update_points_label()

    def clear_ranges(self) -> None:
        self._ranges.clear()
        self._next_range_number = 1
        self._range_list.clear()
        self._status.setText(localize("Marque início e fim de um ou mais trechos."))
        self.ranges_changed.emit(())

    def reset(self) -> None:
        self._in_point = None
        self._out_point = None
        self.clear_ranges()
        self._summary.clear()
        self._update_points_label()

    def set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)

    def set_summary(self, text: str) -> None:
        self._summary.setPlainText(localize(text))

    def _add_range(self) -> None:
        if self._in_point is None or self._out_point is None:
            self._status.setText(localize("Marque início e fim antes de adicionar o trecho."))
            return
        start_frame, start_seconds = self._in_point
        end_frame, end_seconds = self._out_point
        if end_frame < start_frame:
            start_frame, end_frame = (end_frame, start_frame)
            start_seconds, end_seconds = (end_seconds, start_seconds)
        if end_frame == start_frame:
            self._status.setText(localize("O trecho precisa conter pelo menos dois frames."))
            return
        if any(
            start_frame <= existing.end_frame and end_frame >= existing.start_frame
            for existing in self._ranges
        ):
            self._status.setText(localize("Esse trecho se sobrepõe a uma seleção existente."))
            return
        while f"Trecho {self._next_range_number}" in {r.label for r in self._ranges}:
            self._next_range_number += 1
        frame_range = AnalysisFrameRange(
            start_frame, end_frame, f"Trecho {self._next_range_number}"
        )
        self._next_range_number += 1
        self._ranges.append(frame_range)
        self._range_list.addItem(
            localize(
                f"{frame_range.label}: frames {start_frame}–{end_frame}  "
                f"({format_timecode(start_seconds)}–{format_timecode(end_seconds)})"
            )
        )
        self._status.setText(localize(f"{len(self._ranges)} trecho(s) incluído(s)."))
        self.ranges_changed.emit(tuple(self._ranges))
        self._range_list.setCurrentRow(len(self._ranges) - 1)

    def _remove_selected(self) -> None:
        row = self._range_list.currentRow()
        if row < 0:
            return
        self._range_list.takeItem(row)
        self._ranges.pop(row)
        self._status.setText(localize(f"{len(self._ranges)} trecho(s) incluído(s)."))
        self.ranges_changed.emit(tuple(self._ranges))

    def request_analysis(self) -> None:
        if not self._ranges:
            self._status.setText(localize("Adicione pelo menos um trecho antes da análise."))
            return
        self.analyze_requested.emit(tuple(self._ranges))

    def _update_points_label(self) -> None:
        in_text = (
            f"{self._in_point[0]} / {format_timecode(self._in_point[1])}" if self._in_point else "—"
        )
        out_text = (
            f"{self._out_point[0]} / {format_timecode(self._out_point[1])}"
            if self._out_point
            else "—"
        )
        self._points_label.setText(localize(f"Início: {in_text}   Fim: {out_text}"))

    def set_ranges(self, ranges: tuple[AnalysisFrameRange, ...], index=None) -> None:
        self._ranges = list(ranges)
        self._next_range_number = max(self._next_range_number, len(ranges) + 1)
        self._range_list.clear()
        for value in ranges:
            times = (
                (
                    f"{format_timecode(index[value.start_frame].seconds)}–"
                    f"{format_timecode(index[value.end_frame].seconds)}"
                )
                if index is not None
                else f"frames {value.start_frame}–{value.end_frame}"
            )
            self._range_list.addItem(localize(f"{value.label}: {times}"))
        self.ranges_changed.emit(tuple(self._ranges))

    def edit_range(self, row: int, start: int, end: int, index=None) -> bool:
        if row < 0 or row >= len(self._ranges) or start >= end:
            return False
        if any(
            i != row and start <= r.end_frame and end >= r.start_frame
            for i, r in enumerate(self._ranges)
        ):
            self._status.setText(localize("Esse trecho se sobrepõe a uma seleção existente."))
            return False
        ranges = list(self._ranges)
        ranges[row] = AnalysisFrameRange(start, end, ranges[row].label)
        self.set_ranges(tuple(ranges), index)
        self._range_list.setCurrentRow(row)
        return True
