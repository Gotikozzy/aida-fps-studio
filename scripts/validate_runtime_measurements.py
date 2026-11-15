"""Write deterministic decode and measurement evidence for cross-runtime comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import av
from platformdirs import user_cache_path

from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.media.frame_provider import FrameProvider
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.service import FPSService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    results = []
    for case in json.loads(args.cases.read_text("utf-8")):
        source = Path(case["source"])
        index = TimestampIndex.build(source, cache_directory=user_cache_path("DG FPS", "DG"))
        start = case["start"]
        end = min(start + 119, len(index) - 1)
        print(f"{case['name']}: decoding {start}..{end}", flush=True)
        provider = FrameProvider(source, timestamp_index=index, preserve_precision=True)
        decoded = []
        for frame in provider.frames_in_range(start, end, max_size=(640, 360)):
            decoded.append({
                "timestamp": asdict(frame.timestamp),
                "rgb": hashlib.sha256(frame.rgb.tobytes()).hexdigest(),
                "precise": hashlib.sha256(frame.measurement_rgb.tobytes()).hexdigest()
                if frame.measurement_rgb is not None else None,
                "metadata": frame.signal_metadata,
            })
        measurements = {}
        service = FPSService()
        metadata = MediaProbe().probe(source)
        for mode in ("cpu", "nvidia"):
            print(case["name"], mode, flush=True)
            session = service.analyze(
                source, metadata, index, (AnalysisFrameRange(start, end, "Validation"),),
                args.output.parent / (args.output.stem + "-reports"), mode, None,
                CancellationToken(), lambda *_: None,
            )
            measurements[mode] = asdict(session.analysis)
        results.append({"name": case["name"], "decoded": decoded,
                        "measurements": measurements})
    args.output.write_text(json.dumps({
        "runtime": {"binding": av.__file__, "version": av.ffmpeg_version_info},
        "results": results,
    }, default=str, sort_keys=True), encoding="utf-8")
    print(args.output, flush=True)


if __name__ == "__main__":
    main()
