from __future__ import annotations

from shutil import copy2
from threading import Event
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from dg_fps.media.frame_provider import FrameProvider
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.projects import read_project
from dg_fps.ui.main_window import FPSWindow
from dg_fps.ui.target_controls import SegmentTargetsDialog, TargetSelector


def open_window(qtbot, path, tmp_path):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    assert window.workspaces.currentIndex() == window.home_index
    window.open_source(path)
    return window


def test_timeline_keys_and_end_edit_keep_project_when_visiting_home(qtbot, sample_video, tmp_path):
    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12, timeout=15000)
    canvas = w.timeline.canvas
    canvas.setFocus()
    w.timeline.set_current_frame(2)
    qtbot.keyClick(canvas, Qt.Key.Key_I)
    assert canvas.pending_start == 2
    w.timeline.set_current_frame(8)
    qtbot.keyClick(canvas, Qt.Key.Key_O)
    assert w.panel.ranges[0].start_frame == 2 and w.panel.ranges[0].end_frame == 8
    menu = canvas.context_menu(10)
    assert not menu.actions()[1].isEnabled()
    adjust = next(action for action in menu.actions() if "Ajustar fim" in action.text())
    adjust.trigger()
    assert w.panel.ranges[0].end_frame == 10
    w._undo_range()
    assert w.panel.ranges[0].end_frame == 8
    before = w.panel.ranges, w.timeline.current_frame
    w.workspaces.setCurrentIndex(w.home_index)
    assert w.welcome.isVisible()
    w.workspaces.setCurrentIndex(0)
    assert (w.panel.ranges, w.timeline.current_frame) == before
    w.close()


def test_thumbnail_failure_does_not_block_editing_and_can_be_retried(
    qtbot, sample_video, tmp_path, monkeypatch
):
    proceed = Event()
    original = FrameProvider.thumbnail_by_index

    def unavailable(*args, **kwargs):
        proceed.wait(5)
        raise OSError("test thumbnail error")

    monkeypatch.setattr(FrameProvider, "thumbnail_by_index", unavailable)
    w = open_window(qtbot, sample_video, tmp_path)
    try:
        qtbot.waitUntil(lambda: w._loading_thumbnails, timeout=15000)
        assert not w.process_dialog.isVisible() and w.timeline.frame_count == 12
        assert w.panel.isEnabled() and not w._media_loading
    finally:
        proceed.set()
    qtbot.waitUntil(lambda: w.retry_thumbnails_action.isEnabled(), timeout=15000)
    assert w.timeline.frame_count == 12 and not w.process_dialog.isVisible()
    monkeypatch.setattr(FrameProvider, "thumbnail_by_index", original)
    w.retry_thumbnails_action.trigger()
    qtbot.waitUntil(lambda: w.timeline.thumbnail_count == 12, timeout=15000)
    assert not w._media_loading and not w.retry_thumbnails_action.isEnabled()
    w.close()


def test_invalid_legacy_target_remains_visible_and_blocks_delivery(
    qtbot, sample_video, tmp_path, monkeypatch
):
    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12, timeout=15000)
    w._range_from_mouse(0, 9)
    target = w.content_target
    assert target.combo.model().item(target.combo.findData(30.0)).isEnabled()
    assert not target.combo.model().item(target.combo.findData(40.0)).isEnabled()
    target.set_value(45.5)
    assert target.value() == 45.5 and not target.is_compatible()
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    w._export_delivery()
    assert warnings and w.job_id is None
    target.set_value(None)
    target.combo.setCurrentIndex(target.combo.findData(-1))
    assert target.custom.maximum() == 30 and target.is_compatible()
    dialog = SegmentTargetsDialog(["Trecho 1"], {"Trecho 1": 60}, None, w, capture_rate=30)
    assert not dialog.selectors["Trecho 1"].is_compatible()
    assert not dialog.selectors["Trecho 1"].combo.model().item(3).isEnabled()
    w.close()


def test_studio_fps_uses_capture_metadata_and_a_decimal_point(qtbot, tmp_path):
    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(w)
    summary = SimpleNamespace(container_fps=59.939690067768694, content_fps=59.86168004813477)
    analysis = SimpleNamespace(
        summary=summary, segment_summaries={"A": summary}, unavailable_frame_count=0
    )
    w.session = SimpleNamespace(
        analysis=analysis,
        automatic_references={"A": ContentReference(60, "inferred", "defined")},
    )
    w._refresh_results()
    assert w.fps_value.text() == "60" and w.result_capture.text() == "Captura: 60 FPS"
    summary.content_fps = 58.86
    w._refresh_results()
    assert w.fps_value.text() == "58.86"


def test_target_selector_checks_40_against_the_encoded_rate(qtbot):
    selector = TargetSelector(40)
    qtbot.addWidget(selector)
    for rate, supported in ((58, False), (58.01, True), (118.01, True)):
        selector.set_capture_rate(rate)
        item = selector.combo.model().item(selector.combo.findData(40.0))
        assert item.isEnabled() == selector.is_compatible() == supported


def test_save_confirmation_and_switch_resume_after_successful_write(
    qtbot, sample_video, tmp_path, monkeypatch
):
    w = open_window(qtbot, sample_video, tmp_path)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12, timeout=15000)
    w._range_from_mouse(0, 8)
    project_path = tmp_path / "analysis.aida"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(project_path), ""))
    w.panel.request_analysis()
    qtbot.waitUntil(lambda: w.project_path == project_path and w.job_id is None, timeout=20000)
    original = project_path.read_bytes()
    assert not w._dirty
    w._edit_range(0, 0, 9)
    questions = []

    def decline(*args):
        questions.append(args[2])
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", decline)
    w.panel.request_analysis()
    qtbot.waitUntil(lambda: w.session is not None and w.job_id is None, timeout=20000)
    assert questions == ["Atualizar o projeto com esta análise?"]
    assert project_path.read_bytes() == original and w._dirty
    replacement = tmp_path / "next.mkv"
    copy2(sample_video, replacement)
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Cancel)
    w.open_source(replacement)
    assert w.source == sample_video and w.panel.ranges[0].end_frame == 9
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Save)
    w.open_source(replacement)
    qtbot.waitUntil(lambda: w.source == replacement and not w._media_loading, timeout=20000)
    assert read_project(project_path).state["ranges"][0]["end_frame"] == 9
    w.close()
