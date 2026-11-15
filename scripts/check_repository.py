"""Fail on missing public-source inputs, license drift and private binary payloads."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    assert metadata["license"] == "Apache-2.0"
    assert (
        ROOT / "src/dg_fps/__init__.py"
    ).read_text().strip() == f'__version__ = "{metadata["version"]}"'
    required = [
        "LICENSE",
        "NOTICE",
        "README.md",
        "README.pt-BR.md",
        "SPECIFICATION.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "PRIVACY.md",
        "CODE_SIGNING.md",
        "docs/en/BUILD.md",
        "docs/pt-BR/BUILD.md",
    ]
    assert all((ROOT / name).is_file() for name in required)
    assert (ROOT / "LICENSE").read_bytes() == (ROOT / "installer/public/LICENSE.txt").read_bytes()
    assert (ROOT / "THIRD_PARTY_NOTICES.md").read_bytes() == (
        ROOT / "installer/public/THIRD_PARTY_NOTICES.md"
    ).read_bytes()
    for name in (
        "src/dg_fps/ui/i18n.py",
        "src/dg_fps/ui/licenses.py",
        "installer/public/Terms.txt",
    ):
        text = (ROOT / name).read_text("utf-8")
        assert "proprietary application code" not in text and "código próprio fechado" not in text
    for manifest in (ROOT / "build-support").glob("*-sources.json"):
        for row in json.loads(manifest.read_text()):
            assert row["url"].startswith("https://") and len(row["sha256"]) == 64
    print("Public-source metadata and license checks passed")


if __name__ == "__main__":
    main()
