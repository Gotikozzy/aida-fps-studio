"""Assemble readable notices and bind distribution review to the actual payload."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    "PySide6-Essentials", "shiboken6", "av", "numpy", "opencv-python",
    "platformdirs", "pyinstaller",
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def collect(bundle: Path, compiler_license: Path) -> Path:
    """Keep original full notices, including Python's transitive notices."""
    licenses = bundle / "third_party_licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    inventory = []
    packages = set(PACKAGES)
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(bundle / "AIDA-FPS-Studio.exe")).open_embedded_archive("PYZ.pyz")
    owners = importlib.metadata.packages_distributions()
    for module in archive.toc:
        if not module.startswith("dg_fps"):
            packages.update(owners.get(module.split(".", 1)[0], []))
    packages = {n.lower().replace("_", "-") for n in packages}
    for name in sorted(packages):
        dist = importlib.metadata.distribution(name)
        inventory.append({"package": name, "version": dist.version,
                          "license": dist.metadata.get("License-Expression")
                          or dist.metadata.get("License", "See original notices")})
        for entry in dist.files or ():
            if ".." in entry.parts or "__pycache__" in entry.parts or entry.suffix == ".pyc":
                continue
            if any(word in str(entry).lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    target = licenses / name / str(entry)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", licenses / "Python-LICENSE.txt")
    shutil.copy2(ROOT / "native/NVIDIA-MIT-LICENSE.txt", licenses / "NVIDIA-Optical-Flow-MIT.txt")
    shutil.copy2(compiler_license, licenses / "NSIS-LICENSE.txt")
    originals = ROOT / "installer/third_party_texts"
    for source in originals.rglob("*"):
        if source.is_file():
            target = licenses / source.relative_to(originals)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    sources = ROOT / "installer/corresponding-sources"
    if sources.is_dir():
        for source in sources.iterdir():
            if source.is_file():
                target = licenses / "sources" / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    shutil.copy2(ROOT / "installer/third_party_texts/sources.json",
                 licenses / "license-text-sources.json")
    inventory.extend([
        {"package": "Python", "version": sys.version.split()[0]},
        {"package": "NVIDIA Optical Flow MIT helper files", "version": "5.0.7"},
        {"package": "NSIS", "version": "3.13"},
    ])
    (licenses / "inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "AIDA FPS Studio — THIRD-PARTY COMPONENTS / COMPONENTES DE TERCEIROS",
        "",
        "Qt/PySide/Shiboken: LGPL option selected; commercial license not claimed.",
        "Qt/PySide/Shiboken: opção LGPL; não se declara licença comercial.",
        "Native transitive review: distribution-review.json. QA is not a public clearance.",
        "Revisão transitiva: distribution-review.json. QA não é liberação pública.",
        "",
    ]
    for entry in inventory:
        original = entry.get("license", "See original notices / Consulte os avisos originais")
        lines.append(f"{entry['package']} {entry['version']}: {original}")
    (licenses / "COMPONENTS.txt").write_text("\n".join(lines), encoding="utf-8")
    return licenses


def review_payload(bundle: Path, policy_path: Path) -> dict:
    """A filename or self-reported LGPL string alone never grants release approval.

    Approvals require exact binary hashes and preserved license files. Copyleft
    approvals also require the exact corresponding-source archive locally.
    """
    policy = json.loads(policy_path.read_text("utf-8"))
    approvals = {item["sha256"]: item for item in policy.get("approved_binaries", [])}
    binaries = []
    blockers = []
    if policy.get("inventory_sha256"):
        inventory = bundle / "third_party_licenses/inventory.json"
        if not inventory.is_file() or sha256(inventory) != policy["inventory_sha256"]:
            blockers.append({"path": "third_party_licenses/inventory.json",
                             "issues": ["unreviewed_python_inventory"]})
    for path in sorted((bundle / "_internal").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".dll", ".pyd", ".exe"}:
            continue
        digest = sha256(path)
        approved = approvals.get(digest)
        reasons = []
        if approved is None:
            reasons.append("binary_not_reviewed")
        else:
            if not approved.get("distribution_compatible"):
                reasons.append("not_approved_for_distribution")
            if not approved.get("component") or not approved.get("license"):
                reasons.append("missing_component_or_license")
            notices = approved.get("notices", [])
            if not notices or any(not confined_file(bundle, n) for n in notices):
                reasons.append("missing_license_notice")
            elif any(sha256(confined_file(bundle, n)) != approved.get("notice_sha256", {}).get(n)
                     for n in notices):
                reasons.append("unverified_license_notice")
            if approved.get("corresponding_source_required", True):
                source = confined_file(bundle, approved.get("source_archive", ""))
                if source is None or sha256(source) != approved.get("source_sha256"):
                    reasons.append("missing_exact_corresponding_source")
        # Known GPL components cannot be cleared merely by adding an approval row.
        if path.name.lower().startswith(("libx264", "libx265")):
            reasons.append("unexpected_codec_in_validated_runtime")
        record = {"path": path.relative_to(bundle).as_posix(), "sha256": digest,
                  "component": approved.get("component") if approved else None,
                  "issues": reasons}
        binaries.append(record)
        if reasons:
            blockers.append(record)
    if not binaries:
        blockers.append({"path": "_internal", "issues": ["no_native_payload"]})
    return {"format_version": 1, "public_release_allowed": not blockers,
            "native_files": binaries, "blockers": blockers}


def confined_file(root: Path, name: str) -> Path | None:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        return None
    path = (root / name).resolve()
    if path.is_relative_to(root.resolve()) and path.is_file():
        return path
    return None


def combined_terms(terms: Path, license_file: Path, notices: Path, licenses: Path) -> str:
    parts = [terms.read_text("utf-8-sig"), license_file.read_text("utf-8-sig"),
             notices.read_text("utf-8-sig")]
    parts.append(
        "\nTHIRD-PARTY LICENSES / LICENÇAS DE TERCEIROS\n"
        "Original notices follow. Each license governs its own component.\n"
        "Os avisos originais seguem abaixo. Cada licença rege seu componente.\n"
        "Accepting the AIDA terms does not waive third-party license rights.\n"
        "Aceitar os termos do AIDA não limita direitos previstos nestas licenças.\n"
    )
    for path in sorted(licenses.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".md", ".rst", ""}:
            parts.append("\n\n===== " + path.relative_to(licenses).as_posix() + " =====\n\n")
            parts.append(path.read_text("utf-8-sig", errors="replace"))
    return "\n\n".join(parts)


def localized_terms(terms: Path) -> dict[str, str]:
    """Present existing AIDA terms per language, without upstream concatenation."""
    text = terms.read_text("utf-8-sig")
    if "\nPORTUGUÊS\n" not in text or "\nENGLISH\n" not in text:
        return {"pt": text, "en": text}  # Internal QA/isolated test fixtures.
    pt, en = text.split("\nPORTUGUÊS\n", 1)[1].split("\nENGLISH\n", 1)
    en = en.split("\nOs textos completos de licenças", 1)[0]
    return {"pt": "AIDA FPS Studio — Termos de uso\n\n" + pt.strip(),
            "en": "AIDA FPS Studio — Terms of use\n\n" + en.strip()}


def license_catalog(terms: Path, license_file: Path, notices: Path, licenses: Path) -> str:
    """Offline, escaped complete documents, accessible before installer acceptance."""
    documents = [(p.name, p) for p in (terms, license_file, notices)]
    documents.extend((p.relative_to(licenses).as_posix(), p)
                     for p in sorted(licenses.rglob("*"))
                     if p.is_file() and p.suffix.lower() in {".txt", ".md", ".rst", ""})
    sections = "\n".join(
        f"<details><summary>{escape(name)}</summary><pre>"
        + escape(path.read_text("utf-8-sig", errors="replace")) + "</pre></details>"
        for name, path in documents
    )
    return """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIDA — Termos e licenças / Terms and licenses</title>
<style>body{background:#12161c;color:#e4e9ef;font:16px/1.6 system-ui;max-width:1100px;
margin:40px auto;padding:0 24px}h1{font-size:28px}p{color:#b8c4d0}summary{cursor:pointer;
padding:15px;color:#74d8e8;overflow-wrap:anywhere}details{border-bottom:1px solid #34404e}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 monospace;padding:0 18px}
summary:focus-visible{outline:2px solid #ff9528}strong{color:#ffb465}</style>
<h1>AIDA FPS Studio — Termos e licenças / Terms and licenses</h1>
<p>O AIDA usa Qt/PySide/Shiboken e FFmpeg sob LGPL, além de outros componentes de
terceiros. Seus textos completos estão abaixo. Abra um documento para consultar.</p>
<p lang="en">AIDA uses LGPL Qt/PySide/Shiboken and FFmpeg and other third-party
components. Complete documents follow. Expand a document to read it.</p>
<p><strong>Os termos do AIDA não limitam os direitos de terceiros.<br>
AIDA terms do not restrict third-party license rights.</strong></p>
<p>Fontes e instruções / Sources and replacement instructions:
third_party_licenses/sources — SOURCES-AND-REPLACEMENT.txt</p>
""" + sections + "</html>"
