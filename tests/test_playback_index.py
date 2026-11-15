from __future__ import annotations

import numpy as np
import pytest

from dg_fps.controllers.media_controller import MediaController
from dg_fps.media import timestamp_index
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.timestamp_index import TimestampIndex


def test_auto_index_recovers_without_changing_timestamps(sample_video, monkeypatch, tmp_path):
    expected = TimestampIndex.build(sample_video)

    def unsupported(*args, **kwargs):
        raise TypeError("Hardware-owned frames unavailable")

    monkeypatch.setattr(timestamp_index, "HWAccel", unsupported)
    actual = TimestampIndex.build(
        sample_video, hardware_acceleration=True, cache_directory=tmp_path
    )
    assert actual.decoder == "cpu"
    assert [actual[i] for i in range(len(actual))] == list(expected)
    monkeypatch.setattr(
        timestamp_index.av, "open", lambda *_a, **_k: pytest.fail("Use index cache")
    )
    cached = TimestampIndex.build(sample_video, cache_directory=tmp_path)
    assert cached.decoder == "cache" and list(cached) == list(expected)


def test_cancel_index_is_not_retried(sample_video):
    from dg_fps.jobs.cancellation import JobCancelled

    calls = []

    def cancel(index):
        calls.append(index)
        raise JobCancelled()

    with pytest.raises(JobCancelled):
        TimestampIndex.build(sample_video, hardware_acceleration=True, on_frame=cancel)
    assert calls == [0]


def test_preview_skips_only_requested_images_and_preserves_exact_seek(sample_video):
    index = TimestampIndex.build(sample_video)
    provider = FrameProvider(sample_video, timestamp_index=index, threaded_decode=True)
    frames = list(
        provider.frames_in_range(
            0, 11, max_size=(48, 32), skip_before_seconds=lambda: index[6].seconds
        )
    )
    assert [frame.timestamp.index for frame in frames] == list(range(6, 12))
    assert all(frame.rgb.shape == (32, 48, 3) for frame in frames)
    exact = FrameProvider(sample_video, timestamp_index=index).frame_by_index(6)
    assert exact.rgb.shape == (64, 96, 3)
    assert exact.timestamp == frames[0].timestamp


def test_scaled_playback_never_pollutes_seek_cache(qtbot, sample_video, tmp_path):
    controller = MediaController(index_cache_directory=tmp_path)
    controller.open_media(sample_video)
    qtbot.waitUntil(lambda: controller.timestamp_index is not None, timeout=15000)
    assert controller.start_playback(0, buffer_size=6, max_size=(48, 32))
    qtbot.waitUntil(lambda: controller.playback_buffer_ready, timeout=5000)
    frame = controller.take_playback_frame_at_or_before(0.2)
    assert frame is not None and frame.rgb.shape == (32, 48, 3)
    assert all(item.rgb.shape == (64, 96, 3) for item in controller._frame_cache.values())
    controller.stop_playback()
    controller.request_frame(frame.timestamp.index)
    frames = []
    controller.frame_ready.connect(frames.append)
    qtbot.waitUntil(lambda: bool(frames), timeout=5000)
    expected = FrameProvider(sample_video).frame_by_index(frame.timestamp.index)
    assert np.array_equal(frames[-1].rgb, expected.rgb)
    controller.shutdown()
