"""Compare complete measurements, presentation pixels and timings across source snapshots.

Run with PYTHONPATH=<validated media runtime>;<snapshot>/src and then current src.
Finding UUIDs, redundant nested analyzer IDs, adapter version 1.2.0/1.2.1 and
DLL location are normalized. The top-level analyzer_id/version remain compared.
Timing is diagnostic and never a measurement-equivalence tolerance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from dataclasses import asdict
from pathlib import Path
from shutil import copy2

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import av
from platformdirs import user_cache_path
from PySide6.QtWidgets import QApplication

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex, _cache_path
from dg_fps.presentation.cadence_video import CadenceVideoExporter
from dg_fps.presentation.renderer import qimage_to_rgb
from dg_fps.service import FPSService


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


def normalize(value: object, key: str = "") -> object:
    if isinstance(value, dict):
        normalized = {k: normalize(v, k) for k, v in value.items() if k != "id"}
        if value.get("backend") == "nvidia_optical_flow_cuda" and value.get("version") in {
            "1.2.0",
            "1.2.1",
        }:
            normalized["version"] = "equivalent_adapter_1.2.x"
        return normalized
    if isinstance(value, (list, tuple)):
        return [normalize(v, key) for v in value]
    if key == "native_library":
        return Path(str(value)).name
    if key in {"flow_backend_version", "backward_version"} and value in {"1.2.0", "1.2.1"}:
        return "equivalent_adapter_1.2.x"
    return value


def compare_records(baseline: Path, candidate: Path) -> None:
    old = json.loads(baseline.read_text("utf-8"))
    records = json.loads(candidate.read_text("utf-8"))
    comparisons = []
    for before, after in zip(old["cases"], records["cases"], strict=True):
        assert before["name"] == after["name"]
        for key in ("index_hash", "decode_hash"):
            assert before[key] == after[key], (after["name"], key)
        comparison = {"name": after["name"], "exact": True}
        old_index = statistics.median(before["cached_index_seconds"])
        new_index = statistics.median(after["cached_index_seconds"])
        comparison["cached_index"] = {
            "old_seconds": old_index,
            "new_seconds": new_index,
            "time_reduction_percent": 100 * (1 - new_index / old_index),
        }
        for stage in ("analysis", "export"):
            comparison[stage] = {}
            for mode in ("cpu", "nvidia"):
                a, b = before[stage][mode], after[stage][mode]
                if stage == "analysis":
                    # Read complete saved documents, including adapter versions inside
                    # refinement ROIs. Preserve the original recorded hashes/timings.
                    documents = [
                        json.loads(
                            (path.parent / f"{after['name']}-{mode}-analysis.json").read_text(
                                "utf-8"
                            )
                        )
                        for path in (baseline, candidate)
                    ]
                    hashes = [digest(normalize(document)) for document in documents]
                    assert hashes[0] == hashes[1], (after["name"], mode, "complete analysis")
                else:
                    for key in ("rendered_hash", "encoded_hash", "mapping_hash"):
                        assert a[key] == b[key], (after["name"], mode, key)
                comparison[stage][mode] = {
                    "old_seconds": a["median_seconds"],
                    "new_seconds": b["median_seconds"],
                    "time_reduction_percent": 100 * (1 - b["median_seconds"] / a["median_seconds"]),
                }
        comparisons.append(comparison)
    records["comparison"] = comparisons
    records["comparison_exclusions"] = [
        "generated finding UUIDs",
        "redundant nested analyzer IDs (top-level ID/version compared)",
        "NVIDIA adapter version 1.2.0 / 1.2.1, including refinement ROIs",
        "DLL location",
    ]
    records["passed"] = True
    candidate.write_text(json.dumps(records, indent=2), "utf-8")
    print("Exact measurement, presentation, output pixels and provenance: PASS", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("build/lgpl-runtime/cases.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument("--frames", type=int, default=72)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    if args.compare_only:
        if args.baseline is None:
            parser.error("--compare-only requires --baseline")
        compare_records(args.baseline, args.output)
        return
    app = QApplication.instance() or QApplication([])
    assert app is not None
    root = args.output.parent
    root.mkdir(parents=True, exist_ok=True)
    records = {"runtime": {"av": av.__file__, "ffmpeg": av.ffmpeg_version_info}, "cases": []}
    for case in json.loads(args.cases.read_text("utf-8")):
        source = Path(case["source"])
        print(case["name"], "index/cache", flush=True)
        if not source.is_file():
            raise FileNotFoundError(source)
        cache = root / "index-cache"
        target = _cache_path(source.resolve(), 0, cache)
        for app_name in ("DG FPS", "AIDA FPS Studio"):
            candidate = _cache_path(source.resolve(), 0, user_cache_path(app_name, "DG"))
            if not target.is_file() and candidate.is_file():
                copy2(candidate, target)
        index_times = []
        for _ in range(args.repeat):
            began = time.perf_counter()
            index = TimestampIndex.build(source, cache_directory=cache)
            index_times.append(time.perf_counter() - began)
        start = case["start"]
        end = min(start + args.frames - 1, len(index) - 1)
        frames = []
        for frame in FrameProvider(source, timestamp_index=index).frames_in_range(start, end):
            frames.append(
                {
                    "timestamp": asdict(frame.timestamp),
                    "rgb": hashlib.sha256(frame.rgb.tobytes()).hexdigest(),
                    "metadata": frame.signal_metadata,
                }
            )
        row = {
            "name": case["name"],
            "source": str(source),
            "index_frames": len(index),
            "index_hash": digest([asdict(f) for f in index]),
            "decode_hash": digest(frames),
            "cached_index_seconds": index_times,
            "analysis": {},
            "export": {},
        }
        metadata = MediaProbe().probe(source)
        sessions = {}
        for mode in ("cpu", "nvidia"):
            timings, hashes = [], []
            for repeat in range(args.repeat):
                print(case["name"], "analysis", mode, repeat, flush=True)
                began = time.perf_counter()
                session = FPSService().analyze(
                    source,
                    metadata,
                    index,
                    (AnalysisFrameRange(start, end, "Validation"),),
                    root / "reports",
                    mode,
                    None,
                    CancellationToken(),
                    lambda *_: None,
                )
                timings.append(time.perf_counter() - began)
                document = normalize(asdict(session.analysis))
                hashes.append(digest(document))
                (root / f"{case['name']}-{mode}-analysis.json").write_text(
                    json.dumps(document, default=str, sort_keys=True), "utf-8"
                )
                sessions[mode] = session
            assert len(set(hashes)) == 1, (case["name"], mode, "nondeterministic analysis")
            row["analysis"][mode] = {
                "seconds": timings,
                "hash": hashes[0],
                "median_seconds": statistics.median(timings),
            }
        # Both encoder modes use the same already measured CPU session.
        for mode in ("cpu", "nvidia"):
            timings, rendered, encoded, mappings = [], [], [], []
            for repeat in range(args.repeat):
                print(case["name"], "export", mode, repeat, flush=True)
                exporter = CadenceVideoExporter(references=sessions["cpu"].automatic_references)
                composed = []
                compose = exporter._compose

                def capture(*args, _compose=compose, _composed=composed, **kwargs):
                    image = _compose(*args, **kwargs)
                    _composed.append(hashlib.sha256(qimage_to_rgb(image).tobytes()).hexdigest())
                    return image

                exporter._compose = capture
                began = time.perf_counter()
                asset = exporter.export(
                    source,
                    index,
                    sessions["cpu"].analysis,
                    root / f"{case['name']}-{mode}-{repeat}.mp4",
                    check_cancelled=lambda: None,
                    report_progress=lambda *_: None,
                    encoding_mode=mode,
                )
                timings.append(time.perf_counter() - began)
                rendered.append(digest(composed))
                with av.open(str(asset.path)) as video:
                    output_frames = [
                        {
                            "pts": f.pts,
                            "time_base": str(f.time_base),
                            "rgb": hashlib.sha256(
                                f.to_ndarray(format="rgb24").tobytes()
                            ).hexdigest(),
                        }
                        for f in video.decode(video=0)
                    ]
                assert len(output_frames) == end - start + 1
                encoded.append(digest(output_frames))
                mapping = json.loads(
                    (asset.path.parent / f"{asset.path.stem}_images" / "frames.json").read_text(
                        "utf-8"
                    )
                )
                mappings.append(digest(mapping))
            assert len(set(rendered)) == len(set(encoded)) == len(set(mappings)) == 1
            row["export"][mode] = {
                "seconds": timings,
                "rendered_hash": rendered[0],
                "encoded_hash": encoded[0],
                "mapping_hash": mappings[0],
                "median_seconds": statistics.median(timings),
            }
        records["cases"].append(row)
        args.output.write_text(json.dumps(records, indent=2), "utf-8")
    if args.baseline:
        compare_records(args.baseline, args.output)


if __name__ == "__main__":
    main()
