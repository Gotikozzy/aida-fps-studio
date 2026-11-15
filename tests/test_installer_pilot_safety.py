"""Prevent accidental production-profile installs and unsafe pilot input extraction."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def pilot_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "pilot_harness", ROOT / "scripts/run_installer_pilot.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sys.modules["prepare_installer_pilot"]


def test_real_product_installer_refused_on_local_or_self_hosted_profile(tmp_path, monkeypatch):
    pilot, _ = pilot_modules(monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_OS", "Windows")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    monkeypatch.setenv("AIDA_INSTALLER_PILOT", "1")
    with pytest.raises(RuntimeError, match="outside the disposable"):
        pilot.guard_disposable_runner(tmp_path)


def test_pilot_output_cannot_escape_dedicated_temporary_directory(tmp_path, monkeypatch):
    pilot, _ = pilot_modules(monkeypatch)
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "RUNNER_OS": "Windows",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "AIDA_INSTALLER_PILOT": "1",
        "RUNNER_TEMP": str(tmp_path),
    }.items():
        monkeypatch.setenv(name, value)
    pilot.guard_disposable_runner(tmp_path / "owned-pilot")
    for invalid in (tmp_path, tmp_path.parent / "outside"):
        with pytest.raises(ValueError, match="dedicated RUNNER_TEMP"):
            pilot.guard_disposable_runner(invalid)


def test_frozen_app_does_not_inherit_ci_tokens_or_developer_python_paths(tmp_path, monkeypatch):
    pilot, _ = pilot_modules(monkeypatch)
    monkeypatch.setenv("WINDIR", str(tmp_path))
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN", "PYTHONPATH", "PYTHONHOME"):
        monkeypatch.setenv(key, "do-not-inherit")
    environment = pilot.app_environment()
    assert all(
        k not in environment
        for k in ("GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN", "PYTHONPATH", "PYTHONHOME")
    )
    assert environment["PATH"] == str(tmp_path / "System32") + os.pathsep + str(tmp_path)


def test_artifact_rejects_duplicate_or_traversal_installer_entries(tmp_path, monkeypatch):
    _, preparation = pilot_modules(monkeypatch)
    archive = tmp_path / "input.zip"
    with ZipFile(archive, "w") as stream:
        stream.writestr("../" + preparation.CURRENT_NAME, b"wrong")
    with pytest.raises(ValueError, match="Unexpected installer"):
        preparation.extract_installer(archive, tmp_path / "setup.exe", "0" * 64)
    assert not (tmp_path / "setup.exe").exists()


def test_artifact_hash_mismatch_never_retains_an_executable(tmp_path, monkeypatch):
    _, preparation = pilot_modules(monkeypatch)
    archive = tmp_path / "input.zip"
    with ZipFile(archive, "w") as stream:
        stream.writestr(preparation.CURRENT_NAME, b"wrong bytes")
    with pytest.raises(ValueError, match="hash mismatch"):
        preparation.extract_installer(archive, tmp_path / "setup.exe", "0" * 64)
    assert not (tmp_path / "setup.exe").exists()


def test_normal_uninstall_allows_nsis_temporary_self_relocation(tmp_path, monkeypatch):
    pilot, _ = pilot_modules(monkeypatch)
    calls = []

    def invoke(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(pilot.subprocess, "run", invoke)
    monkeypatch.setattr(pilot, "registry_value", lambda *_: None)
    pilot.uninstall(tmp_path)
    assert calls == [[str(tmp_path / "Uninstall.exe"), "/S"]]
