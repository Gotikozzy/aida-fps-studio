"""Project and workspace orchestration; measurement remains in the existing service."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QListWidgetItem,
    QMenu,
    QMessageBox,
)

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.media.timestamp_index import IndexCacheCleanup
from dg_fps.presentation.content_targets import content_references, resolve_references
from dg_fps.presentation.fps_display import capture_nominal_text, fps_display
from dg_fps.presentation.frame_timeline import export_references
from dg_fps.projects import (
    ProjectData,
    read_project,
    restore_reports,
    result_from_document,
    save_project,
)
from dg_fps.service import AnalysisSession
from dg_fps.studio_services import (
    export_delivery,
    prepare_analysis,
    render_preview,
)
from dg_fps.ui.about import AboutDialog
from dg_fps.ui.i18n import localize, system_language
from dg_fps.ui.workspace_layout import WorkspaceLayout
from dg_fps.updates import AIDA_URL, HELP_URL


class StudioActions:
    def _init_studio(self) -> None:
        self.project_path = None
        self._dirty = False
        self._revision = 0
        self._restoring = False
        self._last_ranges = ()
        self._undo = []
        self._redo = []
        self._pending_project = None
        self._pending_delivery = None
        self._pending_preview = False
        self._after_project_save: Callable[[], object] | None = None
        self._delivered_pending_save = None
        self._last_failure = ""
        self._media_loading = False
        self._opening_preview_ready = False
        self._navigation_cursor_seconds = None
        self._loading_thumbnails = False
        self._hardware_testing = False
        self._reindex_status: str | None = None
        self._curve = ()
        recent = self._settings.get("recent_projects", [])
        self.recent_projects = (
            [p for p in recent if isinstance(p, str)][:12] if isinstance(recent, list) else []
        )
        self.recovery_path = self.data_directory / "recovery.json"
        self.output_directory = Path(
            self._settings.get("output_directory", str(self.output_directory))
        )
        self.workspace_layout = WorkspaceLayout(
            self.main_splitter, self.vertical_splitter, self._settings
        )
        self.timeline.range_created.connect(self._range_from_mouse)
        self.timeline.range_edited.connect(self._edit_range)
        self.timeline.range_selected.connect(self.panel._range_list.setCurrentRow)
        self.timeline.canvas.mark_start_requested.connect(self._start_range_at)
        self.timeline.canvas.mark_end_requested.connect(self._finish_range_at)
        self.timeline.canvas.delete_requested.connect(self._delete_range)
        for widget in (self.timeline.canvas, self.panel._range_list):
            widget.installEventFilter(self)
        self.panel._range_list.currentRowChanged.connect(self._selected_range)
        self.panel._range_list.itemDoubleClicked.connect(self._rename_range)
        self.preferences.finished.connect(lambda _: self._store_preferences())
        for control, key in (
            (self.analysis_mode, "analysis_mode"),
            (self.encoding_mode, "encoding_mode"),
        ):
            value = self._settings.get(key, "auto")
            control.setCurrentIndex(max(0, control.findData(value)))
        self.index_mode.setCurrentIndex(
            self.index_mode.findData(self._settings.get("hardware_indexing", True))
        )
        self._menu_actions = []
        self.delivery_name.textChanged.connect(self._delivery_edited)
        self.delivery_directory.textChanged.connect(self._delivery_edited)
        self.delivery_kind.currentIndexChanged.connect(self._delivery_edited)

        def menu(title):
            return self.menuBar().addMenu(localize(title))

        def action(parent, text, callback, shortcut=None):
            item = QAction(localize(text), self)
            if shortcut:
                item.setShortcut(QKeySequence(shortcut))
            item.triggered.connect(callback)
            parent.addAction(item)
            self._menu_actions.append(item)
            return item

        file = menu("Arquivo")
        action(file, "Nova análise…", self._choose_source, "Ctrl+N")
        action(file, "Abrir projeto…", self._choose_project, "Ctrl+Shift+O")
        action(file, "Importar vídeo…", self._choose_source)
        action(file, "Salvar projeto", self._save_project, "Ctrl+S")
        action(file, "Salvar projeto como…", lambda: self._save_project(True), "Ctrl+Shift+S")
        action(file, "Mostrar projeto na pasta", self._show_project_folder)
        self.recent_menu = file.addMenu(localize("Projetos recentes"))
        cache_menu = file.addMenu(localize("Cache de índices"))
        self.reindex_action = action(cache_menu, "Reindexar vídeo atual…", self._reindex_video)
        self.reindex_action.setEnabled(False)
        action(cache_menu, "Limpar cache de todos os vídeos…", self._clear_index_cache)
        file.addSeparator()
        action(file, "Sair", self.close, "Ctrl+Q")
        edit = menu("Editar")
        action(edit, "Desfazer", self._undo_range, "Ctrl+Z")
        action(edit, "Refazer", self._redo_range, "Ctrl+Shift+Z")
        action(edit, "Renomear trecho…", self._rename_range, "F2")
        action(edit, "Apagar trecho", self._delete_range)
        action(edit, "Preferências", self._show_preferences)
        analysis = menu("Análise")
        action(analysis, "Analisar trechos", self.panel.request_analysis)
        action(analysis, "Metas por trecho…", self._segment_targets)
        view = menu("Exibir")
        action(view, "Início", lambda: self.workspaces.setCurrentIndex(self.home_index))
        action(view, "Análise", lambda: self.workspaces.setCurrentIndex(0))
        action(view, "Exportação", lambda: self.workspaces.setCurrentIndex(1))
        action(view, "Restaurar painéis", self.workspace_layout.reset)
        self.retry_thumbnails_action = action(
            view, "Gerar miniaturas novamente", self._retry_thumbnails
        )
        self.retry_thumbnails_action.setEnabled(False)
        optimize = view.addMenu(localize("Otimizar prévia"))
        self._menu_actions.append(optimize.menuAction())
        self.preview_actions = (
            action(optimize, "Região atual (CPU)", lambda: self._optimize_monitor("cpu")),
            action(
                optimize,
                "Região atual (NVIDIA se disponível)",
                lambda: self._optimize_monitor("nvidia"),
            ),
            action(optimize, "Cancelar otimização", self.media.cancel_preview_optimization),
        )
        self._set_preview_actions(False)
        legacy = self._settings.get("legacy_results")
        if legacy and Path(legacy).is_dir():
            action(
                file,
                "Resultados de versões anteriores",
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(legacy)),
            )
        help_menu = menu("Ajuda")
        action(help_menu, "Guia rápido", self._show_quick_help)
        action(help_menu, "Central de ajuda online", self._open_online_help, "F1")
        action(help_menu, "Diagnóstico de compatibilidade", self._show_preferences)
        action(
            help_menu,
            "Ajuda e downloads do AIDA",
            lambda: QDesktopServices.openUrl(QUrl(AIDA_URL)),
        )
        action(help_menu, "Copiar informações de diagnóstico", self._copy_diagnostics)
        action(help_menu, "Termos e licenças", self._show_licenses)
        help_menu.addSeparator()
        action(help_menu, "Sobre AIDA FPS Studio", self._show_about)
        self._update_recents()
        self.workspaces.setCurrentIndex(self.home_index)
        self.workspaces.setTabEnabled(0, False)
        self.workspaces.setTabEnabled(1, False)
        self.workspaces.currentChanged.connect(self._workspace_changed)
        self.recovery_button.setVisible(self.recovery_path.is_file())

    def _show_about(self) -> None:
        AboutDialog(self).open()

    def _show_project_folder(self) -> None:
        if self.project_path and self.project_path.is_file():
            self._reveal_delivery(self.project_path)

    def _copy_diagnostics(self) -> None:
        import platform

        from dg_fps import __version__

        document = {
            "application": "AIDA FPS Studio",
            "version": __version__,
            "system": platform.platform(),
            "architecture": platform.machine(),
            "analysis_mode": self.analysis_mode.currentData(),
            "encoding_mode": self.encoding_mode.currentData(),
            "compatibility": self.hardware_status.toPlainText(),
            "last_error": self._last_failure,
        }
        QApplication.clipboard().setText(json.dumps(document, ensure_ascii=False, indent=2))
        self.statusBar().showMessage(localize("Diagnóstico copiado."), 8000)

    def _delivery_edited(self, *_args) -> None:
        if self.source is not None and not self._media_loading:
            self._mark_dirty()

    def _start_update_check(self) -> None:
        from dg_fps.ui.update_flow import UpdateFlow

        if getattr(self, "_update_flow", None) is None:
            self._update_flow = UpdateFlow(self)
        self._startup_update = self._update_flow.checker
        self._update_flow.start()

    def _offer_update(self, release) -> None:
        from dg_fps.ui.update_flow import UpdateFlow

        if getattr(self, "_update_flow", None) is None:
            self._update_flow = UpdateFlow(self)
        self._update_flow.offer(release, manual=True)

    def _show_quick_help(self) -> None:
        from dg_fps.ui.quick_help import QuickHelp

        QuickHelp(self).open()

    def _open_online_help(self) -> None:
        language = (
            system_language() if self.language_preference == "system" else self.language_preference
        )
        QDesktopServices.openUrl(QUrl(f"{HELP_URL}?lang={language}"))

    def _show_licenses(self) -> None:
        from dg_fps.ui.licenses import LicensesDialog

        LicensesDialog(self).open()

    def _workspace_changed(self, index: int) -> None:
        if index == self.home_index:
            self.pause()
        self._focus_changed(None, self.focusWidget())

    def _reindex_video(self) -> None:
        if self.job_id or self._media_loading or self.source is None or self.metadata is None:
            return
        buttons = QMessageBox.StandardButton
        if (
            QMessageBox.question(
                self,
                localize("Reindexar vídeo atual"),
                localize(
                    "Apagar o índice salvo deste vídeo e reindexar agora? "
                    "Se os tempos mudarem, será necessário analisar novamente."
                ),
                buttons.Yes | buttons.No,
                buttons.No,
            )
            != buttons.Yes
        ):
            return
        self.pause()
        self._reindex_status = "Reindexação concluída."
        self._media_loading = True
        self._set_busy(True)
        self._progress("Reindexando vídeo…", 0)
        self.media.reindex(self.metadata)

    def _clear_index_cache(self) -> None:
        if self.job_id or self._media_loading:
            return
        buttons = QMessageBox.StandardButton
        if (
            QMessageBox.question(
                self,
                localize("Limpar cache de índices"),
                localize(
                    "Apagar os índices de todos os vídeos? "
                    "Os índices serão recriados conforme você abrir os vídeos."
                ),
                buttons.Yes | buttons.No,
                buttons.No,
            )
            != buttons.Yes
        ):
            return

        def clear(token, report):
            token.raise_if_cancelled()
            report(0, "Limpando cache de índices…")
            result = self.media.clear_all_cached_indexes()
            token.mark_committed()
            return result

        self.pause()
        self._set_busy(True)
        self.job_id = self.jobs.submit("Limpando cache de índices…", clear)

    def _store_preferences(self) -> None:
        self._settings.update(
            {
                "language": self.language_preference,
                "recent_projects": self.recent_projects,
                "analysis_mode": self.analysis_mode.currentData(),
                "encoding_mode": self.encoding_mode.currentData(),
                "hardware_indexing": self.index_mode.currentData(),
                "output_directory": str(self.output_directory),
                "panel_sizes": self.main_splitter.sizes(),
                "workspace_layout": self.workspace_layout.snapshot(),
            }
        )
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.preferences_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.preferences_path)

    def _show_preferences(self) -> None:
        if self.job_id or self._media_loading:
            return
        self.preferences.open()

    def _state(self) -> dict:
        return {
            "source": str(self.source),
            "ranges": [asdict(r) for r in self.panel.ranges],
            "target": self.content_target.value(),
            "overrides": dict(self.target_overrides),
            "analysis_mode": self.analysis_mode.currentData(),
            "encoding_mode": self.encoding_mode.currentData(),
            "frame": self.current.timestamp.index if self.current else 0,
            "project_path": str(self.project_path) if self.project_path else None,
            "delivery": {
                "name": self.delivery_name.text(),
                "directory": self.delivery_directory.text(),
                "kind": self.delivery_kind.currentData(),
            },
        }

    def _mark_dirty(self) -> None:
        if self._restoring:
            return
        self._dirty = True
        self._revision += 1
        self._update_project_title()
        self._write_recovery()

    def _write_recovery(self) -> None:
        if not self.source or not self.source.is_file():
            return
        stat = self.source.stat()
        state = {
            **self._state(),
            "source_size": stat.st_size,
            "source_mtime_ns": stat.st_mtime_ns,
            "reports_directory": str(self.session.reports.project_directory)
            if self.session
            else None,
        }
        self.recovery_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.recovery_path.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.recovery_path)
        self.recovery_button.show()

    def _update_project_title(self) -> None:
        name = (
            self.project_path.name
            if self.project_path
            else self.source.stem
            if self.source
            else localize("Nova análise")
        )
        title = name + (" *" if self._dirty else "")
        self.project_title.setText(title)
        self.save_state.setText(
            localize(
                "Alterações não salvas"
                if self._dirty
                else "Projeto salvo"
                if self.project_path
                else ""
            )
        )
        self.setWindowTitle(f"AIDA FPS Studio — {title}")

    def _update_recents(self) -> None:
        self.recent_menu.clear()
        self.recent_list.clear()
        self.recent_empty.setVisible(not self.recent_projects)
        for name in self.recent_projects:
            path = Path(name)
            item = QListWidgetItem(path.stem + "\n" + str(path.parent))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.recent_list.addItem(item)
            action = self.recent_menu.addAction(path.name)
            action.triggered.connect(lambda checked=False, p=path: self._open_project(p))
        if not self.recent_projects:
            self.recent_menu.addAction(localize("Nenhum projeto recente")).setEnabled(False)

    def _remember_project(self, path: Path) -> None:
        self.recent_projects = [str(path), *[p for p in self.recent_projects if p != str(path)]][
            :12
        ]
        self._update_recents()
        self._store_preferences()

    def _choose_project(self) -> None:
        if self.job_id or (self._media_loading and not self._opening_preview_ready):
            return
        path, _ = QFileDialog.getOpenFileName(self, localize("Abrir projeto"), "", "AIDA (*.aida)")
        if path:
            self._open_project(Path(path))

    def _open_project(self, path: Path) -> None:
        def load():
            self.pause()
            self._set_busy(True)
            self.job_id = self.jobs.submit(
                "Abrir análise", lambda token, report: read_project(path)
            )

        self._replace_project(load)

    def _replace_project(self, action: Callable[[], None]) -> None:
        if self.job_id or (self._media_loading and not self._opening_preview_ready):
            return
        def replace_action() -> None:
            if self._media_loading or self.timeline.navigation_active:
                self.media.cancel_loading()
                self._pending_project = None
                self._media_loading = False
            action()

        if self.source is None or not self._dirty:
            replace_action()
            return
        buttons = QMessageBox.StandardButton
        choice = QMessageBox.question(
            self,
            "AIDA FPS Studio",
            localize("Salvar alterações antes de trocar de projeto?"),
            buttons.Save | buttons.Discard | buttons.Cancel,
            buttons.Cancel,
        )
        if choice == buttons.Save:
            self._save_project(after_save=replace_action)
        elif choice == buttons.Discard:
            replace_action()

    def _accept_project(self, project: ProjectData) -> None:
        try:
            source, valid = project.source()
        except FileNotFoundError:
            name, _ = QFileDialog.getOpenFileName(
                self,
                localize("Localizar vídeo original"),
                "",
                localize("Vídeos (*.mp4 *.mkv *.mov *.avi *.webm *.m4v);;Todos (*)"),
            )
            if not name:
                return
            source, valid = project.source(Path(name))
        self._pending_project = (project, valid)
        self._load_source(source)
        self.project_path = project.path if project.path.suffix.lower() == ".aida" else None
        self._update_project_title()
        self._remember_project(project.path) if project.path.suffix.lower() == ".aida" else None

    def _restore_indexed_project(self) -> None:
        if not self._pending_project:
            return
        project, valid = self._pending_project
        self._pending_project = None
        index = self.media.timestamp_index
        ranges = tuple(AnalysisFrameRange(**v) for v in project.state.get("ranges", []))
        if any(r.end_frame >= len(index) for r in ranges):
            QMessageBox.warning(
                self,
                "AIDA FPS Studio",
                localize("O vídeo foi alterado. Selecione os trechos novamente."),
            )
            return
        self._restoring = True
        self.panel.set_ranges(ranges, index)
        self.target_overrides = project.state.get("overrides", {})
        self.content_target.set_value(project.state.get("target"))
        delivery = project.state.get("delivery", {})
        if isinstance(delivery, dict):
            name = delivery.get("name")
            directory = delivery.get("directory")
            if isinstance(name, str):
                self.delivery_name.setText(name)
            if isinstance(directory, str) and directory:
                self.delivery_directory.setText(directory)
            self.delivery_kind.setCurrentIndex(
                max(0, self.delivery_kind.findData(delivery.get("kind", "both")))
            )
        for control, key in (
            (self.analysis_mode, "analysis_mode"),
            (self.encoding_mode, "encoding_mode"),
        ):
            control.setCurrentIndex(max(0, control.findData(project.state.get(key, "auto"))))
        self._restoring = False
        self._dirty = False
        self._update_project_title()
        self.seek(min(len(index) - 1, project.state.get("frame", 0)))
        if valid and "analysis.json" in project.reports and "report.json" in project.reports:
            source = self.source
            directory = self.output_directory / f"restored_{uuid4().hex}"
            self._restoring = True
            self._set_busy(True)

            def restore(token, report):
                if not project.source(source)[1]:
                    raise ValueError(
                        "O vídeo foi alterado. Abra e analise novamente antes de exportar."
                    )
                report(15, "Restaurando resultados")
                result = result_from_document(json.loads(project.reports["analysis.json"]), source)
                if tuple(result.frame_ranges) != ranges:
                    raise ValueError("Os resultados não correspondem aos trechos do projeto")
                paths = restore_reports(project, directory)
                stat = source.stat()
                session = AnalysisSession(
                    result, paths, index, stat.st_size, stat.st_mtime_ns, content_references(result)
                )
                prepared = prepare_analysis(session, token)
                if not project.source(source)[1]:
                    raise ValueError("O vídeo mudou durante a restauração")
                return prepared

            self.job_id = self.jobs.submit("Restaurar análise", restore)
        elif not valid:
            self.analysis_state.setText(localize("Vídeo alterado • analisar novamente"))

    def _offer_save_analysis(self) -> bool:
        buttons = QMessageBox.StandardButton
        if self.project_path is not None and self.project_path.is_file():
            choice = QMessageBox.question(
                self,
                "AIDA FPS Studio",
                localize("Atualizar o projeto com esta análise?"),
                buttons.Yes | buttons.No,
                buttons.No,
            )
            if choice != buttons.Yes:
                return False
        return self._save_project(after_save=self._continue_delivery)

    def _save_project(
        self, save_as: bool = False, *, after_save: Callable[[], object] | None = None
    ) -> bool:
        if self.job_id or self._media_loading or not self.source:
            return False
        path = self.project_path
        if save_as or path is None:
            name, _ = QFileDialog.getSaveFileName(
                self,
                localize("Salvar projeto"),
                str(self.source.with_suffix(".aida")),
                "AIDA (*.aida)",
            )
            if not name:
                return False
            path = Path(name)
            if path.suffix.lower() != ".aida":
                path = path.with_suffix(".aida")
                if (
                    path.exists()
                    and QMessageBox.question(
                        self, "AIDA FPS Studio", localize("Substituir arquivos existentes?")
                    )
                    != QMessageBox.StandardButton.Yes
                ):
                    return False
        state = self._state()
        reports = self.session.reports if self.session else None
        if self.session:
            try:
                stat = self.source.stat()
            except OSError as exc:
                QMessageBox.warning(self, "AIDA FPS Studio", str(exc))
                return False
            if (stat.st_size, stat.st_mtime_ns) != (
                self.session.source_size,
                self.session.source_mtime_ns,
            ):
                QMessageBox.warning(
                    self,
                    "AIDA FPS Studio",
                    localize("O vídeo foi alterado. Abra e analise novamente antes de exportar."),
                )
                return False
        self.pause()
        self._after_project_save = after_save
        self._set_busy(True)
        self._progress("Salvando projeto…", 0)
        self.process_dialog.heading.setText(localize("Salvar projeto"))
        self.save_state.setText(localize("Salvando projeto…"))
        self.process_dialog.bar.setRange(0, 0)
        self.job_id = self.jobs.submit(
            "Salvar projeto", lambda token, report: save_project(path, state, reports, token)
        )
        return True

    def _recover(self) -> None:
        if self.job_id or self._media_loading:
            return
        try:
            state = json.loads(self.recovery_path.read_text("utf-8"))
            reports = {}
            directory = state.get("reports_directory")
            if directory:
                from dg_fps.projects import REPORT_NAMES

                reports = {
                    name: (Path(directory) / name).read_bytes()
                    for name in REPORT_NAMES
                    if (Path(directory) / name).is_file()
                }
            project = ProjectData(self.recovery_path, state, reports)

            def restore():
                self._accept_project(project)
                if self._pending_project is not None and state.get("project_path"):
                    self.project_path = Path(state["project_path"])
                    self._update_project_title()

            self._replace_project(restore)
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "AIDA FPS Studio", str(exc))

    def _range_from_mouse(self, start: int, end: int) -> None:
        index = self.media.timestamp_index
        if index is None or self.job_id:
            return
        self.panel.mark_in(start, index[start].seconds)
        self.panel.mark_out(end, index[end].seconds)
        before = len(self.panel.ranges)
        self.panel._add_range()
        if len(self.panel.ranges) == before:
            self.statusBar().showMessage(self.panel._status.text(), 8000)
        else:
            self.panel._in_point = self.panel._out_point = None
            self.timeline.canvas.pending_start = None
            self.timeline.canvas.update()

    def _start_range_at(self, frame: int) -> None:
        index = self.media.timestamp_index
        if index is None or self.job_id or not 0 <= frame < len(index):
            return
        self.panel.mark_in(frame, index[frame].seconds)
        self.panel._out_point = None
        self.timeline.canvas.pending_start = frame
        self.timeline.canvas.update()
        self.statusBar().showMessage(localize("Início marcado. Use O ou o botão direito no fim."))

    def _finish_range_at(self, frame: int) -> None:
        index = self.media.timestamp_index
        if index is None or self.job_id or not 0 <= frame < len(index):
            return
        if self.panel._in_point is None:
            self.statusBar().showMessage(localize("Marque o início do trecho primeiro."), 8000)
            return
        self._range_from_mouse(self.panel._in_point[0], frame)

    def _delete_range(self) -> None:
        if not self.job_id and not self._media_loading:
            self.panel._remove_selected()
            self._selected_range(self.panel._range_list.currentRow())

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and not event.modifiers():
            if (
                watched in (self.timeline.canvas, self.panel._range_list)
                and event.key() == Qt.Key.Key_Delete
            ):
                self._delete_range()
                return True
            if watched is self.timeline.canvas:
                if event.key() == Qt.Key.Key_I:
                    self.mark_in()
                    return True
                if event.key() == Qt.Key.Key_O:
                    self.mark_out()
                    return True
        return super().eventFilter(watched, event)

    def _range_menu(self, button) -> None:
        menu = QMenu(self)
        menu.addAction(localize("Renomear trecho…"), self._rename_range)
        menu.addAction(localize("Limpar trechos"), self.panel.clear_ranges)
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _edit_range(self, row: int, start: int, end: int) -> None:
        if not self.panel.edit_range(row, start, end, self.media.timestamp_index):
            self.statusBar().showMessage(self.panel._status.text(), 8000)

    def _rename_range(self, *_) -> None:
        row = self.panel._range_list.currentRow()
        if row < 0 or self.job_id:
            return
        ranges = list(self.panel.ranges)
        old = ranges[row]
        name, ok = QInputDialog.getText(
            self, localize("Renomear trecho"), localize("Nome"), text=old.label
        )
        name = name.strip()
        if ok and name and all(i == row or r.label != name for i, r in enumerate(ranges)):
            ranges[row] = AnalysisFrameRange(old.start_frame, old.end_frame, name)
            self.panel.set_ranges(tuple(ranges), self.media.timestamp_index)

    def _range_history(self, ranges) -> None:
        if not self._restoring and ranges != self._last_ranges:
            self._undo.append(self._last_ranges)
            self._undo = self._undo[-50:]
            self._redo.clear()
        self._last_ranges = ranges
        self._mark_dirty()

    def _undo_range(self) -> None:
        if self.job_id or not self._undo:
            return
        self._redo.append(self.panel.ranges)
        ranges = self._undo.pop()
        self._restoring = True
        self.panel.set_ranges(ranges, self.media.timestamp_index)
        self._restoring = False
        self._mark_dirty()

    def _redo_range(self) -> None:
        if self.job_id or not self._redo:
            return
        self._undo.append(self.panel.ranges)
        ranges = self._redo.pop()
        self._restoring = True
        self.panel.set_ranges(ranges, self.media.timestamp_index)
        self._restoring = False
        self._mark_dirty()

    def _selected_range(self, row: int) -> None:
        self.timeline.canvas.selected = row
        self.timeline.canvas.update()
        if 0 <= row < len(self.panel.ranges):
            from dg_fps.ui.timeline.timeline_widget import format_timecode

            value = self.panel.ranges[row]
            self.selected_range_name.setText(localize(value.label))
            index = self.media.timestamp_index
            if index is not None:
                self.selected_range_time.setText(
                    f"{format_timecode(index[value.start_frame].seconds)} — "
                    f"{format_timecode(index[value.end_frame].seconds)}"
                )
        else:
            self.selected_range_name.setText("—")
            self.selected_range_time.setText("—")
        self._refresh_results()

    def _refresh_results(self) -> None:
        if not self.session:
            capture = self.metadata.video_streams[0].average_rate if self.metadata else None
            self.result_capture.setText(
                f"{localize('Captura')}: {capture_nominal_text(capture)} FPS"
                if capture
                else localize("Captura: —")
            )
            self.result_target.setText(localize("Meta: —"))
            self.fps_value.setText("—")
            self.analysis_state.setText(localize("Aguardando análise"))
            if not self.panel.ranges:
                self.analysis_state.setText(
                    localize(
                        "Arraste na linha do tempo para marcar o trecho que quer analisar."
                        if self.source
                        else "Abra um vídeo para começar a análise."
                    )
                )
            else:
                self.analysis_state.setText(
                    localize("Trechos prontos. Clique em Analisar trechos.")
                )
            self.result_plot.points = ()
            self.result_plot.update()
            return
        result = self.session.analysis
        row = self.panel._range_list.currentRow()
        label = self.panel.ranges[row].label if 0 <= row < len(self.panel.ranges) else None
        summary = result.segment_summaries.get(label, result.summary)
        capture = result.summary.container_fps
        self.fps_value.setText(fps_display(summary.content_fps, capture).text)
        self.result_capture.setText(f"{localize('Captura')}: {capture_nominal_text(capture)} FPS")
        refs = resolve_references(
            self.session.automatic_references or content_references(result),
            self.content_target.value(),
            self.target_overrides,
        )
        refs = export_references(result, refs)
        reference = refs.get(label or next(iter(refs), ""))
        self.result_target.setText(
            f"{localize('Meta')}: {reference.target_fps:g} FPS"
            if reference and reference.target_fps
            else localize("Meta: —")
        )
        unavailable = result.unavailable_frame_count
        if unavailable:
            self.analysis_state.setText(
                localize(f"Leitura parcial · {unavailable} quadros ilegíveis")
            )
        else:
            self.analysis_state.setText(
                localize("Análise concluída. Revise o FPS, salve o projeto ou exporte.")
            )
        self.result_plot.points = tuple(
            p for p in self._curve if label is None or p.segment == label
        )
        self.result_plot.update()

    def _choose_delivery_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, localize("Destino"), self.delivery_directory.text()
        )
        if path:
            self.delivery_directory.setText(path)

    def _export_delivery(self) -> None:
        if self.job_id or self._media_loading or not self.panel.ranges:
            return
        if not self._targets_compatible(notify=True):
            return
        name = self.delivery_name.text().strip()
        if (
            not name
            or Path(name).name != name
            or Path(name).is_reserved()
            or name.endswith(".")
            or any(c in name for c in '<>:"/\\|?*')
        ):
            QMessageBox.warning(
                self, "AIDA FPS Studio", localize("Escolha um nome de arquivo válido.")
            )
            return
        target = Path(self.delivery_directory.text()) / name
        kind = self.delivery_kind.currentData()
        suffixes = (
            (".mp4", ".json") if kind == "both" else (".mp4",) if kind == "video" else (".json",)
        )
        if target.suffix.lower() in {".mp4", ".json"}:
            target = target.with_suffix("")
        if (
            any(target.with_name(target.name + s).exists() for s in suffixes)
            and QMessageBox.question(
                self, "AIDA FPS Studio", localize("Substituir arquivos existentes?")
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        mode = self.encoding_mode.currentData()
        language = (
            system_language() if self.language_preference == "system" else self.language_preference
        )
        if self.project_path is None:
            self._save_project(
                after_save=lambda: self._start_delivery(target, kind, mode, language)
            )
            return
        self._start_delivery(target, kind, mode, language)

    def _start_delivery(self, target, kind, mode, language) -> None:
        """Continue the validated export without repeating overwrite prompts."""
        if self.session is None:
            self._pending_delivery = (target, kind, mode, language)
            self._analyze(self.panel.ranges)
            if not self.job_id:
                self._pending_delivery = None
            return
        self._submit_delivery(target, kind, mode, language)

    def _submit_delivery(self, target, kind, mode, language) -> None:
        refs = resolve_references(
            self.session.automatic_references or content_references(self.session.analysis),
            self.content_target.value(),
            dict(self.target_overrides),
        )
        session = self.session
        self.pause()
        self._set_busy(True)
        self.job_id = self.jobs.submit(
            "Exportar entrega",
            lambda token, report: export_delivery(
                self.service, session, target, kind, mode, language, refs, token, report
            ),
        )

    def _continue_delivery(self) -> bool:
        pending = self._pending_delivery
        self._pending_delivery = None
        if pending is None or self.session is None:
            if self._pending_preview and self.session is not None:
                self._pending_preview = False
                self._preview_export()
                return True
            return False
        self._submit_delivery(*pending)
        return True

    def _preview_export(self) -> None:
        if self.job_id or self._media_loading:
            return
        if not self._targets_compatible(notify=True):
            return
        if self.session is None:
            if not self.panel.ranges:
                self.statusBar().showMessage(localize("Selecione um trecho na timeline"), 8000)
                return
            self._pending_preview = True
            self._analyze(self.panel.ranges)
            if not self.job_id:
                self._pending_preview = False
            return
        session = self.session
        frame = self.current.timestamp.index if self.current else 0
        refs = resolve_references(
            session.automatic_references or content_references(session.analysis),
            self.content_target.value(),
            dict(self.target_overrides),
        )
        language = (
            system_language() if self.language_preference == "system" else self.language_preference
        )
        self.pause()
        self._set_busy(True)
        self.job_id = self.jobs.submit(
            "Preparando prévia",
            lambda token, report: render_preview(session, refs, language, frame, token),
        )

    def _cancel_operation(self) -> None:
        if self.job_id:
            self._cancel()
        elif self._media_loading:
            self.media.cancel_loading()
            self._media_loading = False
            self._pending_project = None
            self._reindex_status = None
            self._set_busy(False)
            self._progress("Operação cancelada", 0)
            if self.timeline.navigation_active:
                self.timeline.opening.interrupted()
                self.panel.setEnabled(False)
                self.export_button.setEnabled(False)
                self.reindex_action.setEnabled(False)
            self._request_visible_thumbnails()

    def _studio_completion(self, result) -> bool:
        if isinstance(result, IndexCacheCleanup):
            self._set_busy(False)
            self._progress(
                f"Índices removidos: {result.removed}", 100 if not result.failures else 0
            )
            if result.failures:
                QMessageBox.warning(
                    self,
                    localize("Alguns índices não puderam ser removidos"),
                    "\n".join(result.failures),
                )
            return True
        if isinstance(result, ProjectData):
            self._set_busy(False)
            self._accept_project(result)
            return True
        if isinstance(result, Path):
            after_save, self._after_project_save = self._after_project_save, None
            self.project_path = result
            self._dirty = False
            self._remember_project(result)
            self._update_project_title()
            self._write_recovery()
            self._set_busy(False)
            self._progress("Análise salva", 100)
            delivered, self._delivered_pending_save = self._delivered_pending_save, None
            if after_save is not None:
                after_save()
            elif delivered is not None:
                self._finish_delivery(delivered)
            return True
        from dg_fps.studio_services import Delivery

        if isinstance(result, Delivery):
            self._delivered_pending_save = result
            self.last_export_path = result.paths[0]
            self.export_folder_button.setToolTip(str(result.paths[0]))
            self._set_busy(False)
            self._mark_dirty()
            if not self._save_project(after_save=lambda: self._finish_delivery(result)):
                self._delivery_save_failed("")
            return True
        if isinstance(result, QImage):
            self.export_preview.set_image(result)
            self._set_busy(False)
            self._progress("Prévia atualizada", 100)
            return True
        return False

    def _delivery_save_failed(self, message: str) -> None:
        delivery, self._delivered_pending_save = self._delivered_pending_save, None
        self._update_project_title()
        self._finish_delivery(delivery)
        self._progress("Entrega salva; projeto com alterações não salvas.", 100)
        choice = QMessageBox.question(
            self,
            localize("Entrega salva"),
            localize(
                "Os arquivos foram exportados, mas o projeto não pôde ser salvo. "
                "Tentar salvar o projeto novamente?"
            )
            + ("\n\n" + message if message else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice == QMessageBox.StandardButton.Yes:
            self._save_project()

    def _finish_delivery(self, delivery) -> None:
        self.last_export_path = delivery.paths[0]
        self.export_folder_button.setToolTip(str(delivery.paths[0]))
        self._progress("Entrega salva e verificada", 100)
        self._reveal_delivery(delivery.paths[0])
        if delivery.warnings:
            QMessageBox.warning(self, "AIDA FPS Studio", "\n".join(delivery.warnings))

    def _reveal_delivery(self, path: Path) -> None:
        import ctypes
        from ctypes import wintypes

        shell = ctypes.WinDLL("shell32", use_last_error=True)
        shell.ILCreateFromPathW.argtypes = [wintypes.LPCWSTR]
        shell.ILCreateFromPathW.restype = ctypes.c_void_p
        shell.SHOpenFolderAndSelectItems.argtypes = [
            ctypes.c_void_p,
            wintypes.UINT,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        shell.SHOpenFolderAndSelectItems.restype = ctypes.c_long
        shell.ILFree.argtypes = [ctypes.c_void_p]
        shell.ILFree.restype = None
        ole = ctypes.WinDLL("ole32")
        ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        ole.CoInitializeEx.restype = ctypes.c_long
        ole.CoUninitialize.argtypes = []
        ole.CoUninitialize.restype = None
        initialized = ole.CoInitializeEx(None, 2)
        item = None
        try:
            item = shell.ILCreateFromPathW(str(path.resolve()))
            if not item or shell.SHOpenFolderAndSelectItems(item, 0, None, 0) < 0:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
        finally:
            if item:
                shell.ILFree(item)
            if initialized >= 0:
                ole.CoUninitialize()

    def dragEnterEvent(self, event) -> None:
        if (event.mimeData().hasUrls() and not self.job_id
                and (not self._media_loading or self._opening_preview_ready)):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() == ".aida":
                self._open_project(path)
            else:
                self.open_source(path)
            event.acceptProposedAction()
