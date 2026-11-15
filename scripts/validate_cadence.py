"""Offline, known-cadence CPU/NVIDIA calibration; generated media stays in build/."""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

from dg_fps.analyzers.base import AnalysisContext
from dg_fps.analyzers.cadence import CadenceAnalyzer
from dg_fps.backends import select_backend
from dg_fps.reports.cadence_json import CadenceJsonWriter


def make_source(path: Path, kind: str, fps: int) -> Path:
    texture = np.random.default_rng(808).integers(30, 220, (192, 320, 3), np.uint8)
    with av.open(str(path), "w") as output:
        stream = output.add_stream("mpeg4" if kind == "compressed" else "ffv1", rate=60)
        stream.width, stream.height = 320, 192
        stream.pix_fmt = "yuv420p" if kind == "compressed" else "bgr0"
        for index in range(121):
            update = index * fps // 60
            if kind == "localized":
                image = np.zeros_like(texture)
                image[80:112, 144:176] = np.roll(texture[80:112, 144:176], update * 2, axis=1)
            elif kind == "subpixel":
                image = cv2.warpAffine(
                    texture,
                    np.float32([[1, 0, update * 0.25], [0, 1, 0]]),
                    (320, 192),
                    borderMode=cv2.BORDER_REFLECT,
                )
            else:
                image = np.roll(texture, update * 3, axis=1)
            frame = av.VideoFrame.from_ndarray(image, "rgb24")
            frame.pts, frame.time_base = index, Fraction(1, 60)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nvidia", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("build/cadence-validation-v030"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for mode in ["cpu", "nvidia"] if args.nvidia else ["cpu"]:
        backend = select_backend(mode)
        for kind, expected in [
            ("distributed", 30),
            ("localized", 15),
            ("subpixel", 30),
            ("compressed", 30),
        ]:
            path = make_source(args.output / f"{kind}.mkv", kind, expected)
            result = CadenceAnalyzer(backend=backend).analyze(AnalysisContext(path, 60.0))
            backends = sorted(
                {
                    sample.flow_backend
                    for sample in result.samples
                    if sample.flow_backend not in {"not_compared", "exact_pixel_comparison"}
                }
            )
            measured = result.summary.content_fps
            passed = (
                measured is not None
                and abs(measured - expected) <= 0.6
                and result.summary.observable_window_ratio > 0.7
                and (mode != "nvidia" or backends == ["nvidia_optical_flow_cuda"])
            )
            record = {
                "mode": mode,
                "case": kind,
                "expected": expected,
                "measured": measured,
                "coverage": result.summary.observable_window_ratio,
                "backends": backends,
                "passed": passed,
            }
            records.append(record)
            CadenceJsonWriter(app_name="DG FPS calibration", app_version="0.3.1").write(
                result,
                source_metadata={"synthetic": True, "expected_fps": expected},
                projects_root=args.output / mode,
            )
            print(json.dumps(record))
    (args.output / "results.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return 0 if all(record["passed"] for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
