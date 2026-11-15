"""Render the actual native workspace with an existing, unmodified measurement."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from platformdirs import user_cache_path
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.content_targets import content_references
from dg_fps.projects import result_from_document, save_project
from dg_fps.reports.cadence_json import ReportPaths
from dg_fps.service import AnalysisSession
from dg_fps.studio_services import prepare_analysis, render_preview
from dg_fps.ui.main_window import FPSWindow
from dg_fps.ui.theme import ANALYST_STYLE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--language", choices=("pt", "en"), default="pt")
    args = parser.parse_args()
    app = QApplication([])
    app.setStyleSheet(ANALYST_STYLE)
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    proof = Path("build/studio-real") / args.language
    proof.mkdir(parents=True, exist_ok=True)
    original = args.analysis.read_bytes()
    data = json.loads(original)
    source = Path(data["source"]["path"])
    result = result_from_document(data, source)
    index = TimestampIndex.build(source, cache_directory=user_cache_path("DG FPS", "DG"))
    reports = proof / "reports"
    reports.mkdir(exist_ok=True)
    for name in ("analysis.json", "report.json", "content_reference.json", "llm_report.json"):
        if args.analysis.with_name(name).is_file():
            shutil.copy2(args.analysis.with_name(name), reports / name)
    stat = source.stat()
    session = AnalysisSession(
        result,
        ReportPaths(reports, reports / "analysis.json", reports / "report.json"),
        index,
        stat.st_size,
        stat.st_mtime_ns,
        content_references(result),
    )
    prepared = prepare_analysis(session, CancellationToken())
    w = FPSWindow(proof / "data", proof / "cache", language=args.language)
    w.resize(1600, 960)
    w._show_project_workspace()
    w.source = source
    provider = FrameProvider(source, timestamp_index=index)
    w.media._provider = provider
    w.media._frame_count = len(index)
    frame = result.samples[min(360, len(result.samples) - 1)].frame_index
    w._media_opened(MediaProbe().probe(source), provider.frame_by_index(frame))
    w._index_ready(len(index))
    w.file_label.setText(source.name)
    w._show_frame(provider.frame_by_index(frame))
    w.panel.set_ranges(result.frame_ranges, index)
    thumbs = [provider.thumbnail_by_index(round(i * (len(index) - 1) / 18)) for i in range(19)]
    w._thumbnails_ready(thumbs)
    w.job_id = "proof"
    w._restoring = True
    w._job_completed("proof", prepared)
    w.panel._range_list.setCurrentRow(0)
    w.timeline.zoom_control.setValue(75)
    w.show()
    app.processEvents()
    project = proof / "minha_analise.aida"
    save_project(project, w._state(), session.reports, CancellationToken())
    w.project_path = project
    w._dirty = False
    w._update_project_title()
    app.processEvents()
    w.grab().save(str(proof / "analysis.png"))
    refs = content_references(result)
    image = render_preview(session, refs, args.language, frame, CancellationToken())
    w.workspaces.setCurrentIndex(1)
    app.processEvents()
    w.export_preview.set_image(image)
    app.processEvents()
    w.grab().save(str(proof / "export.png"))
    w.workspaces.setCurrentIndex(0)
    w.process_dialog.message.setText(
        "Analisando trechos…" if args.language == "pt" else "Analyzing ranges…"
    )
    w.process_dialog.bar.setValue(48)
    w.process_dialog.open()
    app.processEvents()
    w.process_dialog.grab().save(str(proof / "process.png"))
    w.process_dialog.hide()
    w.close()
    assert args.analysis.read_bytes() == original
    print(f"Native UI proof: {proof.resolve()}")


if __name__ == "__main__":
    main()
