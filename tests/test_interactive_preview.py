from __future__ import annotations

from threading import Event
from time import sleep

import cv2
import numpy as np
import pytest

from dg_fps.controllers.media_controller import MediaController
from dg_fps.core.errors import MediaOpenError
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.preview import build_preview_region, cached_thumbnail
from dg_fps.media.timestamp_index import TimestampIndex


def test_proxy_addresses_exact_original_frames_even_after_an_encoded_seek(sample_video):
    index = TimestampIndex.build(sample_video)
    provider = FrameProvider(sample_video, timestamp_index=index)
    region = build_preview_region(provider, 1, 11, "cpu", lambda: None, lambda count: None)

    for frame_index in (10, 1, 11, 5):
        original = provider.frame_by_index(frame_index)
        frame = region.frame(index[frame_index], lambda: None)
        assert frame.timestamp == original.timestamp
        preview_luma = cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2GRAY).ravel()
        original_luma = cv2.cvtColor(original.rgb, cv2.COLOR_RGB2GRAY).ravel()
        assert np.corrcoef(preview_luma, original_luma)[0, 1] > 0.85

    played = tuple(region.frames(7, 11, index.__getitem__, lambda: None, (48, 32)))
    assert [frame.timestamp for frame in played] == [index[i] for i in range(7, 12)]
    assert all(frame.rgb.shape == (32, 48, 3) for frame in played)

    with sample_video.open("ab") as source:
        source.write(b"changed")
    with pytest.raises(MediaOpenError, match="source changed"):
        region.frame(index[5], lambda: None)


def test_cached_thumbnail_is_reused_and_keeps_source_timestamp(sample_video, tmp_path, monkeypatch):
    provider = FrameProvider(sample_video)
    first = cached_thumbnail(tmp_path, sample_video, provider, 3, lambda: None)

    def fail(*args, **kwargs):
        raise AssertionError("cache miss")

    monkeypatch.setattr(provider, "thumbnail_by_index", fail)
    cached = cached_thumbnail(tmp_path, sample_video, provider, 3, lambda: None)
    assert cached.timestamp == first.timestamp
    assert cached.rgb.shape == first.rgb.shape


def test_new_seek_cancels_obsolete_decode_before_delivering_exact_frame(
    qtbot, sample_video, monkeypatch
):
    index = TimestampIndex.build(sample_video)
    provider = FrameProvider(sample_video, timestamp_index=index)
    original = provider.frame_by_index
    entered = Event()

    def decode(frame_index, *, max_size, check_cancelled):
        if frame_index == 3:
            entered.set()
            while True:
                check_cancelled()
                sleep(0.005)
        return original(frame_index, max_size=max_size, check_cancelled=check_cancelled)

    monkeypatch.setattr(provider, "frame_by_index", decode)
    controller = MediaController()
    controller._source_path = sample_video
    controller._provider = provider
    controller._frame_count = len(index)
    delivered = []
    controller.frame_ready.connect(lambda frame: delivered.append(frame.timestamp))
    try:
        controller.request_frame(3)
        qtbot.waitUntil(entered.is_set)
        controller.request_frame(6)
        qtbot.waitUntil(lambda: bool(delivered))
        assert delivered == [index[6]]
    finally:
        controller.shutdown()
