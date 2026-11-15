"""Compare decoded pixels and complete CPU analysis with the preserved 0.3.1 snapshot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import av

from dg_fps.analyzers.base import AnalysisContext
from dg_fps.analyzers.cadence import CadenceAnalyzer
from dg_fps.vision.optical_flow.opencv_cpu import OpenCVFarnebackBackend


def without_generated_ids(value: dict) -> dict:
    # Finding UUIDs are intentionally new for every analysis, even in the same build.
    return {
        **value,
        "findings": [
            {key: item for key, item in finding.items() if key != "id"}
            for finding in value["findings"]
        ],
    }


def main() -> None:
    baseline = Path("build/v040-baseline")
    original = json.loads((baseline / "decode-analysis.json").read_text("utf-8"))
    records = {
        "av_version": av.__version__,
        "cases": {},
        "critical_sources": {},
        "excluded": ["findings[].id (generated UUID)"],
    }
    for name, old in original.items():
        path = Path(name)
        with av.open(str(path)) as container:
            frames = [
                {
                    "pts": frame.pts,
                    "time_base": str(frame.time_base),
                    "rgb": hashlib.sha256(frame.to_ndarray(format="rgb24").tobytes()).hexdigest(),
                }
                for frame in container.decode(video=0)
            ]
        result = CadenceAnalyzer(backend=OpenCVFarnebackBackend()).analyze(
            AnalysisContext(path.resolve(), 60.0)
        )
        data = json.loads(json.dumps(asdict(result), default=str))
        row = {
            "pixels_and_timestamps_equal": old["frames"] == frames,
            "analysis_equal": without_generated_ids(old["analysis"]) == without_generated_ids(data),
        }
        records["cases"][name] = row
        assert all(row.values()), name
        print(name, row, flush=True)
    for name in (
        "analyzers/cadence.py",
        "analyzers/local_motion.py",
        "analyzers/base.py",
        "reports/cadence_json.py",
        "vision/optical_flow/nvidia_native.py",
        "vision/optical_flow/opencv_cpu.py",
        "_native/dg_nvidia_optical_flow.dll",
    ):
        before = Path("build/v031-source-reference/dg-fps-0.3.1/src/dg_fps") / name
        after = Path("src/dg_fps") / name
        equal = (
            hashlib.sha256(before.read_bytes()).digest()
            == hashlib.sha256(after.read_bytes()).digest()
        )
        records["critical_sources"][name] = equal
        assert equal, name
    records["passed"] = True
    (baseline / "final-comparison.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
