"""Download hash-verified build inputs; never execute a downloaded installer."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def download(row: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / row["file"]
    if not path.is_file():
        partial = path.with_suffix(path.suffix + ".part")
        try:
            with (
                urllib.request.urlopen(row["url"], timeout=120) as response,
                partial.open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
            with partial.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != row["sha256"]:
                raise ValueError("Download hash mismatch: " + row["file"])
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != row["sha256"]:
            raise ValueError("Input hash mismatch: " + row["file"])
    return path


def extract(path: Path, directory: Path) -> None:
    if path.name.endswith(".7z.exe"):
        return  # Explicitly extracted with 7z in the documented build step.
    directory.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".zip":
        with ZipFile(path) as archive:
            for info in archive.infolist():
                target = (directory / info.filename).resolve()
                if not target.is_relative_to(directory.resolve()) or "\\" in info.filename:
                    raise ValueError("Unsafe ZIP entry")
            archive.extractall(directory)
    else:
        with tarfile.open(path) as archive:
            archive.extractall(directory, filter="data")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    media = ROOT / "build/lgpl-native"
    targets = (
        ("media", media),
        ("qt", ROOT / "installer/corresponding-sources"),
        ("cuda", ROOT / "build/cuda"),
        ("nsis", ROOT / "build/nsis-portable"),
    )
    for group, directory in targets:
        manifest = ROOT / f"build-support/{group}-sources.json"
        if group == "cuda":
            manifest = ROOT / "build-support/cuda-source.json"
        rows = json.loads(manifest.read_text("utf-8"))
        for row in rows:
            path = download(row, directory)
            if args.extract and group != "qt":
                folder = directory
                if row["file"].endswith(".tar.xz"):
                    folder = directory / row["file"].removesuffix(".tar.xz")
                elif row["file"].endswith(".tar.gz"):
                    folder = directory / row["file"].removesuffix(".tar.gz")
                elif group == "media":
                    folder = directory / "nasm"
                extract(path, folder)
        if group in {"media", "qt"}:
            shutil.copy2(
                manifest, directory / ("sources.json" if group == "media" else "qt-sources.json")
            )


if __name__ == "__main__":
    main()
