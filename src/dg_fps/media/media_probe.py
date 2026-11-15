from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import av

from dg_fps.core.errors import MediaOpenError


def _fraction_text(value: Fraction | None) -> str | None:
    return f"{value.numerator}/{value.denominator}" if value is not None else None


def _fraction_float(value: Fraction | None) -> float | None:
    return float(value) if value is not None else None


def _scaled_time(value: int | None, time_base: Fraction | None) -> float | None:
    if value is None or time_base is None:
        return None
    return float(value * time_base)


@dataclass(frozen=True, slots=True)
class VideoStreamMetadata:
    index: int
    codec_name: str | None
    codec_long_name: str | None
    width: int
    height: int
    pixel_format: str | None
    time_base: str | None
    start_time_seconds: float | None
    duration_seconds: float | None
    average_rate: float | None
    base_rate: float | None
    guessed_rate: float | None
    declared_frames: int | None


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    source_path: Path
    file_size_bytes: int
    container_name: str
    container_long_name: str
    duration_seconds: float | None
    bit_rate: int | None
    video_streams: tuple[VideoStreamMetadata, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_path"] = str(self.source_path)
        return data


class MediaProbe:
    def probe(self, source_path: Path) -> MediaMetadata:
        path = source_path.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            with av.open(str(path), mode="r") as container:
                video_streams = tuple(
                    self._video_metadata(stream) for stream in container.streams.video
                )
                duration = (
                    float(container.duration / av.time_base)
                    if container.duration is not None
                    else None
                )
                return MediaMetadata(
                    source_path=path,
                    file_size_bytes=path.stat().st_size,
                    container_name=container.format.name,
                    container_long_name=container.format.long_name,
                    duration_seconds=duration,
                    bit_rate=container.bit_rate,
                    video_streams=video_streams,
                )
        except (av.error.FFmpegError, OSError, ValueError) as exc:
            raise MediaOpenError(f"Could not inspect media: {path}") from exc

    @staticmethod
    def _video_metadata(stream: av.video.stream.VideoStream) -> VideoStreamMetadata:
        codec = stream.codec_context.codec
        frames = stream.frames if stream.frames > 0 else None
        return VideoStreamMetadata(
            index=stream.index,
            codec_name=codec.name if codec else None,
            codec_long_name=codec.long_name if codec else None,
            width=stream.codec_context.width,
            height=stream.codec_context.height,
            pixel_format=stream.codec_context.pix_fmt,
            time_base=_fraction_text(stream.time_base),
            start_time_seconds=_scaled_time(stream.start_time, stream.time_base),
            duration_seconds=_scaled_time(stream.duration, stream.time_base),
            average_rate=_fraction_float(stream.average_rate),
            base_rate=_fraction_float(stream.base_rate),
            guessed_rate=_fraction_float(stream.guessed_rate),
            declared_frames=frames,
        )
