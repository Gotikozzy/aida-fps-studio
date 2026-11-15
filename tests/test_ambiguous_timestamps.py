from pathlib import Path
from unittest.mock import patch

import av
import numpy as np
import pytest

from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.timestamp_index import FrameTimestamp, TimestampIndex


@pytest.mark.parametrize("pts", [(0, 0, 1), (None, None, None), (0, None, 1)])
def test_frame_identity_survives_ambiguous_pts(tmp_path: Path, pts: tuple[int | None, ...]) -> None:
    frames = []
    for i, value in enumerate(pts):
        frame = av.VideoFrame.from_ndarray(np.full((8, 8, 3), i * 60, np.uint8), format="rgb24")
        frame.pts = value
        frames.append(frame)
    index = TimestampIndex(
        FrameTimestamp(i, 0, value, None, "1/30", i / 30, False, "P", False)
        for i, value in enumerate(pts)
    )
    source = tmp_path / "source.mp4"
    source.touch()

    class Container:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def decode(self, **kwargs):
            return iter(frames)

    provider = FrameProvider(source, timestamp_index=index)
    with patch.object(provider, "_open_container", return_value=Container()):
        selected = list(provider.frames_in_range(1, 2))
        single = provider.frame_by_index(1)
    assert [item.timestamp.index for item in selected] == [1, 2]
    assert [int(item.rgb[0, 0, 0]) for item in selected] == [60, 120]
    assert single.timestamp.pts == pts[1]
    assert int(single.rgb[0, 0, 0]) == 60


def test_precision_path_preserves_sub_eight_bit_differences(tmp_path: Path) -> None:
    pixels = np.full((8, 8, 3), 32000, np.uint16)
    pixels[4:, :, :] += 16
    frame = av.VideoFrame.from_ndarray(pixels, format="rgb48le")
    timestamp = FrameTimestamp(0, 0, 0, None, "1/30", 0.0, False, "I", False)
    source = tmp_path / "source.mp4"
    source.touch()
    provider = FrameProvider(source, preserve_precision=True)
    decoded = provider._decoded_frame(timestamp, frame, None)
    assert decoded.measurement_rgb is not None
    np.testing.assert_array_equal(decoded.measurement_rgb, pixels)
    assert decoded.signal_metadata["source_component_bits"] == 16
