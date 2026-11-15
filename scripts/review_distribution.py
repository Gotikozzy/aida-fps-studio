"""Record hash-bound review for this validated, pinned release composition.

Unknown native files fail closed. This is a technical distribution review, not a
mechanism for reclassifying GPL codecs or approving arbitrary future binaries.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
from pathlib import Path

from distribution_licenses import collect, review_payload, sha256
from package_release import ROOT, VERSION


def main() -> None:
    expected = {
        "PySide6-Essentials": "6.12.0",
        "shiboken6": "6.12.0",
        "av": "16.1.0",
        "numpy": "2.5.4",
        "opencv-python": "4.14.0.94",
        "platformdirs": "4.14.5",
    }
    for name, version in expected.items():
        if importlib.metadata.version(name) != version:
            raise ValueError("Review must be repeated for changed component: " + name)
    # This classifies distribution inputs, not measurement equivalence or legal clearance.
    # Measurement and clean-CI gates are independently required by the release policy.
    bundle = ROOT / "dist" / VERSION / "AIDA-FPS-Studio"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compiler-license", type=Path, default=ROOT / "build/nsis-portable/nsis-3.13/COPYING"
    )
    args = parser.parse_args()
    collect(bundle, args.compiler_license)
    license_root = "third_party_licenses/"
    source_root = license_root + "sources/"
    all_notices = [
        license_root + "GNU-LGPL-3.0.txt",
        license_root + "GNU-GPL-3.0.txt",
        license_root + "SOURCES-AND-REPLACEMENT.txt",
    ]
    approvals = []
    notice_paths = [
        p
        for p in (bundle / "third_party_licenses").rglob("*")
        if p.is_file() and p.suffix.lower() in {".txt", ".md", ".rst"}
    ]
    for path in sorted((bundle / "_internal").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".dll", ".pyd", ".exe"}:
            continue
        relative = path.relative_to(bundle / "_internal")
        parts = relative.parts
        name = path.name.lower()
        component = license_id = source_name = None
        if re.fullmatch(r"(?:msvcp140|vcruntime140)(?:[_-][a-z0-9]+)*\.dll", name):
            component, license_id = "Microsoft VC Runtime", "Microsoft-VC-Runtime-2015-2022"
        elif parts[0] == "av.libs":
            if not re.fullmatch(
                r"(?:avcodec|avdevice|avfilter|avformat|avutil|swresample|swscale)-\d+\.dll", name
            ):
                raise ValueError("Unexpected media library: " + str(relative))
            component = "FFmpeg + OpenH264 + dav1d"
            license_id = "LGPL-3.0-or-later AND BSD-2/3-Clause"
            source_name = "aida-media-corresponding-sources.zip"
        elif parts[0] == "av" and path.suffix == ".pyd":
            component, license_id = "PyAV 16.1.0, import names rebound", "BSD-3-Clause"
        elif parts[0] == "numpy":
            component, license_id = "NumPy", "BSD-3-Clause"
        elif parts[0] == "numpy.libs" and name.startswith("libscipy_openblas"):
            component = "OpenBLAS/LAPACK with GCC runtime exception"
            license_id = "BSD-3-Clause AND GPL-3.0-or-later WITH GCC-exception-3.1"
        elif parts[0] == "cv2" and path.suffix == ".pyd":
            component, license_id = "OpenCV (video-I/O plugin excluded)", "Apache-2.0"
        elif parts[0] == "shiboken6" or (
            parts[0] == "PySide6" and (path.suffix == ".pyd" or name == "pyside6.abi3.dll")
        ):
            component, license_id = "PySide6/Shiboken6", "LGPL-3.0-only"
            source_name = "pyside-setup-6.12.0.tar.xz"
        elif parts[0] == "PySide6":
            component, license_id = "Qt 6.12.0", "LGPL-3.0-only"
            if name in {"qt6svg.dll", "qsvg.dll", "qsvgicon.dll"}:
                source_name = "qtsvg-6.12.0.tar.gz"
            elif name in {"qicns.dll", "qtga.dll", "qtiff.dll", "qwbmp.dll", "qwebp.dll"}:
                source_name = "qtimageformats-6.12.0.tar.gz"
            else:
                source_name = "qtbase-6.12.0.tar.gz"
        elif parts[:2] == ("dg_fps", "_native") and name == "dg_nvidia_optical_flow.dll":
            component, license_id = "AIDA NVIDIA bridge + SDK MIT headers", "Apache-2.0 AND MIT"
        elif len(parts) == 1 and name.startswith(("libssl-3", "libcrypto-3")):
            component, license_id = "OpenSSL 3", "Apache-2.0"
        elif len(parts) == 1 and name == "libffi-8.dll":
            component, license_id = "libffi", "MIT"
        elif len(parts) == 1 and name == "sqlite3.dll":
            component, license_id = "SQLite", "Public-Domain"
        elif len(parts) == 1 and (
            name in {"python3.dll", "python312.dll"}
            or (
                path.suffix == ".pyd"
                and path.stem
                in {
                    "_asyncio",
                    "_bz2",
                    "_ctypes",
                    "_decimal",
                    "_hashlib",
                    "_lzma",
                    "_multiprocessing",
                    "_overlapped",
                    "_queue",
                    "_socket",
                    "_sqlite3",
                    "_ssl",
                    "_uuid",
                    "_wmi",
                    "pyexpat",
                    "select",
                    "unicodedata",
                }
            )
        ):
            component = "CPython 3.12.7 and documented dependencies"
            license_id = "PSF-2.0 AND permissive notices"
        if component is None:
            raise ValueError("Unreviewed native component: " + str(relative))
        if component.startswith("Microsoft"):
            selected = ["third_party_licenses/Microsoft-VC-Runtime-2015-2022.txt"]
        elif component.startswith("OpenSSL"):
            selected = ["third_party_licenses/OpenSSL-APACHE-LICENSE.txt"]
        elif component == "libffi":
            selected = ["third_party_licenses/libffi-LICENSE.txt"]
        elif component == "SQLite":
            selected = ["third_party_licenses/SQLite-NOTICE.txt"]
        elif component.startswith("CPython"):
            selected = [
                "third_party_licenses/Python-LICENSE.txt",
                "third_party_licenses/CPython-3.12.7-THIRD-PARTY-NOTICES.txt",
                "third_party_licenses/bzip2-LICENSE.txt",
                "third_party_licenses/XZ-LZMA-COPYING.txt",
                "third_party_licenses/Zlib-LICENSE.txt",
            ]
        elif component.startswith("AIDA"):
            selected = ["third_party_licenses/NVIDIA-Optical-Flow-MIT.txt"]
        elif component.startswith("FFmpeg"):
            selected = [
                "third_party_licenses/OpenH264-LICENSE.txt",
                "third_party_licenses/dav1d-COPYING.txt",
                "third_party_licenses/NV-CODEC-HEADERS-LICENSE.txt",
                "third_party_licenses/GCC-RUNTIME-EXCEPTION-3.1.txt",
                "third_party_licenses/MinGW-w64-Runtime-LICENSE.txt",
            ]
        else:
            prefix = (
                "av/"
                if component.startswith("PyAV")
                else "numpy/"
                if component.startswith(("NumPy", "OpenBLAS"))
                else "opencv-python/"
                if component.startswith("OpenCV")
                else "qt-upstream/"
            )
            selected = [
                p.relative_to(bundle).as_posix()
                for p in notice_paths
                if (bundle / "third_party_licenses" / prefix) in p.parents
            ]
        notices = sorted(set(all_notices + selected))
        if not selected:
            raise ValueError("Missing component notices: " + component)
        record = {
            "sha256": sha256(path),
            "component": component,
            "license": license_id,
            "distribution_compatible": True,
            "notices": notices,
            "notice_sha256": {n: sha256(bundle / n) for n in notices},
            "corresponding_source_required": source_name is not None,
        }
        if source_name:
            record.update(
                source_archive=source_root + source_name,
                source_sha256=sha256(bundle / source_root / source_name),
            )
        approvals.append(record)
    policy = ROOT / "installer/distribution-review.json"
    policy.write_text(
        json.dumps(
            {
                "format_version": 1,
                "product_model": "Apache-2.0 open-source application",
                "inventory_sha256": sha256(bundle / "third_party_licenses/inventory.json"),
                "review_basis": "Pinned component versions, complete upstream notices/sources, "
                "media/GPU equivalence requires separate release evidence; no GPL codecs.",
                "approved_binaries": approvals,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report = review_payload(bundle, policy)
    if not report["public_release_allowed"]:
        raise ValueError(report["blockers"])
    (bundle / license_root / "distribution-review.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("Reviewed native files:", len(approvals))


if __name__ == "__main__":
    main()
