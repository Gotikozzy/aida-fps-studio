"""Representative navigation images; never an input to measurement or export."""

from __future__ import annotations

import logging
import math
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, closing
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from pathlib import Path

import av
import cv2
import numpy as np
from numpy.typing import NDArray

from dg_fps.core.errors import MediaOpenError
from dg_fps.media.media_probe import MediaMetadata
from dg_fps.media.timestamp_index import TimestampIndex, _cache_path, _load_cache

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NavigationFrame:
    source_path: Path
    source_size: int
    source_mtime_ns: int
    requested_seconds: float
    stream_index: int
    pts: int
    time_base: Fraction
    key_frame: bool
    rgb: NDArray[np.uint8]

    @property
    def seconds(self) -> float:
        return float(self.pts * self.time_base)


def navigation_span(metadata: MediaMetadata) -> tuple[float, float] | None:
    stream = metadata.video_streams[0]
    duration = stream.duration_seconds or metadata.duration_seconds
    start = stream.start_time_seconds or 0.0
    if duration is None or not math.isfinite(duration) or duration <= 0 or not math.isfinite(start):
        return None
    return start, duration


def initial_navigation_times(metadata: MediaMetadata) -> tuple[float, ...]:
    span = navigation_span(metadata)
    if span is None:
        return ()
    start, duration = span
    return tuple(start + duration * ratio for ratio in (0.0, 0.2, 0.4, 0.6, 0.8, 0.95))


def cached_timestamp_index(source: Path, directory: Path | None) -> TimestampIndex | None:
    if directory is None:
        return None
    try:
        path = _cache_path(source.resolve(), 0, directory)
        frames = _load_cache(path, source)
        return None if not frames else TimestampIndex(frames, decoder="cache")
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        LOGGER.info("navigation_index_cache_unavailable", exc_info=True)
        return None


class NavigationReader:
    def __init__(self, source: Path, cache_directory: Path | None = None) -> None:
        self.source = source.resolve()
        stat = self.source.stat()
        self.identity = (stat.st_size, stat.st_mtime_ns)
        self.directory = cache_directory

    def _check_source(self) -> None:
        stat = self.source.stat()
        if (stat.st_size, stat.st_mtime_ns) != self.identity:
            raise MediaOpenError("O vídeo mudou durante a preparação da prévia")

    def frames(
        self,
        times: Sequence[float],
        *,
        max_size: tuple[int, int] = (160, 90),
        check_cancelled: Callable[[], None],
    ) -> Iterator[NavigationFrame]:
        if min(max_size) < 1 or len(times) > 8 or not all(math.isfinite(t) for t in times):
            raise ValueError("Invalid navigation preview request")
        with ExitStack() as stack:
            db = None
            if self.directory is not None and max_size == (160, 90):
                try:
                    self.directory.mkdir(parents=True, exist_ok=True)
                    db = stack.enter_context(
                        closing(
                            sqlite3.connect(
                                self.directory / "aida-navigation-v1.sqlite3", timeout=0.1
                            )
                        )
                    )
                    db.execute(
                        "CREATE TABLE IF NOT EXISTS previews ("
                        "id INTEGER PRIMARY KEY, key TEXT UNIQUE NOT NULL, "
                        "pts INTEGER, base TEXT, stream INTEGER, keyframe INTEGER, image BLOB)"
                    )
                except (OSError, sqlite3.Error):
                    LOGGER.debug("navigation_cache_unavailable", exc_info=True)
                    db = None
            container = None
            for seconds in times:
                check_cancelled()
                self._check_source()
                cache_key = sha256(
                    repr(
                        (
                            str(self.source),
                            self.identity,
                            seconds,
                            max_size,
                            "cpu-slice-representative-v1",
                        )
                    ).encode()
                ).hexdigest()
                cached = self._cached(db, cache_key, seconds)
                if cached is not None:
                    check_cancelled()
                    self._check_source()
                    yield cached
                    continue
                try:
                    if container is None:
                        container = stack.enter_context(av.open(str(self.source), "r"))
                        container.streams.video[0].thread_type = "SLICE"
                    stream = container.streams.video[0]
                    if stream.time_base is None:
                        raise MediaOpenError("Base temporal indisponível para a prévia")
                    container.seek(
                        round(seconds / stream.time_base),
                        stream=stream,
                        backward=True,
                        any_frame=False,
                    )
                    for examined, frame in enumerate(container.decode(video=0)):
                        check_cancelled()
                        if examined >= 64:
                            raise MediaOpenError("Prévia temporal indisponível neste ponto")
                        base = frame.time_base or stream.time_base
                        if frame.pts is None or frame.is_corrupt or base is None:
                            continue
                        scale = min(max_size[0] / frame.width, max_size[1] / frame.height, 1)
                        rgb = frame.reformat(
                            width=max(1, round(frame.width * scale)),
                            height=max(1, round(frame.height * scale)),
                            format="rgb24",
                        ).to_ndarray(format="rgb24")
                        result = NavigationFrame(
                            self.source,
                            *self.identity,
                            seconds,
                            stream.index,
                            frame.pts,
                            base,
                            frame.key_frame,
                            rgb,
                        )
                        self._check_source()
                        self._store(db, cache_key, result)
                        check_cancelled()
                        yield result
                        break
                    else:
                        raise MediaOpenError("Nenhuma imagem disponível para a prévia")
                except (av.error.FFmpegError, OSError, ValueError, IndexError) as exc:
                    raise MediaOpenError("Não foi possível preparar a prévia temporal") from exc

    def _cached(
        self, db: sqlite3.Connection | None, key: str, seconds: float
    ) -> NavigationFrame | None:
        if db is None:
            return None
        try:
            row = db.execute(
                "SELECT pts, base, stream, keyframe, image FROM previews WHERE key=?", (key,)
            ).fetchone()
            if row:
                rgb = cv2.imdecode(np.frombuffer(row[4], np.uint8), cv2.IMREAD_COLOR)
                base = Fraction(row[1])
                if (
                    rgb is not None
                    and base > 0
                    and isinstance(row[0], int)
                    and isinstance(row[2], int)
                    and row[2] >= 0
                    and rgb.shape[0] <= 90
                    and rgb.shape[1] <= 160
                    and math.isfinite(float(row[0] * base))
                ):
                    return NavigationFrame(
                        self.source,
                        *self.identity,
                        seconds,
                        row[2],
                        row[0],
                        base,
                        bool(row[3]),
                        cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB),
                    )
        except (sqlite3.Error, cv2.error, ValueError, TypeError, ZeroDivisionError, OverflowError):
            LOGGER.debug("navigation_cache_miss", exc_info=True)
        return None

    @staticmethod
    def _store(db: sqlite3.Connection | None, key: str, frame: NavigationFrame) -> None:
        if db is None:
            return
        try:
            ok, encoded = cv2.imencode(
                ".jpg", cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85]
            )
            if ok:
                db.execute(
                    "INSERT OR REPLACE INTO previews (key,pts,base,stream,keyframe,image) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        key,
                        frame.pts,
                        str(frame.time_base),
                        frame.stream_index,
                        int(frame.key_frame),
                        encoded.tobytes(),
                    ),
                )
                db.execute("DELETE FROM previews WHERE id <= (SELECT max(id)-2048 FROM previews)")
                db.commit()
        except (sqlite3.Error, cv2.error):
            LOGGER.debug("navigation_cache_write_failed", exc_info=True)
