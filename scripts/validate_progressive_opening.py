"""Measure the real Qt opening flow with empty app caches; never run analysis."""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
from pathlib import Path
from shutil import copy2
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.preview import PREVIEW_SIZE
from dg_fps.media.timestamp_index import TimestampIndex, _cache_path, _load_cache
from dg_fps.ui.main_window import FPSWindow
from dg_fps.ui.theme import ANALYST_STYLE

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/v0814-proof"


def until(app: QApplication, predicate, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        app.processEvents()
        if time.monotonic() >= deadline:
            raise TimeoutError("Opening workflow did not reach the expected state")
        time.sleep(0.001)
    app.processEvents()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(ANALYST_STYLE)
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    result = {
        "scope": "Qt window, empty app caches, warm OS cache, CPU indexing; 3 runs",
        "cases": [],
    }
    for case in json.loads((ROOT / "build/lgpl-runtime/cases.json").read_text("utf-8")):
        source = Path(case["source"])
        runs = []
        for number in range(3):
            directory = OUTPUT / case["name"] / uuid4().hex
            cache = directory / "cache"
            window = FPSWindow(directory / "data", cache, language="pt")
            window.resize(1440, 900)
            window.media.hardware_indexing = False
            window.show()
            app.processEvents()
            try:
                began = time.perf_counter()
                window.open_source(source)
                until(app, lambda window=window: window._opening_preview_ready)
                first = time.perf_counter() - began
                assert not window.process_dialog.isVisible()
                assert window.timeline.navigation_active
                assert window.media.timestamp_index is None
                assert not window.panel.isEnabled() and not window.export_button.isEnabled()
                until(app, lambda window=window: bool(window.timeline.opening._frames))
                first_thumbnail = time.perf_counter() - began
                until(app, lambda window=window: len(window.timeline.opening._frames) == 6)
                six = time.perf_counter() - began
                images = tuple(window.timeline.opening._frames)
                requested = window.metadata.video_streams[0].start_time_seconds or 0
                requested += (
                    window.metadata.video_streams[0].duration_seconds
                    or window.metadata.duration_seconds
                ) * 0.7
                seek = time.perf_counter()
                window._request_navigation_time(requested)
                until(
                    app,
                    lambda window=window: (
                        window.current is None
                        and bool(window.timeline.opening.position.text())
                        and window.view.preview_notice != "Buscando prévia por tempo…"
                    ),
                )
                seek = time.perf_counter() - seek
                if number == 0:
                    assert window.grab().save(str(OUTPUT / f"{case['name']}-opening-pt.png"))
                window._cancel_operation()
                assert window.media.timestamp_index is None
                assert not window.panel.isEnabled()
            finally:
                window.close()
                app.processEvents()
            reference_path = _cache_path(
                source.resolve(), 0, ROOT / "build/v0813-proof/index-cache"
            )
            reference = TimestampIndex(_load_cache(reference_path, source))
            by_pts = {(t.pts, t.time_base): t for t in reference}
            for image in images:
                assert (image.pts, str(image.time_base)) in by_pts
            runs.append(
                {
                    "first_frame_seconds": first,
                    "first_thumbnail_seconds": first_thumbnail,
                    "six_thumbnails_seconds": six,
                    "interactive_seek_seconds": seek,
                    "thumbnail_pts_exact": True,
                }
            )
            print(case["name"], number, runs[-1], flush=True)

        # Reopening uses the same validated cache as the previous release.
        target = _cache_path(source.resolve(), 0, cache)
        copy2(reference_path, target)
        cached_window = FPSWindow(directory / "cached-data", cache, language="en")
        cached_window.resize(1000, 760)
        cached_window.show()
        app.processEvents()
        try:
            began = time.perf_counter()
            cached_window.open_source(source)
            until(
                app,
                lambda cached_window=cached_window, reference=reference: (
                    cached_window.timeline.frame_count == len(reference)
                ),
            )
            cached_seconds = time.perf_counter() - began
            assert not cached_window.timeline.navigation_active
            assert cached_window.media.timestamp_index.decoder == "cache"
            assert tuple(cached_window.media.timestamp_index) == tuple(reference)
            until(
                app, lambda cached_window=cached_window: cached_window.media.cached_frame_count > 0
            )
            expected = FrameProvider(source, timestamp_index=reference).frame_by_index(
                0, max_size=PREVIEW_SIZE
            )
            assert cached_window.current.timestamp == expected.timestamp
            assert np.array_equal(cached_window.current.rgb, expected.rgb)
            assert cached_window.grab().save(str(OUTPUT / f"{case['name']}-ready-en.png"))
        finally:
            cached_window.close()
            app.processEvents()
        result["cases"].append(
            {
                "name": case["name"],
                "runs": runs,
                "cached_open_seconds": cached_seconds,
                "cached_index_exact": True,
                "exact_frame_pixels_equal": True,
                "medians": {
                    key: statistics.median(run[key] for run in runs)
                    for key in runs[0]
                    if key.endswith("seconds")
                },
            }
        )
        (OUTPUT / "opening-window.json").write_text(json.dumps(result, indent=2), "utf-8")
    result["passed"] = True
    (OUTPUT / "opening-window.json").write_text(json.dumps(result, indent=2), "utf-8")
    # Hash every existing non-UI/non-controller module against the preserved release.
    baseline = ROOT / "build/v0814-before/src/dg_fps"
    records = {}
    for before in baseline.rglob("*.py"):
        relative = before.relative_to(baseline)
        if relative.parts[0] in {"ui", "controllers"} or relative.as_posix() == "__init__.py":
            continue
        after = ROOT / "src/dg_fps" / relative
        a, b = (hashlib.sha256(path.read_bytes()).hexdigest() for path in (before, after))
        assert a == b, relative
        records[relative.as_posix()] = {"identical": True, "sha256": b}
    old_dll = baseline / "_native/dg_nvidia_optical_flow.dll"
    new_dll = ROOT / "src/dg_fps/_native/dg_nvidia_optical_flow.dll"
    assert old_dll.read_bytes() == new_dll.read_bytes()
    (OUTPUT / "core-integrity.json").write_text(
        json.dumps({"passed": True, "files": records, "native_dll_identical": True}, indent=2),
        "utf-8",
    )


if __name__ == "__main__":
    main()
