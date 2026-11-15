from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog
from test_standalone import session_for

from dg_fps.core.enums import JobStatus
from dg_fps.jobs.models import JobRecord
from dg_fps.presentation.cadence_video import CadenceVideoAsset
from dg_fps.ui.main_window import FPSWindow


def test_all_file_dialogs_use_windows_default(qtbot, sample_video, tmp_path, monkeypatch):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    calls = []

    def dialog(*args, **kwargs):
        calls.append(kwargs)
        return "", ""

    def folder(*args, **kwargs):
        calls.append(kwargs)
        return ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", dialog)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", folder)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", dialog)
    window._choose_source()
    window._choose_output()
    _, window.session = session_for(sample_video, tmp_path / "reports")
    window._export()
    assert len(calls) == 3
    for kwargs in calls:
        assert (
            not kwargs.get("options", QFileDialog.Option(0))
            & QFileDialog.Option.DontUseNativeDialog
        )
    window.close()


def test_media_and_completed_record_cannot_finish_export_bar(qtbot, tmp_path):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.job_id = "export"
    window.progress.setValue(91)
    window._media_progress("Indexação concluída", 100)
    window._job_progress(JobRecord("export", "Export", status=JobStatus.COMPLETED, progress=100))
    assert window.progress.value() == 91
    window.job_id = None
    window.close()


def test_missing_destination_cannot_be_presented_as_success(qtbot, tmp_path, monkeypatch):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    messages = []
    monkeypatch.setattr(
        "dg_fps.ui.main_window.QMessageBox.warning", lambda *args: messages.append(args)
    )
    window.job_id = "export"
    window._job_completed(
        "export", CadenceVideoAsset(tmp_path / "missing.mp4", 1920, 1080, "CPU", ())
    )
    assert window.progress.value() == 0 and messages
    assert not window.export_folder_button.isEnabled()
    window.close()


def test_completed_video_exposes_its_actual_folder(qtbot, sample_video, tmp_path, monkeypatch):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    window._show_project_workspace()
    window.workspaces.setCurrentIndex(1)
    service, session = session_for(sample_video, tmp_path / "reports")
    from dg_fps.jobs.cancellation import CancellationToken

    asset = service.export(
        session, tmp_path / "other folder" / "out.mp4", "cpu", CancellationToken(), lambda *_: None
    )
    window.job_id = "export"
    window._job_completed("export", asset)
    assert window.progress.value() == 100 and window.export_folder_button.isEnabled()
    assert str(asset.path) in window.export_folder_button.toolTip()
    opened = []
    monkeypatch.setattr(
        "dg_fps.ui.main_window.QDesktopServices.openUrl", lambda url: opened.append(url)
    )
    window._open_export_folder()
    assert Path(opened[0].toLocalFile()) == asset.path.parent
    window.close()
