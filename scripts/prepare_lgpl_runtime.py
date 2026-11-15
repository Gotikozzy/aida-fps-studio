"""Create an isolated PyAV runtime linked to explicitly selected LGPL FFmpeg DLLs.

Does not change the installed environment. Only PE import names are rebound;
the binding's code and the analyzer's code are unchanged. Run validation in a
fresh process with PYTHONPATH pointing at the generated site directory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path

import pefile

LIBRARY = re.compile(
    rb"(avcodec|avdevice|avfilter|avformat|avutil|swresample|swscale)-(\d+)"
    rb"(?:-[0-9a-f]+)?\.dll", re.IGNORECASE,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(ffmpeg_bin: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("Use a new output directory; the baseline is never overwritten")
    source = Path(importlib.util.find_spec("av").origin).parent
    output.mkdir(parents=True)
    shutil.copytree(source, output / "av", ignore=shutil.ignore_patterns("__pycache__"))
    libraries = output / "av.libs"
    libraries.mkdir()
    for path in ffmpeg_bin.glob("*.dll"):
        shutil.copy2(path, libraries / path.name)
    changes = []
    for path in (output / "av").rglob("*.pyd"):
        before = digest(path)
        data = bytearray(path.read_bytes())
        pe = pefile.PE(data=bytes(data))
        imports = [*getattr(pe, "DIRECTORY_ENTRY_IMPORT", []),
                   *getattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT", [])]
        rebound = []
        for entry in imports:
            match = LIBRARY.fullmatch(entry.dll)
            if match is None:
                continue
            name = match[1] + b"-" + match[2] + b".dll"
            if not (libraries / name.decode("ascii")).is_file():
                raise ValueError("Missing matching FFmpeg ABI library: " + name.decode())
            offset = pe.get_offset_from_rva(entry.struct.Name)
            data[offset:offset + len(entry.dll) + 1] = name + b"\0" * (
                len(entry.dll) + 1 - len(name)
            )
            rebound.append({"from": entry.dll.decode(), "to": name.decode()})
        pe.close()
        if rebound:
            path.write_bytes(data)
            changes.append({"path": path.relative_to(output).as_posix(),
                            "original_sha256": before, "sha256": digest(path),
                            "imports": rebound})
    if not changes:
        raise ValueError("No PyAV import libraries were rebound")
    (output / "runtime-manifest.json").write_text(json.dumps({
        "binding": str(source), "changes": changes,
        "libraries": [{"name": p.name, "sha256": digest(p)} for p in libraries.glob("*.dll")],
    }, indent=2), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ffmpeg_bin", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.ffmpeg_bin, args.output)
