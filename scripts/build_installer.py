"""Build a per-user setup from the existing Windows bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from distribution_licenses import collect, license_catalog, localized_terms, review_payload
from package_release import DIST, ROOT, VERSION

APP_EXE = "AIDA-FPS-Studio.exe"


def payload_files(bundle: Path) -> set[str]:
    files = {APP_EXE, "Terms.txt", "LICENSE.txt", "THIRD_PARTY_NOTICES.md"}
    files.add("third_party_licenses/NSIS-LICENSE.txt")
    for name in ("_internal", "third_party_licenses"):
        directory = bundle / name
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                files.add(path.relative_to(bundle).as_posix())
    return files


def removal_commands(files: set[str]) -> str:
    directories = set()
    commands = []
    for name in sorted(files):
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or '"' in name
            or "\n" in name
            or ":" in name
            or "\\" in name
            or (len(path.parts) > 1 and path.parts[0] not in {"_internal", "third_party_licenses"})
            or (
                len(path.parts) == 1
                and name not in {APP_EXE, "Terms.txt", "LICENSE.txt", "THIRD_PARTY_NOTICES.md"}
            )
        ):
            raise ValueError(f"Unsafe installer-owned path: {name}")
        escaped = name.replace("/", "\\").replace("$", "$$")
        commands.append(f'Delete "$INSTDIR\\{escaped}"')
        directories.update(p.as_posix() for p in path.parents if str(p) != ".")
    for name in sorted(directories, key=lambda p: (p.count("/"), p), reverse=True):
        escaped = name.replace("/", "\\").replace("$", "$$")
        commands.append(f'RMDir "$INSTDIR\\{escaped}"')
    return "\n".join(commands) + "\n"


def uninstall_commands(bundle: Path, historical: set[str] | None = None) -> str:
    return removal_commands(payload_files(bundle) | (historical or set()))


def retired_files(historical: set[str], current: set[str]) -> set[str]:
    """NTFS paths differing only by case name the same installed file."""
    installed = {name.casefold() for name in current}
    return {name for name in historical if name.casefold() not in installed}


def historical_files() -> set[str]:
    """Track exact previously shipped paths; never recursively remove install folders."""
    manifest = ROOT / "installer/managed-files.json"
    files = set(json.loads(manifest.read_text("utf-8"))) if manifest.is_file() else set()
    removal_commands(files)  # Validate before persisting or compiling.
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", required=True, type=Path, help="Path to NSIS makensis.exe")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--qa", action="store_true", help="Use draft terms for internal testing")
    mode.add_argument(
        "--legal-dir", type=Path, help="Directory with reviewed distribution documents"
    )
    args = parser.parse_args()

    installer = ROOT / "installer"
    bundle = DIST / VERSION / "AIDA-FPS-Studio"
    compiler = args.compiler.resolve()
    compiler_license = compiler.parent / "COPYING"
    if not compiler_license.is_file():
        compiler_license = compiler.parent.parent / "COPYING"
    legal = installer / "qa" if args.qa else args.legal_dir.resolve()
    terms = legal / "Terms.txt"
    license_file = legal / "LICENSE.txt"
    notices = ROOT / "THIRD_PARTY_NOTICES.md" if args.qa else legal / "THIRD_PARTY_NOTICES.md"
    required = (
        compiler,
        compiler_license,
        bundle / APP_EXE,
        terms,
        license_file,
        notices,
    )
    for path in required:
        if not path.is_file():
            parser.error(f"Required file missing: {path}")
    if not (bundle / "_internal").is_dir():
        parser.error("Run build_windows.py and package_release.py to prepare the Windows bundle")
    if not args.qa and legal == installer / "qa":
        parser.error("The internal QA terms cannot be used for public distribution")

    licenses = collect(bundle, compiler_license)
    translated_terms = localized_terms(terms)
    aida_terms = licenses / "aida"
    aida_terms.mkdir(exist_ok=True)
    for language, text in translated_terms.items():
        (aida_terms / f"Terms.{language}.txt").write_text(text + "\n", encoding="utf-8")
    catalog = licenses / "LICENSES.html"
    catalog.write_text(license_catalog(terms, license_file, notices, licenses), encoding="utf-8")
    review = review_payload(bundle, installer / "distribution-review.json")
    (licenses / "distribution-review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not args.qa and not review["public_release_allowed"]:
        parser.error(
            "Public distribution blocked: unreviewed/incompatible native components. "
            "See third_party_licenses/distribution-review.json. QA remains available."
        )

    output = DIST / "installer" / ("qa" if args.qa else "public")
    output.mkdir(parents=True, exist_ok=True)
    suffix = "-qa" if args.qa else ""
    stem = f"AIDA-FPS-Studio-{VERSION}-windows-x64-setup{suffix}"
    package = output / f"{stem}.zip"
    with tempfile.TemporaryDirectory(dir=output) as temp:
        staging = Path(temp)
        setup = staging / f"{stem}.exe"
        remove_files = staging / "uninstall.nsh"
        historical = historical_files()
        remove_files.write_text(uninstall_commands(bundle, historical), encoding="utf-8-sig")
        retired = staging / "retired.nsh"
        retired.write_text(
            removal_commands(retired_files(historical, payload_files(bundle))),
            encoding="utf-8-sig",
        )
        wizard_terms = staging / "Terms.txt"
        wizard_terms.write_text(terms.read_text("utf-8-sig"), encoding="utf-8-sig")
        terms_pt, terms_en = staging / "Terms.pt.txt", staging / "Terms.en.txt"
        terms_pt.write_text(translated_terms["pt"], encoding="utf-16")
        terms_en.write_text(translated_terms["en"], encoding="utf-16")
        defines = {
            "Version": VERSION,
            "Edition": " QA" if args.qa else "",
            "BundleDir": bundle,
            "SetupPath": setup,
            "TermsPath": wizard_terms,
            "TermsPtPath": terms_pt,
            "TermsEnPath": terms_en,
            "LicenseCatalog": catalog,
            "LicensePath": license_file,
            "NoticesPath": notices,
            "CompilerLicense": compiler_license,
            "AppIcon": ROOT / "src/dg_fps/assets/aida-executable.ico",
            "RemoveFiles": remove_files,
            "RetireFiles": retired,
        }
        subprocess.run(
            [
                str(compiler),
                "/WX",
                "/INPUTCHARSET",
                "UTF8",
                *(f"/D{key}={value}" for key, value in defines.items()),
                str(installer / "windows.nsi"),
            ],
            check=True,
            cwd=ROOT,
        )
        shutil.copy2(setup, output / setup.name)
        staged_package = staging / package.name
        with ZipFile(staged_package, "w", ZIP_STORED) as archive:
            archive.write(setup, setup.name)
        staged_package.replace(package)
    with package.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    package.with_suffix(".sha256").write_text(f"{digest}  {package.name}\n", encoding="ascii")
    print(package)


if __name__ == "__main__":
    main()
