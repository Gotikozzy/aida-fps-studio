from __future__ import annotations

import logging
import math
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event
from uuid import uuid4

import av
from PySide6.QtCore import QObject, Signal, Slot

from dg_fps.core.enums import JobStatus
from dg_fps.core.errors import MediaOpenError
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.jobs.gpu_queue import GPUQueue
from dg_fps.jobs.job_manager import JobManager
from dg_fps.jobs.models import JobRecord
from dg_fps.jobs.worker import ProgressReporter
from dg_fps.media.frame_provider import (
    DecodedFrame,
    FrameProvider,
    VideoThumbnail,
)
from dg_fps.media.media_probe import MediaMetadata, MediaProbe
from dg_fps.media.navigation_preview import (
    NavigationFrame,
    NavigationReader,
    cached_timestamp_index,
    initial_navigation_times,
)
from dg_fps.media.preview import PREVIEW_SIZE, PreviewRegion, build_preview_region, cached_thumbnail
from dg_fps.media.timestamp_index import IndexCacheCleanup, TimestampIndex, clear_index_cache

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MediaOpenResult:
    source_path: Path
    metadata: MediaMetadata
    first_frame: DecodedFrame
    identity: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class NavigationUpdate:
    epoch: str
    frame: NavigationFrame
    request: str | None = None


@dataclass(frozen=True, slots=True)
class NavigationBootstrap:
    source: Path
    epoch: str
    index: TimestampIndex | None = None


@dataclass(frozen=True, slots=True)
class IndexBuildResult:
    source_path: Path
    index: TimestampIndex
    timing_changed: bool | None = None
    refreshed_metadata: MediaMetadata | None = None


@dataclass(frozen=True, slots=True)
class FrameDecodeResult:
    source_path: Path
    frame: DecodedFrame


@dataclass(frozen=True, slots=True)
class FramePrefetchResult:
    source_path: Path
    frame: DecodedFrame


@dataclass(frozen=True, slots=True)
class ThumbnailBuildResult:
    source_path: Path
    thumbnail: VideoThumbnail


@dataclass(frozen=True, slots=True)
class PlaybackCompleteResult:
    source_path: Path
    session_id: str


class MediaController(QObject):
    media_opened = Signal(object, object)
    index_ready = Signal(int)
    index_rebuilt = Signal(bool, object)
    frame_ready = Signal(object)
    frame_unavailable = Signal(str)
    thumbnails_ready = Signal(object)
    thumbnails_failed = Signal(str)
    thumbnail_loading_changed = Signal(bool)
    preview_status = Signal(str)
    progress_changed = Signal(str, int)
    error_occurred = Signal(str)
    navigation_thumbnails_ready = Signal(object)
    navigation_frame_ready = Signal(object)
    navigation_failed = Signal(str)
    _navigation_event = Signal(object)

    _CACHE_LIMIT_BYTES = 256 * 1024 * 1024

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        index_cache_directory: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._jobs = JobManager(self)
        self._jobs.job_changed.connect(self._on_job_changed)
        self._jobs.job_completed.connect(self._on_job_completed)
        self._jobs.job_failed.connect(self._on_job_failed)
        self._gpu_jobs = GPUQueue(self)
        self._gpu_jobs.job_changed.connect(self._on_job_changed)
        self._gpu_jobs.job_completed.connect(self._on_job_completed)
        self._gpu_jobs.job_failed.connect(self._on_job_failed)
        self._gpu_jobs.job_cancelled.connect(self._on_job_cancelled)
        self.hardware_indexing = True
        self._navigation_jobs = JobManager(self, max_threads=1)
        self._navigation_jobs.job_completed.connect(self._on_job_completed)
        self._navigation_jobs.job_failed.connect(self._on_job_failed)
        self._navigation_jobs.job_cancelled.connect(self._on_job_cancelled)
        self._navigation_event.connect(self._on_navigation_update)
        self._navigation_epoch = ""
        self._navigation_bootstrap_id: str | None = None
        self._navigation_seek_id: str | None = None
        self._navigation_request: str | None = None
        self._navigation_frames: list[NavigationFrame] = []
        self._navigation_pending: tuple[Path, MediaMetadata] | None = None
        self._navigation_identity: tuple[int, int] | None = None
        self._navigation_idle = Event()
        self._navigation_idle.set()
        self._source_path: Path | None = None
        self._index_cache_directory = index_cache_directory
        self._provider: FrameProvider | None = None
        self._open_job_id: str | None = None
        self._index_job_id: str | None = None
        self._decode_job_id: str | None = None
        self._prefetch_job_id: str | None = None
        self._thumbnail_job_id: str | None = None
        self._thumbnail_indices: tuple[int, ...] = ()
        self._thumbnails: OrderedDict[int, VideoThumbnail] = OrderedDict()
        self._preview_job_id: str | None = None
        self._preview_request: tuple[int, int, str] | None = None
        self._preview_region: PreviewRegion | None = None
        self._background_suspended = False
        self._playback_job_id: str | None = None
        self._playback_session_id: str | None = None
        self._playback_queue: Queue[DecodedFrame] | None = None
        self._playback_peek: DecodedFrame | None = None
        self._playback_eof = False
        self._playback_prefill = 1
        self._frame_count = 0
        self._last_requested_index: int | None = None
        self._pending_frame_index: int | None = None
        self._prefetch_direction = 1
        self._frame_cache: OrderedDict[int, DecodedFrame] = OrderedDict()
        self._cache_bytes = 0

        self._jobs.job_cancelled.connect(self._on_job_cancelled)

    @property
    def decode_pending(self) -> bool:
        return self._decode_job_id is not None

    @property
    def cached_frame_count(self) -> int:
        return len(self._frame_cache)

    @property
    def playback_exhausted(self) -> bool:
        queue = self._playback_queue
        return (
            self._playback_eof and self._playback_peek is None and (queue is None or queue.empty())
        )

    @property
    def timestamp_index(self) -> TimestampIndex | None:
        if self._provider is None or self._frame_count == 0:
            return None
        return self._provider.timestamp_index

    def open_media(self, source_path: Path) -> None:
        path = source_path.resolve()
        self.stop_playback()
        self._cancel_active_jobs()
        self._navigation_epoch = uuid4().hex
        self._navigation_idle = Event()
        self._navigation_idle.set()
        self._navigation_bootstrap_id = self._navigation_seek_id = None
        self._navigation_request = None
        self._navigation_pending = None
        self._navigation_identity = None
        self._navigation_frames.clear()
        self._reset_presentation()
        self._index_job_id = None
        self._decode_job_id = self._prefetch_job_id = self._thumbnail_job_id = None
        self._source_path = path
        self._provider = None
        self._frame_count = 0
        self._last_requested_index = None
        self._pending_frame_index = None
        self._clear_cache()

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            stat = path.stat()
            report(5, "Lendo metadados")
            metadata = MediaProbe().probe(path)
            token.raise_if_cancelled()
            report(50, "Decodificando primeiro frame")
            first_frame = FrameProvider(path).first_frame(max_size=PREVIEW_SIZE)
            report(100, "Vídeo aberto")
            current = path.stat()
            identity = (stat.st_size, stat.st_mtime_ns)
            if identity != (current.st_size, current.st_mtime_ns):
                raise MediaOpenError("O vídeo mudou durante a abertura")
            return MediaOpenResult(path, metadata, first_frame, identity)

        self._open_job_id = self._jobs.submit("Abrir vídeo", task)

    def request_navigation_time(self, seconds: float) -> None:
        if self._source_path is None or self._frame_count or not math.isfinite(seconds):
            return
        if self._navigation_seek_id is not None:
            self._navigation_jobs.cancel(self._navigation_seek_id)
        if self._navigation_bootstrap_id is not None:
            self._navigation_jobs.cancel(self._navigation_bootstrap_id)
        source, epoch = self._source_path, self._navigation_epoch
        request = self._navigation_request = uuid4().hex
        identity = self._navigation_identity
        self._navigation_idle.clear()

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            reader = NavigationReader(source)
            if reader.identity != identity:
                raise MediaOpenError("O vídeo mudou durante a preparação da prévia")
            with closing(
                reader.frames(
                    (seconds,), max_size=PREVIEW_SIZE, check_cancelled=token.raise_if_cancelled
                )
            ) as frames:
                frame = next(frames)
            token.raise_if_cancelled()
            return NavigationUpdate(epoch, frame, request)

        self._navigation_seek_id = self._navigation_jobs.submit("Buscar prévia temporal", task)

    def _start_navigation(self, source: Path, metadata: MediaMetadata) -> None:
        epoch, identity = self._navigation_epoch, self._navigation_identity
        directory = self._index_cache_directory
        self._navigation_pending = (source, metadata)

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            token.raise_if_cancelled()
            cached = cached_timestamp_index(source, directory)
            if cached is not None:
                token.raise_if_cancelled()
                stat = source.stat()
                if identity != (stat.st_size, stat.st_mtime_ns):
                    raise MediaOpenError("O vídeo mudou durante a abertura")
                return NavigationBootstrap(source, epoch, cached)
            reader = NavigationReader(source, directory)
            if reader.identity != identity:
                raise MediaOpenError("O vídeo mudou durante a preparação da prévia")
            with closing(
                reader.frames(
                    initial_navigation_times(metadata), check_cancelled=token.raise_if_cancelled
                )
            ) as frames:
                for frame in frames:
                    self._navigation_event.emit(NavigationUpdate(epoch, frame))
            token.raise_if_cancelled()
            return NavigationBootstrap(source, epoch)

        self._navigation_bootstrap_id = self._navigation_jobs.submit("Preparando miniaturas", task)

    @Slot(object)
    def _on_navigation_update(self, update: NavigationUpdate) -> None:
        if (
            update.epoch != self._navigation_epoch
            or update.frame.source_path != self._source_path
            or self._frame_count
        ):
            return
        if update.request is not None:
            if update.request == self._navigation_request:
                self.navigation_frame_ready.emit(update.frame)
        else:
            self._navigation_frames.append(update.frame)
            self.navigation_thumbnails_ready.emit(tuple(self._navigation_frames))

    def _finish_navigation_bootstrap(self, *, use_cache: bool = False) -> None:
        pending = self._navigation_pending
        self._navigation_pending = None
        if pending is None or pending[0] != self._source_path or self._frame_count:
            return
        try:
            stat = pending[0].stat()
            if self._navigation_identity != (stat.st_size, stat.st_mtime_ns):
                raise MediaOpenError("O vídeo mudou durante a abertura")
        except (OSError, MediaOpenError) as exc:
            self.error_occurred.emit(str(exc))
            return
        self._start_index(*pending, use_cache=use_cache)

    def request_frame(self, frame_index: int) -> None:
        if (
            self._provider is None
            or self._source_path is None
            or not 0 <= frame_index < self._frame_count
            or self._background_suspended
        ):
            return
        previous = self._last_requested_index
        if self._decode_job_id is not None and previous == frame_index:
            return
        if previous is not None and frame_index != previous:
            self._prefetch_direction = 1 if frame_index > previous else -1
        self._last_requested_index = frame_index
        self._cancel_thumbnail()
        if self._prefetch_job_id is not None:
            self._jobs.cancel(self._prefetch_job_id)
            self._prefetch_job_id = None

        cached = self._cache_get(frame_index)
        if self._decode_job_id is not None:
            self._pending_frame_index = frame_index
            self._jobs.cancel(self._decode_job_id)
            if cached is not None:
                self.frame_ready.emit(cached)
            return
        if cached is not None:
            self.frame_ready.emit(cached)
            self._after_frame(frame_index)
            return
        provider = self._provider
        source_path = self._source_path
        preview = self._preview_region

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            check = token.raise_if_cancelled
            if preview is not None and preview.contains(frame_index):
                try:
                    frame = preview.frame(provider.timestamp_index[frame_index], check)
                    return FrameDecodeResult(source_path, frame)
                except (MediaOpenError, av.error.FFmpegError, OSError):
                    LOGGER.warning("preview_seek_fallback", extra={"frame_index": frame_index})
            frame = provider.frame_by_index(
                frame_index, max_size=PREVIEW_SIZE, check_cancelled=check
            )
            return FrameDecodeResult(source_path, frame)

        self._decode_job_id = self._jobs.submit(f"Frame {frame_index}", task)

    def _after_frame(self, frame_index: int) -> None:
        self._start_thumbnails()
        following = frame_index + self._prefetch_direction
        if self._thumbnail_job_id is not None or self._background_suspended:
            return
        if self._preview_region is None or not self._preview_region.contains(following):
            self._start_prefetch(following)

    def nearby_preview(self, frame_index: int) -> DecodedFrame | None:
        index = self.timestamp_index
        if index is None or not self._frame_cache:
            return None
        time = index[frame_index].seconds
        closest = min(
            self._frame_cache.values(), key=lambda frame: abs(frame.timestamp.seconds - time)
        )
        return closest if abs(closest.timestamp.seconds - time) <= 0.5 else None

    @property
    def playback_buffer_ready(self) -> bool:
        return self._playback_queue is not None and (
            self._playback_eof or self._playback_queue.qsize() >= self._playback_prefill
        )

    def start_playback(
        self,
        start_index: int,
        *,
        buffer_size: int | None = None,
        max_size: tuple[int, int] = (1280, 720),
    ) -> bool:
        if min(max_size) < 1:
            raise ValueError("Preview dimensions must be positive")
        if (
            self._provider is None
            or self._source_path is None
            or not 0 <= start_index < self._frame_count
            or self._background_suspended
        ):
            return False
        if buffer_size is None:
            index = self._provider.timestamp_index
            seconds = index[-1].seconds - index[0].seconds
            fps = (len(index) - 1) / seconds if seconds > 0 else 30.0
            frame_bytes = max_size[0] * max_size[1] * 3
            buffer_size = max(1, min(60, math.ceil(fps * 0.5), 64 * 1024 * 1024 // frame_bytes))
        if buffer_size < 1:
            raise ValueError("Playback buffer size must be positive")
        self.stop_playback()
        if self._decode_job_id is not None:
            self._jobs.cancel(self._decode_job_id)
            self._decode_job_id = None
            self._pending_frame_index = None
        if self._prefetch_job_id is not None:
            self._jobs.cancel(self._prefetch_job_id)
            self._prefetch_job_id = None
        self._cancel_thumbnail()
        provider = self._provider
        preview = self._preview_region
        end_index = self._frame_count - 1
        source_path = self._source_path
        session_id = str(uuid4())
        frame_queue: Queue[DecodedFrame] = Queue(maxsize=buffer_size)
        self._playback_session_id = session_id
        self._playback_queue = frame_queue
        self._playback_peek = None
        self._playback_eof = False
        self._playback_prefill = min(buffer_size, max(1, buffer_size // 3))
        deadline = [float("-inf")]
        self._playback_cutoff = deadline

        def playback_frames(token: CancellationToken) -> Iterator[DecodedFrame]:
            position = start_index
            check = token.raise_if_cancelled

            def cutoff() -> float:
                return deadline[0]

            if preview is not None and preview.contains(position):
                try:
                    yield_until = min(end_index, preview.end)
                    for frame in preview.frames(
                        position,
                        yield_until,
                        provider.timestamp_index.__getitem__,
                        check,
                        max_size,
                        cutoff,
                    ):
                        position = frame.timestamp.index + 1
                        yield frame
                    position = yield_until + 1
                except (MediaOpenError, av.error.FFmpegError, OSError):
                    LOGGER.warning("preview_playback_fallback", extra={"frame_index": position})
            if position > end_index:
                return
            yield from provider.frames_in_range(
                position,
                end_index,
                check_cancelled=check,
                max_size=max_size,
                skip_before_seconds=cutoff,
            )

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            with closing(playback_frames(token)) as frames:
                for frame in frames:
                    while True:
                        token.raise_if_cancelled()
                        try:
                            frame_queue.put(frame, timeout=0.05)
                        except Full:
                            continue
                        break
            return PlaybackCompleteResult(source_path, session_id)

        self._playback_job_id = self._jobs.submit("Reprodução sequencial", task)
        return True

    def stop_playback(self) -> None:
        was_playing = self._playback_session_id is not None
        if self._playback_job_id is not None:
            self._jobs.cancel(self._playback_job_id)
        self._playback_job_id = None
        self._playback_session_id = None
        self._playback_queue = None
        self._playback_peek = None
        self._playback_eof = False
        if was_playing:
            self._start_thumbnails()

    def take_next_playback_frame(self) -> DecodedFrame | None:
        frame = self._playback_peek
        self._playback_peek = None
        if frame is None:
            frame = self._playback_queue_get()
        return frame

    def take_playback_frame_at_or_before(self, seconds: float) -> DecodedFrame | None:
        if self._playback_session_id is not None:
            self._playback_cutoff[0] = seconds - 0.050
        selected: DecodedFrame | None = None
        candidate = self._playback_peek
        self._playback_peek = None
        if candidate is None:
            candidate = self._playback_queue_get()
        while candidate is not None:
            if candidate.timestamp.seconds > seconds:
                self._playback_peek = candidate
                break
            selected = candidate
            candidate = self._playback_queue_get()
        return selected

    def shutdown(self) -> None:
        self.stop_playback()
        self._cancel_active_jobs()
        self._jobs.shutdown(wait=True)
        self._gpu_jobs.shutdown(wait=True)
        self._navigation_jobs.shutdown(wait=True)
        self._clear_cache()
        self._provider = None
        self._source_path = None
        self._pending_frame_index = None

    def cancel_loading(self) -> None:
        self._cancel_active_jobs()
        self._navigation_epoch = uuid4().hex
        self._navigation_bootstrap_id = self._navigation_seek_id = None
        self._navigation_request = None
        self._navigation_pending = None
        self._open_job_id = self._index_job_id = self._decode_job_id = self._thumbnail_job_id = None

    def set_thumbnail_viewport(self, frame_indices: tuple[int, ...]) -> None:
        if frame_indices == self._thumbnail_indices:
            self._start_thumbnails()
            return
        self._cancel_thumbnail()
        self._thumbnail_indices = frame_indices
        self._publish_thumbnails()
        self._start_thumbnails()

    def retry_thumbnails(self) -> None:
        for frame in self._thumbnail_indices:
            item = self._thumbnails.get(frame)
            if item is not None and item.rgb is None:
                del self._thumbnails[frame]
        self._start_thumbnails()

    def suspend_preview_work(self, suspended: bool) -> None:
        if suspended == self._background_suspended:
            return
        self._background_suspended = suspended
        if not suspended:
            if self._preview_request is not None:
                self._start_preview_optimization(*self._preview_request)
            else:
                self._start_thumbnails()
            return
        self._cancel_thumbnail()
        self.stop_playback()
        self._cancel_preview_job()
        self._pending_frame_index = None
        for job_id in (self._decode_job_id, self._prefetch_job_id):
            if job_id is not None:
                self._jobs.cancel(job_id)
        self._decode_job_id = self._prefetch_job_id = None

    def optimize_preview(self, center: int, *, mode: str = "cpu") -> None:
        index = self.timestamp_index
        if index is None or not 0 <= center < len(index) or self._background_suspended:
            return
        self._cancel_thumbnail()
        self.cancel_preview_optimization(resume=False)
        seconds = index[center].seconds
        start = min(center, max(center - 120, index.nearest_at_or_after(seconds - 2).index))
        end = max(center, min(center + 120, index.nearest_at_or_after(seconds + 2).index))
        self._start_preview_optimization(start, end, mode)

    def _start_preview_optimization(self, start: int, end: int, mode: str) -> None:
        provider = self._provider
        if provider is None:
            return
        self._preview_request = (start, end, mode)

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            return build_preview_region(
                provider,
                start,
                end,
                mode,
                token.raise_if_cancelled,
                lambda count: report(round(100 * count / (end - start + 1)), ""),
            )

        manager = self._gpu_jobs if mode == "nvidia" else self._jobs
        self._preview_job_id = manager.submit("Otimizar prévia", task)
        self.preview_status.emit("Otimizando prévia da região…")

    def cancel_preview_optimization(self, *, resume: bool = True) -> None:
        if self._preview_request is not None:
            self._cancel_preview_job()
            self._preview_request = None
            self.preview_status.emit("Otimização da prévia cancelada.")
            if resume:
                self._start_thumbnails()

    def _cancel_preview_job(self) -> None:
        if self._preview_job_id is not None:
            self._jobs.cancel(self._preview_job_id)
            self._gpu_jobs.cancel(self._preview_job_id)
            self._preview_job_id = None

    def _reset_presentation(self) -> None:
        self.cancel_preview_optimization(resume=False)
        self._preview_region = None
        self._thumbnail_indices = ()
        self._thumbnails.clear()
        self._thumbnail_job_id = None
        self._decode_job_id = self._prefetch_job_id = None

    def clear_all_cached_indexes(self) -> IndexCacheCleanup:
        return clear_index_cache(self._index_cache_directory)

    def reindex(self, metadata: MediaMetadata) -> None:
        if self._source_path is None:
            return
        self.stop_playback()
        self.cancel_loading()
        self._prefetch_job_id = None
        self._pending_frame_index = None
        self._reset_presentation()
        self._start_index(self._source_path, metadata, rebuild=True)

    def _start_index(
        self,
        source_path: Path,
        metadata: MediaMetadata,
        *,
        rebuild: bool = False,
        use_cache: bool = True,
    ) -> None:
        expected_frames = metadata.video_streams[0].declared_frames or 0
        hardware_acceleration = self.hardware_indexing
        previous = self.timestamp_index if rebuild else None
        navigation_idle = self._navigation_idle

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            initial_stat = source_path.stat()

            def on_frame(frame_index: int) -> None:
                token.raise_if_cancelled()
                while not navigation_idle.wait(0.02):
                    token.raise_if_cancelled()
                if frame_index % 10 != 0:
                    return
                progress = (
                    min(99, int(((frame_index + 1) / expected_frames) * 100))
                    if expected_frames > 0
                    else 0
                )
                report(progress, f"Indexando frame {frame_index + 1}")

            token.raise_if_cancelled()
            refreshed_metadata = None
            if rebuild:
                stat = source_path.stat()
                cleanup = clear_index_cache(self._index_cache_directory, source_path)
                if cleanup.failures:
                    raise OSError("\n".join(cleanup.failures))
                refreshed_metadata = MediaProbe().probe(source_path)
            index = TimestampIndex.build(
                source_path,
                on_frame=on_frame,
                cache_directory=self._index_cache_directory,
                hardware_acceleration=hardware_acceleration,
                reuse_cache=use_cache and not rebuild,
            )
            token.raise_if_cancelled()
            final_stat = source_path.stat()
            if (initial_stat.st_size, initial_stat.st_mtime_ns) != (
                final_stat.st_size,
                final_stat.st_mtime_ns,
            ):
                clear_index_cache(self._index_cache_directory, source_path)
                raise ValueError("O vídeo mudou durante a indexação.")
            if not len(index):
                raise ValueError("Não foi possível ler o vídeo")
            timing_changed = None
            if rebuild:
                current_stat = source_path.stat()
                if (stat.st_size, stat.st_mtime_ns) != (
                    current_stat.st_size,
                    current_stat.st_mtime_ns,
                ):
                    clear_index_cache(self._index_cache_directory, source_path)
                    raise ValueError("O vídeo mudou durante a reindexação.")
                timing_changed = previous is not None and (
                    len(previous) != len(index)
                    or any(
                        (a.stream_index, a.pts, a.time_base, a.seconds, a.is_corrupt)
                        != (b.stream_index, b.pts, b.time_base, b.seconds, b.is_corrupt)
                        for a, b in zip(previous, index, strict=True)
                    )
                )
            report(100, f"Índice concluído: {len(index)} frames")
            return IndexBuildResult(source_path, index, timing_changed, refreshed_metadata)

        manager = self._gpu_jobs if hardware_acceleration else self._jobs
        self._index_job_id = manager.submit("Indexar timestamps", task)

    def _cancel_active_jobs(self) -> None:
        self._navigation_idle.set()
        for job_id in (
            self._navigation_bootstrap_id,
            self._navigation_seek_id,
            self._open_job_id,
            self._index_job_id,
            self._decode_job_id,
            self._prefetch_job_id,
            self._thumbnail_job_id,
            self._playback_job_id,
            self._preview_job_id,
        ):
            if job_id is not None:
                self._jobs.cancel(job_id)
                self._gpu_jobs.cancel(job_id)
                self._navigation_jobs.cancel(job_id)

    @Slot(object)
    def _on_job_changed(self, record: JobRecord) -> None:
        if record.id in (self._open_job_id, self._index_job_id) and record.message:
            self.progress_changed.emit(record.message, record.progress)
        if (
            record.id == self._preview_job_id
            and record.status == JobStatus.RUNNING
            and record.progress
        ):
            self.preview_status.emit(f"Otimizando prévia da região… {record.progress}%")

    @Slot(str, object)
    def _on_job_completed(self, job_id: str, result: object) -> None:
        if isinstance(result, NavigationUpdate):
            if job_id != self._navigation_seek_id:
                return
            self._navigation_seek_id = None
            self._navigation_idle.set()
            self._on_navigation_update(result)
            return
        if isinstance(result, NavigationBootstrap):
            if (
                job_id != self._navigation_bootstrap_id
                or result.epoch != self._navigation_epoch
                or result.source != self._source_path
            ):
                return
            self._navigation_bootstrap_id = None
            if result.index is None:
                self._finish_navigation_bootstrap()
            else:
                self._navigation_pending = None
                self._index_job_id = job_id
                self._on_job_completed(job_id, IndexBuildResult(result.source, result.index))
            return
        if isinstance(result, MediaOpenResult):
            if result.source_path != self._source_path or job_id != self._open_job_id:
                return
            self._provider = FrameProvider(result.source_path, hardware_acceleration=False)
            self._navigation_identity = result.identity
            self.media_opened.emit(result.metadata, result.first_frame)
            self._start_navigation(result.source_path, result.metadata)
        elif isinstance(result, IndexBuildResult):
            if result.source_path != self._source_path or job_id != self._index_job_id:
                return
            self._provider = FrameProvider(
                result.source_path,
                timestamp_index=result.index,
                threaded_decode=True,
            )
            self._frame_count = len(result.index)
            if self._navigation_seek_id is not None:
                self._navigation_jobs.cancel(self._navigation_seek_id)
                self._navigation_seek_id = None
            self._navigation_request = None
            self._navigation_idle.set()
            self._navigation_frames.clear()
            if result.timing_changed is not None:
                self._clear_cache()
                self.index_rebuilt.emit(result.timing_changed, result.refreshed_metadata)
            self.index_ready.emit(len(result.index))
        elif isinstance(result, FrameDecodeResult):
            if result.source_path != self._source_path or job_id != self._decode_job_id:
                return
            self._decode_job_id = None
            self._cache_put(result.frame)
            if self._pending_frame_index is not None:
                self._dispatch_pending_frame()
            elif not self._background_suspended:
                self.frame_ready.emit(result.frame)
                self._after_frame(result.frame.timestamp.index)
        elif isinstance(result, FramePrefetchResult):
            if result.source_path != self._source_path or job_id != self._prefetch_job_id:
                return
            self._prefetch_job_id = None
            self._cache_put(result.frame)
        elif isinstance(result, ThumbnailBuildResult):
            if result.source_path != self._source_path or job_id != self._thumbnail_job_id:
                return
            self._thumbnail_job_id = None
            frame = result.thumbnail.timestamp.index
            self._thumbnails[frame] = result.thumbnail
            self._thumbnails.move_to_end(frame)
            while len(self._thumbnails) > 96:
                self._thumbnails.popitem(last=False)
            self._publish_thumbnails()
            self._start_thumbnails()
        elif isinstance(result, PreviewRegion):
            if job_id != self._preview_job_id:
                return
            self._preview_job_id = None
            self._preview_request = None
            self._preview_region = result
            self.preview_status.emit(
                "Prévia otimizada (NVIDIA)."
                if result.encoder == "h264_nvenc"
                else "Prévia otimizada (CPU)."
            )
            self._start_thumbnails()
        elif isinstance(result, PlaybackCompleteResult):
            if (
                result.source_path != self._source_path
                or result.session_id != self._playback_session_id
                or job_id != self._playback_job_id
            ):
                return
            self._playback_job_id = None
            self._playback_eof = True

    @Slot(str, str)
    def _on_job_failed(self, job_id: str, error: str) -> None:
        if job_id == self._navigation_bootstrap_id:
            self._navigation_bootstrap_id = None
            LOGGER.info("navigation_bootstrap_fallback", extra={"reason": error})
            self._finish_navigation_bootstrap()
            return
        if job_id == self._navigation_seek_id:
            self._navigation_seek_id = None
            self._navigation_idle.set()
            self.navigation_failed.emit(error)
            self.preview_status.emit("Prévia temporal indisponível. A indexação continua.")
            return
        if job_id == self._prefetch_job_id:
            self._prefetch_job_id = None
            return
        if job_id == self._thumbnail_job_id:
            self._thumbnail_job_id = None
            self.thumbnail_loading_changed.emit(False)
            self.thumbnails_failed.emit(error)
            return
        if job_id == self._preview_job_id:
            request = self._preview_request
            self._preview_job_id = None
            self._preview_request = None
            if request is not None and request[2] == "nvidia":
                self._start_preview_optimization(request[0], request[1], "cpu")
                self.preview_status.emit("NVIDIA indisponível para a prévia. Tentando pela CPU…")
            else:
                self.preview_status.emit("Prévia otimizada indisponível. Usando o original.")
                self._start_thumbnails()
            return
        if job_id == self._playback_job_id:
            self._playback_job_id = None
            self._playback_eof = True
            self.frame_unavailable.emit(error)
            return
        if job_id in (self._open_job_id, self._index_job_id, self._decode_job_id):
            if job_id == self._decode_job_id:
                self._decode_job_id = None
                if self._pending_frame_index is not None:
                    self._dispatch_pending_frame()
                    return
                self.frame_unavailable.emit(error)
                self._start_thumbnails()
                return
            self.error_occurred.emit(error)

    @Slot(str)
    def _on_job_cancelled(self, job_id: str) -> None:
        if job_id == self._navigation_bootstrap_id:
            self._navigation_bootstrap_id = None
            self._finish_navigation_bootstrap(use_cache=True)
        if job_id == self._navigation_seek_id:
            self._navigation_seek_id = None
            self._navigation_idle.set()
        if job_id == self._decode_job_id:
            self._decode_job_id = None
            self._dispatch_pending_frame()
            self._start_thumbnails()
        if job_id == self._prefetch_job_id:
            self._prefetch_job_id = None
        if job_id == self._thumbnail_job_id:
            self._thumbnail_job_id = None
        if job_id == self._playback_job_id:
            self._playback_job_id = None

    def _publish_thumbnails(self) -> None:
        self.thumbnails_ready.emit(
            [
                self._thumbnails[frame]
                for frame in self._thumbnail_indices
                if frame in self._thumbnails
            ]
        )

    def _cancel_thumbnail(self) -> None:
        if self._thumbnail_job_id is not None:
            self._jobs.cancel(self._thumbnail_job_id)
            self._thumbnail_job_id = None

    def _start_thumbnails(self) -> None:
        if (
            self._provider is None
            or self._source_path is None
            or self._background_suspended
            or self._thumbnail_job_id is not None
            or self._decode_job_id is not None
            or self._playback_session_id is not None
            or self._preview_job_id is not None
        ):
            return
        frame_index = next(
            (frame for frame in self._thumbnail_indices if frame not in self._thumbnails), None
        )
        if frame_index is None:
            self.thumbnail_loading_changed.emit(False)
            return
        provider, source = self._provider, self._source_path
        directory = self._index_cache_directory

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            try:
                thumbnail = cached_thumbnail(
                    directory, source, provider, frame_index, token.raise_if_cancelled
                )
            except MediaOpenError as exc:
                LOGGER.warning("Thumbnail frame %s unavailable: %s", frame_index, exc)
                thumbnail = VideoThumbnail(provider.timestamp_index[frame_index], None)
            return ThumbnailBuildResult(source, thumbnail)

        self._thumbnail_job_id = self._jobs.submit("Gerar miniatura", task)
        self.thumbnail_loading_changed.emit(True)

    def _start_prefetch(self, frame_index: int) -> None:
        if (
            self._provider is None
            or self._source_path is None
            or not 0 <= frame_index < self._frame_count
            or frame_index in self._frame_cache
        ):
            return
        provider = self._provider
        source_path = self._source_path

        def task(token: CancellationToken, report: ProgressReporter) -> object:
            token.raise_if_cancelled()
            frame = provider.frame_by_index(
                frame_index, max_size=PREVIEW_SIZE, check_cancelled=token.raise_if_cancelled
            )
            token.raise_if_cancelled()
            return FramePrefetchResult(source_path, frame)

        self._prefetch_job_id = self._jobs.submit(f"Prefetch frame {frame_index}", task)

    def _cache_get(self, frame_index: int) -> DecodedFrame | None:
        frame = self._frame_cache.get(frame_index)
        if frame is not None:
            self._frame_cache.move_to_end(frame_index)
        return frame

    def _cache_put(self, frame: DecodedFrame) -> None:
        frame_index = frame.timestamp.index
        previous = self._frame_cache.pop(frame_index, None)
        if previous is not None:
            self._cache_bytes -= previous.rgb.nbytes
        self._frame_cache[frame_index] = frame
        self._cache_bytes += frame.rgb.nbytes
        while self._cache_bytes > self._CACHE_LIMIT_BYTES and len(self._frame_cache) > 1:
            _, removed = self._frame_cache.popitem(last=False)
            self._cache_bytes -= removed.rgb.nbytes

    def _clear_cache(self) -> None:
        self._frame_cache.clear()
        self._cache_bytes = 0

    def _dispatch_pending_frame(self) -> None:
        frame_index = self._pending_frame_index
        self._pending_frame_index = None
        if frame_index is not None and self._provider is not None:
            self.request_frame(frame_index)

    def _playback_queue_get(self) -> DecodedFrame | None:
        queue = self._playback_queue
        if queue is None:
            return None
        try:
            return queue.get_nowait()
        except Empty:
            return None
