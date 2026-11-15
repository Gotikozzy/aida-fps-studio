"""Re-export stored frame measurements without rerunning or changing the analyzer."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import av
from platformdirs import user_cache_path
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import QApplication

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.analyzers.cadence import (
    CadenceAnalysisResult,
    CadenceParameters,
    CadenceSample,
    CadenceSummary,
    RepeatedFrameEvent,
)
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.cadence_video import CadenceVideoExporter
from dg_fps.presentation.export_verification import verify_mp4
from dg_fps.reports.llm_report import write_llm_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    protected = [
        args.analysis,
        args.analysis.with_name("report.json"),
        args.analysis.with_name("content_reference.json"),
        args.analysis.with_name("fps_1080p.mp4"),
    ]
    hashes = {p: sha256(p.read_bytes()).hexdigest() for p in protected if p.is_file()}
    data = json.loads(args.analysis.read_text("utf-8"))
    result = CadenceAnalysisResult(
        analyzer_id=data["analyzer"]["id"],
        analyzer_version=data["analyzer"]["version"],
        source_path=Path(data["source"]["path"]),
        parameters=CadenceParameters(**data["parameters"]),
        summary=CadenceSummary(**data["summary"]),
        samples=tuple(CadenceSample(**row) for row in data["frames"]),
        events=tuple(RepeatedFrameEvent(**row) for row in data["events"]),
        findings=(),  # Not consumed by the renderer; original findings stay in the report.
        limitations=tuple(data["limitations"]),
        frame_ranges=tuple(AnalysisFrameRange(**row) for row in data["selected_ranges"]),
        segment_summaries={
            label: CadenceSummary(**row) for label, row in data["segment_summaries"].items()
        },
    )
    original_samples = [asdict(s) for s in result.samples]
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    index = TimestampIndex.build(
        result.source_path, cache_directory=user_cache_path("DG FPS", "DG")
    )
    print(f"Index: {index.decoder}, {len(index)} frames", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_llm_report(result, index, args.output.parent / "llm_report.json", args.analysis)
    last_progress = -10

    def progress(value: int, message: str) -> None:
        nonlocal last_progress
        if value >= last_progress + 10:
            print(f"{value}% {message}", flush=True)
            last_progress = value

    asset = CadenceVideoExporter().export(
        result.source_path,
        index,
        result,
        args.output,
        check_cancelled=lambda: None,
        report_progress=progress,
        encoding_mode="auto",
    )
    mapping_path = args.output.parent / f"{args.output.stem}_images/frames.json"
    mapping = json.loads(mapping_path.read_text("utf-8"))
    verify_mp4(
        args.output,
        frames=len(result.samples),
        last_pts=mapping["frames"][-1]["output_pts"],
        width=asset.width,
        height=asset.height,
        check_cancelled=lambda: None,
    )
    with av.open(str(args.output)) as video:
        count = 0
        for number, frame in enumerate(video.decode(video=0)):
            source_frame = mapping["frames"][number]["source"]
            assert source_frame["index"] == result.samples[number].frame_index
            assert source_frame["pts"] == result.samples[number].pts
            expected = mapping["frames"][number]["output_pts"] / 90000
            assert abs(float(frame.pts * frame.time_base) - expected) < 1 / 90000
            count += 1
            if number in (120, 240, 360):
                rgb = frame.to_ndarray(format="rgb24")
                QImage(
                    rgb.data,
                    rgb.shape[1],
                    rgb.shape[0],
                    rgb.shape[1] * 3,
                    QImage.Format.Format_RGB888,
                ).copy().save(str(args.output.with_name(f"preview-{number}.png")))
    assert count == len(result.samples)
    assert [asdict(s) for s in result.samples] == original_samples
    assert all(sha256(p.read_bytes()).hexdigest() == digest for p, digest in hashes.items())
    proof = {
        "frames": count,
        "source_index": index.decoder,
        "codec": asset.codec,
        "originals_unchanged": True,
        "samples_unchanged": True,
        "original_sha256": {str(p): h for p, h in hashes.items()},
        "references": mapping["content_references"],
        "chart_points": {k: len(v) for k, v in mapping["presentation_frames"].items()},
    }
    args.output.with_suffix(".verification.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(proof, ensure_ascii=False), flush=True)
    del app


if __name__ == "__main__":
    main()
