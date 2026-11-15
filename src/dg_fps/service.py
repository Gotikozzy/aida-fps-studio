"""FPS workflows, independent of widgets and application state."""

from __future__ import annotations

import errno
import json
import logging
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import av

from dg_fps import __version__
from dg_fps.analyzers.base import AnalysisContext, AnalysisFrameRange
from dg_fps.analyzers.cadence import CadenceAnalysisResult, CadenceAnalyzer
from dg_fps.backends import select_backend
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.jobs.worker import ProgressReporter
from dg_fps.media.media_probe import MediaMetadata
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.cadence_video import CadenceVideoAsset, CadenceVideoExporter
from dg_fps.presentation.content_targets import ContentReference, content_references
from dg_fps.presentation.export_verification import synchronize_file, verify_mp4
from dg_fps.presentation.video_encoder import EncoderUnavailable
from dg_fps.reports.cadence_json import CadenceJsonWriter, ReportPaths
from dg_fps.reports.llm_report import write_llm_report

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalysisSession:
    analysis: CadenceAnalysisResult
    reports: ReportPaths
    timestamp_index: TimestampIndex
    source_size: int
    source_mtime_ns: int
    automatic_references: dict[str, ContentReference] | None = None


class FPSService:
    def __init__(self) -> None:
        self.writer = CadenceJsonWriter(app_name="AIDA FPS Studio", app_version=__version__)

    def analyze(
        self,
        source: Path,
        metadata: MediaMetadata,
        index: TimestampIndex,
        ranges: tuple[AnalysisFrameRange, ...],
        output: Path,
        mode: str,
        library: Path | None,
        token: CancellationToken,
        report: ProgressReporter,
    ) -> AnalysisSession:
        if not ranges:
            raise ValueError("Selecione pelo menos um trecho")
        ordered = sorted(ranges, key=lambda value: value.start_frame)
        for position, value in enumerate(ordered):
            if value.frame_count < 2 or value.end_frame >= len(index):
                raise ValueError("Trecho fora do vídeo ou com menos de dois frames")
            if position and ordered[position - 1].end_frame >= value.start_frame:
                raise ValueError("Os trechos não podem se sobrepor")
        if len({value.label for value in ranges}) != len(ranges):
            raise ValueError("Os nomes dos trechos precisam ser únicos")
        stat = source.stat()
        backend = select_backend(mode, library)
        report(0, f"Analisando: {backend.backend_id}")
        fps = metadata.video_streams[0].average_rate or 0.0
        try:
            result = CadenceAnalyzer(backend=backend).analyze(
                AnalysisContext(source, fps, token.raise_if_cancelled, report, ranges, index)
            )
        finally:
            close = getattr(backend, "close", None)
            if close is not None:
                close()
        token.raise_if_cancelled()
        current = source.stat()
        if (current.st_size, current.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise RuntimeError("O vídeo mudou durante a análise; abra o arquivo novamente")
        # Each analysis has its own directory; later runs never replace previous evidence.
        reports = self.writer.write(
            result,
            source_metadata=metadata.to_dict(),
            projects_root=output / f"analise_{uuid4().hex[:12]}",
        )
        automatic = content_references(result)
        write_llm_report(
            result,
            index,
            reports.llm_report_json,
            reports.analysis_json,
            automatic,
            automatic_references=automatic,
        )
        report(100, "Análise concluída. Confira o resultado antes de exportar.")
        return AnalysisSession(result, reports, index, stat.st_size, stat.st_mtime_ns, automatic)

    def export(
        self,
        session: AnalysisSession,
        output: Path,
        mode: str,
        token: CancellationToken,
        report: ProgressReporter,
        *,
        language: str = "pt",
        references: dict[str, ContentReference] | None = None,
    ) -> CadenceVideoAsset:
        if session.analysis.unavailable_frame_count:
            raise ValueError(
                "A seleção contém quadros ilegíveis. Escolha Somente relatório LLM "
                "ou ajuste os trechos para exportar o vídeo."
            )
        if language not in {"pt", "en"}:
            raise ValueError("Unsupported video language")
        if mode not in {"cpu", "auto", "nvidia"}:
            raise ValueError("Modo de exportação inválido")
        source = session.analysis.source_path
        stat = source.stat()
        if (stat.st_size, stat.st_mtime_ns) != (session.source_size, session.source_mtime_ns):
            raise RuntimeError("O vídeo foi alterado. Abra e analise novamente antes de exportar.")
        output = output.resolve()
        if output == source:
            raise ValueError("O vídeo de saída não pode substituir o vídeo original")
        output.parent.mkdir(parents=True, exist_ok=True)
        fallback_reason = None
        # Render in a temporary directory. Failure/cancellation preserves existing exports.
        with TemporaryDirectory(
            prefix=".dg-fps-", dir=output.parent, ignore_cleanup_errors=True
        ) as temporary:
            staged = Path(temporary) / "video.mp4"
            exporter = CadenceVideoExporter(language=language, references=references)

            def render_progress(value: int, message: str) -> None:
                report(min(90, max(0, value) * 90 // 99), message)

            try:
                asset = exporter.export(
                    source,
                    session.timestamp_index,
                    session.analysis,
                    staged,
                    check_cancelled=token.raise_if_cancelled,
                    report_progress=render_progress,
                    encoding_mode=mode,
                )
            except (av.error.FFmpegError, EncoderUnavailable) as exc:
                if getattr(exc, "errno", None) in {errno.ENOSPC, errno.EACCES, errno.EROFS}:
                    raise RuntimeError(
                        f"Não foi possível gravar o vídeo em {output}: {exc}"
                    ) from exc
                if mode == "cpu":
                    raise
                token.raise_if_cancelled()
                fallback_reason = str(exc)
                LOGGER.warning("encoding_fallback", extra={"reason": fallback_reason})
                report(0, "A aceleração falhou; reiniciando a exportação pela CPU")
                asset = exporter.export(
                    source,
                    session.timestamp_index,
                    session.analysis,
                    staged,
                    check_cancelled=token.raise_if_cancelled,
                    report_progress=render_progress,
                    encoding_mode="cpu",
                )
            token.raise_if_cancelled()
            current = source.stat()
            if (current.st_size, current.st_mtime_ns) != (
                session.source_size,
                session.source_mtime_ns,
            ):
                raise RuntimeError("O vídeo mudou durante a exportação; analise novamente")
            report(91, "Verificando o arquivo MP4")
            assets_directory = output.parent / f"{output.stem[:80]}_{uuid4().hex[:12]}_assets"
            images = staged.parent / f"{staged.stem}_images"
            mapping = json.loads(images.joinpath("frames.json").read_text(encoding="utf-8"))
            expected_frames = sum(value.frame_count for value in session.analysis.frame_ranges)
            if len(mapping["frames"]) != expected_frames:
                raise ValueError("Mapeamento de frames incompleto; exportação interrompida")
            last_pts = mapping["frames"][-1]["output_pts"]
            staged_size = verify_mp4(
                staged,
                frames=expected_frames,
                last_pts=last_pts,
                width=asset.width,
                height=asset.height,
                check_cancelled=token.raise_if_cancelled,
            )
            report(94, "Sincronizando a gravação do vídeo")
            synchronize_file(staged)
            mapping.update(
                {
                    "source": str(source),
                    "analysis": str(session.reports.analysis_json),
                    "codec": asset.codec,
                    "encoding_requested": mode,
                    "fallback_reason": fallback_reason,
                    "audio": "omitted",
                    "video_language": language,
                    "branding": "AIDA",
                }
            )
            images.joinpath("frames.json").write_text(
                json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            report(97, "Gravando o vídeo na pasta escolhida")
            token.raise_if_cancelled()
            # Commit video before exposing it as an asset in the reports.
            images.rename(assets_directory)
            keyframes = tuple(
                assets_directory / path.relative_to(images) for path in asset.keyframe_paths
            )
            try:
                staged.replace(output)
            except OSError as exc:
                with suppress(OSError):
                    assets_directory.rename(images)
                raise RuntimeError(f"Não foi possível gravar o vídeo em {output}: {exc}") from exc
            verify_mp4(
                output,
                frames=expected_frames,
                last_pts=last_pts,
                width=asset.width,
                height=asset.height,
                expected_size=staged_size,
                check_cancelled=lambda: None,
                verify_tail=False,
            )
            token.mark_committed()
        final = replace(asset, path=output, keyframe_paths=keyframes)
        report(99, "Registrando o vídeo nos relatórios")
        try:
            self.writer.register_asset(
                session.reports,
                name=f"video_{uuid4().hex[:8]}",
                asset_path=output,
                metadata={
                    "codec": asset.codec,
                    "frame_provenance": str(assets_directory / "frames.json"),
                    "encoding_requested": mode,
                    "fallback_reason": fallback_reason,
                    "width": asset.width,
                    "height": asset.height,
                    "video_language": language,
                    "branding": "AIDA",
                },
            )
            write_llm_report(
                session.analysis,
                session.timestamp_index,
                session.reports.llm_report_json,
                session.reports.analysis_json,
                exporter.references,
                automatic_references=session.automatic_references,
            )
        except (OSError, ValueError) as exc:
            LOGGER.exception("export_report_registration_failed", extra={"reason": str(exc)})
            final = replace(
                final,
                warnings=(
                    f"O MP4 foi salvo em {output}, "
                    f"mas os relatórios não puderam ser atualizados: {exc}",
                ),
            )
        report(100, f"Vídeo salvo e verificado: {output}")
        return final
