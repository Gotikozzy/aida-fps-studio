"""Public portable delivery must retain project licenses and bilingual documentation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def test_portable_archive_contains_licenses_and_both_readmes(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "release_packaging", ROOT / "scripts/package_release.py"
    )
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    monkeypatch.setattr(package, "ROOT", tmp_path)
    monkeypatch.setattr(package, "DIST", tmp_path / "dist")
    bundle = package.DIST / package.VERSION / "AIDA-FPS-Studio"
    bundle.mkdir(parents=True)
    (bundle / "AIDA-FPS-Studio.exe").write_bytes(b"synthetic application")
    for name in package.DOCUMENTS:
        (tmp_path / name).write_text(f"Original content of {name}", encoding="utf-8")
    native = tmp_path / "native"
    native.mkdir()
    (native / "NVIDIA-MIT-LICENSE.txt").write_text("Original MIT notice", encoding="utf-8")
    monkeypatch.setattr(
        package.importlib.metadata,
        "distribution",
        lambda _: SimpleNamespace(version="test-fixture", files=[]),
    )

    def fake_archive(arguments, **_kwargs):
        output = next(
            value.removeprefix("--output=") for value in arguments if value.startswith("--output=")
        )
        with ZipFile(output, "w") as archive:
            archive.writestr("source.txt", "Synthetic Git archive")

    monkeypatch.setattr(package.subprocess, "run", fake_archive)
    package.main()
    portable = package.DIST / f"AIDA-FPS-Studio-{package.VERSION}-windows-x64.zip"
    with ZipFile(portable) as archive:
        for name in ("LICENSE", "NOTICE", "README.md", "README.pt-BR.md", "PRIVACY.md"):
            assert archive.read(f"AIDA-FPS-Studio/{name}") == (tmp_path / name).read_bytes()
