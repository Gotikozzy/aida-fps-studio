"""Compare a preserved 0.3.0 adapter/DLL against the optimized adapter on real NVIDIA.

The baseline directory must contain nvidia_native.py, dg_nvidia_optical_flow.dll
and analysis-hashes.json saved before optimization. No CPU fallback is allowed.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import av
import numpy as np

from dg_fps.analyzers.base import AnalysisContext
from dg_fps.analyzers.cadence import CadenceAnalyzer
from dg_fps.backends import bundled_library_path
from dg_fps.vision.optical_flow.nvidia_native import NvidiaNativeBackend


def normalized(value: Any) -> Any:
    """Exclude only intentionally changed adapter version and native DLL path."""
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items() if key != "native_library"}
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    if isinstance(value, str) and value in {"1.1.0", "1.2.0"}:
        return "adapter-version"
    return value


def mixed_source(path: Path) -> Path:
    """Black, static, distributed motion, hold, local overlay and resumed motion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    texture = np.random.default_rng(2511).integers(30, 220, (192, 320, 3), np.uint8)
    with av.open(str(path), "w") as output:
        stream = output.add_stream("ffv1", rate=60)
        stream.width, stream.height, stream.pix_fmt = 320, 192, "bgr0"
        for number in range(181):
            if number < 10:
                image = np.zeros_like(texture)
            elif number < 30:
                image = texture.copy()
            elif number < 70:
                image = np.roll(texture, 3 * ((number - 30) // 2), axis=1)
            elif number < 140:
                image = np.roll(texture, 57, axis=1)
                if number >= 100:
                    image[16:48, 16:48] = np.roll(
                        texture[16:48, 16:48], (number - 100) // 2, axis=1
                    )
            else:
                image = np.roll(texture, 57 + 3 * ((number - 140) // 2), axis=1)
            frame = av.VideoFrame.from_ndarray(image, "rgb24")
            frame.pts, frame.time_base = number, Fraction(1, 60)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path("build/gpu-baseline-v030"))
    parser.add_argument(
        "--fixtures", type=Path, default=Path("build/cadence-validation-v030-final")
    )
    parser.add_argument("--output", type=Path, default=Path("build/gpu-validation-v031.json"))
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location(
        "baseline_adapter", args.baseline / "nvidia_native.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = module.NvidiaNativeBackend(args.baseline / "dg_nvidia_optical_flow.dll")
    new = NvidiaNativeBackend(bundled_library_path())
    driver = ctypes.WinDLL("nvcuda.dll")
    driver.cuCtxGetCurrent.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    driver.cuCtxGetCurrent.restype = ctypes.c_int

    def current_context():
        context = ctypes.c_void_p()
        assert driver.cuCtxGetCurrent(ctypes.byref(context)) == 0
        return context.value

    records: dict[str, Any] = {"gpu": new.gpu_name, "vectors": [], "analyses": []}
    source = Path(__file__).resolve().parents[1] / "src/dg_fps"
    expected_hashes = json.loads((args.baseline / "analysis-hashes.json").read_text("utf-8"))
    records["analytical_sources_unchanged"] = all(
        hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
        for name, digest in expected_hashes.items()
    )
    assert records["analytical_sources_unchanged"]
    rng = np.random.default_rng(2301)
    try:
        for height, width in [(192, 320), (360, 640), (192, 320), (160, 160), (361, 641)]:
            a = rng.integers(20, 235, (height, width, 3), np.uint8)
            b = np.roll(a, 3, axis=1)
            retained = None
            cached_uploads = None
            for number, (left, right) in enumerate([(a, b), (b, a), (a, b), (a, a)]):
                start = time.perf_counter()
                before = old.compute(left, right)
                old_seconds = time.perf_counter() - start
                previous_context = current_context()
                start = time.perf_counter()
                after = new.compute(left, right)
                new_seconds = time.perf_counter() - start
                assert current_context() == previous_context
                if number == 0:
                    cached_uploads = new.resource_stats()["uploads"]
                elif number in (1, 2):
                    assert new.resource_stats()["uploads"] == cached_uploads
                assert np.array_equal(before.vectors, after.vectors)
                assert np.array_equal(before.magnitude, after.magnitude)
                if retained is not None:
                    assert np.array_equal(retained[0].vectors, retained[1])
                retained = (after, after.vectors.copy())
                records["vectors"].append(
                    {
                        "dimensions": [width, height],
                        "pair": number,
                        "exact": True,
                        "old_seconds": old_seconds,
                        "new_seconds": new_seconds,
                    }
                )
            # Same array object with changed pixels must invalidate the input cache.
            a[:] = rng.integers(20, 235, a.shape, np.uint8)
            reference = old.compute(a, b)
            assert np.array_equal(reference.vectors, new.compute(a, b).vectors)
            # Exercise context restoration and serialized use from different threads.
            with ThreadPoolExecutor(max_workers=2) as pool:
                outputs = list(pool.map(lambda _, a=a, b=b: new.compute(a, b), range(4)))
            assert all(np.array_equal(reference.vectors, item.vectors) for item in outputs)
        records["resource_stats"] = new.resource_stats()
        assert records["resource_stats"]["cached_sessions"] <= 2
        print(
            "Exact vectors, mutable inputs, retained outputs and thread handoff: PASS", flush=True
        )
        mixed = mixed_source(args.output.parent / "gpu-mixed-context-v031.mkv")
        for kind in ("distributed", "localized", "subpixel", "compressed", "mixed_context"):
            path = mixed if kind == "mixed_context" else args.fixtures / f"{kind}.mkv"
            context = AnalysisContext(path.resolve(), 60.0)
            timings: dict[str, list[float]] = {"old": [], "new": []}
            reference = None
            summary = None
            # Alternate order; compare complete results, not just rounded averages.
            orders = (
                (("old", "new"),)
                if kind == "mixed_context"
                else (("old", "new"), ("new", "old"), ("old", "new"))
            )
            for order in orders:
                for name in order:
                    start = time.perf_counter()
                    result = CadenceAnalyzer(backend=old if name == "old" else new).analyze(context)
                    timings[name].append(time.perf_counter() - start)
                    data = normalized(asdict(result))
                    if reference is None:
                        reference = data
                    assert data == reference, f"Analysis changed: {kind}/{name}"
                    summary = asdict(result.summary)
            before = statistics.median(timings["old"])
            after = statistics.median(timings["new"])
            row = {
                "case": kind,
                "exact": True,
                "old_seconds": before,
                "new_seconds": after,
                "speedup": before / after,
                "runs": timings,
                "summary": summary,
            }
            records["analyses"].append(row)
            print(
                f"{kind}: identical, {before:.3f}s -> {after:.3f}s ({before / after:.2f}x)",
                flush=True,
            )
    finally:
        new.close()
        new.close()
    records["passed"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
