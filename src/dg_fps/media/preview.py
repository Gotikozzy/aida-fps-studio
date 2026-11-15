"""Presentation-only media. Original frame identities always come from the source index."""

from __future__ import annotations

import io
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass
from fractions import Fraction
from itertools import chain
from pathlib import Path

import av
import cv2
import numpy as np

from dg_fps.core.errors import MediaOpenError
from dg_fps.media.frame_provider import DecodedFrame, FrameProvider, VideoThumbnail, _frame_to_rgb
from dg_fps.media.timestamp_index import FrameTimestamp
from dg_fps.presentation.video_encoder import add_video_stream

PREVIEW_SIZE = (1280, 720)
_PROXY_RATE = 30  # Internal addressing only. Playback and editing use original time.


def cached_thumbnail(
    directory: Path | None,
    source: Path,
    provider: FrameProvider,
    frame_index: int,
    check_cancelled: Callable[[], None],
) -> VideoThumbnail:
    timestamp = provider.timestamp_index[frame_index]
    if directory is None:
        return provider.thumbnail_by_index(frame_index, check_cancelled=check_cancelled)

    try:
        stat = source.stat()
        directory.mkdir(parents=True, exist_ok=True)
        key = repr((str(source), stat.st_size, stat.st_mtime_ns, timestamp))
        cache_path = directory / "aida-thumbnails-v1.sqlite3"
        with closing(sqlite3.connect(cache_path, timeout=0.1)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS thumbs ("
                "id INTEGER PRIMARY KEY, key TEXT UNIQUE, image BLOB NOT NULL)"
            )
            row = db.execute("SELECT image FROM thumbs WHERE key = ?", (key,)).fetchone()
            if row:
                image = cv2.imdecode(np.frombuffer(row[0], dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is not None:
                    return VideoThumbnail(timestamp, cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    except (OSError, sqlite3.Error, cv2.error):
        return provider.thumbnail_by_index(frame_index, check_cancelled=check_cancelled)

    thumbnail = provider.thumbnail_by_index(frame_index, check_cancelled=check_cancelled)
    check_cancelled()
    if thumbnail.rgb is not None:
        try:
            image = cv2.cvtColor(thumbnail.rgb, cv2.COLOR_RGB2BGR)
            ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            current = source.stat()
            if ok and (stat.st_size, stat.st_mtime_ns) == (current.st_size, current.st_mtime_ns):
                with closing(sqlite3.connect(cache_path, timeout=0.1)) as db, db:
                    db.execute(
                        "INSERT OR REPLACE INTO thumbs (key, image) VALUES (?, ?)",
                        (key, encoded.tobytes()),
                    )
                    db.execute("DELETE FROM thumbs WHERE id <= (SELECT max(id) - 2048 FROM thumbs)")
        except (OSError, sqlite3.Error, cv2.error):
            pass  # Presentation can proceed without a writable cache.
    return thumbnail


@dataclass(frozen=True, slots=True)
class PreviewRegion:
    start: int
    end: int
    video: bytes
    encoder: str
    source_path: Path
    source_identity: tuple[int, int]

    def contains(self, frame_index: int) -> bool:
        return self.start <= frame_index <= self.end

    def frame(self, timestamp: FrameTimestamp, check_cancelled: Callable[[], None]) -> DecodedFrame:
        with closing(
            self.frames(timestamp.index, timestamp.index, lambda _: timestamp, check_cancelled)
        ) as frames:
            return next(frames)

    def frames(
        self,
        start: int,
        end: int,
        original: Callable[[int], FrameTimestamp],
        check_cancelled: Callable[[], None],
        max_size: tuple[int, int] | None = None,
        skip_before_seconds: Callable[[], float] | None = None,
    ) -> Iterator[DecodedFrame]:
        if not self.contains(start) or not self.contains(end) or start > end:
            raise MediaOpenError("Frame range outside the preview")
        if _identity(self.source_path) != self.source_identity:
            raise MediaOpenError("The preview source changed")
        position = start
        expected = Fraction(position - self.start, _PROXY_RATE)
        with av.open(io.BytesIO(self.video)) as container:
            stream = container.streams.video[0]
            container.seek(int(expected / stream.time_base), stream=stream, backward=True)
            for frame in container.decode(stream):
                check_cancelled()
                if frame.pts is None or frame.is_corrupt:
                    continue
                time = frame.pts * (frame.time_base or stream.time_base)
                if time > expected:
                    break
                if time < expected:
                    continue
                timestamp = original(position)
                if skip_before_seconds is None or timestamp.seconds >= skip_before_seconds():
                    yield DecodedFrame(timestamp, _frame_to_rgb(frame, max_size))
                if position == end:
                    return
                position += 1
                expected += Fraction(1, _PROXY_RATE)
        raise MediaOpenError("Could not find the expected frame in the preview")


def _identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def build_preview_region(
    provider: FrameProvider,
    start: int,
    end: int,
    mode: str,
    check_cancelled: Callable[[], None],
    on_frame: Callable[[int], None],
) -> PreviewRegion:
    source = provider.source_path
    identity = _identity(source)
    buffer = io.BytesIO()
    with (
        closing(
            provider.frames_in_range(
                start, end, max_size=PREVIEW_SIZE, check_cancelled=check_cancelled
            )
        ) as frames,
        av.open(buffer, "w", format="mp4") as output,
    ):
        first = next(frames)
        height, width = first.rgb.shape[:2]
        selection = add_video_stream(
            output,
            rate=_PROXY_RATE,
            width=max(2, width // 2 * 2),
            height=max(2, height // 2 * 2),
            quality=27,
            cpu_preset="ultrafast",
            mode=mode,
        )
        stream = selection.stream
        stream.codec_context.gop_size = 8
        stream.codec_context.max_b_frames = 0
        count = 0
        for count, item in enumerate(chain((first,), frames), start=1):
            check_cancelled()
            if item.timestamp != provider.timestamp_index[start + count - 1]:
                raise MediaOpenError("Preview source frame does not match the original index")
            frame = av.VideoFrame.from_ndarray(item.rgb, format="rgb24")
            frame.pts = count - 1
            frame.time_base = Fraction(1, _PROXY_RATE)
            for packet in stream.encode(frame):
                output.mux(packet)
            if count % 8 == 0:
                on_frame(count)
        if count != end - start + 1:
            raise MediaOpenError("Incomplete preview region")
        check_cancelled()
        for packet in stream.encode():
            output.mux(packet)
    region = PreviewRegion(start, end, buffer.getvalue(), selection.codec, source, identity)
    # Verify the encoded ordinal address space before publishing it.
    with av.open(io.BytesIO(region.video)) as container:
        count = 0
        for count, frame in enumerate(container.decode(video=0), start=1):
            check_cancelled()
            if (
                frame.pts is None
                or frame.is_corrupt
                or frame.pts * frame.time_base != Fraction(count - 1, _PROXY_RATE)
            ):
                raise MediaOpenError("Preview timestamp could not be verified")
        if count != end - start + 1:
            raise MediaOpenError("Incomplete encoded preview region")
    if _identity(source) != identity:
        raise MediaOpenError("The preview source changed")
    return region
