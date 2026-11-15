from __future__ import annotations

import json
import time
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QLibraryInfo, QRectF, Qt, QTimer, QTranslator, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QImage,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.controllers.media_controller import MediaController
from dg_fps.core.enums import JobStatus
from dg_fps.hardware import HardwareCheck, check_hardware
from dg_fps.jobs.gpu_queue import GPUQueue
from dg_fps.jobs.models import JobRecord
from dg_fps.media.frame_provider import DecodedFrame, VideoThumbnail
from dg_fps.media.media_probe import MediaMetadata
from dg_fps.media.navigation_preview import NavigationFrame, navigation_span
from dg_fps.presentation.cadence_video import CadenceVideoAsset
from dg_fps.presentation.content_targets import (
    capture_target_limit,
    content_references,
    reference_state,
    resolve_references,
)
from dg_fps.presentation.fps_display import capture_nominal_text, fps_display
from dg_fps.presentation.frame_timeline import export_references
from dg_fps.service import AnalysisSession, FPSService
from dg_fps.studio_services import PreparedAnalysis, prepare_analysis
from dg_fps.ui.cadence_panel import CadencePanel
from dg_fps.ui.i18n import localize, set_language, system_language, translate_tree
from dg_fps.ui.studio_actions import StudioActions
from dg_fps.ui.studio_workspace import build_workspace
from dg_fps.ui.target_controls import SegmentTargetsDialog, TargetSelector
from dg_fps.ui.timeline.timeline_widget import TimelineWidget


class VideoView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(320, 180)
        self.setAccessibleName(localize("Prévia do vídeo"))
        self.image = QImage()
        self.preview_notice = ""

    def set_notice(self, text: str) -> None:
        if text == self.preview_notice:
            return
        self.preview_notice = text
        self.update()

    def set_frame(self, rgb: np.ndarray) -> None:
        height, width, _ = rgb.shape
        self.image = QImage(
            rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888
        ).copy()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        if self.image.isNull():
            painter.setPen(Qt.GlobalColor.lightGray)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                localize("Abra um vídeo para analisar FPS e cadência"),
            )
            return
        size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRectF(
            (self.width() - size.width()) / 2,
            (self.height() - size.height()) / 2,
            size.width(),
            size.height(),
        )
        painter.drawImage(target, self.image)
        if self.preview_notice:
            label = localize(self.preview_notice)
            width = painter.fontMetrics().horizontalAdvance(label) + 24
            badge = QRectF(self.width() - width - 12, 12, width, 28)
            painter.fillRect(badge, Qt.GlobalColor.black)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)


class FPSWindow(StudioActions, QMainWindow):
    def __init__(
        self, data_directory: Path, cache_directory: Path, *, language: str | None = None
    ) -> None:
        super().__init__()
        self.data_directory = data_directory
        self.preferences_path = data_directory / "settings.json"
        self._settings = {}
        with suppress(OSError, ValueError, AttributeError):
            self._settings = json.loads(self.preferences_path.read_text(encoding="utf-8"))
        if not isinstance(self._settings, dict):
            self._settings = {}
        preference = "system"
        with suppress(OSError, ValueError, AttributeError):
            preference = json.loads(self.preferences_path.read_text(encoding="utf-8")).get(
                "language", "system"
            )
        self.language_preference = language or (
            preference if preference in {"system", "pt", "en"} else "system"
        )
        set_language(
            system_language() if self.language_preference == "system" else self.language_preference
        )
        self.qt_translator = QTranslator(self)
        self.hardware_result: HardwareCheck | None = None
        self.setWindowTitle("AIDA FPS Studio")
        available = self.screen().availableGeometry()
        self.resize(
            min(1600, round(available.width() * 0.95)), min(960, round(available.height() * 0.95))
        )
        self.source: Path | None = None
        self.metadata: MediaMetadata | None = None
        self.current: DecodedFrame | None = None
        self.session: AnalysisSession | None = None
        self.last_export_path: Path | None = None
        self.target_overrides: dict[str, float | None] = {}
        self.output_directory = data_directory / "resultados"
        self.job_id: str | None = None
        self.service = FPSService()
        self.jobs = GPUQueue(self)
        self.jobs.job_changed.connect(self._job_progress)
        self.jobs.job_completed.connect(self._job_completed)
        self.jobs.job_failed.connect(self._job_failed)
        self.jobs.job_cancelled.connect(self._job_cancelled)
        self.media = MediaController(self, index_cache_directory=cache_directory)
        self.media.media_opened.connect(self._media_opened)
        self.media.navigation_thumbnails_ready.connect(self._navigation_thumbnails_ready)
        self.media.navigation_frame_ready.connect(self._navigation_frame_ready)
        self.media.navigation_failed.connect(self._navigation_failed)
        self.media.index_ready.connect(self._index_ready)
        self.media.index_rebuilt.connect(self._index_rebuilt)
        self.media.frame_ready.connect(self._preview_frame_ready)
        self.media.frame_unavailable.connect(self._frame_unavailable)
        self.media.thumbnails_ready.connect(self._thumbnails_ready)
        self.media.thumbnails_failed.connect(self._thumbnails_failed)
        self.media.thumbnail_loading_changed.connect(self._thumbnail_loading_changed)
        self.media.preview_status.connect(
            lambda message: self.statusBar().showMessage(localize(message), 8000)
        )
        self.media.progress_changed.connect(self._media_progress)
        self.media.error_occurred.connect(self._media_error)
        self.timer = QTimer(self)
        self.timer.setInterval(5)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._play_tick)
        self.play_start = 0.0
        self.play_seconds = 0.0
        self._timeline_updated = 0.0
        self.view = VideoView()
        self.timeline = TimelineWidget()
        self.timeline.opening.time_requested.connect(self._request_navigation_time)
        self.timeline.opening.cancel_requested.connect(self._cancel_operation)
        self.timeline.opening.retry_requested.connect(self._restart_navigation)
        self._thumbnail_timer = QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.setInterval(120)
        self._thumbnail_timer.timeout.connect(self._request_visible_thumbnails)
        self.timeline.canvas.viewport_changed.connect(lambda: self._thumbnail_timer.start())
        self.timeline.frame_requested.connect(self.seek)
        self.timeline.seek_started.connect(self.pause)
        self.timeline.previous_requested.connect(lambda: self.step(-1))
        self.timeline.next_requested.connect(lambda: self.step(1))
        self.timeline.play_requested.connect(self.toggle_play)
        self.timeline.mark_in_requested.connect(self.mark_in)
        self.timeline.mark_out_requested.connect(self.mark_out)
        self.panel = CadencePanel()
        self.panel.mark_in_requested.connect(self.mark_in)
        self.panel.mark_out_requested.connect(self.mark_out)
        self.panel.analyze_requested.connect(self._analyze)
        self.panel.ranges_changed.connect(self._ranges_changed)
        self.open_button = QPushButton(localize("Abrir vídeo"))
        self.open_button.clicked.connect(self._choose_source)
        self.folder_button = QPushButton(localize("Pasta dos resultados…"))
        self.folder_button.clicked.connect(self._choose_output)
        self.show_folder = QPushButton(localize("Abrir resultados"))
        self.show_folder.clicked.connect(self._open_results)
        self.file_label = QLabel(localize("Nenhum vídeo aberto"))
        self.file_label.setProperty("i18n_skip", True)
        self.file_label.setWordWrap(True)
        self.analysis_mode = self._mode_box()
        self.encoding_mode = self._mode_box()
        self.index_mode = QComboBox()
        self.index_mode.addItem(localize("Automático"), True)
        self.index_mode.addItem(localize("Processador (CPU)"), False)
        self.index_mode.setToolTip(
            localize("Prepara a navegação ao abrir o próximo vídeo. "
                     "Escolha CPU ou detecção automática.")
        )
        self.index_mode.currentIndexChanged.connect(
            lambda: setattr(self.media, "hardware_indexing", self.index_mode.currentData())
        )
        self.content_target = TargetSelector()
        self.content_target.changed.connect(self._targets_changed)
        self.segment_targets_button = QPushButton(localize("Metas por trecho…"))
        self.segment_targets_button.clicked.connect(self._segment_targets)
        self.language_box = QComboBox()
        for label, value in (
            ("Sistema (automático)", "system"),
            ("Português", "pt"),
            ("English", "en"),
        ):
            self.language_box.addItem(localize(label), value)
        self.language_box.setCurrentIndex(self.language_box.findData(self.language_preference))
        self.language_box.currentIndexChanged.connect(self._language_changed)
        self.hardware_button = QPushButton(localize("Verificar aceleração gráfica"))
        self.hardware_button.clicked.connect(self._test_hardware)
        self.hardware_status = QPlainTextEdit(
            localize("Ainda não testado. O modo Automático verifica a compatibilidade ao analisar.")
        )
        self.hardware_status.setReadOnly(True)
        self.hardware_status.setMaximumHeight(120)
        self.hardware_status.setMinimumHeight(85)
        self.export_button = QPushButton(localize("Exportar vídeo com gráfico — 1080p"))
        self.export_button.clicked.connect(self._export_delivery)
        self.export_button.setEnabled(False)
        self.export_folder_button = QPushButton(localize("Abrir pasta da entrega"))
        self.export_folder_button.setEnabled(False)
        self.export_folder_button.clicked.connect(self._open_export_folder)
        self.cancel_button = QPushButton(localize("Cancelar"))
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setVisible(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        build_workspace(self)
        self._init_studio()
        self.panel.setEnabled(False)
        self.navigation_actions: list[QAction] = []
        for key, callback in (
            ("Ctrl+O", self._choose_source),
            ("V", lambda: self.timeline.select_tool.setChecked(False)),
            ("R", lambda: self.timeline.select_tool.setChecked(True)),
            ("Space", self.toggle_play),
            ("Left", lambda: self.step(-1)),
            ("Right", lambda: self.step(1)),
            ("I", self.mark_in),
            ("O", self.mark_out),
            ("Ctrl+R", self.panel.request_analysis),
            ("Ctrl+Shift+A", self.panel._add_range),
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(callback)
            self.addAction(action)
            if key != "Ctrl+O":
                self.navigation_actions.append(action)
        application = QApplication.instance()
        if application is not None:
            application.focusChanged.connect(self._focus_changed)
        self._apply_language()

    def _language_changed(self) -> None:
        self.language_preference = self.language_box.currentData()
        self._store_preferences()
        self._apply_language()

    def _apply_language(self) -> None:
        language = (
            system_language() if self.language_preference == "system" else self.language_preference
        )
        set_language(language)
        app = QApplication.instance()
        if app is not None:
            app.removeTranslator(self.qt_translator)
            if language == "pt":
                translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
                if self.qt_translator.load("qtbase_pt_BR", translations):
                    app.installTranslator(self.qt_translator)
        translate_tree(self)
        if self.source is None:
            self.file_label.setText(localize("Nenhum vídeo aberto"))
        self.statusBar().showMessage(localize(self.statusBar().currentMessage()))
        for item in self.findChildren(QAction):
            item.setText(localize(item.text()))
        if hasattr(self, "workspaces"):
            self.timeline.opening.retranslate()
            self._update_project_title()
            self._refresh_results()
        if self.hardware_result is not None:
            self._display_hardware(self.hardware_result)
        if self.session is not None:
            self._targets_changed()

    def _test_hardware(self) -> None:
        if self.job_id or self._media_loading:
            return
        self.pause()
        self._hardware_testing = True
        self.hardware_status.setPlainText(localize("Testando compatibilidade NVIDIA…"))
        self._set_busy(True, show_progress=False)
        self.hardware_dialog.message.setText(localize("Testando compatibilidade NVIDIA…"))
        self.hardware_dialog.bar.setValue(0)
        self.hardware_dialog.open()
        self.job_id = self.jobs.submit("Testar NVIDIA", check_hardware)

    def _display_hardware(self, result: HardwareCheck) -> None:

        def state(value: bool) -> str:
            return localize("Disponível" if value else "Indisponível")

        lines = [
            localize(f"Análise com NVIDIA: {state(result.optical_flow)}"),
            localize(f"Exportação com NVIDIA: {state(result.nvenc)}"),
        ]
        for gpu in result.gpus:
            lines.append(
                f"{gpu.name}: {localize('Aprovado' if gpu.optical_flow else 'Não aprovado')}"
            )
        details = [
            localize(f"Ponte incluída: {state(result.bridge_found)}"),
            localize(f"Driver NVIDIA: {state(result.driver_available)}"),
        ]
        if result.reason == "bridge_missing":
            lines.append(
                localize("Reinstale o AIDA FPS Studio para restaurar os arquivos de aceleração.")
            )
        elif result.reason == "driver_missing":
            lines.append(
                localize("Instale ou atualize o driver de vídeo NVIDIA e teste novamente.")
            )
        elif result.reason == "no_devices":
            lines.append(localize("Nenhuma GPU NVIDIA detectada pelo driver."))
        elif not result.optical_flow:
            lines.append(
                localize(
                    "A aceleração da análise está indisponível. "
                    "Use o processador ou atualize o driver NVIDIA e teste novamente."
                )
            )
        if not result.nvenc:
            lines.append(localize("Você pode exportar o vídeo usando o processador (CPU)."))
        lines.append(localize("CPU continua disponível para análise e exportação."))
        self.hardware_status.setPlainText(localize("\n".join(lines)))
        details.extend(gpu.detail for gpu in result.gpus if gpu.detail)
        if result.reason not in {"", "bridge_missing", "driver_missing", "no_devices"}:
            details.append(result.reason)
        self.hardware_status.setToolTip(localize("\n".join(details)))

    def _focus_changed(self, old: QWidget | None, current: QWidget | None) -> None:
        del old
        editing = isinstance(current, (QLineEdit, QAbstractSpinBox, QPlainTextEdit, QComboBox))
        in_analysis = self.workspaces.currentIndex() == 0
        for action in getattr(self, "navigation_actions", ()):
            action.setEnabled(in_analysis and not editing)

    @staticmethod
    def _mode_box() -> QComboBox:
        box = QComboBox()
        box.addItem(localize("Processador (CPU)"), "cpu")
        box.addItem(localize("Automático"), "auto")
        box.addItem(localize("Placa de vídeo NVIDIA"), "nvidia")
        box.setCurrentIndex(1)
        return box

    def _choose_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            localize("Abrir vídeo"),
            "",
            localize("Vídeos (*.mp4 *.mkv *.mov *.avi *.webm *.m4v);;Todos (*)"),
        )
        if path:
            self.open_source(Path(path))

    def _segment_targets(self) -> None:
        labels = [value.label for value in self.panel.ranges]
        if not labels or self.job_id:
            return
        dialog = SegmentTargetsDialog(
            labels,
            self.target_overrides,
            self.content_target.value(),
            self,
            capture_rate=self.content_target.capture_rate,
        )
        if dialog.exec():
            self.target_overrides = dialog.values()
            self._targets_changed()

    def _targets_changed(self) -> None:
        self.export_preview.clear_image()
        self._targets_compatible()
        if hasattr(self, "_restoring"):
            self._mark_dirty()
            self._refresh_results()
        if self.session is None:
            return
        references = resolve_references(
            self.session.automatic_references or content_references(self.session.analysis),
            self.content_target.value(),
            self.target_overrides,
        )
        references = export_references(self.session.analysis, references)
        lines = [localize("Referências do conteúdo (apresentação):")]
        capture_limit = capture_target_limit(self.session.analysis.summary.container_fps)
        for label, reference in references.items():
            target = (
                f"{reference.target_fps:g} FPS"
                if reference.target_fps is not None
                else localize("indeterminada")
            )
            origin = localize("manual" if reference.origin == "manual" else "inferida")
            measured = self.session.analysis.segment_summaries[label]
            state = reference_state(measured.content_fps, reference, capture_limit)
            status = localize(
                {
                    "near_reference": "Próximo da referência",
                    "below_reference": "Abaixo da referência",
                    "above_reference": "Acima da referência",
                    "no_reference": "Sem referência",
                    "capture_limited": "Captura limita a comparação",
                    "inconclusive": "inconclusivo",
                }[state]
            )
            lines.append(f"{localize(label)}: {target} ({origin}) — {status}")
        base = getattr(self, "_measured_summary", self.panel.summary_text)
        self.panel.set_summary(localize(base) + "\n\n" + "\n".join(lines))
        path = self.session.reports.project_directory / "content_reference.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "analysis": str(self.session.reports.analysis_json),
                    "default_target": self.content_target.value(),
                    "overrides": self.target_overrides,
                    "segments": {
                        label: reference.to_dict() for label, reference in references.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _targets_compatible(self, *, notify: bool = False) -> bool:
        limit = self.content_target.capture_limit
        compatible = self.content_target.is_compatible() and all(
            self.content_target.supports_target(v) for v in self.target_overrides.values()
        )
        if limit == 0:
            message = localize("Taxa da captura indisponível. Use Automático.")
        elif not compatible:
            message = localize(
                "Há metas incompatíveis com a captura. Escolha outra meta ou Automático."
            )
        else:
            message = localize(f"Limite da captura: {limit:g} FPS") if limit is not None else ""
        self.target_validation.setText(message)
        if notify and not compatible:
            self.workspaces.setCurrentIndex(0)
            self.inspector_tabs.setCurrentIndex(1)
            QMessageBox.warning(self, "AIDA FPS Studio", message)
        return compatible

    def open_source(self, source: Path) -> None:
        self._replace_project(lambda: self._load_source(source))

    def _show_project_workspace(self) -> None:
        self.workspaces.setTabEnabled(0, True)
        self.workspaces.setTabEnabled(1, True)
        self.workspaces.setCurrentIndex(0)

    def _load_source(self, source: Path) -> None:
        self._write_recovery()
        self.pause()
        if not self._pending_project:
            self.project_path = None
        self._restoring = True
        self._undo.clear()
        self._redo.clear()
        self._curve = ()
        self._pending_delivery = None
        self._pending_preview = False
        self.timeline.canvas.pending_start = None
        self._show_project_workspace()
        self.source = source.resolve()
        self.last_export_path = None
        self.export_folder_button.setEnabled(False)
        self.target_overrides.clear()
        self.metadata = None
        self.reindex_action.setEnabled(False)
        self.current = None
        self._opening_preview_ready = False
        self._navigation_cursor_seconds = None
        self.session = None
        self.content_target.set_capture_rate(None)
        self.content_target.set_value(None)
        self.export_button.setEnabled(False)
        self.view.image = QImage()
        self.view.set_notice("")
        self._thumbnail_timer.stop()
        self._set_preview_actions(False)
        self.panel.reset()
        self.panel.setEnabled(False)
        self.timeline.set_frame_count(0)
        self.timeline.set_navigation_mode(False)
        self.timeline.set_thumbnails([])
        self.timeline.set_cadence_samples(())
        self.file_label.setText(source.name)
        self.delivery_name.setText(source.stem)
        self.source_details.setText("")
        self.source_thumbnail.clear()
        self._restoring = False
        self._dirty = False
        self._update_project_title()
        self._media_loading = True
        self._loading_thumbnails = False
        self.retry_thumbnails_action.setEnabled(False)
        self.process_dialog.cancel.setText(localize("Cancelar"))
        self.process_dialog.message.setText(localize("Abrindo e preparando vídeo…"))
        self.process_dialog.heading.setText(localize("Preparando vídeo"))
        self.process_dialog.bar.setRange(0, 100)
        self.process_dialog.bar.setValue(0)
        self.process_dialog.open()
        self.media.open_media(self.source)

    def _media_opened(self, metadata: MediaMetadata, frame: DecodedFrame) -> None:
        self._set_media_metadata(metadata)
        self._show_frame(frame)
        self.source_thumbnail.setPixmap(
            QPixmap.fromImage(self.view.image).scaled(
                210,
                100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._opening_preview_ready = True
        self.reindex_action.setEnabled(False)
        self.process_dialog.hide()
        self.timeline.opening.reset(navigation_span(metadata))
        self.timeline.set_navigation_mode(True)
        self.timeline.opening.set_position(frame.timestamp.seconds, frame.timestamp.seconds)
        self.view.set_notice("Prévia representativa · preparando índice preciso")
        self._progress("Prévia disponível. Preparando índice preciso…", 0)

    def _navigation_thumbnails_ready(self, frames: tuple[NavigationFrame, ...]) -> None:
        if self.timeline.navigation_active:
            self.timeline.opening.set_frames(frames)

    def _request_navigation_time(self, seconds: float) -> None:
        if self.job_id or not self.timeline.navigation_active or not self._opening_preview_ready:
            return
        self._navigation_cursor_seconds = seconds
        self.view.set_notice("Buscando prévia por tempo…")
        self.media.request_navigation_time(seconds)

    def _navigation_frame_ready(self, frame: NavigationFrame) -> None:
        if not self.timeline.navigation_active:
            return
        self.current = None
        self.view.set_frame(frame.rgb)
        self.view.set_notice("Prévia representativa · posição exata após indexação")
        self.timeline.opening.set_position(frame.requested_seconds, frame.seconds)

    def _restart_navigation(self) -> None:
        if self.source is not None and self.job_id is None:
            self.media.cancel_loading()
            self._load_source(self.source)

    def _navigation_failed(self, message: str) -> None:
        if self.timeline.navigation_active:
            self.view.set_notice("Prévia temporal indisponível")

    def _set_media_metadata(self, metadata: MediaMetadata) -> None:
        self.metadata = metadata
        self.reindex_action.setEnabled(True)
        stream = metadata.video_streams[0]
        self.content_target.set_capture_rate(stream.average_rate or 0.0)
        self._targets_compatible()
        self.source_details.setText(
            f"{stream.width} × {stream.height} · {capture_nominal_text(stream.average_rate)} FPS"
        )

    def _index_ready(self, count: int) -> None:
        index = self.media.timestamp_index
        if index is not None:
            decoder = {
                "cpu": "CPU",
                "cache": localize("índice salvo"),
                "d3d11va": "GPU (Windows)",
            }.get(index.decoder, index.decoder)
            self.file_label.setToolTip(f"{self.source}\n{localize('Indexação')}: {decoder}")
        if count <= 0:
            self._media_error("Não foi possível ler o vídeo")
            return
        self.timeline.set_thumbnails([])
        had_pending_project = self._pending_project is not None
        was_reindex = self._reindex_status is not None
        self._finish_media_loading()
        self.reindex_action.setEnabled(True)
        if not was_reindex and not had_pending_project:
            seconds = self._navigation_cursor_seconds
            target = index.nearest_at_or_after(seconds).index if seconds is not None else 0
            self.seek(target)
        self._set_preview_actions(True)
        self._request_visible_thumbnails()

    def _index_rebuilt(self, timing_changed: bool, metadata: MediaMetadata) -> None:
        index = self.media.timestamp_index
        if index is None:
            return
        self._set_media_metadata(metadata)
        if self.session is not None:
            try:
                stat = self.source.stat()
                source_changed = (stat.st_size, stat.st_mtime_ns) != (
                    self.session.source_size,
                    self.session.source_mtime_ns,
                )
            except OSError:
                source_changed = True
            timing_changed = timing_changed or source_changed
        if timing_changed:
            ranges = tuple(r for r in self.panel.ranges if r.end_frame < len(index))
            removed_ranges = len(ranges) != len(self.panel.ranges)
            self.panel._in_point = self.panel._out_point = None
            self.timeline.canvas.pending_start = None
            self.panel.set_ranges(ranges, index)
            self._undo.clear()
            self._redo.clear()
            self._reindex_status = (
                "Índice atualizado. Revise os trechos e analise novamente."
                if removed_ranges
                else "Índice atualizado. Analise novamente."
            )
            self.analysis_state.setText(localize("Índice atualizado. Analise novamente."))
        elif self.session is not None:
            self.session = replace(self.session, timestamp_index=index)

    def _request_visible_thumbnails(self) -> None:
        if not self._media_loading:
            frames = self.timeline.canvas.thumbnail_frames()
            self.media.set_thumbnail_viewport(tuple(dict.fromkeys(frames)))

    def _thumbnail_loading_changed(self, loading: bool) -> None:
        self._loading_thumbnails = loading
        if loading:
            self.retry_thumbnails_action.setEnabled(False)
        elif any(image.isNull() for image in self.timeline.canvas.images.values()):
            self.retry_thumbnails_action.setEnabled(True)

    def _set_preview_actions(self, enabled: bool) -> None:
        for action in self.preview_actions:
            action.setEnabled(enabled)

    def _optimize_monitor(self, mode: str) -> None:
        if not self.job_id and not self._media_loading and self.timeline.frame_count:
            self.pause()
            self.media.optimize_preview(self.timeline.current_frame, mode=mode)

    def _retry_thumbnails(self) -> None:
        if self.job_id or self._media_loading or not self.timeline.frame_count:
            return
        self.retry_thumbnails_action.setEnabled(False)
        self.media.retry_thumbnails()

    def _thumbnails_ready(self, items: list[VideoThumbnail]) -> None:
        self.timeline.set_thumbnails(items)
        if not self._loading_thumbnails:
            self.retry_thumbnails_action.setEnabled(any(item.rgb is None for item in items))

    def _frame_unavailable(self, message: str) -> None:
        if not self.timer.isActive():
            self.view.set_notice("Quadro selecionado indisponível")
        self.statusBar().showMessage(localize(f"Quadro indisponível. {message}"), 8000)

    def _thumbnails_failed(self, message: str) -> None:
        self.retry_thumbnails_action.setEnabled(True)
        self.retry_thumbnails_action.setToolTip(message)
        self.statusBar().showMessage(localize("Vídeo pronto. Gere as miniaturas pelo menu Exibir."))

    def _finish_media_loading(self) -> None:
        index = self.media.timestamp_index
        count = len(index)
        self._media_loading = False
        self._opening_preview_ready = False
        self.timeline.set_navigation_mode(False)
        self._loading_thumbnails = False
        self.process_dialog.hide()
        self.process_dialog.cancel.setText(localize("Cancelar"))
        self.timeline.canvas.set_index(index)
        self.timeline.set_frame_count(count)
        if self._reindex_status is not None:
            notice, self._reindex_status = self._reindex_status, None
            self._set_busy(False)
            self.seek(self.timeline.current_frame)
            self._progress(notice, 100)
            return
        self.panel.setEnabled(count > 1)
        self.panel._analyze.setEnabled(count > 1 and bool(self.panel.ranges))
        self._progress(f"Pronto: {count} frames. Use I e O para criar um trecho.", 100)
        self._restore_indexed_project()
        self.export_button.setEnabled(bool(self.panel.ranges) and not self.job_id)

    def _preview_frame_ready(self, frame: DecodedFrame) -> None:
        if (
            not self.timeline.navigation_active
            and frame.timestamp.index == self.timeline.current_frame
        ):
            self._show_frame(frame)

    def _show_frame(self, frame: DecodedFrame) -> None:
        self.view.set_notice("")
        self.current = frame
        self.view.set_frame(frame.rgb)
        now = time.monotonic()
        if self.timer.isActive() and now - self._timeline_updated < 0.050:
            return
        self._timeline_updated = now
        if self.timeline.canvas.drag is not None:
            return
        self.timeline.set_current_frame(frame.timestamp.index)
        self.timeline.set_timecode(
            frame.timestamp.seconds, self.metadata.duration_seconds if self.metadata else None
        )

    def seek(self, frame: int) -> None:
        index = self.media.timestamp_index
        if self.job_id or self._media_loading or index is None or not 0 <= frame < len(index):
            return
        self.pause()
        self.timeline.set_current_frame(frame)
        self.timeline.set_timecode(
            index[frame].seconds, self.metadata.duration_seconds if self.metadata else None
        )
        if self.current is None or self.current.timestamp.index != frame:
            self.view.set_notice("Buscando quadro selecionado…")
            if self.timeline.canvas.drag is not None:
                nearby = self.media.nearby_preview(frame)
                if nearby is not None:
                    self.view.set_frame(nearby.rgb)
        elif self.view.preview_notice:
            self._show_frame(self.current)
        self.media.request_frame(frame)

    def step(self, direction: int) -> None:
        if self.current and self.timeline.frame_count:
            self.seek(
                max(0, min(self.timeline.frame_count - 1, self.timeline.current_frame + direction))
            )

    def pause(self) -> None:
        was_playing = self.timer.isActive()
        self.timer.stop()
        self.media.stop_playback()
        self.timeline.set_playback_state(0, 1)
        if was_playing and self.current is not None:
            self._show_frame(self.current)

    def toggle_play(self) -> None:
        if self.timer.isActive():
            self.pause()
            return
        if self.job_id or self.current is None or self.media.timestamp_index is None:
            return
        index = self.media.timestamp_index
        start_frame = self.timeline.current_frame
        if self.media.start_playback(
            start_frame,
            max_size=(
                max(320, min(1280, self.view.width())),
                max(180, min(720, self.view.height())),
            ),
        ):
            self.play_start = -1.0
            self.play_seconds = index[start_frame].seconds
            self.timeline.set_playback_state(1, 1)
            self.timer.start()

    def _play_tick(self) -> None:
        if self.play_start < 0:
            if not self.media.playback_buffer_ready:
                return
            self.play_start = time.monotonic()
        frame = self.media.take_playback_frame_at_or_before(
            self.play_seconds + time.monotonic() - self.play_start
        )
        if frame is not None:
            self._show_frame(frame)
        if self.media.playback_exhausted:
            self.pause()

    def mark_in(self) -> None:
        if self.panel.isEnabled() and not self._media_loading:
            frame = self.timeline.current_frame
            self.pause()
            self._start_range_at(frame)

    def mark_out(self) -> None:
        if self.panel.isEnabled() and not self._media_loading:
            frame = self.timeline.current_frame
            self.pause()
            self._finish_range_at(frame)

    def _ranges_changed(self, ranges: tuple[AnalysisFrameRange, ...]) -> None:
        labels = {value.label for value in ranges}
        self.target_overrides = {k: v for k, v in self.target_overrides.items() if k in labels}
        self.timeline.set_analysis_ranges(ranges)
        self.session = None
        self.export_button.setEnabled(bool(ranges) and not self.job_id)
        self.timeline.set_cadence_samples(())
        self.panel.set_summary(localize(""))
        self._curve = ()
        self.timeline.canvas.points = ()
        self.timeline.canvas.update()
        self.export_preview.clear_image()
        self._refresh_results()
        self._range_history(ranges)
        self.panel._analyze.setEnabled(bool(ranges) and not self.job_id)

    def _choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            localize("Pasta dos resultados"),
            str(self.output_directory),
        )
        if path:
            self.output_directory = Path(path)
            self.folder_button.setToolTip(localize(str(self.output_directory)))

    def _open_results(self) -> None:
        path = self.session.reports.project_directory if self.session else self.output_directory
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_export_folder(self) -> None:
        if self.last_export_path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_export_path.parent)))

    def _analyze(self, ranges: tuple[AnalysisFrameRange, ...]) -> None:
        index = self.media.timestamp_index
        if self.job_id or not self.source or (not self.metadata) or (index is None) or (not ranges):
            return
        self.pause()
        source, metadata, output = (self.source, self.metadata, self.output_directory)
        mode = self.analysis_mode.currentData()
        self.session = None
        self._set_busy(True)
        self.panel.set_summary(localize("Analisando FPS e cadência…"))
        self.job_id = self.jobs.submit(
            "Analisar FPS",
            lambda token, report: prepare_analysis(
                self.service.analyze(
                    source, metadata, index, ranges, output, mode, None, token, report
                ),
                token,
            ),
        )

    def _export(self) -> None:
        if self.session is None or self.job_id:
            return
        if not self._targets_compatible(notify=True):
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            localize("Exportar vídeo com gráfico"),
            str(self.session.reports.project_directory / "fps_1080p.mp4"),
            localize("MP4 (*.mp4)"),
        )
        if not path:
            return
        output = Path(path)
        if output.suffix.lower() != ".mp4":
            output = output.with_suffix(".mp4")
            if (
                output.exists()
                and QMessageBox.question(
                    self, localize("Substituir vídeo"), localize(f"Substituir {output.name}?")
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        self.pause()
        references = resolve_references(
            self.session.automatic_references or content_references(self.session.analysis),
            self.content_target.value(),
            dict(self.target_overrides),
        )
        session, mode = (self.session, self.encoding_mode.currentData())
        language = (
            system_language() if self.language_preference == "system" else self.language_preference
        )
        self._set_busy(True)
        self.job_id = self.jobs.submit(
            "Exportar vídeo",
            lambda token, report: self.service.export(
                session, output, mode, token, report, language=language, references=references
            ),
        )

    def _set_busy(self, busy: bool, *, show_progress: bool = True) -> None:
        self.media.suspend_preview_work(busy)
        self.panel.set_busy(busy)
        self.timeline.setEnabled(not busy)
        for control in (
            self.open_button,
            self.folder_button,
            self.analysis_mode,
            self.encoding_mode,
            self.index_mode,
            self.content_target,
            self.segment_targets_button,
            self.hardware_button,
        ):
            control.setEnabled(not busy)
        self.export_button.setEnabled(
            not busy and self.media.timestamp_index is not None and bool(self.panel.ranges)
        )
        self.export_folder_button.setEnabled(not busy and self.last_export_path is not None)
        self.cancel_button.setEnabled(busy)
        self.cancel_button.hide()
        if not busy:
            self.panel.setEnabled(self.media.timestamp_index is not None)
        self.panel._analyze.setEnabled(
            not busy and self.media.timestamp_index is not None and bool(self.panel.ranges)
        )
        self.workspaces.tabBar().setEnabled(not busy)
        for menu in self.menuBar().actions():
            menu.setEnabled(not busy)
        if busy and show_progress:
            self.process_dialog.heading.setText(localize("Preparando operação…"))
            self.progress.setValue(0)
            self.process_dialog.message.setText(localize("Preparando operação…"))
            self.process_dialog.bar.setRange(0, 100)
            self.process_dialog.bar.setValue(0)
            self.process_dialog.open()
        else:
            self.process_dialog.hide()
            self.hardware_dialog.hide()

    def _cancel(self) -> None:
        self._after_project_save = None
        self._pending_delivery = None
        self._pending_preview = False
        if self.job_id:
            self.jobs.cancel(self.job_id)

    def _progress(self, message: str, value: int) -> None:
        self.statusBar().showMessage(localize(message))
        self.progress.setValue(value)
        dialog = self.hardware_dialog if self._hardware_testing else self.process_dialog
        if dialog.isVisible():
            dialog.message.setText(localize(message))
            dialog.bar.setValue(min(99, value))

    def _media_progress(self, message: str, value: int) -> None:
        # A late seek/thumbnail/index notification cannot finish an export's bar.
        if self.job_id is None:
            self._progress(message, value)
            if self._media_loading and self.timeline.navigation_active:
                self.timeline.opening.progress.setValue(min(99, value))

    def _job_progress(self, record: JobRecord) -> None:
        if record.id == self.job_id and record.status == JobStatus.RUNNING:
            self.process_dialog.heading.setText(localize(record.name))
            if self._hardware_testing and record.message:
                self.hardware_status.setPlainText(localize(record.message))
            self._progress(record.message or record.name, record.progress)

    def _job_completed(self, job_id: str, result: object) -> None:
        if job_id != self.job_id:
            return
        if isinstance(result, CadenceVideoAsset):
            try:
                if not result.path.is_file() or result.path.stat().st_size <= 0:
                    raise OSError(localize("O MP4 não foi encontrado no destino"))
            except OSError as exc:
                self._job_failed(job_id, f"{result.path}: {exc}")
                return
        self.job_id = None
        if self._studio_completion(result):
            return
        if isinstance(result, PreparedAnalysis):
            self._curve = result.points
            self.timeline.canvas.points = result.points
            self.timeline.canvas.update()
            result = result.session
        if isinstance(result, HardwareCheck):
            self._hardware_testing = False
            self.hardware_result = result
            self._display_hardware(result)
            self._progress("Teste NVIDIA concluído", 100)
        elif isinstance(result, AnalysisSession):
            restored = self._restoring
            self.session = result
            self.timeline.set_cadence_samples(result.analysis.samples)
            summary = result.analysis.summary
            capture = summary.container_fps

            def rate(value: float | None) -> str:
                display = fps_display(value, capture)
                return display.text if display.value is not None else localize("inconclusivo")

            backends = {sample.flow_backend for sample in result.analysis.samples}
            processors = []
            if any("nvidia" in backend for backend in backends):
                processors.append("NVIDIA")
            if "opencv_farneback_cpu" in backends or not processors:
                processors.append("CPU")
            self.panel.set_summary(
                localize(
                    f"Cadência visual (inclui retenções): {rate(summary.content_fps)} FPS\n"
                    f"Captura nominal: {capture_nominal_text(capture)} FPS\n"
                    f"Cobertura observável: {summary.observable_window_ratio:.1%}\n"
                    f"Tempo ambíguo: {summary.ambiguous_seconds:.3f} s\n"
                    f"Retenções prolongadas: {summary.prolonged_retention_seconds:.3f} s\n"
                    "Retenção não identifica pausa nem queda do jogo.\n"
                    + "\n".join(
                        (
                            f"{label}: {rate(value.content_fps)} FPS"
                            for label, value in result.analysis.segment_summaries.items()
                        )
                    )
                    + f"\n\nProcessamento: {', '.join(processors)}"
                    + "\nRelatórios salvos. Use Abrir resultados para acessar."
                )
            )
            self._measured_summary = self.panel.summary_text
            self._targets_changed()
            self.show_folder.setToolTip(localize(str(result.reports.project_directory)))
            self._refresh_results()
            self._restoring = False
            self._write_recovery()
            self._set_busy(False)
            if not restored and self._pending_delivery is None and self._offer_save_analysis():
                return
            if self._continue_delivery():
                return
            self._progress("Análise concluída. Confira o resultado e exporte quando desejar.", 100)
        elif isinstance(result, CadenceVideoAsset):
            self.last_export_path = result.path
            self.export_folder_button.setToolTip(str(result.path))
            self._progress(f"Vídeo salvo e verificado: {result.path}", 100)
            self._set_busy(False)
            if result.warnings:
                QMessageBox.warning(
                    self,
                    localize("Vídeo salvo com aviso"),
                    "\n".join(localize(value) for value in result.warnings),
                )
            return
        self._set_busy(False)

    def _job_failed(self, job_id: str, message: str) -> None:
        if job_id != self.job_id:
            return
        self.job_id = None
        self._last_failure = message
        self._after_project_save = None
        if self._hardware_testing:
            self._hardware_testing = False
            self.hardware_status.setPlainText(localize(message))
        self._pending_delivery = None
        self._pending_preview = False
        self._restoring = False
        self._set_busy(False)
        if self._delivered_pending_save is not None:
            self._delivery_save_failed(message)
            return
        self._update_project_title()
        self._progress("Operação interrompida", 0)
        QMessageBox.warning(self, localize("Não foi possível concluir"), localize(message))

    def _job_cancelled(self, job_id: str) -> None:
        if job_id == self.job_id:
            self.job_id = None
            self._after_project_save = None
            if self._hardware_testing:
                self.hardware_status.setPlainText(localize("Operação cancelada"))
            self._hardware_testing = False
            self._pending_delivery = None
            self._pending_preview = False
            self._restoring = False
            self._set_busy(False)
            if self._delivered_pending_save is not None:
                self._delivery_save_failed(localize("Operação cancelada"))
                return
            self._update_project_title()
            self._progress("Operação cancelada", 0)

    def _media_error(self, message: str) -> None:
        self.pause()
        self._media_loading = False
        self._loading_thumbnails = False
        if self._reindex_status is not None:
            self._reindex_status = None
            self._set_busy(False)
            self._progress("Reindexação interrompida.", 0)
            QMessageBox.warning(self, localize("Não foi possível reindexar"), localize(message))
            return
        self._pending_project = None
        self.process_dialog.hide()
        self.panel.setEnabled(False)
        if self.timeline.navigation_active:
            self.timeline.opening.interrupted()
        self._progress("Não foi possível ler o vídeo", 0)
        QMessageBox.warning(self, localize("Vídeo indisponível"), localize(message))

    def closeEvent(self, event: QCloseEvent) -> None:
        updater = getattr(self, "_update_flow", None)
        if updater is not None and updater.busy:
            updater.cancel()
            event.ignore()
            return
        if self.job_id:
            self.statusBar().showMessage(localize(
                "Aguarde a operação terminar ou cancele pelo progresso."
            ))
            event.ignore()
            return
        if self.source is not None and self._dirty:
            buttons = QMessageBox.StandardButton
            choice = QMessageBox.question(
                self, "AIDA FPS Studio", localize("Salvar alterações antes de fechar?"),
                buttons.Save | buttons.Discard | buttons.Cancel, buttons.Cancel,
            )
            if choice == buttons.Save:
                event.ignore()
                if not self._save_project(after_save=self.close):
                    self._pending_update_installer = None
                return
            if choice != buttons.Discard:
                self._pending_update_installer = None
                event.ignore()
                return
        self._write_recovery()
        self._store_preferences()
        installer = getattr(self, "_pending_update_installer", None)
        if installer is not None:
            import os

            from dg_fps.updates import launch_installer

            try:
                launch_installer(installer, os.getpid())
            except OSError:
                self._pending_update_installer = None
                QMessageBox.warning(self, localize("Atualização não concluída"), localize(
                    "Não foi possível abrir o instalador. "
                    "Tente novamente ou baixe a atualização na página do AIDA."
                ))
                event.ignore()
                return
            self._pending_update_installer = None
        self.process_dialog.hide()
        self.pause()
        # Both managers share the serial GPU pool: cancel media before waiting
        # on that pool, otherwise a background index can outlive the close.
        self.media.shutdown()
        self.jobs.shutdown(wait=True)
        event.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not getattr(self, "_initial_centered", False):
            self._initial_centered = True
            from dg_fps.ui.splash import _center

            QTimer.singleShot(0, lambda: _center(self, self.screen()))
