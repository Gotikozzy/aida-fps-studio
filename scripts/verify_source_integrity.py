"""Check the imported measurement/UI baseline without importing the application."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(root: Path = ROOT) -> list[str]:
    baseline = json.loads((root / "build-support/measurement-baseline.json").read_text("utf-8"))
    errors = []
    for name, expected in baseline["files"].items():
        path = root / name
        if not path.is_file():
            errors.append(name)
            continue
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            errors.append(name)
    return errors


if __name__ == "__main__":
    failures = verify()
    if failures:
        raise SystemExit("Baseline differs: " + ", ".join(failures))
    print("0.8.14 measurement baseline preserved")
