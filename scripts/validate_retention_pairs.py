"""Fresh CPU/NVIDIA pair comparisons against a preserved analyzer module."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import av
from PySide6.QtWidgets import QApplication

from dg_fps.analyzers.cadence import CadenceAnalyzer
from dg_fps.backends import select_backend
from dg_fps.jobs.gpu_queue import GPUQueue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("retention_pair_baseline", args.baseline)
    assert spec and spec.loader
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    app = QApplication([])
    queue = GPUQueue()

    def task(token, progress):
        records = []
        for report in args.reports:
            llm = json.loads(report.read_text("utf-8"))
            doc = json.loads(Path(llm["provenance"]["analysis_file"]).read_text("utf-8"))
            source = Path(doc["source"]["path"])
            frames = doc["frames"]
            choices = {next(s["frame_index"] for s in frames
                            if not s["repeated"] and s["mean_absolute_difference"] is not None)}
            seconds = sorted(
                (s for segment in llm["segments"] for s in segment["per_second"]
                 if s["measured_fps"] is not None), key=lambda s: s["measured_fps"],
            )[:3]
            for second in seconds:
                repeated = next((s for s in frames if s["segment"] == second["segment"]
                                 and second["second"] <= s["timestamp_seconds"]
                                 < second["second"] + 1 and s["repeated"]), None)
                if repeated:
                    choices.add(repeated["frame_index"])
            # Decode once; compare both implementations with exactly the same arrays.
            lookup = {s["frame_index"]: s for s in frames}
            pairs = []
            with av.open(str(source)) as container:
                stream = container.streams.video[0]
                for i in sorted(choices):
                    if i - 1 not in lookup:
                        continue
                    expected = [Fraction(lookup[j]["pts"]) * Fraction(lookup[j]["time_base"])
                                for j in (i - 1, i)]
                    container.seek(
                        int(expected[0] / stream.time_base), stream=stream, backward=True,
                    )
                    decoded = {}
                    for frame in container.decode(stream):
                        if frame.pts is None:
                            continue
                        stamp = frame.pts * frame.time_base
                        if stamp in expected:
                            decoded[stamp] = frame.to_ndarray(format="rgb24")
                        if stamp >= expected[-1]:
                            break
                    assert all(t in decoded for t in expected), (source.name, i)
                    pairs.append((i, decoded[expected[0]], decoded[expected[1]]))
            for mode in ("cpu", "nvidia"):
                backend = select_backend(mode)
                try:
                    old = baseline.CadenceAnalyzer(backend=backend)
                    new = CadenceAnalyzer(backend=backend)
                    for number, previous, current in pairs:
                        token.raise_if_cancelled()
                        a = old._measure_pair(previous, current)
                        b = new._measure_pair(previous, current)
                        da, db = asdict(a), asdict(b)
                        da.pop("flow_parameters")
                        db.pop("flow_parameters")
                        assert da == db, (source.name, mode, number)
                        if mode == "nvidia":
                            assert b.flow_backend in {
                                "nvidia_optical_flow_cuda", "exact_pixel_comparison"
                            }
                        records.append({"source": source.name, "frame": number, "mode": mode,
                                        "pair_metrics_identical": True, "backend": b.flow_backend})
                        print(source.name, mode, number, "identical", flush=True)
                finally:
                    close = getattr(backend, "close", None)
                    if close is not None:
                        close()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(records, indent=2), "utf-8")
        return records

    queue.job_completed.connect(lambda *_: app.exit(0))

    def failed(_, message):
        print(message, flush=True)
        app.exit(1)

    queue.job_failed.connect(failed)
    queue.submit("Validate preserved pair measurements", task)
    code = app.exec()
    queue.shutdown(wait=True)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
