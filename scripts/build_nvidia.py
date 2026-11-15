"""Developer-only build. Users need a supported display driver, not CUDA Toolkit."""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cmake = shutil.which("cmake")
if cmake is None:
    candidate = Path(
        "C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/"
        "CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
    )
    cmake = str(candidate) if candidate.is_file() else None
if cmake is None:
    raise RuntimeError("Install CMake and Visual Studio C++ Build Tools")
arguments = [cmake, "-S", str(root / "native"), "-B", str(root / "build/nvidia"), "-A", "x64"]
version = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]["version"]
arguments.extend([f"-DAIDA_VERSION={version}", f"-DAIDA_VERSION_COMMA={version.replace('.', ',')}"])
redistributed = root / "build/cuda/cuda_cudart-windows-x86_64-12.6.77-archive"
if redistributed.is_dir():
    arguments.append(f"-DAIDA_CUDA_DRIVER_ROOT={redistributed}")
cuda = os.environ.get("CUDA_PATH")
if cuda and not redistributed.is_dir():
    arguments.append(f"-DCUDAToolkit_ROOT={cuda}")
subprocess.run(arguments, check=True)
subprocess.run([cmake, "--build", str(root / "build/nvidia"), "--config", "Release"], check=True)
