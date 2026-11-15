"""Require byte-identical measurement sources and native bridge for 0.8.13."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    old = root / "build/v0813-before/src/dg_fps"
    new = root / "src/dg_fps"
    protected = [
        *old.joinpath("analyzers").glob("*.py"),
        *old.joinpath("core").glob("*.py"),
        *(
            old / name
            for name in (
                "backends.py",
                "media/media_probe.py",
                "vision/optical_flow/base.py",
                "vision/optical_flow/opencv_cpu.py",
                "presentation/video_encoder.py",
                "presentation/export_verification.py",
                "reports/cadence_json.py",
                "projects.py",
                "_native/dg_nvidia_optical_flow.dll",
            )
        ),
    ]
    records = {}
    for before in protected:
        name = before.relative_to(old)
        a = hashlib.sha256(before.read_bytes()).hexdigest()
        b = hashlib.sha256((new / name).read_bytes()).hexdigest()
        assert a == b, str(name)
        records[name.as_posix()] = {"sha256": b, "identical": True}
    frozen = {}
    if args.frozen:
        from PyInstaller.archive.readers import CArchiveReader

        before_archive = CArchiveReader(
            str(root / "dist/0.8.12/AIDA-FPS-Studio/AIDA-FPS-Studio.exe")
        ).open_embedded_archive("PYZ.pyz")
        after_archive = CArchiveReader(
            str(root / "dist/0.8.13/AIDA-FPS-Studio/AIDA-FPS-Studio.exe")
        ).open_embedded_archive("PYZ.pyz")
        for before in protected:
            if before.suffix != ".py":
                continue
            parts = list(before.relative_to(old).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            module = ".".join(("dg_fps", *parts))
            assert before_archive.extract(module) == after_archive.extract(module), module
            frozen[module] = True
        before_dll = (
            root / "dist/0.8.12/AIDA-FPS-Studio/_internal/dg_fps/_native/dg_nvidia_optical_flow.dll"
        )
        after_dll = (
            root / "dist/0.8.13/AIDA-FPS-Studio/_internal/dg_fps/_native/dg_nvidia_optical_flow.dll"
        )
        assert before_dll.read_bytes() == after_dll.read_bytes()
        frozen["dg_nvidia_optical_flow.dll"] = True
    output = root / "build/v0813-proof/measurement-integrity.json"
    output.write_text(
        json.dumps({"passed": True, "files": records, "frozen": frozen}, indent=2), "utf-8"
    )
    print(f"{len(records)} protected sources/binaries identical")


if __name__ == "__main__":
    main()
