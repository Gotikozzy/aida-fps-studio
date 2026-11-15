from __future__ import annotations

from dataclasses import replace
from shutil import copy2
from threading import Event

from PySide6.QtWidgets import QMessageBox
from test_standalone import session_for

from dg_fps.media.timestamp_index import (
    TimestampIndex,
    _cache_path,
    _write_cache,
    clear_index_cache,
)
from dg_fps.ui.main_window import FPSWindow


def load_video(qtbot, video, directory):
    window = FPSWindow(directory / "data", directory / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    window.open_source(video)
    qtbot.waitUntil(lambda: window.timeline.frame_count == 12, timeout=15000)
    return window


def test_confirmed_cache_actions_preserve_active_analysis_and_unrelated_files(
    qtbot, sample_video, tmp_path, monkeypatch
):
    cache = tmp_path / "cache"
    other_video = tmp_path / "other.mkv"
    copy2(sample_video, other_video)
    TimestampIndex.build(other_video, cache_directory=cache)
    other_index = _cache_path(other_video.resolve(), 0, cache)
    own_index = _cache_path(sample_video.resolve(), 0, cache)
    unrelated = cache / "not-an-index.aida-index.npz"
    unrelated.write_bytes(b"unrelated")
    nested = cache / "nested" / other_index.name
    nested.parent.mkdir()
    copy2(other_index, nested)
    w = load_video(qtbot, sample_video, tmp_path)
    _, session = session_for(sample_video, tmp_path / "reports")
    w.panel.set_ranges(session.analysis.frame_ranges, w.media.timestamp_index)
    w.session = session
    old = w.media.timestamp_index
    original_report = session.reports.analysis_json.read_bytes()

    buttons = QMessageBox.StandardButton
    monkeypatch.setattr(QMessageBox, "question", lambda *_: buttons.No)
    w.reindex_action.trigger()
    w._clear_index_cache()
    assert own_index.is_file() and other_index.is_file() and w.media.timestamp_index is old
    assert w.job_id is None and not w._media_loading

    monkeypatch.setattr(QMessageBox, "question", lambda *_: buttons.Yes)
    w.reindex_action.trigger()
    qtbot.waitUntil(lambda: not w._media_loading, timeout=15000)
    assert w.media.timestamp_index is not old and w.media.timestamp_index.decoder != "cache"
    assert w.session.analysis is session.analysis
    assert w.session.timestamp_index is w.media.timestamp_index
    assert own_index.is_file() and other_index.is_file()

    w._clear_index_cache()
    qtbot.waitUntil(lambda: w.job_id is None, timeout=10000)
    assert not own_index.exists() and not other_index.exists()
    assert unrelated.read_bytes() == b"unrelated" and nested.is_file()
    assert w.session.analysis is session.analysis and w.timeline.frame_count == 12
    assert session.reports.analysis_json.read_bytes() == original_report
    w.close()


def test_reindex_replaces_stale_times_and_invalidates_only_active_measurement(
    qtbot, sample_video, tmp_path, monkeypatch
):
    cache = tmp_path / "cache"
    fresh = TimestampIndex.build(sample_video)
    cached = _cache_path(sample_video.resolve(), 0, cache)
    _write_cache(cached, sample_video, [replace(f, seconds=f.seconds + 0.1) for f in fresh])
    w = load_video(qtbot, sample_video, tmp_path)
    assert w.media.timestamp_index.decoder == "cache"
    _, session = session_for(sample_video, tmp_path / "reports")
    w.panel.set_ranges(session.analysis.frame_ranges, w.media.timestamp_index)
    w.session = session
    ranges = w.panel.ranges
    original_report = session.reports.analysis_json.read_bytes()
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    w.reindex_action.trigger()
    qtbot.waitUntil(lambda: not w._media_loading, timeout=15000)
    assert w.session is None and w.panel.ranges == ranges
    assert [f.seconds for f in w.media.timestamp_index] == [f.seconds for f in fresh]
    assert session.reports.analysis_json.read_bytes() == original_report
    w.close()


def test_cache_cleanup_invalidates_writes_from_an_older_index_build(sample_video, tmp_path):
    cache = tmp_path / "cache"

    def on_frame(number):
        if number == 1:
            clear_index_cache(cache)

    index = TimestampIndex.build(sample_video, cache_directory=cache, on_frame=on_frame)
    assert len(index) == 12
    assert not list(cache.glob("*.aida-index.npz"))


def test_cancel_reindex_keeps_the_active_index_and_ranges(
    qtbot, sample_video, tmp_path, monkeypatch
):
    w = load_video(qtbot, sample_video, tmp_path)
    w._range_from_mouse(1, 8)
    old_index = w.media.timestamp_index
    old_ranges = w.panel.ranges
    started = Event()
    proceed = Event()
    build = TimestampIndex.build

    def delayed(cls, source, **kwargs):
        started.set()
        proceed.wait(5)
        kwargs["on_frame"](0)
        return build(source, **kwargs)

    monkeypatch.setattr(TimestampIndex, "build", classmethod(delayed))
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    try:
        w.reindex_action.trigger()
        qtbot.waitUntil(started.is_set, timeout=10000)
        w._cancel_operation()
        assert w.media.timestamp_index is old_index
        assert w.panel.ranges == old_ranges and w.timeline.isEnabled()
        assert not w._media_loading and not w.process_dialog.isVisible()
    finally:
        proceed.set()
        w.close()
