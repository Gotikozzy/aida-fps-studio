from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def main() -> None:
    DIST.mkdir(exist_ok=True)
    import subprocess
    source_zip = DIST / f"AIDA-FPS-Studio-{VERSION}-source.zip"
    subprocess.run([
        "git", "archive", "--format=zip", f"--prefix=aida-fps-studio-{VERSION}/",
        f"--output={source_zip}", "HEAD",
    ], cwd=ROOT, check=True)
    bundle = DIST / VERSION / "AIDA-FPS-Studio"
    if not (bundle / "AIDA-FPS-Studio.exe").is_file():
        raise RuntimeError("Gere o executável antes do pacote Windows")
    licenses = bundle / "third_party_licenses"
    inventory = []
    for name in (
        "PySide6-Essentials",
        "shiboken6",
        "av",
        "numpy",
        "opencv-python",
        "platformdirs",
        "pyinstaller",
    ):
        distribution = importlib.metadata.distribution(name)
        inventory.append({"package": name, "version": distribution.version})
        for entry in distribution.files or ():
            if any(token in str(entry).lower() for token in ("license", "copying", "notice")):
                source = Path(distribution.locate_file(entry))
                # Only package files; metadata may contain console paths outside site-packages.
                if source.is_file() and ".." not in entry.parts:
                    target = licenses / name / Path(str(entry))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read_bytes())
    licenses.mkdir(parents=True, exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        (licenses / "Python-LICENSE.txt").write_bytes(python_license.read_bytes())
    inventory.append({"package": "Python", "version": sys.version.split()[0]})
    (licenses / "NVIDIA-Optical-Flow-MIT.txt").write_bytes(
        (ROOT / "native/NVIDIA-MIT-LICENSE.txt").read_bytes()
    )
    inventory.append({"package": "NVIDIA Optical Flow MIT helper files", "version": "5.0.7"})
    (licenses / "inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for name in documents[:4]:
        (bundle / name).write_bytes((ROOT / name).read_bytes())
    with ZipFile(DIST / f"AIDA-FPS-Studio-{VERSION}-windows-x64.zip", "w", ZIP_DEFLATED) as archive:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                archive.write(path, Path("AIDA-FPS-Studio") / path.relative_to(bundle))
    names = [f"AIDA-FPS-Studio-{VERSION}-source.zip", f"AIDA-FPS-Studio-{VERSION}-windows-x64.zip"]
    checksums = []
    for name in names:
        with (DIST / name).open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        checksums.append(f"{digest}  {name}\n")
    (DIST / "SHA256SUMS.txt").write_text("".join(checksums), encoding="utf-8")
    print(f"Pacotes criados em {DIST}")


if __name__ == "__main__":
    main()
