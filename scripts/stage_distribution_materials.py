"""Preserve upstream notices and provide LGPL sources alongside the installer."""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sources = ROOT / "installer/corresponding-sources"
    notices = ROOT / "installer/third_party_texts/qt-upstream"
    native = ROOT / "build/lgpl-native"
    for archive in sources.glob("*.tar.*"):
        with tarfile.open(archive) as stream:
            for member in stream.getmembers():
                path = Path(member.name)
                if not member.isfile() or ".." in path.parts:
                    continue
                upper = path.name.upper()
                if ("LICENSE" in upper or "COPYING" in upper or "NOTICE" in upper
                        or upper == "QT_ATTRIBUTION.JSON"
                        or upper == "COPYRIGHT"):
                    data = stream.extractfile(member).read()
                    if b"\0" in data or len(data) > 2_000_000:
                        continue
                    target = notices / archive.name / (member.name + ".txt")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
    media = sources / "aida-media-corresponding-sources.zip"
    with ZipFile(media, "w", ZIP_STORED) as archive:
        for name in ("ffmpeg-8.0.1.tar.xz", "openh264-v2.6.0.tar.gz", "dav1d-1.5.1.tar.gz",
                     "nv-codec-headers-12.1.14.0.tar.gz", "sources.json", "configure.json"):
            archive.write(native / name, name)
        for name in ("build_lgpl_ffmpeg.py", "prepare_lgpl_runtime.py"):
            archive.write(ROOT / "scripts" / name, "build/" + name)
        archive.write(native / "site/runtime-manifest.json", "runtime-manifest.json")
        archive.writestr("README.txt", (
            "AIDA media libraries: FFmpeg 8.0.1 (LGPL-3.0-or-later), OpenH264 2.6.0 (BSD), "
            "dav1d 1.5.1 (BSD), nv-codec-headers 12.1.14.0 (MIT).\n"
            "No GPL/nonfree codecs are enabled. configure.json records all configure arguments.\n"
            "Unmodified upstream source archives are supplied in full.\n"
            "Build: GCC 16.2 via w64devkit 2.11.0, NASM 2.16.03, Meson 1.9.1, Ninja 1.13.0.\n"
            "Stage archives as build/lgpl-native, extract them, install the developer tools, "
            "then run build_lgpl_ffmpeg.py with Python 3.12.\n"
            "prepare_lgpl_runtime.py rebinds the unmodified BSD PyAV 16.1.0 binding's import "
            "names to standard FFmpeg DLL names; no binding machine code is changed.\n"
            "Compatible replacement DLLs can replace those under _internal/av.libs.\n"
            "Back up the installed folder first; library ABI compatibility remains necessary.\n"
            "Build helpers may be used, copied, changed and redistributed to rebuild and "
            "replace these libraries; AIDA application code is separately licensed under Apache-2.0.\n"
        ))
    entries = []
    for path in sorted(sources.iterdir()):
        if path.is_file() and path.name != "inventory.json":
            entries.append({"file": path.name,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (sources / "inventory.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print("Source archives:", len(entries), "upstream notices:", len(list(notices.rglob('*.txt'))))


if __name__ == "__main__":
    main()
