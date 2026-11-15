"""Test exact production installers only in a disposable GitHub-hosted Windows VM."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from prepare_installer_pilot import CURRENT_HASH, LEGACY_HASHES, sha256

APP = "AIDA FPS Studio"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP}"
PROJECT_CLASS = r"Software\Classes\DetonandoGueek.AIDA.Project"


def guard_disposable_runner(output: Path) -> None:
    required = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_OS": "Windows",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "AIDA_INSTALLER_PILOT": "1",
    }
    if any(os.environ.get(k) != v for k, v in required.items()):
        raise RuntimeError("Refusing real-product installation outside the disposable hosted pilot")
    temporary = Path(os.environ["RUNNER_TEMP"]).resolve()
    resolved = output.resolve()
    if resolved == temporary or not resolved.is_relative_to(temporary):
        raise ValueError("Pilot evidence must be in a dedicated RUNNER_TEMP subdirectory")


def app_environment(*, desktop: bool = False) -> dict[str, str]:
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.upper().startswith(("PYTHON", "ACTIONS_")) or key.upper() in {
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "QT_PLUGIN_PATH",
            "QT_QPA_PLATFORM_PLUGIN_PATH",
        }:
            environment.pop(key)
    windows = Path(environment["WINDIR"])
    environment["PATH"] = os.pathsep.join((str(windows / "System32"), str(windows)))
    environment["QT_QPA_PLATFORM"] = "windows" if desktop else "offscreen"
    return environment


def run(argv: list[str], expected: int = 0, *, timeout: int = 240) -> int:
    result = subprocess.run(argv, env=app_environment(), timeout=timeout, check=False)
    if result.returncode != expected:
        raise RuntimeError(f"Unexpected exit {result.returncode}, expected {expected}: {argv[0]}")
    return result.returncode


def registry_value(key: str, value: str = ""):
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return winreg.QueryValueEx(handle, value)[0]
    except FileNotFoundError:
        return None


def payload_hashes(directory: Path) -> dict[str, str]:
    return {
        p.relative_to(directory).as_posix(): sha256(p)
        for p in directory.rglob("*")
        if p.is_file() and p.name not in {".disable-update-check", "pilot-user-note.txt"}
    }


def frozen_self_test(install: Path, output: Path) -> dict:
    run([str(install / "AIDA-FPS-Studio.exe"), "--self-test", str(output)])
    result = json.loads((output / "self-test.json").read_text("utf-8"))
    if result["status"] != "passed" or result["frames"] != 16:
        raise AssertionError("Frozen CPU self-test failed")
    return result


def uninstall(install: Path) -> None:
    # NSIS requires _?= last and unquoted, including spaces. This is a direct
    # CreateProcess command line, never passed through cmd.exe or another shell.
    command = subprocess.list2cmdline([str(install / "Uninstall.exe"), "/S"])
    command += " _?=" + str(install)
    result = subprocess.run(command, env=app_environment(), timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(f"Uninstaller exit: {result.returncode}")
    deadline = time.monotonic() + 30
    while (install / "Uninstall.exe").exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not (install / "AIDA-FPS-Studio.exe").exists()
    assert registry_value(UNINSTALL_KEY, "DisplayVersion") is None
    assert registry_value(PROJECT_CLASS + r"\shell\open\command") is None


def make_legacy_project(old_result: dict, path: Path) -> None:
    """A legacy-format fixture from the old frozen report, not an invented GUI save."""
    from dg_fps.jobs.cancellation import CancellationToken
    from dg_fps.projects import result_from_document, save_project
    from dg_fps.reports.cadence_json import ReportPaths

    reports = Path(old_result["reports"])
    document = json.loads((reports / "analysis.json").read_text("utf-8"))
    source = Path(old_result["source"])
    result = result_from_document(document, source)
    state = {
        "source": str(source),
        "ranges": [asdict(r) for r in result.frame_ranges],
        "frame": 0,
        "target": 30,
        "overrides": {},
        "analysis_mode": "cpu",
        "encoding_mode": "cpu",
    }
    # The serializer is byte-identical to 0.8.14. Preserve the genuine old report
    # unchanged; the fixture container is truthfully created by this 0.8.15 harness.
    save_project(
        path,
        state,
        ReportPaths(reports, reports / "analysis.json", reports / "report.json"),
        CancellationToken(),
    )


def owned_windows(pid: int) -> list[tuple[int, str]]:
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user.IsWindowVisible.argtypes = [ctypes.c_void_p]
    found = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def visit(handle, _):
        owner = ctypes.c_ulong()
        user.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid and user.IsWindowVisible(handle):
            text = ctypes.create_unicode_buffer(user.GetWindowTextLengthW(handle) + 1)
            user.GetWindowTextW(handle, text, len(text))
            found.append((handle, text.value))
        return True

    user.EnumWindows.argtypes = [callback_type, ctypes.c_void_p]
    user.EnumWindows(visit, None)
    return found


def open_frozen_project(install: Path, project: Path, results: Path, evidence: Path) -> dict:
    """Exercise the actual installed EXE's normal .aida opening path and graceful exit."""
    from PySide6.QtWidgets import QApplication

    process = subprocess.Popen(
        [str(install / "AIDA-FPS-Studio.exe"), str(project)], env=app_environment(desktop=True)
    )
    deadline = time.monotonic() + 90
    handle = None
    restored = None
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Project-open process exited early: {process.returncode}")
            windows = owned_windows(process.pid)
            handle = next((h for h, name in windows if project.name in name), None)
            restored = next(results.glob("restored_*/analysis.json"), None)
            if handle and restored:
                break
            time.sleep(0.2)
        if not handle or restored is None:
            raise RuntimeError("Installed project did not reach its restored-results state")
        application = QApplication.instance() or QApplication([])
        image = application.primaryScreen().grabWindow(handle)
        if image.isNull() or not image.save(str(evidence / "project-open.png")):
            raise RuntimeError("Could not capture the owned project window")
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.PostMessageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        close_deadline = time.monotonic() + 30
        while process.poll() is None and time.monotonic() < close_deadline:
            user.PostMessageW(handle, 0x0010, 0, 0)  # WM_CLOSE, only this pilot process.
            time.sleep(0.25)
        if process.poll() is None:
            raise RuntimeError("Project window did not close cleanly")
        assert process.returncode == 0
        return {
            "window_caption_verified": True,
            "restored_analysis": str(restored),
            "clean_exit": True,
            "restored_analysis_sha256": sha256(restored),
        }
    finally:
        if process.poll() is None:
            process.terminate()  # Only the process this harness created, in the VM.
            process.wait(timeout=15)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--legacy-version", choices=("0.8.12", "0.8.14"), required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    guard_disposable_runner(args.output)
    assert (
        sha256(args.legacy) == LEGACY_HASHES[args.legacy_version]
        and sha256(args.candidate) == CURRENT_HASH
    )
    install = Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP
    if install.exists() or registry_value(UNINSTALL_KEY, "DisplayVersion") is not None:
        raise RuntimeError("Runner is not clean; refusing to replace an existing AIDA installation")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {
        "status": "running",
        "scope": "exact installers on disposable Windows runner",
        "checks": [],
        "legacy_version": args.legacy_version,
        "legacy_sha256": LEGACY_HASHES[args.legacy_version],
        "candidate_sha256": CURRENT_HASH,
    }

    def checked(name: str) -> None:
        record["checks"].append(name)
        (output / "pilot.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print("PASS", name, flush=True)

    from platformdirs import user_cache_path, user_data_path

    settings = user_data_path(APP, "DG") / "settings.json"
    results = output / "user-results"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        json.dumps(
            {
                "language": "en",
                "output_directory": str(results),
                "pilot_sentinel": "preserve-user-settings",
            }
        ),
        encoding="utf-8",
    )
    project = output / "user-projects" / "legacy-results.aida"
    project.parent.mkdir()
    cache = user_cache_path(APP, "DG") / "pilot-user-cache.txt"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("preserve cache", encoding="utf-8")
    try:
        run([str(args.candidate.resolve()), "/S"])
        assert registry_value(UNINSTALL_KEY, "DisplayVersion") == "0.8.15"
        canonical = payload_hashes(install)
        checked("fresh_0.8.15_exact_installer")
        record["fresh_self_test"] = frozen_self_test(install, output / "fresh-self-test")
        checked("fresh_frozen_cpu_analysis_export")
        uninstall(install)
        assert not install.exists()
        checked("fresh_uninstall_removes_owned_payload_and_registration")

        run([str(args.legacy.resolve()), "/S"])
        assert registry_value(UNINSTALL_KEY, "DisplayVersion") == args.legacy_version
        old_files = set(payload_hashes(install))
        old_result = frozen_self_test(install, output / "legacy-self-test")
        make_legacy_project(old_result, project)
        original_project = sha256(project)
        original_source = sha256(Path(old_result["source"]))
        original_settings = sha256(settings)
        (install / "pilot-user-note.txt").write_text("preserve unknown user file", encoding="utf-8")
        checked("legacy_install_and_genuine_legacy_analysis_fixture")

        # The update must wait for its parent instead of replacing a running app.
        with subprocess.Popen(
            [sys.executable, "-c", "print('ready',flush=True); input()"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        ) as parent:
            assert parent.stdout.readline().strip() == "ready"
            update = subprocess.Popen(
                [str(args.candidate.resolve()), "/S", f"/UPDATEPID={parent.pid}"],
                env=app_environment(),
            )
            try:
                time.sleep(0.75)
                assert update.poll() is None
                assert registry_value(UNINSTALL_KEY, "DisplayVersion") == args.legacy_version
                parent.stdin.write("\n")
                parent.stdin.flush()
                parent.wait(timeout=10)
                assert update.wait(timeout=240) == 0
            finally:
                if update.poll() is None:
                    update.terminate()
                    update.wait(timeout=15)
        assert registry_value(UNINSTALL_KEY, "DisplayVersion") == "0.8.15"
        assert payload_hashes(install) == canonical
        assert all(not (install / name).exists() for name in old_files - canonical.keys())
        assert sha256(settings) == original_settings and sha256(project) == original_project
        checked("upgrade_waits_for_parent_and_preserves_settings_projects")
        checked("upgrade_payload_matches_clean_install_and_retires_old_files")
        record["upgrade_self_test"] = frozen_self_test(install, output / "upgrade-self-test")
        checked("upgraded_frozen_cpu_analysis_export")

        # Normal startup must restore the existing project's actual old measurements.
        (install / ".disable-update-check").touch()
        record["project_open"] = open_frozen_project(install, project, results, output)
        old_analysis = Path(old_result["reports"]) / "analysis.json"
        assert record["project_open"]["restored_analysis_sha256"] == sha256(old_analysis)
        assert sha256(project) == original_project
        checked("normal_frozen_project_open_preserves_legacy_measurements")
        run([str(args.candidate.resolve()), "/S"])
        assert payload_hashes(install) == canonical
        checked("same_version_reinstall")
        run([str(args.legacy.resolve()), "/S"], expected=2)
        assert registry_value(UNINSTALL_KEY, "DisplayVersion") == "0.8.15"
        assert payload_hashes(install) == canonical
        checked("downgrade_blocked_without_payload_changes")

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        lock = kernel.CreateFileW(
            str(install / "AIDA-FPS-Studio.exe"), 0x80000000, 0, None, 3, 0x80, None
        )
        assert lock not in (None, ctypes.c_void_p(-1).value)
        try:
            run([str(args.candidate.resolve()), "/S"], expected=1)
            command = subprocess.list2cmdline([str(install / "Uninstall.exe"), "/S"])
            command += " _?=" + str(install)
            result = subprocess.run(command, env=app_environment(), timeout=60, check=False)
            assert result.returncode == 1
            assert registry_value(UNINSTALL_KEY, "DisplayVersion") == "0.8.15"
        finally:
            kernel.CloseHandle(lock)
        checked("locked_executable_blocks_update_and_uninstall")

        shortcut = (
            Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs" / (APP + ".lnk")
        )
        assert shortcut.is_file()
        assert str(install) in registry_value(PROJECT_CLASS + r"\shell\open\command")
        checked("start_menu_and_project_association_registered")
        uninstall(install)
        assert not shortcut.exists()
        assert registry_value(r"Software\Classes\.aida") is None
        assert (install / "pilot-user-note.txt").read_text("utf-8") == "preserve unknown user file"
        assert sha256(project) == original_project
        assert sha256(Path(old_result["source"])) == original_source
        assert cache.read_text("utf-8") == "preserve cache"
        assert json.loads(settings.read_text("utf-8"))["pilot_sentinel"] == "preserve-user-settings"
        assert (install / ".disable-update-check").is_file()
        checked("uninstall_preserves_projects_video_settings_cache_and_unknown_files")
        record["status"] = "passed"
    except Exception as error:
        record.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        (output / "pilot.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "checks": len(record["checks"])}))


if __name__ == "__main__":
    main()
