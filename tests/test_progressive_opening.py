from __future__ import annotations

import sqlite3
from dataclasses import replace
from fractions import Fraction
from shutil import copy2
from threading import Event
from time import sleep

import av
import numpy as np
import pytest

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.controllers.media_controller import MediaController, NavigationUpdate
from dg_fps.core.errors import MediaOpenError
from dg_fps.jobs.cancellation import CancellationToken, JobCancelled
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.navigation_preview import (
    NavigationReader,
    cached_timestamp_index,
    initial_navigation_times,
    navigation_span,
)
from dg_fps.media.timestamp_index import TimestampIndex, _cache_path
from dg_fps.ui.main_window import FPSWindow


def blocked_index(monkeypatch):
    reference = TimestampIndex.build
    entered, release = Event(), Event()

    def build(source, **kwargs):
        entered.set()
        while not release.wait(0.005):
            kwargs["on_frame"](0)
        return reference(source, **kwargs)

    monkeypatch.setattr(TimestampIndex, "build", build)
    return entered, release


def test_navigation_has_real_pts_and_no_invented_frame_index(sample_video):
    reference = TimestampIndex.build(sample_video)
    by_pts = {(t.pts, t.time_base): t for t in reference}
    metadata = MediaProbe().probe(sample_video)
    frames = list(
        NavigationReader(sample_video).frames(
            initial_navigation_times(metadata), check_cancelled=lambda: None
        )
    )
    assert len(frames) == 6
    for frame in frames:
        assert not hasattr(frame, "index")
        timestamp = by_pts[(frame.pts, str(frame.time_base))]
        expected = FrameProvider(sample_video, timestamp_index=reference).thumbnail_by_index(
            timestamp.index
        )
        assert np.array_equal(frame.rgb, expected.rgb)
        assert frame.seconds == timestamp.seconds


def test_navigation_cache_does_not_require_or_build_timestamp_index(
    sample_video, tmp_path, monkeypatch
):
    reader = NavigationReader(sample_video, tmp_path)
    expected = list(reader.frames((0.1, 0.2), check_cancelled=lambda: None))

    def fail(*args, **kwargs):
        pytest.fail("Cached preview must not open a decoder or build a measurement index")

    monkeypatch.setattr(av, "open", fail)
    monkeypatch.setattr(TimestampIndex, "build", fail)
    actual = list(reader.frames((0.1, 0.2), check_cancelled=lambda: None))
    assert [(f.pts, f.time_base) for f in actual] == [(f.pts, f.time_base) for f in expected]
    assert all(f.rgb.shape == (64, 96, 3) for f in actual)
    assert not list(tmp_path.glob("*.npz"))


def test_unwritable_navigation_cache_is_optional(sample_video, tmp_path):
    unavailable = tmp_path / "not-a-directory"
    unavailable.write_text("keep", encoding="utf-8")
    frames = list(
        NavigationReader(sample_video, unavailable).frames((0.0,), check_cancelled=lambda: None)
    )
    assert len(frames) == 1
    assert unavailable.read_text("utf-8") == "keep"


def test_corrupted_navigation_cache_falls_back_to_decode(sample_video, tmp_path):
    reader = NavigationReader(sample_video, tmp_path)
    expected = list(reader.frames((0.1,), check_cancelled=lambda: None))[0]
    with sqlite3.connect(tmp_path / "aida-navigation-v1.sqlite3") as db:
        db.execute("UPDATE previews SET image=?, base=?", (b"invalid", "invalid"))
    actual = list(reader.frames((0.1,), check_cancelled=lambda: None))[0]
    assert actual.pts == expected.pts and np.array_equal(actual.rgb, expected.rgb)


def test_changed_source_and_cancelled_reader_cannot_publish(sample_video, tmp_path):
    source = tmp_path / "copy.mkv"
    copy2(sample_video, source)
    reader = NavigationReader(source)
    with source.open("ab") as handle:
        handle.write(b"modified")
    with pytest.raises(MediaOpenError, match="mudou"):
        list(reader.frames((0.1,), check_cancelled=lambda: None))
    token = CancellationToken()
    token.cancel()
    with pytest.raises(JobCancelled):
        list(
            NavigationReader(sample_video).frames((0.1,), check_cancelled=token.raise_if_cancelled)
        )


def test_unknown_duration_falls_back_without_guessing_frame_count(sample_video):
    metadata = MediaProbe().probe(sample_video)
    stream = replace(metadata.video_streams[0], duration_seconds=None)
    unknown = replace(metadata, duration_seconds=None, video_streams=(stream,))
    assert navigation_span(unknown) is None
    assert initial_navigation_times(unknown) == ()


def test_empty_or_invalid_exact_cache_does_not_become_authoritative(sample_video, tmp_path):
    path = _cache_path(sample_video.resolve(), 0, tmp_path)
    path.write_bytes(b"not a valid NPZ")
    assert cached_timestamp_index(sample_video, tmp_path) is None


def test_window_is_navigable_before_index_and_promotes_cursor_using_real_pts(
    qtbot, sample_video, tmp_path, monkeypatch
):
    reference = TimestampIndex.build(sample_video)
    entered, release = blocked_index(monkeypatch)
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    window.open_source(sample_video)
    try:
        qtbot.waitUntil(entered.is_set, timeout=10000)
        assert window._media_loading and window._opening_preview_ready
        assert not window.process_dialog.isVisible()
        assert window.timeline.navigation_active and window.timeline.frame_count == 0
        assert len(window.timeline.opening._frames) == 6
        assert window.media.timestamp_index is None
        assert window.media.cached_frame_count == 0
        assert not window.panel.isEnabled() and not window.export_button.isEnabled()
        window._analyze((AnalysisFrameRange(0, 1, "pending"),))
        assert window.job_id is None
        window._request_navigation_time(0.2)
        qtbot.waitUntil(
            lambda: window.current is None and "0.200" in window.timeline.opening.position.text(),
            timeout=10000,
        )
        assert window.media.cached_frame_count == 0
        release.set()
        qtbot.waitUntil(lambda: window.timeline.frame_count == 12, timeout=10000)
        target = reference.nearest_at_or_after(0.2)
        qtbot.waitUntil(
            lambda: window.current is not None and window.current.timestamp == target, timeout=10000
        )
        assert not window.timeline.navigation_active and not window._media_loading
        assert window.panel.isEnabled()
        assert tuple(window.media.timestamp_index) == tuple(reference)
    finally:
        release.set()
        window.media.shutdown()


def test_valid_exact_cache_bypasses_preliminary_thumbnail_decode(
    qtbot, sample_video, tmp_path, monkeypatch
):
    cache = tmp_path / "cache"
    expected = TimestampIndex.build(sample_video, cache_directory=cache)

    def unexpected(*args, **kwargs):
        pytest.fail("A valid exact index must bypass preliminary decoding")

    monkeypatch.setattr(NavigationReader, "frames", unexpected)
    monkeypatch.setattr(TimestampIndex, "build", unexpected)
    controller = MediaController(index_cache_directory=cache)
    delivered = []
    controller.index_ready.connect(delivered.append)
    try:
        controller.open_media(sample_video)
        qtbot.waitUntil(lambda: bool(delivered), timeout=10000)
        assert tuple(controller.timestamp_index) == tuple(expected)
        assert controller.timestamp_index.decoder == "cache"
    finally:
        controller.shutdown()


def test_bootstrap_preview_failure_still_builds_exact_index(
    qtbot, sample_video, tmp_path, monkeypatch
):
    def fail(*args, **kwargs):
        raise MediaOpenError("preview unavailable")

    monkeypatch.setattr(NavigationReader, "frames", fail)
    controller = MediaController(index_cache_directory=tmp_path)
    ready = []
    controller.index_ready.connect(ready.append)
    try:
        controller.open_media(sample_video)
        qtbot.waitUntil(lambda: ready == [12], timeout=10000)
    finally:
        controller.shutdown()


def test_cancel_and_close_are_available_during_background_index(
    qtbot, sample_video, tmp_path, monkeypatch
):
    entered, release = blocked_index(monkeypatch)
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    window.show()
    window.open_source(sample_video)
    qtbot.waitUntil(entered.is_set, timeout=10000)
    window._cancel_operation()
    assert not window._media_loading and window.timeline.navigation_active
    assert window.timeline.opening.retry.isVisible()
    assert not window.panel.isEnabled() and window.media.timestamp_index is None
    window.close()
    assert not window.isVisible()
    release.set()


def test_same_path_reopened_drops_old_navigation_epoch(qtbot, sample_video, tmp_path):
    controller = MediaController(index_cache_directory=tmp_path)
    controller._source_path = sample_video.resolve()
    old = next(NavigationReader(sample_video).frames((0.0,), check_cancelled=lambda: None))
    controller._navigation_epoch = "new-opening"
    delivered = []
    controller.navigation_thumbnails_ready.connect(delivered.append)
    try:
        controller._on_navigation_update(NavigationUpdate("old-opening", old))
        assert delivered == []
    finally:
        controller.shutdown()


def test_latest_time_request_cancels_obsolete_preview(qtbot, sample_video, tmp_path, monkeypatch):
    entered, release = blocked_index(monkeypatch)
    original = NavigationReader.frames
    slow_seek = Event()

    def slow(self, times, **kwargs):
        if times == (0.1,):
            slow_seek.set()
            while True:
                kwargs["check_cancelled"]()
                sleep(0.005)
        yield from original(self, times, **kwargs)

    monkeypatch.setattr(NavigationReader, "frames", slow)
    controller = MediaController(index_cache_directory=tmp_path)
    delivered = []
    controller.navigation_frame_ready.connect(delivered.append)
    try:
        controller.open_media(sample_video)
        qtbot.waitUntil(entered.is_set, timeout=10000)
        controller.request_navigation_time(0.1)
        qtbot.waitUntil(slow_seek.is_set, timeout=10000)
        controller.request_navigation_time(0.3)
        qtbot.waitUntil(lambda: bool(delivered), timeout=10000)
        assert [frame.requested_seconds for frame in delivered] == [0.3]
        assert controller._navigation_idle.is_set()
    finally:
        release.set()
        controller.shutdown()


def test_time_request_can_preempt_initial_thumbnails_without_losing_index(
    qtbot, sample_video, tmp_path, monkeypatch
):
    original = NavigationReader.frames
    initial_started = Event()

    def slow(self, times, **kwargs):
        if len(times) == 6:
            initial_started.set()
            while True:
                kwargs["check_cancelled"]()
                sleep(0.005)
        yield from original(self, times, **kwargs)

    monkeypatch.setattr(NavigationReader, "frames", slow)
    controller = MediaController(index_cache_directory=tmp_path)
    ready = []
    controller.index_ready.connect(ready.append)
    try:
        controller.open_media(sample_video)
        qtbot.waitUntil(initial_started.is_set, timeout=10000)
        controller.request_navigation_time(0.2)
        qtbot.waitUntil(lambda: ready == [12], timeout=10000)
        assert controller.timestamp_index is not None
    finally:
        controller.shutdown()


def test_failed_time_seek_releases_index_and_clears_seeking_notice(
    qtbot, sample_video, tmp_path, monkeypatch
):
    entered, release = blocked_index(monkeypatch)
    original = NavigationReader.frames

    def fail_seek(self, times, **kwargs):
        if len(times) == 1:
            raise MediaOpenError("seek failed")
        yield from original(self, times, **kwargs)

    monkeypatch.setattr(NavigationReader, "frames", fail_seek)
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    window.open_source(sample_video)
    try:
        qtbot.waitUntil(entered.is_set, timeout=10000)
        window._request_navigation_time(0.2)
        qtbot.waitUntil(lambda: window.view.preview_notice == "Prévia temporal indisponível")
        assert window.media._navigation_idle.is_set()
        release.set()
        qtbot.waitUntil(lambda: window.timeline.frame_count == 12, timeout=10000)
    finally:
        release.set()
        window.media.shutdown()


def test_switch_source_while_indexing_then_close_without_waiting_for_completion(
    qtbot, sample_video, tmp_path, monkeypatch
):
    other = tmp_path / "other.mkv"
    copy2(sample_video, other)
    entered, release = blocked_index(monkeypatch)
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    window.show()
    window.open_source(sample_video)
    qtbot.waitUntil(entered.is_set, timeout=10000)
    window.open_source(other)
    qtbot.waitUntil(
        lambda: window._opening_preview_ready and window.source == other.resolve(), timeout=10000
    )
    qtbot.waitUntil(lambda: len(window.timeline.opening._frames) == 6, timeout=10000)
    assert all(f.source_path == other.resolve() for f in window.timeline.opening._frames)
    assert window.close()
    assert window.media._navigation_jobs._pool.activeThreadCount() == 0
    release.set()


def test_vfr_and_nonzero_start_preview_preserves_fractional_timestamp(tmp_path):
    source = tmp_path / "vfr.mkv"
    with av.open(str(source), "w") as output:
        stream = output.add_stream("ffv1", rate=30)
        stream.width, stream.height, stream.pix_fmt = 96, 64, "bgr0"
        for pts in (1000, 1033, 1100, 1117, 1200, 1300):
            frame = av.VideoFrame.from_ndarray(np.full((64, 96, 3), pts % 200, np.uint8), "rgb24")
            frame.pts, frame.time_base = pts, Fraction(1, 1000)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    reference = TimestampIndex.build(source)
    frames = list(NavigationReader(source).frames((1.1, 1.25), check_cancelled=lambda: None))
    assert all(
        (f.pts, str(f.time_base)) in {(t.pts, t.time_base) for t in reference} for f in frames
    )
