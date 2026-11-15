"""Write/reopen CPU and optional NVIDIA MP4 on the selected volume, with Unicode paths."""

from __future__ import annotations

import argparse
import json
import os
import time
from fractions import Fraction
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import av
import numpy as np
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.service import FPSService
from dg_fps.ui.main_window import FPSWindow
from dg_fps.ui.theme import ANALYST_STYLE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--proof", type=Path, default=Path("build/export-storage-v041"))
    args = parser.parse_args()
    args.proof.mkdir(parents=True, exist_ok=True)
    source = args.proof / "source.mkv"
    texture = np.random.default_rng(73).integers(30, 220, (192, 320, 3), np.uint8)
    with av.open(str(source), "w") as output:
        stream = output.add_stream("ffv1", rate=60)
        stream.width, stream.height, stream.pix_fmt = 320, 192, "bgr0"
        for index in range(16):
            frame = av.VideoFrame.from_ndarray(np.roll(texture, 3 * (index // 2), axis=1), "rgb24")
            frame.pts, frame.time_base = index, Fraction(1, 60)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(ANALYST_STYLE)
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    service = FPSService()
    metadata = MediaProbe().probe(source)
    index = TimestampIndex.build(source)
    session = service.analyze(
        source,
        metadata,
        index,
        (AnalysisFrameRange(0, 15, "Trecho 1"),),
        args.proof / "reports",
        "cpu",
        None,
        CancellationToken(),
        lambda *_: None,
    )
    records = []
    for mode in ("cpu", "nvidia"):
        output = args.output_directory / f"vídeo final {mode}.mp4"
        values = []

        def progress(value, message, output=output, values=values):
            if value == 100:
                assert output.is_file() and output.stat().st_size > 0
                with av.open(str(output)) as video:
                    assert len(list(video.decode(video=0))) == 16
            values.append({"value": value, "message": message})

        asset = service.export(
            session,
            output,
            mode,
            CancellationToken(),
            progress,
            language="en",
        )
        assert not asset.warnings and values[-1]["value"] == 100
        records.append(
            {
                "requested": mode,
                "codec": asset.codec,
                "path": str(asset.path),
                "size": asset.path.stat().st_size,
                "frames": 16,
                "progress": values,
                "readable_at_100": True,
            }
        )
    window = FPSWindow(args.proof / "data", args.proof / "cache", language="en")
    window.show()
    window.open_source(source)
    deadline = time.monotonic() + 30
    while window.media.timestamp_index is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert window.media.timestamp_index is not None
    window.job_id = "analysis-proof"
    window._restoring = True
    window._job_completed("analysis-proof", session)
    window.job_id = "export-proof"
    window._job_completed("export-proof", asset)
    app.processEvents()
    assert window.export_folder_button.isEnabled()
    assert window.last_export_path == asset.path
    window.grab().save(str(args.proof / "saved-video-en.png"))
    window.close()
    (args.proof / "results.json").write_text(
        json.dumps({"status": "passed", "outputs": records}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(records, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
