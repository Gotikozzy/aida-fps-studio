"""Generate a 4K60 control and measure the real Qt preview without analysis work."""

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

from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.ui.main_window import FPSWindow
from dg_fps.ui.theme import ANALYST_STYLE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("build/preview-4k60.mkv"))
    parser.add_argument("--output", type=Path, default=Path("build/preview-v040"))
    parser.add_argument("--cpu-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.source.exists():
        args.source.parent.mkdir(parents=True, exist_ok=True)
        texture = np.random.default_rng(734).integers(20, 230, (180, 320, 3), np.uint8)
        texture = np.tile(texture, (12, 12, 1))
        with av.open(str(args.source), "w") as output:
            stream = output.add_stream("libx264", rate=60)
            stream.width, stream.height, stream.pix_fmt = 3840, 2160, "yuv420p"
            stream.options = {"preset": "ultrafast", "crf": "22", "g": "60"}
            for index in range(241):
                frame = av.VideoFrame.from_ndarray(np.roll(texture, index * 2, axis=1), "rgb24")
                frame.pts, frame.time_base = index, Fraction(1, 60)
                for packet in stream.encode(frame):
                    output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)
    index_start = time.perf_counter()
    cpu_index = TimestampIndex.build(args.source)
    cpu_seconds = time.perf_counter() - index_start
    start = time.perf_counter()
    auto_index = TimestampIndex.build(args.source, hardware_acceleration=not args.cpu_only)
    auto_seconds = time.perf_counter() - start
    assert list(auto_index) == list(cpu_index)
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(ANALYST_STYLE)
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.is_file():
        QFontDatabase.addApplicationFont(str(font))
    window = FPSWindow(args.output / "data", args.output / "cache", language="en")
    window.show()
    window.open_source(args.source)
    deadline = time.monotonic() + 120
    while window.media.timestamp_index is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert window.media.timestamp_index is not None
    shown = []
    original = window._show_frame

    def display(frame):
        if window.timer.isActive():
            shown.append((time.monotonic(), frame.timestamp.index, frame.rgb.shape))
        original(frame)

    window._show_frame = display
    window.toggle_play()
    deadline = time.monotonic() + 30
    while window.timer.isActive() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert not window.timer.isActive() and len(shown) > 2
    elapsed = shown[-1][0] - shown[0][0]
    source_elapsed = cpu_index[shown[-1][1]].seconds - cpu_index[shown[0][1]].seconds
    clock_elapsed = shown[-1][0] - window.play_start
    window.grab().save(str(args.output / "preview.png"))
    window.close()
    result = {
        "source": str(args.source.resolve()),
        "av_version": av.__version__,
        "source_frames": len(cpu_index),
        "presentations": len(shown),
        "elapsed_seconds": elapsed,
        "clock_elapsed_seconds": clock_elapsed,
        "source_seconds": source_elapsed,
        "speed_ratio": source_elapsed / elapsed,
        "presentations_per_second": (len(shown) - 1) / elapsed,
        "maximum_preview_shape": max(item[2] for item in shown),
        "index_cpu_seconds": cpu_seconds,
        "index_auto_seconds": auto_seconds,
        "index_auto_decoder": getattr(auto_index, "decoder", "not_recorded"),
        "index_equal": True,
    }
    (args.output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
