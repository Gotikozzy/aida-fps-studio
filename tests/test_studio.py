from __future__ import annotations

import json
from dataclasses import asdict
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox
from test_standalone import session_for

from dg_fps.jobs.cancellation import CancellationToken, JobCancelled
from dg_fps.projects import read_project, restore_reports, result_from_document, save_project
from dg_fps.studio_services import export_delivery, publish_copy
from dg_fps.ui.main_window import FPSWindow


def state(source, session):
    return {
        "source": str(source),
        "ranges": [asdict(v) for v in session.analysis.frame_ranges],
        "target": 40,
        "overrides": {},
        "frame": 3,
    }


def test_project_round_trip_preserves_all_measurements_and_original_reports(sample_video, tmp_path):
    _, session = session_for(sample_video, tmp_path / "internal")
    path = tmp_path / "minha_analise.aida"
    save_project(path, state(sample_video, session), session.reports, CancellationToken())
    project = read_project(path)
    source, valid = project.source()
    assert source == sample_video and valid
    paths = restore_reports(project, tmp_path / "restored")
    restored = result_from_document(json.loads(paths.analysis_json.read_text("utf-8")), source)
    assert asdict(restored) == asdict(session.analysis)
    assert paths.analysis_json.read_bytes() == session.reports.analysis_json.read_bytes()
    assert project.state["target"] == 40
    with ZipFile(path) as archive:
        assert all(not name.endswith((".mp4", ".mkv")) for name in archive.namelist())
    sample_video.write_bytes(sample_video.read_bytes() + b"changed")
    assert project.source()[1] is False


def test_cancel_project_save_preserves_existing_file(sample_video, tmp_path):
    path = tmp_path / "saved.aida"
    path.write_bytes(b"existing")
    token = CancellationToken()
    token.cancel()
    with pytest.raises(JobCancelled):
        save_project(path, {"source": str(sample_video)}, None, token)
    assert path.read_bytes() == b"existing"
    assert not list(tmp_path.glob("*.tmp"))


def test_report_only_delivery_never_encodes_video_and_keeps_output_clean(
    sample_video, tmp_path, monkeypatch
):
    service, session = session_for(sample_video, tmp_path / "internal")

    def forbid(*args, **kwargs):
        pytest.fail("Report-only delivery encoded a video")

    monkeypatch.setattr(service, "export", forbid)
    output = tmp_path / "delivery" / "my.analysis"
    result = export_delivery(
        service, session, output, "report", "cpu", "pt", {}, CancellationToken(), lambda *_: None
    )
    assert len(result.paths) == 1 and result.paths[0].name == "my.analysis.json"
    assert sorted(p.suffix for p in output.parent.iterdir()) == [".json"]
    data = json.loads(result.paths[0].read_text("utf-8"))
    assert data["report_type"] == "aida_llm_measurement_context"


def test_delivery_both_publishes_only_video_and_llm_report(qapp, sample_video, tmp_path):
    service, session = session_for(sample_video, tmp_path / "internal")
    target = tmp_path / "delivery" / "test"
    result = export_delivery(
        service, session, target, "both", "cpu", "en", {}, CancellationToken(), lambda *_: None
    )
    assert {p.name for p in target.parent.iterdir()} == {"test.mp4", "test.json"}
    assert all(p.is_file() and p.stat().st_size > 0 for p in result.paths)
    assert list(session.reports.project_directory.glob("exports/*/*_assets/frames.json"))


def test_delivery_io_failure_does_not_replace_existing_file(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_text("new", encoding="utf-8")
    target = tmp_path / "delivery.json"
    target.write_text("existing", encoding="utf-8")

    def fail(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr("dg_fps.studio_services.os.fsync", fail)
    with pytest.raises(OSError):
        publish_copy(source, target, CancellationToken())
    assert target.read_text("utf-8") == "existing"
    assert not list(tmp_path.glob("*.tmp"))


def test_visual_selection_handles_undo_and_redo_preserve_frame_indices(
    qtbot, sample_video, tmp_path
):
    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    w.open_source(sample_video)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12, timeout=15000)
    canvas = w.timeline.canvas
    a = QPoint(round(canvas.x_at(1)), 107)
    b = QPoint(round(canvas.x_at(8)), 107)
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=a)
    qtbot.mouseMove(canvas, b)
    assert canvas.current == 8
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=b)
    assert [(r.start_frame, r.end_frame) for r in w.panel.ranges] == [(1, 8)]
    a = QPoint(round(canvas.x_at(1)), 107)
    b = QPoint(round(canvas.x_at(3)), 107)
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=a)
    qtbot.mouseMove(canvas, b)
    assert canvas.current == 3
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=b)
    assert w.panel.ranges[0].start_frame == 3
    w._undo_range()
    assert w.panel.ranges[0].start_frame == 1
    w._redo_range()
    assert w.panel.ranges[0].start_frame == 3
    assert canvas.frame_at(canvas.x_at(6)) == 6
    w.close()


def test_context_menu_marks_clicked_frames_and_delete_is_scoped(
    qtbot, sample_video, tmp_path
):
    from PySide6.QtGui import QContextMenuEvent
    from PySide6.QtWidgets import QApplication, QMenu

    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    w.open_source(sample_video)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12, timeout=15000)
    canvas = w.timeline.canvas
    actions = iter((0, 1))

    for frame in (2, 9):
        pos = QPoint(round(canvas.x_at(frame)), 60)
        QApplication.sendEvent(
            canvas,
            QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, canvas.mapToGlobal(pos)),
        )
        menu = QApplication.activePopupWidget()
        assert isinstance(menu, QMenu)
        menu.actions()[next(actions)].trigger()
        menu.close()
        qtbot.wait(10)
    assert [(r.start_frame, r.end_frame) for r in w.panel.ranges] == [(2, 9)]
    assert canvas.pending_start is None
    assert w.export_button.isEnabled()
    canvas.setFocus()
    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    assert not w.panel.ranges
    w._undo_range()
    assert len(w.panel.ranges) == 1
    w.workspaces.setCurrentIndex(1)
    w.delivery_name.setText("abc")
    w.delivery_name.setFocus()
    w.delivery_name.setCursorPosition(0)
    qtbot.keyClick(w.delivery_name, Qt.Key.Key_Delete)
    assert w.delivery_name.text() == "bc"
    assert len(w.panel.ranges) == 1
    w.workspaces.setCurrentIndex(0)
    w.panel._range_list.setCurrentRow(0)
    w.panel._range_list.setFocus()
    qtbot.keyClick(w.panel._range_list, Qt.Key.Key_Delete)
    assert not w.panel.ranges
    w.close()


@pytest.mark.parametrize("kind", ["video", "report", "both"])
def test_one_click_export_analyzes_then_delivers_and_reuses_result(
    qtbot, sample_video, tmp_path, monkeypatch, kind
):
    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(w)
    w.show()
    w.open_source(sample_video)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12, timeout=15000)
    w._range_from_mouse(0, 9)
    w.analysis_mode.setCurrentIndex(w.analysis_mode.findData("cpu"))
    w.encoding_mode.setCurrentIndex(w.encoding_mode.findData("cpu"))
    w.delivery_directory.setText(str(tmp_path / "delivery"))
    w.delivery_kind.setCurrentIndex(w.delivery_kind.findData(kind))
    original = w.service.analyze
    calls = []

    def analyze(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(w.service, "analyze", analyze)
    save_path = tmp_path / "auto-export.aida"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        lambda *a, **k: (str(save_path), ""),
    )
    w.workspaces.setCurrentIndex(1)
    for name in ("first", "second"):
        w.delivery_name.setText(name)
        qtbot.mouseClick(w.export_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda name=name: w.job_id is None and w.last_export_path is not None
            and w.last_export_path.stem == name,
            timeout=30000,
        )
        assert w.session is not None
        assert w._pending_delivery is None
        suffixes = {p.suffix for p in (tmp_path / "delivery").glob(name + ".*")}
        assert suffixes == ({".mp4", ".json"} if kind == "both"
                            else {".json"} if kind == "report" else {".mp4"})
    assert len(calls) == 1
    assert save_path.is_file()
    w.close()


@pytest.mark.parametrize("cancel", [False, True])
def test_failed_or_cancelled_auto_analysis_never_exports(
    qtbot, sample_video, tmp_path, monkeypatch, cancel
):
    from threading import Event

    gate = Event()
    started = Event()
    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(w)
    w.show()
    w.open_source(sample_video)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12, timeout=15000)
    w._range_from_mouse(0, 9)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_: None)

    def analyze(*args):
        started.set()
        gate.wait(5)
        args[-2].raise_if_cancelled()
        raise RuntimeError("Test failure")

    def forbid(*args, **kwargs):
        pytest.fail("Delivery started after unsuccessful analysis")

    monkeypatch.setattr(w.service, "analyze", analyze)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "failed.aida"), "")
    )
    monkeypatch.setattr(w, "_submit_delivery", forbid)
    w._export_delivery()
    qtbot.waitUntil(started.is_set, timeout=10000)
    if cancel:
        w._cancel_operation()
    gate.set()
    qtbot.waitUntil(lambda: w.job_id is None, timeout=10000)
    assert w._pending_delivery is None and w.session is None
    assert w.export_button.isEnabled()
    w.close()


def test_ui_project_reopens_result_without_running_analyzer(
    qtbot, sample_video, tmp_path, monkeypatch
):
    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(w)
    w.show()
    w.open_source(sample_video)
    qtbot.waitUntil(lambda: w.timeline.frame_count == 12, timeout=15000)
    w.panel.mark_in(0, 0)
    w.panel.mark_out(9, 0.3)
    w.panel._add_range()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    w.panel.request_analysis()
    qtbot.waitUntil(lambda: w.session is not None and w.job_id is None, timeout=20000)
    before = asdict(w.session.analysis)
    path = tmp_path / "project.aida"
    save_project(path, w._state(), w.session.reports, CancellationToken())

    def forbid(*args, **kwargs):
        pytest.fail("Saved project reran the analyzer")

    monkeypatch.setattr(w.service, "analyze", forbid)
    w.panel.clear_ranges()
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Discard)
    w._open_project(path)
    qtbot.waitUntil(lambda: w.session is not None and w.job_id is None, timeout=20000)
    assert asdict(w.session.analysis) == before
    assert w.project_path == path
    assert not w._dirty
    assert str(path) in w.recent_projects
    assert w.timeline.canvas.points
    assert w.workspaces.tabText(0) == "Análise"
    w.language_box.setCurrentIndex(w.language_box.findData("en"))
    assert w.workspaces.tabText(0) == "Analysis"
    assert w.inspector_tabs.tabText(0) == "Results"
    w.close()


def test_export_preview_renders_and_resizes_without_changing_analysis(
    qtbot, sample_video, tmp_path
):
    from dg_fps.studio_services import render_preview

    _, session = session_for(sample_video, tmp_path / "internal")
    before = asdict(session.analysis)
    image = render_preview(session, {}, "pt", 2, CancellationToken())
    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(w)
    w._show_project_workspace()
    w.workspaces.setCurrentIndex(1)
    w.show()
    w.job_id = "preview"
    w._job_completed("preview", image)
    for width in (1440, 1180):
        w.resize(width, 820)
        qtbot.wait(20)
        assert not w.export_preview.grab().isNull()
    assert asdict(session.analysis) == before
    w.close()


def test_project_rejects_invalid_manifest_and_overlapping_ranges(sample_video, tmp_path):
    for manifest in (
        {"format": "aida-project", "version": 1},
        {
            "format": "aida-project",
            "version": 1,
            "source": str(sample_video),
            "source_size": 1,
            "source_mtime_ns": 1,
            "ranges": [
                {"start_frame": 0, "end_frame": 5, "label": "A"},
                {"start_frame": 4, "end_frame": 8, "label": "B"},
            ],
        },
    ):
        path = tmp_path / "bad.aida"
        with ZipFile(path, "w") as archive:
            archive.writestr("project.json", json.dumps(manifest))
        with pytest.raises(ValueError):
            read_project(path)
