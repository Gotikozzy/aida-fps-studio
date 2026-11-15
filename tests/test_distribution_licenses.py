from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "distribution_licenses", ROOT / "scripts/distribution_licenses.py"
)
licenses = importlib.util.module_from_spec(spec)
spec.loader.exec_module(licenses)


def test_public_build_requires_exact_notices_source_and_binary(tmp_path):
    bundle = tmp_path / "bundle"
    native = bundle / "_internal"
    native.mkdir(parents=True)
    binary = native / "library.dll"
    binary.write_bytes(b"library")
    policy = tmp_path / "review.json"
    policy.write_text('{"approved_binaries": []}', encoding="utf-8")
    assert not licenses.review_payload(bundle, policy)["public_release_allowed"]
    notice = bundle / "notice.txt"
    notice.write_text("license text", encoding="utf-8")
    source = bundle / "source.zip"
    source.write_bytes(b"exact source archive")
    approval = {
        "sha256": licenses.sha256(binary), "component": "library", "license": "LGPL-3.0",
        "distribution_compatible": True, "notices": ["notice.txt"],
        "notice_sha256": {"notice.txt": licenses.sha256(notice)},
        "corresponding_source_required": True, "source_archive": "source.zip",
        "source_sha256": licenses.sha256(source),
    }
    policy.write_text(json.dumps({"approved_binaries": [approval]}), encoding="utf-8")
    assert licenses.review_payload(bundle, policy)["public_release_allowed"]
    source.write_bytes(b"wrong source")
    assert not licenses.review_payload(bundle, policy)["public_release_allowed"]
    approval["corresponding_source_required"] = False
    policy.write_text(json.dumps({"approved_binaries": [approval]}), encoding="utf-8")
    assert licenses.review_payload(bundle, policy)["public_release_allowed"]
    binary.write_bytes(b"new binary version")
    assert not licenses.review_payload(bundle, policy)["public_release_allowed"]


def test_gpl_codec_cannot_be_cleared_by_approval_flag(tmp_path):
    native = tmp_path / "_internal"
    native.mkdir()
    binary = native / "libx264-165.dll"
    binary.write_bytes(b"GPL codec")
    (tmp_path / "notice.txt").write_text("GPL", encoding="utf-8")
    policy = tmp_path / "review.json"
    policy.write_text(json.dumps({"approved_binaries": [{
        "sha256": licenses.sha256(binary), "component": "x264", "license": "GPL-2.0",
        "distribution_compatible": True, "notices": ["notice.txt"],
        "notice_sha256": {"notice.txt": licenses.sha256(tmp_path / "notice.txt")},
        "corresponding_source_required": False,
    }]}), encoding="utf-8")
    report = licenses.review_payload(tmp_path, policy)
    assert not report["public_release_allowed"]
    assert "unexpected_codec_in_validated_runtime" in report["blockers"][0]["issues"]
    assert licenses.confined_file(tmp_path, "../outside.txt") is None


def test_installer_acceptance_contains_complete_third_party_texts(tmp_path):
    for name in ("terms.txt", "license.txt", "notices.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    directory = tmp_path / "licenses"
    directory.mkdir()
    (directory / "COPYING").write_text("COMPLETE LGPL TEXT", encoding="utf-8")
    (directory / "other.txt").write_text("COMPLETE OTHER LICENSE", encoding="utf-8")
    text = licenses.combined_terms(
        tmp_path / "terms.txt", tmp_path / "license.txt", tmp_path / "notices.txt", directory
    )
    assert "COMPLETE LGPL TEXT" in text and "COMPLETE OTHER LICENSE" in text
    assert "does not waive" in text and "COPYING" in text


def test_readable_terms_are_localized_and_full_catalog_keeps_originals(tmp_path):
    terms = tmp_path / "Terms.txt"
    terms.write_text("AIDA\nPORTUGUÊS\nTermos portugueses.\nENGLISH\nEnglish terms.\n",
                     encoding="utf-8")
    localized = licenses.localized_terms(terms)
    assert "English terms" not in localized["pt"]
    assert "Termos portugueses" not in localized["en"]
    assert "Termos portugueses" in localized["pt"]
    for name in ("LICENSE.txt", "NOTICES.md"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    folder = tmp_path / "licenses"
    folder.mkdir()
    (folder / "COPYING").write_text("COPYRIGHT <owner> & COMPLETE LICENSE", encoding="utf-8")
    catalog = licenses.license_catalog(terms, tmp_path / "LICENSE.txt",
                                       tmp_path / "NOTICES.md", folder)
    assert "COPYRIGHT &lt;owner&gt; &amp; COMPLETE LICENSE" in catalog
    assert "<details>" in catalog and "COPYING" in catalog
    assert "FFmpeg" in catalog and "LGPL" in catalog


def test_installer_cleanup_only_allows_known_owned_paths(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from build_installer import removal_commands

    for unsafe in ("../project.aida", "C:/data/project.aida", "project.aida",
                   "data/project.aida", "_internal/../../project.aida"):
        with pytest.raises(ValueError):
            removal_commands({unsafe})
    commands = removal_commands({"_internal/old/library.dll"})
    assert 'Delete "$INSTDIR\\_internal\\old\\library.dll"' in commands
    assert "RMDir /r" not in commands
    assert 'RMDir "$INSTDIR"' not in commands


def test_installer_uninstall_remembers_retired_owned_files(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from build_installer import payload_files, uninstall_commands

    (tmp_path / "_internal").mkdir()
    (tmp_path / "third_party_licenses").mkdir()
    (tmp_path / "_internal/new.dll").write_bytes(b"new")
    retired = {"_internal/old.dll"}
    text = uninstall_commands(tmp_path, retired)
    assert "old.dll" in text and "new.dll" in text
    assert "third_party_licenses/NSIS-LICENSE.txt" in payload_files(tmp_path)


def test_upgrade_cleanup_respects_windows_case_insensitive_paths(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from build_installer import retired_files

    previous = {"third_party_licenses/PySide6-Essentials/LICENSE.txt", "_internal/old.dll"}
    current = {"third_party_licenses/pyside6-essentials/LICENSE.txt", "_internal/new.dll"}
    assert retired_files(previous, current) == {"_internal/old.dll"}
