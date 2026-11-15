"""User deliveries, separate from internal project evidence and analysis logic."""

from __future__ import annotations

import hashlib
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from dg_fps.analyzers.cadence import cadence_advance_map
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.jobs.worker import ProgressReporter
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.presentation.cadence_video import CadenceVideoExporter
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.presentation.frame_timeline import build_frame_timeline, export_references
from dg_fps.presentation.second_timeline import build_second_timeline, second_key
from dg_fps.reports.llm_report import write_llm_report
from dg_fps.service import AnalysisSession, FPSService


@dataclass(frozen=True)
class Delivery:
    paths: tuple[Path, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedAnalysis:
    session: AnalysisSession
    points: tuple


def prepare_analysis(session: AnalysisSession, token: CancellationToken) -> PreparedAnalysis:
    references = export_references(session.analysis, session.automatic_references)
    points = build_frame_timeline(session.analysis, references, token.raise_if_cancelled)
    return PreparedAnalysis(session, tuple(p for values in points.values() for p in values))


def render_preview(
    session: AnalysisSession,
    references: dict,
    language: str,
    frame_index: int,
    token: CancellationToken,
):
    exporter = CadenceVideoExporter(language, export_references(session.analysis, references))
    result = session.analysis
    if not result.samples:
        raise ValueError("Nenhum quadro legível nos trechos selecionados.")
    points = build_frame_timeline(result, exporter.references, token.raise_if_cancelled)
    sample = next((s for s in result.samples if s.frame_index == frame_index), None)
    if sample is None:
        if any(r.start_frame <= frame_index <= r.end_frame for r in result.frame_ranges):
            raise ValueError(f"Quadro {frame_index} indisponível na seleção.")
        sample = result.samples[0]
    frames = points[sample.segment]
    seconds = build_second_timeline(
        result.samples,
        session.timestamp_index,
        exporter.references,
        result.summary.container_fps,
        token.raise_if_cancelled,
    )
    exporter._active_second = next(
        s for s in seconds[sample.segment] if s.second == second_key(sample.timestamp_seconds)
    )
    exporter._chart_frames = deque(
        p for p in frames if sample.timestamp_seconds - 6 <= p.seconds <= sample.timestamp_seconds
    )
    exporter._graph_start = frames[0].seconds
    provider = FrameProvider(result.source_path, timestamp_index=session.timestamp_index)
    rgb = provider.frame_by_index(sample.frame_index).rgb
    token.raise_if_cancelled()
    motion = None
    if sample.frame_index > 0 and (
        not result.unavailable_frame_count or sample.similarity_to_previous is not None
    ):
        previous = provider.frame_by_index(sample.frame_index - 1).rgb
        motion = cadence_advance_map(previous, rgb, evidence=sample.flow_parameters)
    return exporter._compose(
        rgb,
        sample,
        sample.segment,
        result.summary.container_fps,
        exporter._active_second.measured_fps,
        (),
        (),
        motion,
    )


def publish_copy(source: Path, target: Path, token: CancellationToken) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == target.resolve():
        return
    with NamedTemporaryFile(dir=target.parent, suffix=".tmp", delete=False) as output:
        temporary = Path(output.name)
        try:
            digest = hashlib.sha256()
            with source.open("rb") as data:
                while block := data.read(1024 * 1024):
                    token.raise_if_cancelled()
                    output.write(block)
                    digest.update(block)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            output.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        with temporary.open("rb") as data:
            if hashlib.file_digest(data, "sha256").digest() != digest.digest():
                raise OSError("Falha ao verificar arquivo de entrega")
        token.raise_if_cancelled()
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def export_delivery(
    service: FPSService,
    session: AnalysisSession,
    target: Path,
    kind: str,
    mode: str,
    language: str,
    references: dict[str, ContentReference],
    token: CancellationToken,
    report: ProgressReporter,
) -> Delivery:
    if kind not in {"both", "video", "report"}:
        raise ValueError("Formato de entrega inválido")
    stat = session.analysis.source_path.stat()
    if (stat.st_size, stat.st_mtime_ns) != (session.source_size, session.source_mtime_ns):
        raise ValueError("O vídeo foi alterado. Abra e analise novamente antes de exportar.")
    if target.suffix.lower() in {".mp4", ".json"}:
        target = target.with_suffix("")
    targets = [target.with_name(target.name + ".mp4")] if kind != "report" else []
    if kind != "video":
        targets.append(target.with_name(target.name + ".json"))
    if session.analysis.source_path.resolve() in [p.resolve() for p in targets]:
        raise ValueError("A entrega não pode substituir o vídeo original")
    warnings = ()
    video = None
    if kind != "report":
        internal = session.reports.project_directory / "exports" / uuid4().hex / "video.mp4"
        video = service.export(
            session,
            internal,
            mode,
            token,
            lambda value, message: report(min(95, value * 95 // 100), message),
            language=language,
            references=references,
        )
        warnings = video.warnings
    else:
        token.raise_if_cancelled()
        report(40, "Preparando relatório LLM")
        write_llm_report(
            session.analysis,
            session.timestamp_index,
            session.reports.llm_report_json,
            session.reports.analysis_json,
            references,
        )
    for output in targets:
        report(97, "Gravando entrega")
        original = video.path if output.suffix == ".mp4" else session.reports.llm_report_json
        publish_copy(original, output, token)
    token.mark_committed()
    return Delivery(tuple(targets), warnings)
