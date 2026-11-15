from __future__ import annotations

import logging
import re
from bisect import bisect_left
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Any

import av
import numpy as np
from av.codec.hwaccel import HWAccel

from dg_fps.core.errors import MediaOpenError

LOGGER = logging.getLogger(__name__)
_INDEX_FILENAME = re.compile(r"[0-9a-f]{24}\.aida-index\.npz")
_cache_lock = Lock()
_cache_generation = 0


@dataclass(frozen=True, slots=True)
class IndexCacheCleanup:
    removed: int
    failures: tuple[str, ...]


def clear_index_cache(directory: Path | None, source: Path | None = None) -> IndexCacheCleanup:
    """Remove only index files directly inside the configured cache directory."""
    global _cache_generation
    if directory is None or not directory.is_dir():
        return IndexCacheCleanup(0, ())
    directory = directory.resolve()
    paths = (
        (_cache_path(source.resolve(), 0, directory),)
        if source is not None
        else directory.glob("*.aida-index.npz")
    )
    removed = 0
    failures = []
    with _cache_lock:
        _cache_generation += 1
        for path in paths:
            if not _INDEX_FILENAME.fullmatch(path.name) or path.is_symlink() or path.is_dir():
                continue
            try:
                path.unlink()
                removed += 1
            except FileNotFoundError:
                continue
            except OSError as exc:
                failures.append(str(exc))
    return IndexCacheCleanup(removed, tuple(failures))


@dataclass(frozen=True, slots=True)
class FrameTimestamp:
    index: int
    stream_index: int
    pts: int | None
    dts: int | None
    time_base: str | None
    seconds: float
    key_frame: bool
    picture_type: str | None
    is_corrupt: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TimestampIndex:
    def __init__(self, frames: Iterable[FrameTimestamp], *, decoder: str = "cpu") -> None:
        self.decoder = decoder
        self._frames = tuple(frames)
        pts = tuple(frame.pts for frame in self._frames)
        self.has_unambiguous_pts = all(value is not None for value in pts) and len(set(pts)) == len(
            pts
        )
        self._seconds = tuple(frame.seconds for frame in self._frames)
        if any(
            current < previous
            for previous, current in zip(self._seconds, self._seconds[1:], strict=False)
        ):
            raise ValueError("Frame timestamps must be monotonically ordered")

    def __len__(self) -> int:
        return len(self._frames)

    def __getitem__(self, index: int) -> FrameTimestamp:
        return self._frames[index]

    def nearest_at_or_after(self, seconds: float) -> FrameTimestamp:
        if not self._frames:
            raise IndexError("Timestamp index is empty")
        position = min(bisect_left(self._seconds, seconds), len(self._frames) - 1)
        return self._frames[position]

    @classmethod
    def build(
        cls,
        source_path: Path,
        *,
        video_stream: int = 0,
        on_frame: Callable[[int], None] | None = None,
        cache_directory: Path | None = None,
        hardware_acceleration: bool = False,
        reuse_cache: bool = True,
        _generation: int | None = None,
    ) -> TimestampIndex:
        path = source_path.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        cache_path = _cache_path(path, video_stream, cache_directory)
        with _cache_lock:
            generation = _cache_generation if _generation is None else _generation
        if cache_path is not None and reuse_cache:
            cached = _load_cache(cache_path, path)
            if cached is not None:
                return cls(cached, decoder="cache")
        entries: list[FrameTimestamp] = []
        try:
            options: dict[str, Any] = {}
            if hardware_acceleration:
                # Raw hardware frames preserve provenance and avoid pixel downloads.
                # Older PyAV cannot do this; never accept its metadata-losing transfer.
                options["hwaccel"] = HWAccel(
                    "d3d11va", allow_software_fallback=True, is_hw_owned=True
                )
            with av.open(str(path), mode="r", **options) as container:
                stream = container.streams.video[video_stream]
                stream.thread_type = "AUTO"
                for index, frame in enumerate(container.decode(video=video_stream)):
                    if on_frame is not None:
                        on_frame(index)
                    time_base = frame.time_base or stream.time_base
                    entries.append(frame_timestamp_from_av(index, stream.index, frame, time_base))
                decoder = "d3d11va" if stream.codec_context.is_hwaccel else "cpu"
        except (av.error.FFmpegError, OSError, ValueError, IndexError, TypeError) as exc:
            if hardware_acceleration:
                LOGGER.info("index_cpu_fallback", extra={"reason": str(exc)})
                return cls.build(
                    path,
                    video_stream=video_stream,
                    on_frame=on_frame,
                    cache_directory=cache_directory,
                    hardware_acceleration=False,
                    reuse_cache=reuse_cache,
                    _generation=generation,
                )
            raise MediaOpenError(f"Could not index video timestamps: {path}") from exc
        if cache_path is not None:
            with _cache_lock:
                if generation == _cache_generation:
                    _write_cache(cache_path, path, entries)
        return cls(entries, decoder=decoder)


def _cache_path(path: Path, video_stream: int, directory: Path | None) -> Path | None:
    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    identity = sha256(f"{path}|{video_stream}".encode()).hexdigest()[:24]
    return directory / f"{identity}.aida-index.npz"


def _load_cache(path: Path, source: Path) -> list[FrameTimestamp] | None:
    if not path.is_file():
        return None
    try:
        stat = source.stat()
        with np.load(path, allow_pickle=False) as data:
            if int(data["source_size"][0]) != stat.st_size:
                return None
            if int(data["source_mtime_ns"][0]) != stat.st_mtime_ns:
                return None
            # Convert NumPy scalars in bulk; intern repeated provenance strings.
            columns = [
                data[name].tolist()
                for name in (
                    "stream_index",
                    "pts",
                    "dts",
                    "time_base",
                    "seconds",
                    "key_frame",
                    "picture_type",
                    "is_corrupt",
                )
            ]
            missing = np.iinfo(np.int64).min
            bases: dict[str, str | None] = {"": None}
            pictures: dict[str, str | None] = {"": None}
            return [
                FrameTimestamp(
                    index=index,
                    stream_index=stream,
                    pts=None if pts == missing else pts,
                    dts=None if dts == missing else dts,
                    time_base=bases.setdefault(base, base),
                    seconds=seconds,
                    key_frame=key,
                    picture_type=pictures.setdefault(picture, picture),
                    is_corrupt=corrupt,
                )
                for index, (stream, pts, dts, base, seconds, key, picture, corrupt) in enumerate(
                    zip(*columns, strict=True)
                )
            ]
    except (OSError, ValueError, KeyError):
        return None


def _write_cache(path: Path, source: Path, frames: list[FrameTimestamp]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    missing = np.iinfo(np.int64).min
    stat = source.stat()
    try:
        with temporary.open("wb") as handle:
            np.savez(
                handle,
                source_size=np.asarray([stat.st_size], dtype=np.int64),
                source_mtime_ns=np.asarray([stat.st_mtime_ns], dtype=np.int64),
                stream_index=np.asarray([item.stream_index for item in frames], dtype=np.int16),
                pts=np.asarray([missing if item.pts is None else item.pts for item in frames]),
                dts=np.asarray([missing if item.dts is None else item.dts for item in frames]),
                time_base=np.asarray([item.time_base or "" for item in frames], dtype="U32"),
                seconds=np.asarray([item.seconds for item in frames], dtype=np.float64),
                key_frame=np.asarray([item.key_frame for item in frames], dtype=np.bool_),
                picture_type=np.asarray([item.picture_type or "" for item in frames], dtype="U8"),
                is_corrupt=np.asarray([item.is_corrupt for item in frames], dtype=np.bool_),
            )
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)


def frame_timestamp_from_av(
    index: int,
    stream_index: int,
    frame: av.VideoFrame,
    time_base: Fraction | None,
) -> FrameTimestamp:
    seconds = float(frame.pts * time_base) if frame.pts is not None and time_base else 0.0
    picture_type = str(frame.pict_type) if frame.pict_type is not None else None
    time_base_text = f"{time_base.numerator}/{time_base.denominator}" if time_base else None
    return FrameTimestamp(
        index=index,
        stream_index=stream_index,
        pts=frame.pts,
        dts=frame.dts,
        time_base=time_base_text,
        seconds=seconds,
        key_frame=frame.key_frame,
        picture_type=picture_type,
        is_corrupt=frame.is_corrupt,
    )
