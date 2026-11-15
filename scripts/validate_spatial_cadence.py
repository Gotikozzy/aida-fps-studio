"""Reanalyze original clips from LLM provenance into a separate validation directory."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from dg_fps.jobs.gpu_queue import GPUQueue
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.projects import result_from_document
from dg_fps.service import FPSService
from dg_fps.studio_services import render_preview


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("build/v072-real"))
    args = parser.parse_args()
    app = QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    queue = GPUQueue()
    outcomes = []

    def task(token, report):
        for file in args.reports:
            llm = json.loads(file.read_text(encoding="utf-8"))
            original_path = Path(llm["provenance"]["analysis_file"])
            original = original_path.read_bytes()
            document = json.loads(original)
            source = Path(document["source"]["path"])
            old = result_from_document(document, source)
            directory = args.output / source.stem
            directory.mkdir(parents=True, exist_ok=True)
            index = TimestampIndex.build(source, cache_directory=args.output / "cache")
            service = FPSService()
            last_percent = -1

            def progress(percent, message, source=source):
                nonlocal last_percent
                if percent // 10 != last_percent:
                    last_percent = percent // 10
                    print(source.stem, percent, message, flush=True)
                report(percent, message)

            session = service.analyze(
                source,
                MediaProbe().probe(source),
                index,
                old.frame_ranges,
                directory,
                "nvidia",
                None,
                token,
                progress,
            )
            new = session.analysis
            changes = [
                a.frame_index
                for a, b in zip(old.samples, new.samples, strict=True)
                if (a.presentation_repeated, a.signal_state)
                != (b.presentation_repeated, b.signal_state)
            ]
            print(source.stem, "decision changes:", len(changes), flush=True)
            outcome = {
                "source": str(source),
                "original_analysis": str(original_path),
                "new_analysis": str(session.reports.analysis_json),
                "old_summary": asdict(old.summary),
                "new_summary": asdict(new.summary),
                "decision_changes": changes,
                "old_input_unchanged": original_path.read_bytes() == original,
            }
            snapshots = [old.samples[len(old.samples) // 2].frame_index]
            if "Grand Theft" in source.name:
                snapshots = [4069, 4400, 5193]
            for frame in snapshots:
                image = render_preview(session, {}, "pt", frame, token)
                assert image.save(str(directory / f"frame-{frame}.png"))
            outcomes.append(outcome)
            (args.output / "comparison.json").write_text(
                json.dumps(outcomes, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return outcomes

    def done(_, result):
        print("Validation complete:", args.output / "comparison.json", flush=True)
        app.exit(0)

    def failed(_, message):
        print(message, flush=True)
        app.exit(1)

    queue.job_completed.connect(done)
    queue.job_failed.connect(failed)
    queue.submit("Validar evidência espacial", task)
    code = app.exec()
    queue.shutdown(wait=True)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
