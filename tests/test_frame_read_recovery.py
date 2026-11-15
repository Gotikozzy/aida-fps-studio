from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import av
import pytest

from dg_fps.analyzers.base import AnalysisContext, AnalysisFrameRange
from dg_fps.analyzers.cadence import CadenceAnalyzer
from dg_fps.core.errors import MediaOpenError
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.service import FPSService
from dg_fps.ui.main_window import FPSWindow


class DecodeFixture:
    def __init__(self, frames, time_base, start_after_seek):
        self.streams = SimpleNamespace(video=[SimpleNamespace(time_base=time_base)])
        self.frames = frames
        self.start_after_seek = start_after_seek
        self.start = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def seek(self, offset, **kwargs):
        self.start = self.start_after_seek(offset)

    def decode(self, **kwargs):
        return iter(self.frames[self.start :])


def decoded_frames(source):
    with av.open(str(source)) as container:
        return list(container.decode(video=0)), container.streams.video[0].time_base


def test_seek_recovers_exact_frame_from_earlier_keyframe(sample_video, monkeypatch):
    original = TimestampIndex.build(sample_video)
    index = TimestampIndex(replace(f, key_frame=f.index % 4 == 0) for f in original)
    frames, time_base = decoded_frames(sample_video)
    offsets = []

    def seek(offset):
        offsets.append(offset)
        return 8  # Simulate a demuxer jumping ahead of the requested frame.

    monkeypatch.setattr(
        FrameProvider, "_open_container", lambda self: DecodeFixture(frames, time_base, seek)
    )
    provider = FrameProvider(sample_video, timestamp_index=index)
    assert provider.thumbnail_by_index(6).timestamp == index[6]
    assert offsets == [index[4].dts]
    assert [f.timestamp.index for f in provider.frames_in_range(6, 9)] == [6, 7, 8, 9]


def test_parallel_decoder_retries_the_unread_frame_with_the_conventional_reader(
    sample_video, monkeypatch
):
    index = TimestampIndex.build(sample_video)
    frames, time_base = decoded_frames(sample_video)
    modes = []

    def open_container(provider):
        modes.append(provider._threaded_decode)
        available = frames[:6] + frames[7:] if provider._threaded_decode else frames
        return DecodeFixture(available, time_base, lambda offset: 0)

    monkeypatch.setattr(FrameProvider, "_open_container", open_container)
    result = CadenceAnalyzer().analyze(
        AnalysisContext(
            sample_video,
            30.0,
            frame_ranges=(AnalysisFrameRange(0, 11, "Selection"),),
            timestamp_index=index,
        )
    )

    assert modes == [True, False]
    assert [sample.pts for sample in result.samples] == [frame.pts for frame in index]
    assert result.samples[6].similarity_to_previous is not None
    assert result.unavailable_frame_count == 0


@pytest.mark.parametrize("unreadable", [{6}, set(range(12))])
def test_read_gaps_are_reported_without_pairing_across_them(
    sample_video, tmp_path, monkeypatch, unreadable
):
    index = TimestampIndex.build(sample_video)
    frames, time_base = decoded_frames(sample_video)
    readable = [f for i, f in enumerate(frames) if i not in unreadable]
    monkeypatch.setattr(
        FrameProvider,
        "_open_container",
        lambda self: DecodeFixture(readable, time_base, lambda offset: 0),
    )
    provider = FrameProvider(sample_video, timestamp_index=index)
    with pytest.raises(MediaOpenError, match="was not found"):
        list(provider.frames_in_range(0, 11))
    token = CancellationToken()
    service = FPSService()
    session = service.analyze(
        sample_video,
        MediaProbe().probe(sample_video),
        index,
        (AnalysisFrameRange(0, 11, "Selection"),),
        tmp_path / "reports",
        "cpu",
        None,
        token,
        lambda *_: None,
    )
    result = session.analysis
    assert result.unavailable_frame_count == len(unreadable)
    assert [s.frame_index for s in result.samples] == [i for i in range(12) if i not in unreadable]
    if unreadable == {6}:
        assert next(s for s in result.samples if s.frame_index == 7).similarity_to_previous is None
        assert result.summary.observed_intervals == 9
    else:
        assert result.summary.content_fps is None
    import json

    report = json.loads(session.reports.llm_report_json.read_text(encoding="utf-8"))
    segment = report["segments"][0]
    assert segment["source_frames"] == [0, 11]
    availability = segment["decode_availability"]
    assert availability["unavailable_frames"] == len(unreadable)
    assert availability["gaps"][0]["source_frames"] == [min(unreadable), max(unreadable)]
    if unreadable == {6}:
        assert availability["unmeasured_seconds_due_to_decode"] == pytest.approx(
            index[7].seconds - index[5].seconds
        )
    with pytest.raises(ValueError, match="Somente relatório"):
        service.export(session, tmp_path / "out.mp4", "cpu", token, lambda *_: None)


def test_one_bad_thumbnail_keeps_the_other_slots(qtbot, sample_video, tmp_path, monkeypatch):
    original = FrameProvider.thumbnail_by_index

    def thumbnail(provider, index, **kwargs):
        if index == 6:
            raise MediaOpenError("Unavailable thumbnail")
        return original(provider, index, **kwargs)

    monkeypatch.setattr(FrameProvider, "thumbnail_by_index", thumbnail)
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    window.open_source(sample_video)
    qtbot.waitUntil(lambda: window.retry_thumbnails_action.isEnabled(), timeout=15000)
    assert window.timeline.thumbnail_count == 11
    assert window.timeline.canvas.images[6].isNull()
    assert window.retry_thumbnails_action.isEnabled()
    window.close()
