"""Versioned, data-only AIDA projects. Media and regenerable caches stay external."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from dg_fps import __version__
from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.analyzers.cadence import (
    CadenceAnalysisResult,
    CadenceParameters,
    CadenceSample,
    CadenceSummary,
    RepeatedFrameEvent,
)
from dg_fps.core.enums import Classification
from dg_fps.core.finding import AnalyzerIdentity, Finding, Interpretation, Observation, TimeRange
from dg_fps.core.roi import RectangleROI
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.reports.cadence_json import ReportPaths

REPORT_NAMES = ("analysis.json", "report.json", "llm_report.json", "content_reference.json")


@dataclass(frozen=True)
class ProjectData:
    path: Path
    state: dict
    reports: dict[str, bytes]

    def source(self, replacement: Path | None = None) -> tuple[Path, bool]:
        candidates = (
            [replacement]
            if replacement
            else [
                self.path.parent / self.state.get("relative_source", ""),
                Path(self.state["source"]),
            ]
        )
        for candidate in candidates:
            if candidate is not None and candidate.is_file():
                stat = candidate.stat()
                valid = (stat.st_size, stat.st_mtime_ns) == (
                    self.state["source_size"],
                    self.state["source_mtime_ns"],
                )
                return candidate.resolve(), valid
        raise FileNotFoundError(self.state["source"])


def save_project(
    path: Path,
    state: dict,
    reports: ReportPaths | None,
    token: CancellationToken,
) -> Path:
    path = path.resolve()
    source = Path(state["source"])
    if path == source.resolve():
        raise ValueError("O projeto não pode substituir o vídeo original")
    stat = source.stat()
    manifest = {
        **state,
        "format": "aida-project",
        "version": 1,
        "application": {"name": "AIDA FPS Studio", "version": __version__},
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "relative_source": os.path.relpath(source, path.parent)
        if source.drive.lower() == path.drive.lower()
        else str(source),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix=".aida.tmp", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "project.json", json.dumps(manifest, ensure_ascii=False, allow_nan=False)
            )
            if reports:
                for name in REPORT_NAMES:
                    token.raise_if_cancelled()
                    file = reports.project_directory / name
                    if file.is_file():
                        archive.write(file, f"reports/{name}")
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        token.raise_if_cancelled()
        temporary.replace(path)
        token.mark_committed()
        return path
    finally:
        temporary.unlink(missing_ok=True)


def read_project(path: Path) -> ProjectData:
    with ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 1_000_000_000:
            raise ValueError("Projeto excede o tamanho suportado")
        manifest = json.loads(archive.read("project.json"))
        if not isinstance(manifest, dict):
            raise ValueError("Manifesto de projeto inválido")
        if manifest.get("format") != "aida-project" or manifest.get("version") != 1:
            raise ValueError("Formato ou versão de projeto não suportado")
        if not isinstance(manifest.get("source"), str) or not manifest["source"]:
            raise ValueError("Projeto sem vídeo de origem")
        for key in ("source_size", "source_mtime_ns"):
            if not isinstance(manifest.get(key), int) or manifest[key] < 0:
                raise ValueError("Identidade da origem inválida")
        if not isinstance(manifest.get("overrides", {}), dict):
            raise ValueError("Referências de projeto inválidas")
        for value in (manifest.get("target"), *manifest.get("overrides", {}).values()):
            if value is not None and (
                not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
            ):
                raise ValueError("Referência de projeto inválida")
        ranges = tuple(AnalysisFrameRange(**v) for v in manifest.get("ranges", []))
        ordered = sorted(ranges, key=lambda r: r.start_frame)
        if any(a.end_frame >= b.start_frame for a, b in zip(ordered, ordered[1:], strict=False)):
            raise ValueError("Trechos sobrepostos no projeto")
        if len({v.label for v in ranges}) != len(ranges):
            raise ValueError("Nomes de trechos duplicados")
        reports = {
            name: archive.read(f"reports/{name}")
            for name in REPORT_NAMES
            if f"reports/{name}" in archive.namelist()
        }
    return ProjectData(path.resolve(), manifest, reports)


def result_from_document(document: dict, source: Path) -> CadenceAnalysisResult:
    findings = []
    for value in document.get("findings", []):
        row = dict(value)
        row["analyzer"] = AnalyzerIdentity(**row["analyzer"])
        row["classification"] = Classification(row["classification"])
        row["range"] = TimeRange(**row["range"])
        row["observations"] = tuple(Observation(**v) for v in row.get("observations", []))
        row["interpretations"] = tuple(Interpretation(**v) for v in row.get("interpretations", []))
        if row.get("region"):
            row["region"] = RectangleROI(**{k: v for k, v in row["region"].items() if k != "type"})
        row["limitations"] = tuple(row.get("limitations", []))
        findings.append(Finding(**row))
    return CadenceAnalysisResult(
        document["analyzer"]["id"],
        document["analyzer"]["version"],
        source,
        CadenceParameters(**document["parameters"]),
        CadenceSummary(**document["summary"]),
        tuple(CadenceSample(**v) for v in document["frames"]),
        tuple(RepeatedFrameEvent(**v) for v in document["events"]),
        tuple(findings),
        tuple(document["limitations"]),
        tuple(AnalysisFrameRange(**v) for v in document["selected_ranges"]),
        {k: CadenceSummary(**v) for k, v in document["segment_summaries"].items()},
    )


def restore_reports(project: ProjectData, directory: Path) -> ReportPaths:
    directory.mkdir(parents=True, exist_ok=False)
    for name, content in project.reports.items():
        (directory / name).write_bytes(content)
    return ReportPaths(directory, directory / "analysis.json", directory / "report.json")
