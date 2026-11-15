"""Reproducible local media composition: FFmpeg + OpenH264 + dav1d + NV headers.

Sources/toolchain are staged under build/lgpl-native with their SHA-256 inventory.
The existing PyAV environment and validated analyzer are never overwritten.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/lgpl-native"
PREFIX = BUILD / "prefix"


def main() -> None:
    tools = BUILD / "toolchain/w64devkit/bin"
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(tools), str(BUILD / "nasm/nasm-2.16.03"),
                                   str(Path(sys.executable).parent), env["PATH"]))
    env.update(CC="gcc", CXX="g++", AR="ar", PKG_CONFIG_PATH=str(PREFIX / "lib/pkgconfig"))
    temporary = BUILD / "tmp"
    temporary.mkdir(exist_ok=True)
    env.update(TMPDIR=temporary.as_posix(), TMP=temporary.as_posix(), TEMP=temporary.as_posix())

    def run(args: list[str], cwd: Path) -> None:
        print("RUN", args, flush=True)
        build_env = env.copy()
        if args[0] == sys.executable:
            # Meson probes GNU patch --version; BusyBox's patch lacks this option.
            build_env["PATH"] = "C:/Program Files/Git/usr/bin;" + build_env["PATH"]
        subprocess.run(args, cwd=cwd, env=build_env, check=True)

    prefix = PREFIX.as_posix()
    run([str(tools / "make.exe"), "-j12", "OS=mingw_nt", "ARCH=x86_64",
         "CC=gcc", "CXX=g++", "AR=ar", "BUILDTYPE=Release", f"PREFIX={prefix}",
         "install-static"], BUILD / "openh264-v2.6.0/openh264-2.6.0")
    run([str(tools / "make.exe"), "OS=mingw_nt", f"PREFIX={prefix}", "install"],
        BUILD / "nv-codec-headers-12.1.14.0/nv-codec-headers-n12.1.14.0")
    dav1d = BUILD / "dav1d-1.5.1/dav1d-1.5.1"
    meson_build = BUILD / "dav1d-build"
    if not meson_build.exists():
        run([sys.executable, "-m", "mesonbuild.mesonmain", "setup", str(meson_build),
             str(dav1d), "--prefix", str(PREFIX), "--libdir=lib", "--buildtype=release",
             "--default-library=static", "-Denable_tools=false", "-Denable_tests=false"], BUILD)
    run([sys.executable, "-m", "mesonbuild.mesonmain", "compile", "-C", str(meson_build),
         "-j", "12"], BUILD)
    run([sys.executable, "-m", "mesonbuild.mesonmain", "install", "-C", str(meson_build)], BUILD)
    ffmpeg = BUILD / "ffmpeg-8.0.1/ffmpeg-8.0.1"
    configure = [str(tools / "sh.exe"), "./configure", f"--prefix={prefix}",
                 "--target-os=mingw32", "--arch=x86_64", "--cc=gcc", "--cxx=g++",
                 "--disable-autodetect", "--enable-shared", "--disable-static",
                 "--disable-gpl", "--disable-nonfree", "--enable-version3",
                 "--enable-libopenh264", "--enable-libdav1d", "--enable-ffnvcodec",
                 "--enable-nvenc", "--enable-nvdec", "--disable-programs", "--disable-doc",
                 "--disable-debug", "--pkg-config-flags=--static", "--extra-libs=-lstdc++"]
    run(configure, ffmpeg)
    (BUILD / "configure.json").write_text(json.dumps(configure[2:], indent=2), encoding="utf-8")
    run([str(tools / "make.exe"), "-j12"], ffmpeg)
    run([str(tools / "make.exe"), "install"], ffmpeg)


if __name__ == "__main__":
    main()
