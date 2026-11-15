"""Fetch immutable pilot inputs; the legacy executable remains a private QA draft."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from zipfile import ZipFile

REPOSITORY = "Gotikozzy/aida-fps-studio"
LEGACY_RELEASE = 446369834
CURRENT_ARTIFACT = 14178822854
LEGACY_NAME = "AIDA-FPS-Studio-0.8.14-windows-x64-setup.exe"
CURRENT_NAME = "AIDA-FPS-Studio-0.8.15-windows-x64-setup.exe"
LEGACY_HASH = "088e604644821a1bbfdf6f4e52b76978dcccb58b8774b46f1abb489a3ca40b8e"
LEGACY_HASHES = {
    "0.8.14": LEGACY_HASH,
    "0.8.12": "e904c7e1c89d6f8094a5f1f6a070fbb8c6882dec46b87a9ca8f22accf59d90e5",
}
PUBLIC_LEGACY_ZIP_HASH = "3b78ff81ce3b89d46168400b675a5935867703202a193a47be483b8a09cab7eb"
CURRENT_HASH = "330f08d0daf617804ea145d0d0594a19d19b16868f6dd6bc54c826d9319585b0"
ARTIFACT_HASH = "c07d55d349f65705db8576368e2546221affd532394b89512168e087d458df67"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def api(path: str) -> dict:
    return json.loads(subprocess.check_output(["gh", "api", f"repos/{REPOSITORY}/{path}"]))


def download(
    path: str, target: Path, expected: str, *, accept: str = "application/octet-stream"
) -> None:
    partial = target.with_suffix(target.suffix + ".part")
    try:
        with partial.open("wb") as stream:
            subprocess.run(
                [
                    "gh",
                    "api",
                    "-H",
                    "Accept: " + accept,
                    f"repos/{REPOSITORY}/{path}",
                ],
                stdout=stream,
                check=True,
            )
        if sha256(partial) != expected:
            raise ValueError("Pilot download hash mismatch: " + target.name)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def extract_installer(archive: Path, target: Path, expected: str, name: str = CURRENT_NAME) -> None:
    """Only the named EXE leaves the artifact, never arbitrary ZIP paths."""
    with ZipFile(archive) as stream:
        entries = [i for i in stream.infolist() if i.filename == name]
        if len(entries) != 1 or entries[0].is_dir() or not 0 < entries[0].file_size < 1_000_000_000:
            raise ValueError("Unexpected installer entry")
        with stream.open(entries[0]) as source, target.open("xb") as output:
            shutil.copyfileobj(source, output)
    if sha256(target) != expected:
        target.unlink()
        raise ValueError("Extracted installer hash mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--legacy-version", choices=("0.8.12", "0.8.14"), required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Pilot input preparation is intended for GitHub Actions")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.legacy_version == "0.8.14":
        release = api(f"releases/{LEGACY_RELEASE}")
        if not release["draft"] or release["tag_name"] != "qa-reference-0.8.14":
            raise ValueError("Unexpected legacy reference release")
        asset = next(a for a in release["assets"] if a["name"] == LEGACY_NAME)
        download(f"releases/assets/{asset['id']}", args.output / LEGACY_NAME, LEGACY_HASH)
    else:
        legacy_zip = args.output / "legacy-0.8.12.zip"
        url = (
            "https://detonandogueek.com.br/static/aida/AIDA-FPS-Studio-0.8.12-windows-x64-setup.zip"
        )
        with urllib.request.urlopen(url, timeout=120) as response, legacy_zip.open("wb") as out:
            shutil.copyfileobj(response, out)
        if sha256(legacy_zip) != PUBLIC_LEGACY_ZIP_HASH:
            raise ValueError("Public 0.8.12 reference hash mismatch")
        name = "AIDA-FPS-Studio-0.8.12-windows-x64-setup.exe"
        extract_installer(legacy_zip, args.output / name, LEGACY_HASHES["0.8.12"], name)
    metadata = api(f"actions/artifacts/{CURRENT_ARTIFACT}")
    if (
        metadata["expired"]
        or metadata.get("digest") != "sha256:" + ARTIFACT_HASH
        or metadata["workflow_run"]["head_sha"] != "7c2ae28552f994c9675669db2fa63f6d2694fc1b"
    ):
        raise ValueError("Unexpected candidate artifact origin")
    archive = args.output / "github-artifact.zip"
    # Actions negotiates JSON before redirecting to the ZIP. Release assets use
    # octet-stream instead; using that media type here produces HTTP 415.
    download(
        f"actions/artifacts/{CURRENT_ARTIFACT}/zip",
        archive,
        ARTIFACT_HASH,
        accept="application/json",
    )
    extract_installer(archive, args.output / CURRENT_NAME, CURRENT_HASH)
    print("Both original installers fetched and verified")


if __name__ == "__main__":
    main()
