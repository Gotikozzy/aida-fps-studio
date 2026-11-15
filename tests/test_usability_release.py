from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton
from test_studio_workflows import open_window

from dg_fps.ui.i18n import localize
from dg_fps.ui.main_window import FPSWindow


def test_cancel_import_preserves_home_and_help_is_available(qtbot, tmp_path, monkeypatch):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    window._choose_source()
    assert window.source is None
    assert window.workspaces.currentIndex() == window.home_index
    window._show_quick_help()
    from dg_fps.ui.quick_help import QuickHelp

    help_window = window.findChild(QuickHelp)
    assert help_window.isVisible()
    qtbot.keyClick(help_window, Qt.Key.Key_Escape)
    assert window.isVisible()
    window.close()


def test_export_validation_and_folder_cancel_preserve_editing(
    qtbot, sample_video, tmp_path, monkeypatch
):
    window = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: not window._media_loading)
    window._range_from_mouse(0, 9)
    before = window.panel.ranges
    window.workspaces.setCurrentIndex(window.home_index)
    window.workspaces.setCurrentIndex(1)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    destination = window.delivery_directory.text()
    window._choose_delivery_folder()
    assert window.delivery_directory.text() == destination
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    for invalid in ("", "CON", "bad/name", "bad:name"):
        window.delivery_name.setText(invalid)
        window._export_delivery()
        assert window.job_id is None and window.panel.ranges == before
    assert len(warnings) == 4
    window.delivery_name.setText("valid-delivery")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window._export_delivery()
    assert window.job_id is None and window.workspaces.isEnabled()
    assert window.panel.ranges == before
    for language in ("en", "pt"):
        window.language_box.setCurrentIndex(window.language_box.findData(language))
        assert window.panel.ranges == before
        assert any(button.text() == localize("Atualizar prévia")
                   for button in window.findChildren(QPushButton))
    window._dirty = False
    window.close()


def test_broken_project_returns_control_to_studio(qtbot, sample_video, tmp_path, monkeypatch):
    window = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: not window._media_loading)
    project = tmp_path / "broken.aida"
    project.write_bytes(b"not a project")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a[2]))
    window._open_project(project)
    qtbot.waitUntil(lambda: bool(warnings) and window.job_id is None)
    assert window.workspaces.isEnabled() and not window.process_dialog.isVisible()
    assert window.source == sample_video
    window.close()
