from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dg_fps.analyzers.cadence import CadenceAnalysisResult, content_cadence_readings

SCHEMA_VERSION = "1.4"


@dataclass(frozen=True, slots=True)
class ReportPaths:
    project_directory: Path
    analysis_json: Path
    report_json: Path

    @property
    def llm_report_json(self) -> Path:
        return self.project_directory / "llm_report.json"


class CadenceJsonWriter:
    def __init__(self, *, app_name: str, app_version: str) -> None:
        self._application = {"name": app_name, "version": app_version}

    def write(
        self,
        result: CadenceAnalysisResult,
        *,
        source_metadata: dict[str, Any],
        projects_root: Path,
    ) -> ReportPaths:
        source = result.source_path.resolve()
        project_id = _project_id(source)
        project_directory = project_directory_for_source(source, projects_root)
        project_directory.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(UTC).isoformat()
        project = {
            "id": project_id,
            "title": source.stem,
            "generated_at": generated_at,
        }
        source_data = {
            "filename": source.name,
            "path": str(source),
            "size_bytes": source.stat().st_size,
            "metadata": source_metadata,
        }
        analyzer = {"id": result.analyzer_id, "version": result.analyzer_version}
        findings = [finding.to_dict() for finding in result.findings]
        presentation = {
            "style_id": "cadence_fluency",
            "measurement": {
                "metric": "content_updates_per_complete_presentation_period",
                "window_seconds": 1.0,
                "classification": "heuristic_visual_change_with_measured_timing",
                "unknown_policy": "null_not_zero",
                "quality_thresholds": None,
                "minimum_complete_update_intervals": 2,
                "static_timeout_seconds": None,
                "retention_policy": "preserve_full_duration_cause_undetermined",
                "summary_weighting": "complete_update_count_divided_by_complete_period_seconds",
                "summary_includes_closed_observable_holds": True,
                "scope_change_policy": "break_periods_and_report_ambiguous_time",
                "coverage_weighting": "timestamp_duration_not_frame_count",
                "repeated_scope": "raw_visual_change_decision",
                "cadence_repeated_scope": "contextual_scene_witness_decision",
                "public_update_decision": "contextual_presentation_repeated",
                "estimated_unique_fps_scope": "raw_pair_change_auxiliary_not_public_fps",
                "extended_hold_ratio": 1.5,
                "capture_ceiling": "observed_intervals_per_second_not_nominal_metadata",
                "frame_generation": "rendered_and_interpolated_frames_not_distinguishable",
            },
            "semantics": "capture_visual_cadence_not_engine_fps",
            "public_output": {
                "format": "continuous_fluency_chart",
                "narration": "none",
            },
        }

        analysis_document = {
            "schema_version": SCHEMA_VERSION,
            "application": self._application,
            "project": project,
            "source": source_data,
            "analyzer": analyzer,
            "parameters": asdict(result.parameters),
            "summary": result.summary.to_dict(),
            "presentation": presentation,
            "selected_ranges": [asdict(item) for item in result.frame_ranges],
            "segment_summaries": {
                label: summary.to_dict() for label, summary in result.segment_summaries.items()
            },
            "frames": [sample.to_dict() for sample in result.samples],
            "events": [event.to_dict() for event in result.events],
            "content_cadence": {
                str(index): asdict(reading)
                for index, reading in content_cadence_readings(result.samples).items()
            },
            "findings": findings,
            "assets": {},
            "limitations": list(result.limitations),
            "provenance": {
                "generated_at": generated_at,
                "method": (
                    "decoded-frame pixel/structure comparison, motion alignment verification, "
                    "complete content-update periods"
                ),
            },
        }
        report_document = {
            "schema_version": SCHEMA_VERSION,
            "application": self._application,
            "project": project,
            "source": source_data,
            "environment": {
                "operating_system": platform.platform(),
                "python": sys.version.split()[0],
            },
            "analysis_summary": {
                "analyzer": analyzer,
                **result.summary.to_dict(),
                "repeated_frame_events": len(result.events),
                "selected_ranges": [asdict(item) for item in result.frame_ranges],
                "segments": {
                    label: summary.to_dict() for label, summary in result.segment_summaries.items()
                },
            },
            "presentation": presentation,
            "findings": findings,
            "evidence": [],
            "assets": {},
            "limitations": list(result.limitations),
        }
        analysis_path = project_directory / "analysis.json"
        report_path = project_directory / "report.json"
        _write_atomic_json(analysis_path, analysis_document)
        _write_atomic_json(report_path, report_document)
        return ReportPaths(project_directory, analysis_path, report_path)

    def register_asset(
        self,
        paths: ReportPaths,
        *,
        name: str,
        asset_path: Path,
        metadata: dict[str, Any],
    ) -> None:
        for path in (paths.analysis_json, paths.report_json):
            with path.open("r", encoding="utf-8") as handle:
                document = json.load(handle)
            assets = document.setdefault("assets", {})
            assets[name] = {"path": str(asset_path.resolve()), **metadata}
            _write_atomic_json(path, document)


def _project_id(source: Path) -> str:
    stat = source.stat()
    identity = f"{source}|{stat.st_size}|{stat.st_mtime_ns}".encode()
    return hashlib.sha256(identity).hexdigest()[:16]


def project_directory_for_source(source: Path, projects_root: Path) -> Path:
    resolved = source.resolve()
    project_id = _project_id(resolved)
    return projects_root.resolve() / f"{_safe_name(resolved.stem)}_{project_id[:8]}"


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned[:80] or "video"


def _write_atomic_json(path: Path, document: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    temporary.replace(path)
