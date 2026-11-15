from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import av
import numpy as np
from av.codec.hwaccel import HWAccel
from av.container import InputContainer
from numpy.typing import NDArray

from dg_fps.core.errors import MediaOpenError
from dg_fps.jobs.cpu_pipeline import cpu_lookahead
from dg_fps.media.timestamp_index import (
    FrameTimestamp,
    TimestampIndex,
    frame_timestamp_from_av,
)


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    timestamp: FrameTimestamp
    rgb: NDArray[np.uint8]
    measurement_rgb: NDArray[np.uint16] | None = None
    signal_metadata: dict[str, str | int] | None = None


@dataclass(frozen=True, slots=True)
class VideoThumbnail:
    timestamp: FrameTimestamp
    rgb: NDArray[np.uint8] | None


class FrameProvider:
    def __init__(
        self,
        source_path: Path,
        *,
        video_stream: int = 0,
        timestamp_index: TimestampIndex | None = None,
        hardware_acceleration: bool = False,
        preserve_precision: bool = False,
        threaded_decode: bool = False,
    ) -> None:
        self._source_path = source_path.resolve()
        if not self._source_path.is_file():
            raise FileNotFoundError(self._source_path)
        self._video_stream = video_stream
        self._index = timestamp_index
        self._hardware_acceleration = hardware_acceleration
        self._preserve_precision = preserve_precision
        self._threaded_decode = threaded_decode
        self._keyframes: tuple[int, ...] | None = None

    @property
    def source_path(self) -> Path:
        return self._source_path

    @property
    def timestamp_index(self) -> TimestampIndex:
        if self._index is None:
            self._index = TimestampIndex.build(
                self._source_path,
                video_stream=self._video_stream,
                hardware_acceleration=self._hardware_acceleration,
            )
        return self._index

    def frame_by_index(
        self,
        index: int,
        *,
        max_size: tuple[int, int] | None = None,
        check_cancelled: Callable[[], None] | None = None,
    ) -> DecodedFrame:
        target = self.timestamp_index[index]
        return self._decode_target(target, max_size=max_size, check_cancelled=check_cancelled)

    def thumbnail_by_index(
        self,
        index: int,
        *,
        max_width: int = 160,
        max_height: int = 90,
        check_cancelled: Callable[[], None] | None = None,
    ) -> VideoThumbnail:
        if max_width < 1 or max_height < 1:
            raise ValueError("Thumbnail dimensions must be positive")
        target = self.timestamp_index[index]
        decoded = self._decode_target(
            target, max_size=(max_width, max_height), check_cancelled=check_cancelled
        )
        return VideoThumbnail(decoded.timestamp, decoded.rgb)

    def frame_at_time(self, seconds: float) -> DecodedFrame:
        if seconds < 0:
            raise ValueError("Timestamp cannot be negative")
        return self._decode_target(self.timestamp_index.nearest_at_or_after(seconds))

    def first_frame(self, *, max_size: tuple[int, int] | None = None) -> DecodedFrame:
        try:
            with self._open_container() as container:
                stream = container.streams.video[self._video_stream]
                frame = next(container.decode(video=self._video_stream))
                timestamp = frame_timestamp_from_av(
                    0,
                    stream.index,
                    frame,
                    frame.time_base or stream.time_base,
                )
                return self._decoded_frame(timestamp, frame, max_size)
        except (av.error.FFmpegError, OSError, ValueError, IndexError, StopIteration) as exc:
            raise MediaOpenError("Could not decode the first video frame") from exc

    def frames_in_range(
        self,
        start_index: int,
        end_index: int,
        *,
        max_size: tuple[int, int] | None = None,
        check_cancelled: Callable[[], None] | None = None,
        skip_before_seconds: Callable[[], float] | None = None,
        allow_incomplete: bool = False,
    ) -> Iterator[DecodedFrame]:
        def read() -> Iterator[DecodedFrame]:
            return self._frames_in_range(
                start_index,
                end_index,
                max_size=max_size,
                check_cancelled=check_cancelled,
                skip_before_seconds=skip_before_seconds,
                allow_incomplete=allow_incomplete,
            )

        if (
            self._threaded_decode
            and not self._hardware_acceleration
            and max_size is None
            and skip_before_seconds is None
            and end_index > start_index
        ):
            with cpu_lookahead(
                read,
                check_cancelled=check_cancelled or (lambda: None),
                size_bytes=lambda frame: (
                    frame.rgb.nbytes
                    + (0 if frame.measurement_rgb is None else frame.measurement_rgb.nbytes)
                ),
            ) as frames:
                yield from frames
        else:
            yield from read()

    def _frames_in_range(
        self,
        start_index: int,
        end_index: int,
        *,
        max_size: tuple[int, int] | None = None,
        check_cancelled: Callable[[], None] | None = None,
        skip_before_seconds: Callable[[], float] | None = None,
        allow_incomplete: bool = False,
    ) -> Iterator[DecodedFrame]:
        index = self.timestamp_index
        if start_index < 0 or end_index < start_index or end_index >= len(index):
            raise IndexError((start_index, end_index))
        if not index.has_unambiguous_pts:
            yield from self._frames_by_position(
                start_index,
                end_index,
                max_size,
                check_cancelled,
                allow_incomplete=allow_incomplete,
            )
            return
        if self._keyframes is None:
            self._keyframes = tuple(f.index for f in index if f.key_frame)
        selected = {index[i].pts: index[i] for i in range(start_index, end_index + 1)}
        end_pts = index[end_index].pts
        assert end_pts is not None
        cursor = start_index
        while cursor <= end_index:
            offsets = self._seek_offsets(cursor)
            start = cursor
            for attempt, offset in enumerate(offsets):
                final_attempt = attempt + 1 == len(offsets)
                try:
                    with closing(
                        self._read_after_seek(offset, end_pts, selected, check_cancelled)
                    ) as candidates:
                        for timestamp, frame in candidates:
                            if timestamp.index < cursor:
                                continue
                            if timestamp.index > cursor:
                                if cursor == start and not final_attempt:
                                    break
                                if not allow_incomplete:
                                    raise MediaOpenError(
                                        f"Frame {cursor} was not found after seeking"
                                    )
                            if (
                                skip_before_seconds is None
                                or timestamp.seconds >= skip_before_seconds()
                            ):
                                decoded = self._decoded_frame(timestamp, frame, max_size)
                                cursor = timestamp.index + 1
                                yield decoded
                            else:
                                cursor = timestamp.index + 1
                            if cursor > end_index:
                                return
                except (av.error.FFmpegError, OSError, ValueError, IndexError) as exc:
                    if not allow_incomplete and (final_attempt or cursor > start):
                        raise MediaOpenError(
                            f"Could not decode frame range {start_index}-{end_index}"
                        ) from exc
                if cursor > start:
                    break
            if not allow_incomplete:
                raise MediaOpenError(f"Frame {cursor} was not found after seeking")
            # An unreadable GOP can end decoding early. Resume at a later keyframe
            # and leave missing positions visible to the caller as a discontinuity.
            following = bisect_right(self._keyframes, max(start, cursor - 1))
            if following == len(self._keyframes):
                return
            cursor = self._keyframes[following]

    def _read_after_seek(
        self,
        offset: int | None,
        end_pts: int,
        selected: dict[int | None, FrameTimestamp],
        check_cancelled: Callable[[], None] | None,
    ) -> Iterator[tuple[FrameTimestamp, av.VideoFrame]]:
        with self._open_container() as container:
            stream = container.streams.video[self._video_stream]
            if offset is not None:
                container.seek(offset, stream=stream, any_frame=False, backward=True)
            for frame in container.decode(video=self._video_stream):
                if check_cancelled is not None:
                    check_cancelled()
                if frame.pts is not None and frame.pts > end_pts:
                    break
                timestamp = selected.get(frame.pts)
                if timestamp is None or frame.is_corrupt:
                    continue
                if timestamp.time_base and timestamp.time_base != str(
                    frame.time_base or stream.time_base
                ):
                    continue
                yield timestamp, frame

    def _seek_offsets(self, frame_index: int) -> tuple[int | None, ...]:
        index = self.timestamp_index
        keys = self._keyframes or ()
        position = bisect_right(keys, frame_index)
        if position == 0:
            target = index[frame_index]
            offset = target.pts if target.dts is None else target.dts
            if frame_index == 0:
                return (None,)
            earlier_index = max(0, frame_index - 120)
            earlier = index[earlier_index]
            earlier_offset = earlier.pts if earlier.dts is None else earlier.dts
            return tuple(dict.fromkeys((offset, earlier_offset if earlier_index else None)))
        offsets = []
        for key in reversed(keys[max(0, position - 2) : position]):
            timestamp = index[key]
            if key == 0:
                offsets.append(None)
            elif timestamp.dts is None:
                offsets.append(timestamp.pts)
            else:
                offsets.append(min(timestamp.dts, timestamp.pts))
        return tuple(dict.fromkeys(offsets))

    def _decode_target(
        self,
        target: FrameTimestamp,
        *,
        max_size: tuple[int, int] | None = None,
        check_cancelled: Callable[[], None] | None = None,
    ) -> DecodedFrame:
        with closing(
            self.frames_in_range(
                target.index, target.index, max_size=max_size, check_cancelled=check_cancelled
            )
        ) as frames:
            return next(frames)

    def _frames_by_position(
        self,
        start: int,
        end: int,
        max_size: tuple[int, int] | None,
        check_cancelled: Callable[[], None] | None,
        *,
        allow_incomplete: bool = False,
    ) -> Iterator[DecodedFrame]:
        """Decode by presentation position when PTS cannot identify a frame."""
        last = -1
        try:
            with self._open_container() as container:
                for position, frame in enumerate(container.decode(video=self._video_stream)):
                    if check_cancelled is not None:
                        check_cancelled()
                    if position >= start:
                        timestamp = self.timestamp_index[position]
                        if frame.pts != timestamp.pts:
                            if allow_incomplete:
                                return
                            raise MediaOpenError("Decoded frame does not match timestamp index")
                        if not frame.is_corrupt:
                            yield self._decoded_frame(timestamp, frame, max_size)
                        elif not allow_incomplete:
                            raise MediaOpenError(f"Frame {position} is corrupt")
                        last = position
                    if position == end:
                        break
        except (av.error.FFmpegError, OSError, ValueError, IndexError) as exc:
            if not allow_incomplete:
                raise MediaOpenError(f"Could not decode frame range {start}-{end}") from exc
        if last != end and not allow_incomplete:
            raise MediaOpenError(f"Incomplete decoded frame range {start}-{end}")

    def _decoded_frame(
        self,
        timestamp: FrameTimestamp,
        frame: av.VideoFrame,
        max_size: tuple[int, int] | None,
    ) -> DecodedFrame:
        metadata: dict[str, str | int] = {
            "source_pixel_format": frame.format.name,
            "source_component_bits": max(component.bits for component in frame.format.components),
            "color_range": str(frame.color_range),
            "colorspace": str(frame.colorspace),
            "color_primaries": str(getattr(frame, "color_primaries", "unknown")),
            "color_transfer": str(getattr(frame, "color_trc", "unknown")),
            "measurement_domain": "encoded_rgb_not_linear_light",
            "conversion": "libav_rgb48le" if self._preserve_precision else "libav_rgb24",
        }
        native = (
            cast(NDArray[np.uint16], frame.to_ndarray(format="rgb48le"))
            if self._preserve_precision
            else None
        )
        return DecodedFrame(timestamp, _frame_to_rgb(frame, max_size), native, metadata)

    def _open_container(self) -> InputContainer:
        if not self._hardware_acceleration:
            container = av.open(str(self._source_path), mode="r")
            if self._threaded_decode:
                container.streams.video[self._video_stream].thread_type = "AUTO"
            return container
        return av.open(
            str(self._source_path),
            mode="r",
            hwaccel=HWAccel("d3d11va", allow_software_fallback=True),
        )


def _frame_to_rgb(frame: av.VideoFrame, max_size: tuple[int, int] | None) -> NDArray[np.uint8]:
    if max_size is not None:
        max_width, max_height = max_size
        scale = min(max_width / frame.width, max_height / frame.height, 1.0)
        width = max(1, round(frame.width * scale))
        height = max(1, round(frame.height * scale))
        frame = frame.reformat(width=width, height=height, format="rgb24")
    return cast(NDArray[np.uint8], frame.to_ndarray(format="rgb24"))
