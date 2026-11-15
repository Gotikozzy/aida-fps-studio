"""Prove capture 60 / content 30 stays measured at 30 with an inferred reference."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import av
import numpy as np
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from dg_fps.analyzers.base import AnalysisContext
from dg_fps.analyzers.cadence import CadenceAnalyzer, content_cadence_readings
from dg_fps.backends import select_backend
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.presentation.cadence_video import CadenceVideoExporter
from dg_fps.presentation.content_targets import content_references, reference_state


def main() -> None:
    output = Path("build/content-reference-v040")
    output.mkdir(parents=True, exist_ok=True)
    source = output / "capture60-content30.mkv"
    texture = np.random.default_rng(808).integers(30, 220, (192, 320, 3), np.uint8)
    with av.open(str(source), "w") as container:
        stream = container.add_stream("ffv1", rate=60)
        stream.width, stream.height, stream.pix_fmt = 320, 192, "bgr0"
        for index in range(241):
            frame = av.VideoFrame.from_ndarray(np.roll(texture, 3 * (index // 2), axis=1), "rgb24")
            frame.pts, frame.time_base = index, Fraction(1, 60)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    backend = select_backend("auto")
    try:
        result = CadenceAnalyzer(backend=backend).analyze(AnalysisContext(source.resolve(), 60.0))
    finally:
        close = getattr(backend, "close", None)
        if close is not None:
            close()
    before = asdict(result)
    references = content_references(result)
    label = next(iter(references))
    assert references[label].target_fps == 30 and asdict(result) == before
    assert reference_state(result.summary.content_fps, references[label], 60) == "near_reference"
    assert abs(result.summary.content_fps - 30) < 0.2
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    sample = result.samples[-1]
    readings = content_cadence_readings(result.samples)
    reading = readings[sample.frame_index]
    rgb = FrameProvider(source).frame_by_index(sample.frame_index).rgb
    for language in ("pt", "en"):
        image = CadenceVideoExporter(language, references)._compose(
            rgb,
            sample,
            label,
            60,
            reading.content_fps,
            tuple(readings[item.frame_index].content_fps for item in result.samples[-180:]),
            tuple(not item.presentation_repeated for item in result.samples[-60:]),
            None,
            reading.status,
            coverage=result.summary.observable_window_ratio,
            ambiguous_seconds=result.summary.ambiguous_seconds,
        )
        assert image.save(str(output / f"reference-{language}.png"))
    proof = {
        "capture_fps": 60,
        "content_fps": result.summary.content_fps,
        "references": {label: reference.to_dict() for label, reference in references.items()},
        "measurement_unchanged": True,
        "status": "near_reference",
    }
    (output / "results.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    print(json.dumps(proof, indent=2))
    app.quit()


if __name__ == "__main__":
    main()
