"""Security/privacy and provenance checks specific to the standalone distribution."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_measurement_import_has_no_changes():
    assert load_script("verify_source_integrity").verify(ROOT) == []


def test_open_source_metadata_and_distribution_licenses_match():
    load_script("check_repository").main()


def test_dependency_update_cannot_silently_leave_hashed_lock_stale(tmp_path):
    checker = load_script("check_repository")
    reference = tmp_path / "requirements-lock.txt"
    reference.write_text("Example_Package==1.0\n", encoding="utf-8")
    (tmp_path / "requirements-windows.lock").write_text(
        "example-package==1.0 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8"
    )
    checker.check_python_locks(tmp_path)
    reference.write_text("Example_Package==2.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hashed Windows lock differ"):
        checker.check_python_locks(tmp_path)


def test_offline_marker_prevents_automatic_network_check(tmp_path, monkeypatch):
    from dg_fps.ui.update_flow import UpdateFlow

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "AIDA-FPS-Studio.exe"))
    (tmp_path / ".disable-update-check").touch()

    class Checker:
        calls = 0

        def start(self):
            self.calls += 1

    class Flow:
        checker = Checker()

    flow = Flow()
    UpdateFlow.start(flow)
    assert flow.checker.calls == 0
    (tmp_path / ".disable-update-check").unlink()
    UpdateFlow.start(flow)
    assert flow.checker.calls == 1


def test_build_bootstrap_rejects_zip_parent_traversal(tmp_path):
    from zipfile import ZipFile

    bootstrap = load_script("bootstrap_sources")
    archive = tmp_path / "input.zip"
    with ZipFile(archive, "w") as stream:
        stream.writestr("../escaped.txt", "unsafe")
    with pytest.raises(ValueError, match="Unsafe ZIP"):
        bootstrap.extract(archive, tmp_path / "output")
    assert not (tmp_path / "escaped.txt").exists()


def test_download_rejects_changed_cached_build_input(tmp_path):
    bootstrap = load_script("bootstrap_sources")
    (tmp_path / "source.zip").write_bytes(b"modified")
    row = {"file": "source.zip", "url": "https://invalid.example/source.zip", "sha256": "0" * 64}
    with pytest.raises(ValueError, match="Input hash mismatch"):
        bootstrap.download(row, tmp_path)
