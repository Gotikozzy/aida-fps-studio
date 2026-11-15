"""Prove exact native vectors with mutable inputs and thread handoff."""

from __future__ import annotations

import importlib.util
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from dg_fps.backends import bundled_library_path
from dg_fps.vision.optical_flow.nvidia_native import NvidiaNativeBackend


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    reference = root / "build/v0813-before/src/dg_fps/vision/optical_flow/nvidia_native.py"
    spec = importlib.util.spec_from_file_location("gray_reference", reference)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = module.NvidiaNativeBackend(bundled_library_path())
    new = NvidiaNativeBackend(bundled_library_path())
    rng = np.random.default_rng(813)
    records = {"gpu": new.gpu_name, "cases": []}
    try:
        for width, height in ((320, 192), (640, 360), (160, 160)):
            a = rng.integers(20, 235, (height, width, 3), np.uint8)
            b = np.roll(a, 3, axis=1)
            retained = None
            timings = {"old": [], "new": []}
            for iteration in range(10):
                if iteration == 4:
                    a[:] = rng.integers(20, 235, a.shape, np.uint8)
                if iteration == 7:
                    a, b = a[:, ::-1], b[:, ::-1]
                results = {}
                order = (("old", old), ("new", new))
                for label, backend in order if iteration % 2 else reversed(order):
                    began = time.perf_counter()
                    results[label] = backend.compute(a, b)
                    timings[label].append(time.perf_counter() - began)
                assert np.array_equal(results["old"].vectors, results["new"].vectors)
                assert np.array_equal(results["old"].magnitude, results["new"].magnitude)
                if retained is not None:
                    assert np.array_equal(retained[0].vectors, retained[1])
                retained = (results["new"], results["new"].vectors.copy())
                a, b = b, a
            with ThreadPoolExecutor(max_workers=2) as pool:
                outputs = list(pool.map(lambda _, a=a, b=b: new.compute(a, b), range(4)))
            expected = old.compute(a, b)
            assert all(np.array_equal(expected.vectors, value.vectors) for value in outputs)
            records["cases"].append({"size": [width, height], "exact": True, "seconds": timings})
    finally:
        old.close()
        new.close()
    records["passed"] = True
    output = root / "build/v0813-proof/native-cache.json"
    output.write_text(json.dumps(records, indent=2), "utf-8")


if __name__ == "__main__":
    main()
