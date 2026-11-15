from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from dg_fps.ui.main_window import FPSWindow


def test_open_select_analyze_and_invalidate(qtbot, sample_video, tmp_path, monkeypatch):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    window.open_source(sample_video)
    qtbot.waitUntil(lambda: window.timeline.frame_count == 12, timeout=15000)
    window.mark_in()
    window.seek(9)
    qtbot.waitUntil(lambda: window.current.timestamp.index == 9, timeout=5000)
    window.mark_out()
    assert len(window.panel.ranges) == 1
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window.panel.request_analysis()
    qtbot.waitUntil(lambda: window.session is not None, timeout=20000)
    assert window.export_button.isEnabled()
    assert "Cadência visual" in window.panel.summary_text
    assert not list((tmp_path / "data").rglob("*.mp4"))
    window.panel.clear_ranges()
    assert window.session is None
    assert not window.export_button.isEnabled()
    window.close()


def test_language_change_preserves_video_and_selection(qtbot, sample_video, tmp_path, monkeypatch):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    window.open_source(sample_video)
    qtbot.waitUntil(lambda: window.timeline.frame_count == 12, timeout=15000)
    window.panel.mark_in(0, 0)
    window.panel.mark_out(9, 0.3)
    window.panel._add_range()
    ranges = window.panel.ranges
    window.language_box.setCurrentIndex(window.language_box.findData("en"))
    assert window.open_button.accessibleName() == "Open video"
    assert window.panel._range_list.item(0).text().startswith("Segment 1:")
    assert window.panel.ranges == ranges
    assert window.panel.ranges[0].label == "Trecho 1"
    assert window.source == sample_video
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window.panel.request_analysis()
    qtbot.waitUntil(lambda: window.session is not None, timeout=20000)
    result = window.session
    report_bytes = result.reports.analysis_json.read_bytes()
    assert "Visual cadence" in window.panel.summary_text
    assert "Segment 1:" in window.panel.summary_text
    window.language_box.setCurrentIndex(window.language_box.findData("pt"))
    assert "Cadência visual" in window.panel.summary_text
    assert window.session is result
    assert result.reports.analysis_json.read_bytes() == report_bytes
    assert window.export_button.isEnabled()
    window.close()
