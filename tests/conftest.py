from __future__ import annotations

import os
from fractions import Fraction
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import av
import numpy as np
import pytest


@pytest.fixture(autouse=True)
def desktop_side_effects(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from dg_fps.ui.main_window import FPSWindow

    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(FPSWindow, "_reveal_delivery", lambda *_: None)


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    path = tmp_path / "movimento.mkv"
    texture = np.random.default_rng(42).integers(30, 220, (64, 96, 3), dtype=np.uint8)
    with av.open(str(path), "w") as output:
        stream = output.add_stream("ffv1", rate=30)
        stream.width, stream.height, stream.pix_fmt = 96, 64, "bgr0"
        for index in range(12):
            frame = av.VideoFrame.from_ndarray(np.roll(texture, index // 2 * 2, axis=1), "rgb24")
            frame.pts, frame.time_base = index, Fraction(1, 30)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return path
