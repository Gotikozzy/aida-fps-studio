from __future__ import annotations

import av
import numpy as np
import pytest
from PySide6.QtGui import QImage

from dg_fps.analyzers.cadence import cadence_advance_map
from dg_fps.core.errors import MediaOpenError
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.cadence_video import _export_frames
from dg_fps.presentation.motion_map import AdvanceMapRenderer
from dg_fps.presentation.renderer import qimage_to_rgb, qimage_to_video_frame


@pytest.mark.parametrize("width,height", [(96, 64), (641, 361), (1920, 1080)])
def test_cached_motion_map_is_pixel_identical(width, height):
    rng = np.random.default_rng(83)
    rgb = rng.integers(0, 256, (height, width, 3), np.uint8)
    renderer = AdvanceMapRenderer()
    evidence = {
        "analysis_size": [640, 360],
        "active_regions": [{"x": 16, "y": 32, "width": 16, "height": 16}],
        "refinement_regions": [
            {
                "x": 25,
                "y": 40,
                "source_size": [width, height],
                "evidence": {"active_regions": [{"x": 8, "y": 8, "width": 16, "height": 16}]},
            }
        ],
    }
    assert renderer.render(rgb, evidence) is None
    for displacement in (0, 1, 3, 0):
        current = np.roll(rgb, displacement, axis=1)
        assert np.array_equal(
            renderer.render(current, evidence), cadence_advance_map(rgb, current, evidence=evidence)
        )
        rgb = current


@pytest.mark.parametrize("width", [95, 96, 641])
def test_direct_qimage_conversion_owns_its_pixels(qapp, width):
    image = QImage(width, 32, QImage.Format.Format_RGB888)
    image.fill(0x123456)
    expected = qimage_to_rgb(image)
    frame = qimage_to_video_frame(image)
    image.fill(0)
    assert np.array_equal(frame.to_ndarray(format="rgb24"), expected)
    assert isinstance(frame, av.VideoFrame)


def test_threaded_original_frames_match_conventional_reader(sample_video):
    index = TimestampIndex.build(sample_video)
    reference = list(FrameProvider(sample_video, timestamp_index=index).frames_in_range(1, 10))
    actual = list(
        FrameProvider(sample_video, timestamp_index=index, threaded_decode=True).frames_in_range(
            1, 10
        )
    )
    assert len(reference) == len(actual)
    for before, after in zip(reference, actual, strict=True):
        assert before.timestamp == after.timestamp
        assert before.signal_metadata == after.signal_metadata
        assert np.array_equal(before.rgb, after.rgb)


def test_export_decode_fallback_resumes_at_first_undelivered_frame(sample_video, monkeypatch):
    index = TimestampIndex.build(sample_video)
    original = FrameProvider.frames_in_range
    requested = []

    def fail_threaded(self, start, end, **kwargs):
        requested.append((self._threaded_decode, start))
        for frame in original(self, start, end, **kwargs):
            if self._threaded_decode and frame.timestamp.index == 4:
                raise MediaOpenError("threaded decode failed")
            yield frame

    monkeypatch.setattr(FrameProvider, "frames_in_range", fail_threaded)
    provider = FrameProvider(sample_video, timestamp_index=index)
    frames = list(_export_frames(provider, 1, 10, lambda: None))
    assert [f.timestamp.index for f in frames] == list(range(1, 11))
    assert requested == [(True, 1), (False, 4)]


def test_composition_is_cpu_producer_and_encoding_stays_on_job_thread(
    qapp, sample_video, tmp_path, monkeypatch
):
    from dataclasses import replace
    from threading import get_ident

    from test_standalone import session_for

    from dg_fps.jobs.cancellation import CancellationToken
    from dg_fps.presentation import cadence_video

    service, session = session_for(sample_video, tmp_path / "reports")
    add_stream = cadence_video.add_video_stream
    compose = cadence_video.CadenceVideoExporter._compose
    encoding_threads, composition_threads = [], []

    def wrapped_stream(*args, **kwargs):
        selection = add_stream(*args, **kwargs)

        class Stream:
            def encode(self, *frames):
                encoding_threads.append(get_ident())
                return selection.stream.encode(*frames)

        return replace(selection, stream=Stream())

    def wrapped_compose(self, *args, **kwargs):
        composition_threads.append(get_ident())
        return compose(self, *args, **kwargs)

    monkeypatch.setattr(cadence_video, "add_video_stream", wrapped_stream)
    monkeypatch.setattr(cadence_video.CadenceVideoExporter, "_compose", wrapped_compose)
    service.export(session, tmp_path / "result.mp4", "cpu", CancellationToken(), lambda *_: None)
    assert set(encoding_threads) == {get_ident()}
    assert len(set(composition_threads)) == 1
    assert composition_threads[0] != get_ident()


def test_render_failure_closes_producers_and_preserves_destination(
    qapp, sample_video, tmp_path, monkeypatch
):
    from threading import enumerate as threads

    from test_standalone import session_for

    from dg_fps.jobs.cancellation import CancellationToken
    from dg_fps.presentation.cadence_video import CadenceVideoExporter

    service, session = session_for(sample_video, tmp_path / "reports")
    destination = tmp_path / "result.mp4"
    destination.write_bytes(b"previous export")

    def fail(*args, **kwargs):
        raise ValueError("composition failed")

    monkeypatch.setattr(CadenceVideoExporter, "_compose", fail)
    with pytest.raises(ValueError, match="composition failed"):
        service.export(session, destination, "cpu", CancellationToken(), lambda *_: None)
    assert destination.read_bytes() == b"previous export"
    assert not any(t.name == "aida-cpu-lookahead" for t in threads())
