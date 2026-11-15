"""Controlled 59.94 Hz fixture: a real cadence change and an explicitly simulated gap."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, replace
from fractions import Fraction
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import av
import numpy as np
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import QApplication

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.service import FPSService


def main() -> None:
    proof = Path("build/second-video-v050")
    proof.mkdir(parents=True, exist_ok=True)
    source = proof / "source-5994.mp4"
    rate = Fraction(60000, 1001)
    texture = np.random.default_rng(73).integers(30, 220, (192, 320, 3), np.uint8)
    if not source.exists():
        with av.open(str(source), "w") as container:
            stream = container.add_stream("libx264", rate=rate)
            stream.width, stream.height, stream.pix_fmt = 320, 192, "yuv420p"
            stream.options = {"preset": "ultrafast", "crf": "18"}
            advances = Fraction(0)
            for number in range(601):
                elapsed = number / float(rate)
                advances += Fraction(30, 1) / rate if 2 <= elapsed < 3 else 1
                image = np.roll(texture, int(advances) * 3, axis=1)
                frame = av.VideoFrame.from_ndarray(image, "rgb24")
                frame.pts, frame.time_base = 144 * 60000 + number * 1001, Fraction(1, 60000)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    service = FPSService()
    index = TimestampIndex.build(source)
    base = service.analyze(
        source,
        MediaProbe().probe(source),
        index,
        (AnalysisFrameRange(0, 600, "Trecho 1"),),
        proof / "original_reports",
        "auto",
        None,
        CancellationToken(),
        lambda *_: None,
    )
    # A labelled test fixture, not a change to the original analyzer result. Keeps
    # real local-motion evidence to reproduce movement plus unavailable cadence.
    original_samples = asdict(base.analysis)
    fixture = replace(
        base.analysis,
        samples=tuple(
            replace(sample, signal_state="uncertain_change")
            if 149 <= sample.timestamp_seconds < 150
            else sample
            for sample in base.analysis.samples
        ),
    )
    references = {"Trecho 1": ContentReference(60, "manual", "user_reference")}
    reports = service.writer.write(
        fixture,
        source_metadata={"synthetic_fixture": True, "simulated_unavailable_interval": [149, 150]},
        projects_root=proof / "fixture_reports",
    )
    session = replace(base, analysis=fixture, reports=reports, automatic_references=references)
    before = json.loads(reports.analysis_json.read_text("utf-8"))
    asset = service.export(
        session,
        proof / "second-presentation.mp4",
        "auto",
        CancellationToken(),
        lambda *_: None,
        language="pt",
        references=references,
    )
    after = json.loads(reports.analysis_json.read_text("utf-8"))
    before.pop("assets", None)
    after.pop("assets", None)
    assert before == after and asdict(base.analysis) == original_samples
    mapping_path = next(proof.glob("second-presentation_*_assets/frames.json"))
    mapping = json.loads(mapping_path.read_text("utf-8"))
    windows = mapping["presentation_seconds"]["Trecho 1"]
    unavailable = next(value for value in windows if value["second"] == 149)
    assert unavailable["origin"] == "reference" and unavailable["measured_fps"] is None
    assert unavailable["displayed_fps"] == 60
    reference_frames = [
        value["output_frame"] for value in mapping["frames"] if value["presentation_second"] == 149
    ]
    snapshot_frame = reference_frames[len(reference_frames) // 2]
    assert any(
        value["measured_fps"] is not None and value["measured_fps"] < 40 for value in windows
    )
    with av.open(str(asset.path)) as video:
        decoded_count = 0
        for number, frame in enumerate(video.decode(video=0)):
            expected = index[number].seconds - index[0].seconds
            assert abs(float(frame.pts * frame.time_base) - expected) <= 1 / 90000 + 1e-9
            decoded_count += 1
            if number == snapshot_frame:
                rgb = frame.to_ndarray(format="rgb24")
                image = QImage(
                    rgb.data,
                    rgb.shape[1],
                    rgb.shape[0],
                    rgb.strides[0],
                    QImage.Format.Format_RGB888,
                ).copy()
                assert image.save(str(proof / "reference-pt.png"))
        assert decoded_count == 601
    result = {
        "status": "passed",
        "synthetic_fixture": True,
        "frames": decoded_count,
        "codec": asset.codec,
        "analysis_unchanged": True,
        "simulated_unavailable_interval": [149, 150],
        "reference_bucket": unavailable,
        "seconds": windows,
        "video": str(asset.path),
        "mapping": str(mapping_path),
    }
    (proof / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "seconds"}, indent=2))
    app.quit()


if __name__ == "__main__":
    main()
