from __future__ import annotations

import json
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from dg_fps.analyzers.cadence import (
    CadenceAnalysisResult,
    CadenceSample,
    content_cadence_readings,
)
from dg_fps.core.errors import MediaOpenError
from dg_fps.jobs.cpu_pipeline import cpu_lookahead
from dg_fps.media.frame_provider import DecodedFrame, FrameProvider
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.content_targets import (
    ContentReference,
)
from dg_fps.presentation.fps_display import DISPLAY_POLICY
from dg_fps.presentation.frame_timeline import (
    FRAME_GRAPH_POLICY,
    PresentationFrame,
    build_frame_timeline,
    export_references,
)
from dg_fps.presentation.motion_map import AdvanceMapRenderer
from dg_fps.presentation.renderer import qimage_to_video_frame
from dg_fps.presentation.second_timeline import (
    SECOND_POLICY,
    PresentationSecond,
    build_second_timeline,
    second_key,
)
from dg_fps.presentation.video_encoder import add_video_stream
from dg_fps.presentation.video_layout import draw_frame_graph, draw_header
from dg_fps.presentation.video_text import VideoText


@dataclass(frozen=True, slots=True)
class CadenceVideoAsset:
    path: Path
    width: int
    height: int
    codec: str
    keyframe_paths: tuple[Path, ...]
    language: str = "pt"
    branding: str = "AIDA"
    warnings: tuple[str, ...] = ()


class CadenceVideoExporter:
    width = 1920
    height = 1080

    def __init__(
        self, language: str = "pt", references: dict[str, ContentReference] | None = None
    ) -> None:
        self.text = VideoText(language)
        self.language = language
        self.references = dict(references) if references is not None else None
        self._active_second: PresentationSecond | None = None
        self._chart_seconds: tuple[PresentationSecond, ...] = ()
        self._chart_frames: deque[PresentationFrame] = deque()
        self._graph_start = 0.0

    def export(
        self,
        source_path: Path,
        timestamp_index: TimestampIndex,
        result: CadenceAnalysisResult,
        output_path: Path,
        *,
        check_cancelled: Callable[[], None],
        report_progress: Callable[[int, str], None],
        encoding_mode: str = "cpu",
    ) -> CadenceVideoAsset:
        output = output_path.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        image_root = output.parent / f"{output.stem}_images"
        image_root.mkdir(parents=True, exist_ok=True)
        self.references = export_references(result, self.references)
        nominal_fps = result.summary.container_fps or 30.0
        rate = Fraction(nominal_fps).limit_denominator(1001)
        timelines = build_second_timeline(
            result.samples, timestamp_index, self.references, nominal_fps, check_cancelled
        )
        frame_timelines = build_frame_timeline(result, self.references, check_cancelled)
        sample_map = {sample.frame_index: sample for sample in result.samples}
        selected_keyframes: dict[int, Path] = {}
        for segment_index, frame_range in enumerate(result.frame_ranges, start=1):
            segment_directory = image_root / f"segment_{segment_index:02d}"
            segment_directory.mkdir(parents=True, exist_ok=True)
            segment_samples = [
                sample for sample in result.samples if sample.segment == frame_range.label
            ]
            segment_events = sorted(
                (
                    event
                    for event in result.events
                    if event.segment == frame_range.label
                    and event.cadence_role in {"extended_hold", "partial_scene_hold"}
                ),
                key=lambda event: event.repeated_frames,
                reverse=True,
            )[:6]
            if segment_events:
                for event in segment_events:
                    selected_keyframes[event.end_frame] = segment_directory
            else:
                peak = segment_samples[len(segment_samples) // 2].frame_index
                selected_keyframes[peak] = segment_directory
        keyframes: list[Path] = []
        total_frames = sum(frame_range.frame_count for frame_range in result.frame_ranges)
        processed = 0
        output_offset = 0.0
        provenance: list[dict[str, object]] = []
        output_time_base = Fraction(1, 90000)
        last_output_pts = -1
        provider = FrameProvider(source_path, timestamp_index=timestamp_index)
        with av.open(str(output), mode="w") as container:
            encoder = add_video_stream(
                container,
                rate=rate,
                width=self.width,
                height=self.height,
                quality=18,
                mode=encoding_mode,
            )
            stream = encoder.stream

            def render_frames() -> Iterator[av.VideoFrame]:
                nonlocal processed, output_offset, last_output_pts
                for frame_range in result.frame_ranges:
                    segment_start = timestamp_index[frame_range.start_frame].seconds
                    seconds = timelines[frame_range.label]
                    seconds_by_key = {value.second: value for value in seconds}
                    frame_points = {p.frame_index: p for p in frame_timelines[frame_range.label]}
                    self._chart_frames.clear()
                    self._graph_start = segment_start
                    advance_renderer = AdvanceMapRenderer()
                    frames = _export_frames(
                        provider, frame_range.start_frame, frame_range.end_frame, check_cancelled
                    )
                    with closing(frames):
                        for decoded in frames:
                            check_cancelled()
                            sample = sample_map[decoded.timestamp.index]
                            self._active_second = seconds_by_key[
                                second_key(sample.timestamp_seconds)
                            ]
                            self._chart_frames.append(frame_points[sample.frame_index])
                            while (
                                len(self._chart_frames) > 1
                                and self._chart_frames[1].seconds < sample.timestamp_seconds - 6
                            ):
                                self._chart_frames.popleft()
                            current_fps = self._active_second.measured_fps
                            advance_map = advance_renderer.render(
                                decoded.rgb, sample.flow_parameters
                            )
                            image = self._compose(
                                decoded.rgb,
                                sample,
                                frame_range.label,
                                nominal_fps,
                                current_fps,
                                (),
                                (),
                                advance_map,
                                "presentation_second",
                                0,
                                result.segment_summaries[frame_range.label].observable_window_ratio,
                                result.segment_summaries[frame_range.label].ambiguous_seconds,
                            )
                            if sample.frame_index in selected_keyframes:
                                keyframe_path = selected_keyframes[sample.frame_index] / (
                                    f"frame_{sample.frame_index:08d}.png"
                                )
                                if not image.save(str(keyframe_path)):
                                    raise OSError(f"Não foi possível salvar: {keyframe_path}")
                                keyframes.append(keyframe_path)
                            video_frame = qimage_to_video_frame(image)
                            output_seconds = (
                                output_offset + decoded.timestamp.seconds - segment_start
                            )
                            output_pts = round(output_seconds / output_time_base)
                            if output_pts <= last_output_pts:
                                raise ValueError(
                                    "Tempos não crescentes no trecho; exportação interrompida"
                                )
                            last_output_pts = output_pts
                            video_frame.pts = output_pts
                            video_frame.time_base = output_time_base
                            provenance.append(
                                {
                                    "output_frame": processed,
                                    "output_pts": output_pts,
                                    "output_time_base": str(output_time_base),
                                    "segment": frame_range.label,
                                    "presentation_second": self._active_second.second,
                                    "source": decoded.timestamp.to_dict(),
                                }
                            )
                            yield video_frame
                            processed += 1
                            if processed % 10 == 0:
                                progress = min(99, round((processed / total_frames) * 100))
                                report_progress(
                                    progress,
                                    f"Renderizando vídeo 1080p: {processed}/{total_frames}",
                                )
                    end = frame_range.end_frame
                    last_seconds = timestamp_index[end].seconds
                    if end + 1 < len(timestamp_index):
                        duration = timestamp_index[end + 1].seconds - last_seconds
                    else:
                        duration = last_seconds - timestamp_index[end - 1].seconds
                    if duration <= 0:
                        raise ValueError("Duração inválida no fim do trecho")
                    output_offset += last_seconds - segment_start + duration

            with cpu_lookahead(
                render_frames,
                check_cancelled=check_cancelled,
                size_bytes=lambda frame: sum(plane.buffer_size for plane in frame.planes),
                max_bytes=16 * 1024 * 1024,
            ) as rendered:
                for video_frame in rendered:
                    check_cancelled()
                    for packet in stream.encode(video_frame):
                        container.mux(packet)
            if processed != total_frames:
                raise ValueError(f"Exportação incompleta: {processed}/{total_frames} frames")
            report_progress(99, "Finalizando o arquivo MP4")
            check_cancelled()
            for packet in stream.encode():
                check_cancelled()
                container.mux(packet)
        (image_root / "frames.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "fps_display_policy": DISPLAY_POLICY,
                    "second_presentation_policy": SECOND_POLICY,
                    "frame_graph_policy": FRAME_GRAPH_POLICY,
                    "presentation_frames": {
                        label: [value.to_dict() for value in values]
                        for label, values in frame_timelines.items()
                    },
                    "presentation_seconds": {
                        label: [value.to_dict() for value in values]
                        for label, values in timelines.items()
                    },
                    "frames": provenance,
                    "content_references": {
                        label: value.to_dict() for label, value in self.references.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        report_progress(99, "Vídeo codificado; preparando a gravação")
        keyframes.sort()
        return CadenceVideoAsset(
            output,
            self.width,
            self.height,
            encoder.description,
            tuple(keyframes),
            self.language,
            "AIDA",
        )

    def _compose(
        self,
        rgb: np.ndarray,
        sample: CadenceSample,
        segment_label: str,
        nominal_fps: float,
        current_fps: float | None,
        history: tuple[float | None, ...],
        advance_history: tuple[bool, ...],
        advance_map: np.ndarray | None,
        content_status: str = "observable_cadence",
        pending_hold_seconds: float = 0.0,
        coverage: float = 0.0,
        ambiguous_seconds: float = 0.0,
    ) -> QImage:
        canvas = QImage(self.width, self.height, QImage.Format.Format_RGB888)
        canvas.fill(QColor("#080b10"))
        source_height, source_width, _ = rgb.shape
        source = QImage(
            rgb.data,
            source_width,
            source_height,
            source_width * 3,
            QImage.Format.Format_RGB888,
        )
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        scale = min(self.width / source_width, self.height / source_height)
        target_width = source_width * scale
        target_height = source_height * scale
        target = QRectF(
            (self.width - target_width) / 2,
            (self.height - target_height) / 2,
            target_width,
            target_height,
        )
        painter.drawImage(target, source)
        self._draw_header(
            painter,
            segment_label,
            sample,
            nominal_fps,
            current_fps,
            content_status,
            pending_hold_seconds,
        )
        self._draw_advance_map(painter, advance_map, sample.presentation_repeated)
        self._draw_graph(
            painter,
            history,
            advance_history,
            nominal_fps,
            sample.presentation_repeated,
            coverage,
            ambiguous_seconds,
        )
        painter.end()
        return canvas

    def _draw_header(
        self,
        painter: QPainter,
        segment_label: str,
        sample: CadenceSample,
        nominal_fps: float,
        current_fps: float | None,
        content_status: str = "observable_cadence",
        pending_hold_seconds: float = 0.0,
    ) -> None:
        draw_header(
            painter,
            self.text,
            nominal_fps,
            current_fps,
            (self.references or {}).get(segment_label),
            self._active_second,
        )

    def _draw_graph(
        self,
        painter: QPainter,
        history: tuple[float | None, ...],
        advance_history: tuple[bool, ...],
        nominal_fps: float,
        repeated: bool,
        coverage: float = 0.0,
        ambiguous_seconds: float = 0.0,
    ) -> None:
        label = self._active_second.segment if self._active_second is not None else ""
        draw_frame_graph(
            painter,
            self.text,
            self._chart_seconds,
            self._active_second,
            (self.references or {}).get(label),
            nominal_fps,
            frames=tuple(self._chart_frames),
            segment_start=self._graph_start,
        )

    def _draw_advance_map(
        self, painter: QPainter, advance_map: np.ndarray | None, repeated: bool
    ) -> None:
        panel = QRectF(1450, 286, 428, 270)
        painter.fillRect(panel, QColor(8, 12, 18, 228))
        painter.setPen(QPen(QColor("#64748b" if repeated else "#22d3ee"), 2))
        painter.drawRect(panel)
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        painter.setPen(QColor("#f8fafc"))
        painter.drawText(QRectF(1472, 302, 380, 28), self.text("MAPA DE MOVIMENTO"))
        if advance_map is not None:
            height, width = advance_map.shape[:2]
            image = QImage(
                advance_map.data,
                width,
                height,
                width * 3,
                QImage.Format.Format_RGB888,
            ).copy()
            size = image.size().scaled(388, 180, Qt.AspectRatioMode.KeepAspectRatio)
            painter.drawImage(
                QRectF(1664 - size.width() / 2, 340, size.width(), size.height()), image
            )
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(
            QRectF(1470, 532, 388, 20),
            self.text("Movimento entre quadros"),
            Qt.AlignmentFlag.AlignCenter,
        )


def _rolling_fps(samples: tuple[CadenceSample, ...], nominal_fps: float) -> dict[int, float | None]:
    return {
        index: reading.content_fps for index, reading in content_cadence_readings(samples).items()
    }


def _export_frames(
    provider: FrameProvider, start: int, end: int, check_cancelled: Callable[[], None]
) -> Iterator[DecodedFrame]:
    """Use validated CPU threading; recover strictly at the first undelivered frame."""
    index = provider.timestamp_index
    if index.has_unambiguous_pts and all(
        frame.time_base is not None and not frame.is_corrupt for frame in index
    ):
        threaded = FrameProvider(provider.source_path, timestamp_index=index, threaded_decode=True)
        try:
            with closing(
                threaded.frames_in_range(start, end, check_cancelled=check_cancelled)
            ) as frames:
                for frame in frames:
                    start = frame.timestamp.index + 1
                    yield frame
            return
        except MediaOpenError:
            check_cancelled()
    if start <= end:
        with closing(
            provider.frames_in_range(start, end, check_cancelled=check_cancelled)
        ) as frames:
            yield from frames
