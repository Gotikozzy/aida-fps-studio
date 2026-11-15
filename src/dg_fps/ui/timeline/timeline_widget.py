from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollBar,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.analyzers.cadence import CadenceSample
from dg_fps.media.frame_provider import VideoThumbnail
from dg_fps.ui.i18n import localize
from dg_fps.ui.icons import transport_icon
from dg_fps.ui.studio_timeline import StudioTimeline
from dg_fps.ui.timeline.cadence_track import CadenceTrack
from dg_fps.ui.timeline.opening_preview import OpeningPreview
from dg_fps.ui.timeline.thumbnail_strip import ThumbnailStrip


class TimelineWidget(QWidget):
    frame_requested = Signal(int)
    seek_started = Signal()
    play_requested = Signal()
    previous_requested = Signal()
    next_requested = Signal()
    mark_in_requested = Signal()
    mark_out_requested = Signal()
    range_created = Signal(int, int)
    range_edited = Signal(int, int, int)
    range_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._frame_count = 0
        self._drag_frame: int | None = None
        self.setObjectName("analystTimeline")
        self._current_label = QLabel(localize("Frame 0"))
        self._frame_entry = QSpinBox()
        self._frame_entry.setObjectName("timelineFrameEntry")
        self._frame_entry.setPrefix(localize("Frame "))
        self._frame_entry.setRange(0, 0)
        self._frame_entry.setKeyboardTracking(False)
        self._frame_entry.setAccessibleName(localize("Ir para frame por índice"))
        self._frame_entry.setToolTip(
            localize("Digite o índice e confirme com Enter • alternativa: Ctrl+G")
        )
        self._frame_entry.editingFinished.connect(self._seek_from_entry)
        self._frame_entry.setEnabled(False)
        self._total_label = QLabel(localize("0 frames"))
        self._timecode_label = QLabel(localize("00:00:00.000 / 00:00:00.000"))
        self._timecode_label.setObjectName("timecodeReadout")
        self._playback_label = QLabel(localize("PAUSADO"))
        self._thumbnail_strip = ThumbnailStrip()
        self._thumbnail_strip.frame_selected.connect(self._request_from_thumbnail)
        self._cadence_track = CadenceTrack()
        self._previous_button = QToolButton()
        self._previous_button.setIcon(transport_icon("previous"))
        self._previous_button.setToolTip(localize("Frame anterior (Seta esquerda)"))
        self._previous_button.setAccessibleName(localize("Frame anterior"))
        self._previous_button.clicked.connect(self.previous_requested)
        self._play_button = QToolButton()
        self._play_button.setIcon(transport_icon("play"))
        self._play_button.setToolTip(localize("Reproduzir ou pausar (Espaço/K)"))
        self._play_button.setAccessibleName(localize("Reproduzir ou pausar"))
        self._play_button.clicked.connect(self.play_requested)
        self._next_button = QToolButton()
        self._next_button.setIcon(transport_icon("next"))
        self._next_button.setToolTip(localize("Próximo frame (Seta direita)"))
        self._next_button.setAccessibleName(localize("Próximo frame"))
        self._next_button.clicked.connect(self.next_requested)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName("frameTimelineSlider")
        self._slider.setAccessibleName(localize("Timeline de frames"))
        self._slider.setAccessibleDescription(
            localize("Seleciona um frame do vídeo usando o índice temporal real")
        )
        self._slider.setToolTip(localize("Timeline de frames — arraste para navegar"))
        self._slider.setTracking(False)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setRange(0, 0)
        self._slider.setEnabled(False)
        self._slider.sliderPressed.connect(self._begin_seek)
        self._slider.sliderMoved.connect(self._preview_seek)
        self._slider.sliderReleased.connect(self._emit_request)
        labels = QHBoxLayout()
        labels.addWidget(self._previous_button)
        labels.addWidget(self._play_button)
        labels.addWidget(self._next_button)
        labels.addSpacing(8)
        labels.addWidget(self._frame_entry)
        labels.addWidget(self._timecode_label)
        labels.addStretch(1)
        labels.addWidget(self._playback_label)
        labels.addWidget(self._total_label)
        self._mark_in = QToolButton()
        self._mark_in.setText(localize("Início · I"))
        self._mark_in.setToolTip(localize("Marcar início no processo ativo (I)"))
        self._mark_in.clicked.connect(self.mark_in_requested)
        self._mark_out = QToolButton()
        self._mark_out.setText(localize("Fim · O"))
        self._mark_out.setToolTip(localize("Marcar fim no processo ativo (O)"))
        self._mark_out.clicked.connect(self.mark_out_requested)
        labels.addWidget(self._mark_in)
        labels.addWidget(self._mark_out)
        self.transport = QWidget()
        self.transport.setLayout(labels)
        self.canvas = StudioTimeline()
        self.canvas.seek_requested.connect(self.request_frame)
        self.canvas.interaction_started.connect(self.seek_started)
        self.canvas.range_created.connect(self.range_created)
        self.canvas.range_edited.connect(self.range_edited)
        self.canvas.range_selected.connect(self.range_selected)
        self.zoom_control = QSlider(Qt.Orientation.Horizontal)
        self.zoom_control.setRange(10, 400)
        self.zoom_control.setValue(10)
        self.zoom_control.setMaximumWidth(150)
        self.zoom_control.setToolTip(localize("Zoom da timeline • Ctrl + roda do mouse"))
        self.zoom_control.valueChanged.connect(lambda v: self.canvas.set_zoom(v / 10))
        self.select_tool = QToolButton()
        self.select_tool.setText("↔")
        self.select_tool.setCheckable(True)
        self.select_tool.setToolTip(localize("Selecionar intervalo • arraste na timeline"))
        self.select_tool.toggled.connect(lambda v: setattr(self.canvas, "selection_mode", v))
        self.scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.scroll.valueChanged.connect(self._pan)
        self.canvas.viewport_changed.connect(self._viewport_changed)
        tools = QHBoxLayout()
        tools.setContentsMargins(0, 0, 0, 0)
        tools.addWidget(QLabel(localize("TIMELINE")))
        tools.addSpacing(16)
        tools.addWidget(self.select_tool)
        tools.addStretch()
        tools.addWidget(QLabel(localize("Zoom")))
        tools.addWidget(self.zoom_control)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        heading = QLabel(localize("TIMELINE  ·  navegação precisa por frame e tempo da captura"))
        heading.setObjectName("timelineHeading")
        heading.hide()
        layout.addWidget(self.transport)
        self.tools = QWidget()
        self.tools.setLayout(tools)
        layout.addWidget(self.tools)
        layout.addWidget(self.canvas)
        layout.addWidget(self.scroll)
        self.opening = OpeningPreview()
        self.opening.hide()
        self.navigation_active = False
        layout.addWidget(self.opening)
        for widget in (self._thumbnail_strip, self._slider, self._cadence_track):
            widget.setParent(self)
            widget.hide()
        self._current_label.hide()
        self.set_frame_count(0)

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def set_navigation_mode(self, enabled: bool) -> None:
        self.navigation_active = enabled
        self.opening.setVisible(enabled)
        for widget in (self.transport, self.tools, self.canvas, self.scroll):
            widget.setVisible(not enabled)

    @property
    def current_frame(self) -> int:
        if self._drag_frame is not None:
            return self._drag_frame
        return self._slider.value()

    @property
    def timecode_text(self) -> str:
        return self._timecode_label.text()

    @property
    def playback_text(self) -> str:
        return self._playback_label.text()

    @property
    def thumbnail_count(self) -> int:
        return self._thumbnail_strip.thumbnail_count

    @property
    def cadence_sample_count(self) -> int:
        return self._cadence_track.sample_count

    def set_frame_count(self, frame_count: int) -> None:
        self._frame_count = max(0, frame_count)
        self.canvas.count = self._frame_count
        if not frame_count:
            self.canvas.times = ()
            self.canvas.points = ()
            self.canvas.images = {}
            self.canvas.offset = 0
        self.canvas.update()
        if self._frame_count == 0:
            self._thumbnail_strip.clear()
            self._cadence_track.clear()
        maximum = max(0, self._frame_count - 1)
        self._slider.setRange(0, maximum)
        self._frame_entry.setRange(0, maximum)
        for control in (
            self._previous_button,
            self._play_button,
            self._next_button,
            self._frame_entry,
            self._mark_in,
            self._mark_out,
        ):
            control.setEnabled(self._frame_count > 0)
        self._slider.setTickInterval(max(1, self._frame_count // 10))
        self._slider.setEnabled(self._frame_count > 0)
        self._thumbnail_strip.set_frame_count(self._frame_count)
        self._cadence_track.set_frame_count(self._frame_count)
        self._total_label.setText(localize(f"{self._frame_count} frames"))
        self.set_current_frame(min(self.current_frame, maximum))

    def set_current_frame(self, frame_index: int) -> None:
        if self._frame_count == 0:
            frame_index = 0
        elif not 0 <= frame_index < self._frame_count:
            raise IndexError(frame_index)
        if self._slider.isSliderDown():
            return
        self._slider.setValue(frame_index)
        self.canvas.current = frame_index
        self.canvas.update()
        self._frame_entry.setValue(frame_index)
        self._thumbnail_strip.set_current_frame(frame_index)
        self._current_label.setText(localize(f"Frame {frame_index}"))

    def set_thumbnails(self, thumbnails: list[VideoThumbnail]) -> None:
        self._thumbnail_strip.set_thumbnails(thumbnails)
        self.canvas.images = dict(self._thumbnail_strip._images)
        self.canvas.update()

    def set_cadence_samples(self, samples: tuple[CadenceSample, ...]) -> None:
        self._cadence_track.set_samples(samples)

    def set_analysis_ranges(self, ranges: tuple[AnalysisFrameRange, ...]) -> None:
        self._cadence_track.set_ranges(ranges)
        self.canvas.ranges = ranges
        self.canvas.update()

    def _pan(self, value: int) -> None:
        self.canvas.offset = value / 1000 * self.canvas.duration() * (1 - 1 / self.canvas.zoom)
        self.canvas.update()
        self.canvas.viewport_changed.emit()

    def _viewport_changed(self) -> None:
        self.scroll.blockSignals(True)
        self.scroll.setRange(0, 1000 if self.canvas.zoom > 1 else 0)
        maximum = self.canvas.duration() * (1 - 1 / self.canvas.zoom)
        self.scroll.setValue(round(self.canvas.offset / maximum * 1000) if maximum else 0)
        self.scroll.blockSignals(False)

    def request_frame(self, frame_index: int) -> None:
        self.set_current_frame(frame_index)
        self.frame_requested.emit(frame_index)

    def set_timecode(self, seconds: float, duration_seconds: float | None) -> None:
        duration = duration_seconds or 0.0
        self._timecode_label.setText(
            localize(f"{format_timecode(seconds)} / {format_timecode(duration)}")
        )

    def set_playback_state(self, direction: int, speed: int) -> None:
        if direction == 0:
            self._play_button.setIcon(transport_icon("play"))
            self._playback_label.setText(localize("PAUSADO"))
            return
        self._play_button.setIcon(transport_icon("pause"))
        label = "AVANÇO" if direction > 0 else "REVERSO"
        self._playback_label.setText(localize(f"{label} {speed}x"))

    def _seek_from_entry(self) -> None:
        if self._frame_count and self._frame_entry.value() != self._slider.value():
            self.seek_started.emit()
            self.request_frame(self._frame_entry.value())

    def _emit_request(self) -> None:
        frame_index = self._drag_frame
        if frame_index is None:
            frame_index = self._slider.sliderPosition()
        self._drag_frame = None
        self._slider.setValue(frame_index)
        self._current_label.setText(localize(f"Frame {frame_index} — carregando…"))
        self.frame_requested.emit(frame_index)

    def _begin_seek(self) -> None:
        self._drag_frame = self._slider.sliderPosition()
        self.seek_started.emit()

    def _preview_seek(self, frame_index: int) -> None:
        self._drag_frame = frame_index
        self._current_label.setText(localize(f"Frame {frame_index} — selecionado"))

    def _request_from_thumbnail(self, frame_index: int) -> None:
        self.seek_started.emit()
        self._slider.setValue(frame_index)
        self._thumbnail_strip.set_current_frame(frame_index)
        self._current_label.setText(localize(f"Frame {frame_index} — carregando…"))
        self.frame_requested.emit(frame_index)


def format_timecode(seconds: float) -> str:
    total_milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"
