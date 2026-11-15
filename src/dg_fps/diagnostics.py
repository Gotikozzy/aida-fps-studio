"""Deterministic, offline CPU check usable in the frozen executable."""

from __future__ import annotations

import json
import time
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.service import FPSService
from dg_fps.ui.main_window import FPSWindow
from dg_fps.ui.theme import ANALYST_STYLE


def run_self_test(directory: Path) -> int:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        application = QApplication.instance()
        application.setStyleSheet(ANALYST_STYLE)
        # Offscreen Qt on Windows needs an explicit installed font for visual QA.
        font = Path("C:/Windows/Fonts/segoeui.ttf")
        if application.platformName() == "offscreen" and font.is_file():
            QFontDatabase.addApplicationFont(str(font))
        source = directory / "synthetic.mkv"
        texture = np.random.default_rng(73).integers(30, 220, (180, 320, 3), np.uint8)
        with av.open(str(source), "w") as container:
            stream = container.add_stream("ffv1", rate=30)
            stream.width, stream.height, stream.pix_fmt = 320, 180, "bgr0"
            for number in range(16):
                rgb = np.roll(texture, 3 * (number // 2), axis=1)
                frame = av.VideoFrame.from_ndarray(rgb, "rgb24")
                frame.pts, frame.time_base = number, Fraction(1, 30)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        index = TimestampIndex.build(source)
        service = FPSService()
        session = service.analyze(
            source,
            MediaProbe().probe(source),
            index,
            (AnalysisFrameRange(0, 15, "Trecho 1"),),
            directory / "reports",
            "cpu",
            None,
            CancellationToken(),
            lambda *_: None,
        )
        asset = service.export(
            session,
            directory / "fps.mp4",
            "cpu",
            CancellationToken(),
            lambda *_: None,
            language="en",
        )
        with av.open(str(asset.path)) as output:
            frames = list(output.decode(video=0))
            decoded_count = len(frames)
            frame_rgb = frames[-1].to_ndarray(format="rgb24")
        if decoded_count != 16:
            raise RuntimeError(f"Esperados 16 frames; encontrados {decoded_count}")
        rate = session.analysis.summary.content_fps
        if rate is None or abs(rate - 15) > 0.6:
            raise RuntimeError(f"Cadência sintética divergente: {rate}")
        from PySide6.QtGui import QImage

        image = QImage(
            frame_rgb.data,
            frame_rgb.shape[1],
            frame_rgb.shape[0],
            frame_rgb.strides[0],
            QImage.Format.Format_RGB888,
        ).copy()
        image.save(str(directory / "video-en.png"))
        window = FPSWindow(directory / "data", directory / "cache", language="pt")
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        window.source = source
        window._show_project_workspace()
        window.resize(1440, 900)
        window.timeline.canvas.set_index(index)
        window.metadata = MediaProbe().probe(source)
        window.timeline.set_frame_count(len(index))
        provider = FrameProvider(source, timestamp_index=index)
        window.timeline.set_thumbnails(
            [provider.thumbnail_by_index(value) for value in (0, 3, 6, 9, 12, 15)]
        )
        window.panel.mark_in(0, index[0].seconds)
        window.panel.mark_out(15, index[15].seconds)
        window.panel._add_range()
        window._show_frame(FrameProvider(source, timestamp_index=index).frame_by_index(6))
        window.file_label.setText(source.name)
        window.job_id = "self-test"
        from dg_fps.studio_services import prepare_analysis

        window._restoring = True
        window._job_completed("self-test", prepare_analysis(session, CancellationToken()))
        window.show()
        application.processEvents()
        window._test_hardware()
        deadline = time.monotonic() + 30
        while window.job_id is not None and time.monotonic() < deadline:
            application.processEvents()
            time.sleep(0.01)
        if window.hardware_result is None:
            raise RuntimeError("NVIDIA compatibility check did not complete")
        (directory / "hardware-check.json").write_text(
            json.dumps(window.hardware_result.to_dict(), indent=2), encoding="utf-8"
        )
        window.panel.setEnabled(True)
        if not window.grab().save(str(directory / "interface.png")):
            raise RuntimeError("Não foi possível salvar a captura da interface")
        window.language_box.setCurrentIndex(window.language_box.findData("en"))
        application.processEvents()
        if not window.grab().save(str(directory / "interface-en.png")):
            raise RuntimeError("Unable to save English interface screenshot")
        window._dirty = False
        window.close()
        result = {
            "status": "passed",
            "frames": decoded_count,
            "codec": asset.codec,
            "content_fps": rate,
            "source": str(source),
            "reports": str(session.reports.project_directory),
            "nvidia": window.hardware_result.to_dict(),
            "video_language": asset.language,
            "video_branding": asset.branding,
        }
        code = 0
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        code = 1
    (directory / "self-test.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return code
