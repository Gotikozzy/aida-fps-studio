"""Consented update presentation, independent from analysis jobs and measurements."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from uuid import uuid4

from platformdirs import user_cache_path
from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from dg_fps import __version__
from dg_fps.ui.i18n import localize
from dg_fps.updates import (
    PrepareUpdate,
    UpdateCheck,
    UpdateDownload,
    UpdateRelease,
    version_key,
)


class UpdateFlow(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.checker = UpdateCheck(self)
        self.checker.succeeded.connect(self._checked)
        self.checker.failed.connect(lambda reason: logging.info(
            "startup_update_check_skipped", extra={"reason": reason}
        ))
        self.pending: UpdateRelease | None = None
        self.offered: set[str] = set()
        self.busy = False
        self.cancelled = False
        self.download = None
        self.prepare = None
        self.dialog = None
        self._installer = None
        self._prepare_error = ""
        self._directory = None
        self._release = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._offer)

    def start(self) -> None:
        program = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
        if (program / ".disable-update-check").is_file():
            logging.info("automatic_update_check_disabled")
            return
        self.checker.start()

    def _checked(self, version: str) -> None:
        if version_key(version) <= version_key(__version__):
            return
        release = self.checker.release or UpdateRelease(version)
        self.offer(release)

    def offer(self, release: UpdateRelease, *, manual: bool = False) -> None:
        if self.busy or (not manual and release.version in self.offered):
            return
        self.pending = release
        self.timer.start(0)

    def _offer(self) -> None:
        if self.pending is None:
            return
        if (not self.window.isVisible() or self.window.job_id or self.window._media_loading
                or QApplication.activeModalWidget() is not None):
            self.timer.start(500)
            return
        release, self.pending = self.pending, None
        self.offered.add(release.version)
        choice = QMessageBox.question(
            self.window, localize("Atualização disponível"), localize(
                "A versão {latest} do AIDA FPS Studio está disponível. "
                "Você está usando a versão {current}.\n\n"
                "Deseja baixar a atualização e abrir o instalador? "
                "O Studio será fechado para atualizar."
            ).format(latest=release.version, current=__version__),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        self._start_download(release)

    def _start_download(self, release: UpdateRelease) -> None:
        self.busy, self.cancelled = True, False
        self._installer, self._prepare_error = None, ""
        self.window.pause()
        self.dialog = QProgressDialog(
            localize("Baixando atualização {version}…").format(version=release.version),
            localize("Cancelar"), 0, 0, self.window,
        )
        self.dialog.setWindowTitle(localize("Atualizar AIDA FPS Studio"))
        self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.dialog.setAutoClose(False)
        self.dialog.setAutoReset(False)
        self.dialog.canceled.connect(self.cancel)
        self.dialog.show()
        directory = user_cache_path("AIDA FPS Studio", "DG") / "updates" / uuid4().hex
        self._directory, self._release = directory, release
        self.download = UpdateDownload(release, directory, self)
        self.download.progress.connect(self._progress)
        self.download.failed.connect(self._failed)
        self.download.cancelled.connect(self._cancelled)
        self.download.succeeded.connect(lambda path: self._prepare(path, release))
        self.download.start()

    def _progress(self, current: int, total: int) -> None:
        if total > 0:
            self.dialog.setRange(0, 100)
            self.dialog.setValue(min(99, int(current / total * 100)))

    def _prepare(self, package, release: UpdateRelease) -> None:
        if self.cancelled:
            self._cancelled()
            return
        self.dialog.setLabelText(localize("Verificando e preparando a atualização…"))
        self.dialog.setRange(0, 0)
        self.prepare = PrepareUpdate(package, release, self)
        self.prepare.succeeded.connect(self._set_installer)
        self.prepare.failed.connect(self._set_error)
        self.prepare.finished.connect(self._prepared)
        self.prepare.start()

    def _set_installer(self, path) -> None:
        self._installer = path

    def _set_error(self, reason: str) -> None:
        self._prepare_error = reason

    def _prepared(self) -> None:
        if self.cancelled or self._prepare_error == "cancelled":
            self._cancelled()
        elif self._installer is None:
            self._failed(self._prepare_error or "archive")
        else:
            self.busy = False
            self.dialog.hide()
            self.window._pending_update_installer = self._installer
            self.window.close()  # Existing Save / Discard / Cancel decisions remain authoritative.

    def cancel(self) -> None:
        self.cancelled = True
        if self.prepare is not None and self.prepare.isRunning():
            self.prepare.cancel_event.set()
        elif self.download is not None:
            self.download.cancel()
        else:
            self._cancelled()

    def _cancelled(self) -> None:
        self.busy = False
        if self.dialog is not None:
            self.dialog.hide()
        self._discard_package()

    def _discard_package(self) -> None:
        if self._directory is None or self._release is None:
            return
        name = self._release.filename
        for filename in (name, name + ".part", name.replace(".zip", ".exe.part")):
            try:
                (self._directory / filename).unlink(missing_ok=True)
            except OSError:
                logging.exception("update_cache_cleanup_failed")

    def _failed(self, reason: str) -> None:
        self.busy = False
        if self.dialog is not None:
            self.dialog.hide()
        self._discard_package()
        logging.warning("update_download_failed", extra={"reason": reason})
        QMessageBox.warning(self.window, localize("Atualização não concluída"), localize(
            "Não foi possível baixar ou verificar a atualização. "
            "O Studio continua disponível. Tente novamente mais tarde "
            "ou baixe o instalador na página do AIDA."
        ))
