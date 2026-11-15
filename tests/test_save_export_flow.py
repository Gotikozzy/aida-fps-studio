from __future__ import annotations

from threading import Event

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox
from test_studio_workflows import open_window

from dg_fps.projects import read_project


def test_direct_export_requires_save_and_autosaves_analysis(
    qtbot, sample_video, tmp_path, monkeypatch
):
    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12)
    w._range_from_mouse(0, 9)
    w.delivery_kind.setCurrentIndex(w.delivery_kind.findData("report"))
    w.delivery_directory.setText(str(tmp_path / "exports"))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    w._export_delivery()
    assert w.job_id is None and w.session is None
    path = tmp_path / "project.aida"
    prompts = []

    def choose(*args, **kwargs):
        prompts.append(True)
        return str(path), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
    original = w.service.analyze

    def analyze(*args, **kwargs):
        assert path.is_file()
        return original(*args, **kwargs)

    monkeypatch.setattr(w.service, "analyze", analyze)
    revealed = []
    monkeypatch.setattr(w, "_reveal_delivery", revealed.append)
    w._export_delivery()
    qtbot.waitUntil(lambda: w.last_export_path is not None and w.job_id is None, timeout=30000)
    assert prompts == [True]
    assert "analysis.json" in read_project(path).reports
    assert read_project(path).state["delivery"]["kind"] == "report"
    assert revealed == [w.last_export_path] and not w._dirty
    assert not w.cancel_button.isVisible()
    w.close()


def test_export_overwrite_is_confirmed_once_before_project_save(
    qtbot, sample_video, tmp_path, monkeypatch
):
    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12)
    w._range_from_mouse(0, 9)
    w.delivery_kind.setCurrentIndex(w.delivery_kind.findData("report"))
    w.delivery_name.setText("existing")
    w.delivery_directory.setText(str(tmp_path))
    (tmp_path / "existing.json").write_text("old", encoding="utf-8")
    path = tmp_path / "project.aida"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    questions = []

    def question(*args):
        questions.append(args[2])
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", question)
    w._export_delivery()
    qtbot.waitUntil(lambda: w.last_export_path is not None and w.job_id is None, timeout=30000)
    assert questions == ["Substituir arquivos existentes?"]
    assert not w._dirty
    w.close()


def test_export_success_is_preserved_if_project_autosave_fails(
    qtbot, sample_video, tmp_path, monkeypatch
):
    import dg_fps.ui.studio_actions as actions

    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12)
    w._range_from_mouse(0, 9)
    path = tmp_path / "project.aida"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    w._save_project()
    qtbot.waitUntil(lambda: w.job_id is None)
    original = path.read_bytes()
    w.delivery_kind.setCurrentIndex(w.delivery_kind.findData("report"))
    w.delivery_directory.setText(str(tmp_path / "exports"))

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(actions, "save_project", fail)
    questions = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: questions.append(args[2]) or QMessageBox.StandardButton.No,
    )
    w._export_delivery()
    qtbot.waitUntil(lambda: bool(questions) and w.job_id is None, timeout=30000)
    assert w.last_export_path.is_file()
    assert w._dirty and path.read_bytes() == original
    assert "arquivos foram exportados" in questions[0]
    assert w._delivered_pending_save is None
    assert "Entrega salva" in w.statusBar().currentMessage()
    w._dirty = False
    w.close()


def test_import_resets_indeterminate_progress(qtbot, sample_video, tmp_path):
    from dg_fps.ui.main_window import FPSWindow

    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(w)
    w.process_dialog.bar.setRange(0, 0)
    w.open_source(sample_video)
    assert w.process_dialog.bar.maximum() == 100
    qtbot.waitUntil(lambda: not w._media_loading)
    w.close()


def test_project_restores_export_choices(qtbot, sample_video, tmp_path, monkeypatch):
    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: not w._media_loading)
    w._range_from_mouse(0, 9)
    w.delivery_name.setText("my-delivery")
    w.delivery_directory.setText(str(tmp_path / "chosen-output"))
    w.delivery_kind.setCurrentIndex(w.delivery_kind.findData("report"))
    path = tmp_path / "settings.aida"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    w._save_project()
    qtbot.waitUntil(lambda: w.job_id is None)
    assert w.save_state.text() == "Projeto salvo"
    w.delivery_name.setText("changed")
    w.delivery_kind.setCurrentIndex(w.delivery_kind.findData("video"))
    assert w._dirty
    w._open_project(path)
    qtbot.waitUntil(
        lambda: (
            w.job_id is None and not w._media_loading and w.delivery_name.text() == "my-delivery"
        ),
        timeout=15000,
    )
    assert w.delivery_kind.currentData() == "report"
    assert w.delivery_directory.text() == str(tmp_path / "chosen-output")
    assert not w._dirty
    w.close()


def test_close_cancel_discard_and_save(qtbot, sample_video, tmp_path, monkeypatch):
    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12)
    w._range_from_mouse(0, 8)
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Cancel)
    assert not w.close() and w.isVisible()
    path = tmp_path / "closed.aida"
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    w.close()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=15000)
    assert read_project(path).state["ranges"][0]["end_frame"] == 8


def test_only_progress_dialog_has_visible_cancel(qtbot, sample_video, tmp_path):
    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12)
    gate = Event()
    w._set_busy(True)
    w.job_id = w.jobs.submit("Test", lambda token, report: gate.wait(2))
    assert w.process_dialog.cancel.isVisible() and not w.cancel_button.isVisible()
    qtbot.mouseClick(w.process_dialog.cancel, Qt.MouseButton.LeftButton)
    gate.set()
    qtbot.waitUntil(lambda: w.job_id is None)
    w.close()
