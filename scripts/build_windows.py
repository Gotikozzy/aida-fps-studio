"""Build inside this project's environment; no dependency on the parent repository."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from PySide6.QtCore import QLibraryInfo

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--media-runtime", type=Path, default=root / "build/lgpl-native/site")
parser.add_argument("--legacy-media-qa", action="store_true")
args = parser.parse_args()
if not args.legacy_media_qa and not (args.media_runtime / "runtime-manifest.json").is_file():
    parser.error("Prepare and validate the LGPL media runtime before building")
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
library = root / "src/dg_fps/_native/dg_nvidia_optical_flow.dll"
qt_portuguese = (
    Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)) / "qtbase_pt_BR.qm"
)
if not library.is_file():
    raise RuntimeError("Build the bundled NVIDIA bridge with scripts/build_nvidia.py first")
version_file = root / "build" / "windows-version.txt"
version_file.parent.mkdir(parents=True, exist_ok=True)
windows_version = (*map(int, version.split(".")), 0)
version_file.write_text(
    f"""
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers={windows_version}, prodvers={windows_version},
        mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)
    ),
    kids=[
        StringFileInfo([StringTable('040904B0', [
            StringStruct('FileDescription', 'AIDA FPS Studio'),
            StringStruct('FileVersion', '{version}'),
            StringStruct('ProductName', 'AIDA FPS Studio'),
            StringStruct('ProductVersion', '{version}'),
            StringStruct('OriginalFilename', 'AIDA-FPS-Studio.exe'),
        ])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])]),
    ],
)
""".lstrip(),
    encoding="utf-8",
)
environment = os.environ.copy()
windows = Path(os.environ.get("SYSTEMROOT", "C:/Windows"))
# Ignore unrelated native tools on the host PATH (for example Poppler's ICU).
# Otherwise dependency scanning can silently bundle incompatible DLLs for Qt.
environment["PATH"] = os.pathsep.join(
    str(path)
    for path in (Path(sys.executable).parent, Path(sys.base_prefix), windows / "System32", windows)
)
for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
    environment.pop(key, None)
if not args.legacy_media_qa:
    environment["PYTHONPATH"] = str(args.media_runtime.resolve())
subprocess.run(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--additional-hooks-dir",
        str(root / "scripts/pyinstaller_hooks"),
        "--windowed",
        "--onedir",
        "--name",
        "AIDA-FPS-Studio",
        "--icon",
        str(root / "src/dg_fps/assets/aida-executable.ico"),
        "--version-file",
        str(version_file),
        "--distpath",
        str(root / "dist" / version),
        "--paths",
        str(root / "src"),
        *(["--paths", str(args.media_runtime.resolve())] if not args.legacy_media_qa else []),
        "--copy-metadata",
        "av",
        "--copy-metadata",
        "numpy",
        "--collect-submodules",
        "av",
        "--add-data",
        f"{library};dg_fps/_native",
        "--add-data",
        f"{qt_portuguese};PySide6/translations",
        "--add-data",
        f"{root / 'src/dg_fps/assets'};dg_fps/assets",
        str(root / "scripts" / "launch.py"),
    ],
    cwd=root,
    env=environment,
    check=True,
)

# Video I/O is exclusively PyAV. This unused OpenCV FFmpeg plugin is not shipped;
# OpenCV's optical flow, image conversion and ROI operations remain unchanged.
bundle = root / "dist" / version / "AIDA-FPS-Studio"
for plugin in (bundle / "_internal/cv2").glob("opencv_videoio_ffmpeg*.dll"):
    plugin.unlink()
software_gl = bundle / "_internal/PySide6/opengl32sw.dll"
if software_gl.is_file():
    # The Studio uses raster Qt Widgets/QImage; it never creates OpenGL widgets.
    software_gl.unlink()
if not args.legacy_media_qa:
    if any((bundle / "_internal/av.libs").glob("libx26*.dll")):
        raise RuntimeError("The frozen bundle selected the legacy GPL media runtime")
    for library in (args.media_runtime / "av.libs").glob("*.dll"):
        target = bundle / "_internal/av.libs" / library.name
        if not target.is_file() or library.read_bytes() != target.read_bytes():
            raise RuntimeError(f"Frozen media library differs from validated input: {library.name}")
        duplicate = bundle / "_internal" / library.name
        if duplicate.is_file():
            if duplicate.read_bytes() != library.read_bytes():
                raise RuntimeError("Conflicting media dependency: " + library.name)
            duplicate.unlink()
