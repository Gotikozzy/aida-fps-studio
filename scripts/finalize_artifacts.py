"""Create release checksums only from final installer bytes; no network publication."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    directory = ROOT / "dist/installer/public"
    setup = directory / f"AIDA-FPS-Studio-{version}-windows-x64-setup.exe"
    if not setup.is_file():
        raise SystemExit("Final installer missing")
    package = setup.with_suffix(".zip")
    with ZipFile(package, "w", ZIP_STORED) as archive:
        archive.write(setup, setup.name)
    hashes = []
    for path in (setup, package):
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        hashes.append(f"{digest}  {path.name}\n")
    digest = hashes[1].split()[0]
    (directory / "SHA256SUMS.txt").write_text("".join(hashes), encoding="ascii")
    package.with_suffix(".sha256").write_text(hashes[1], encoding="ascii")
    # Rebuild portable delivery after legal/source staging and any inner-file signing.
    bundle = ROOT / "dist" / version / "AIDA-FPS-Studio"
    if bundle.is_dir():
        portable = ROOT / "dist" / f"AIDA-FPS-Studio-{version}-windows-x64.zip"
        with ZipFile(portable, "w", ZIP_DEFLATED) as archive:
            for path in sorted(bundle.rglob("*")):
                if path.is_file():
                    archive.write(path, Path("AIDA-FPS-Studio") / path.relative_to(bundle))
    # A candidate file only: never upload this automatically or before signature review.
    (directory / "update.candidate.json").write_text(
        json.dumps(
            {
                "version": version,
                "sha256": digest,
                "size": package.stat().st_size,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Final hashes prepared; verify signing status before publication")


if __name__ == "__main__":
    main()
