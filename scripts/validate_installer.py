"""Exercise the production NSIS script with an isolated identity and tiny fixture.

Never installs, replaces or removes the user's real AIDA installation or .aida handler.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import winreg
from pathlib import Path
from uuid import uuid4

from build_installer import payload_files, removal_commands, retired_files, uninstall_commands
from distribution_licenses import license_catalog, localized_terms
from package_release import VERSION

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-payload", action="store_true")
    args = parser.parse_args()
    name = "AIDA Installer Test " + uuid4().hex[:12]
    staging = ROOT / "build" / name
    bundle = staging / "bundle"
    bundle.mkdir(parents=True)
    for directory in ("_internal", "third_party_licenses"):
        (bundle / directory).mkdir()
        (bundle / directory / "fixture.txt").write_text("test", encoding="utf-8")
    shutil.copy2(Path(os.environ["WINDIR"]) / "System32/where.exe",
                 bundle / "AIDA-FPS-Studio.exe")
    previous_version = "0.8.5"
    old_bundle = (
        ROOT / "dist" / previous_version / "AIDA-FPS-Studio" if args.full_payload else bundle
    )
    new_bundle = ROOT / "dist" / VERSION / "AIDA-FPS-Studio" if args.full_payload else bundle
    old_files, new_files = payload_files(old_bundle), payload_files(new_bundle)
    compiler = ROOT / "build/nsis-portable/nsis-3.13/makensis.exe"
    key = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" + name
    project_class = "AIDA.Test." + name.replace(" ", "")
    extension = ".aida-test-" + uuid4().hex[:12]
    install = Path(os.environ["LOCALAPPDATA"]) / "Programs" / name
    assert not install.exists()

    def version():
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return winreg.QueryValueEx(handle, "DisplayVersion")[0]

    def compile_setup(release, source_bundle):
        setup = staging / f"setup-{release}.exe"
        remove = staging / f"remove-{release}.nsh"
        remove.write_text(uninstall_commands(source_bundle, old_files),
                          encoding="utf-8-sig")
        retired = staging / f"retired-{release}.nsh"
        retired.write_text(
            removal_commands(retired_files(old_files, payload_files(source_bundle))),
            encoding="utf-8-sig",
        )
        terms = staging / "Terms.txt"
        qa_terms = ROOT / "installer/qa/Terms.txt"
        terms.write_text(qa_terms.read_text("utf-8-sig"), encoding="utf-8-sig")
        translated = localized_terms(qa_terms)
        terms_pt, terms_en = staging / "Terms.pt.txt", staging / "Terms.en.txt"
        terms_pt.write_text(translated["pt"], encoding="utf-16")
        terms_en.write_text(translated["en"], encoding="utf-16")
        catalog = staging / "licenses.html"
        catalog.write_text(license_catalog(qa_terms, ROOT / "installer/qa/LICENSE.txt",
                           ROOT / "THIRD_PARTY_NOTICES.md", new_bundle / "third_party_licenses"),
                           encoding="utf-8")
        defines = {
            "Version": release, "Edition": " TEST", "AppName": name,
            "ProjectClass": project_class, "ProjectExtension": extension,
            "BundleDir": source_bundle, "SetupPath": setup,
            "TermsPath": terms,
            "TermsPtPath": terms_pt, "TermsEnPath": terms_en, "LicenseCatalog": catalog,
            "LicensePath": ROOT / "installer/qa/LICENSE.txt",
            "NoticesPath": ROOT / "THIRD_PARTY_NOTICES.md",
            "CompilerLicense": compiler.parent / "COPYING",
            "AppIcon": ROOT / "src/dg_fps/assets/aida-executable.ico",
            "RemoveFiles": remove,
            "RetireFiles": retired,
            "TestUncompressed": "1",
        }
        subprocess.run([str(compiler), "/WX", "/V2", "/INPUTCHARSET", "UTF8",
                        *(f"/D{k}={v}" for k, v in defines.items()),
                        str(ROOT / "installer/windows.nsi")], check=True)
        return setup

    old, new = compile_setup(previous_version, old_bundle), compile_setup(VERSION, new_bundle)
    checks = []
    user_data = staging / "user-data"
    user_data.mkdir()
    project = user_data / "keep.aida"
    project.write_bytes(b"user project must be preserved")
    try:
        subprocess.run([str(old), "/S"], check=True)
        assert version() == previous_version
        if args.full_payload:
            subprocess.run([str(install / "AIDA-FPS-Studio.exe"), "--self-test",
                            str(staging / "fresh-self-test")], check=True)
        checks.append("fresh_install")
        if args.full_payload:
            subprocess.run([str(new), "/S"], check=True)
        else:
            # Gate the parent lifetime: the updater must wait rather than replace
            # a running application's files or forcibly terminate that process.
            with subprocess.Popen(
                [sys.executable, "-c", "print('ready', flush=True); input()"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            ) as parent:
                assert parent.stdout.readline().strip() == "ready"
                with subprocess.Popen([str(new), "/S", f"/UPDATEPID={parent.pid}"]) as update:
                    time.sleep(.5)
                    assert update.poll() is None, "Installer did not wait for its parent"
                    parent.stdin.write("\n")
                    parent.stdin.flush()
                    parent.wait(timeout=5)
                    assert update.wait(timeout=15) == 0
            checks.append("updater_waits_for_parent_exit")
        assert version() == VERSION
        if args.full_payload:
            subprocess.run([str(install / "AIDA-FPS-Studio.exe"), "--self-test",
                            str(staging / "upgrade-self-test")], check=True)
            for managed_name in retired_files(old_files, new_files):
                assert not (install / managed_name).is_file(), managed_name
            checks.append("retired_files_removed")
            import hashlib

            for managed_name in new_files:
                source_file = new_bundle / managed_name
                if source_file.is_file() and managed_name not in {
                    "Terms.txt", "LICENSE.txt", "THIRD_PARTY_NOTICES.md"
                }:
                    with source_file.open("rb") as src, (install / managed_name).open("rb") as dst:
                        assert hashlib.file_digest(src, "sha256").digest() == hashlib.file_digest(
                            dst, "sha256"
                        ).digest(), managed_name
            checks.append("all_installed_payload_hashes")
        checks.append("upgrade")
        subprocess.run([str(new), "/S"], check=True)
        assert version() == VERSION
        checks.append("reinstall")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        lock = kernel.CreateFileW(str(install / "AIDA-FPS-Studio.exe"),
                                  0x80000000, 0, None, 3, 0x80, None)
        assert lock not in (None, ctypes.c_void_p(-1).value)
        try:
            assert subprocess.run([str(new), "/S"], check=False).returncode == 1
            # NSIS requires _?= to be last and unquoted, even when its path has
            # spaces. This is a direct CreateProcess command line, not a shell.
            command = subprocess.list2cmdline([str(install / "Uninstall.exe"), "/S"])
            command += " _?=" + str(install)
            assert subprocess.run(command, check=False).returncode == 1
            assert (install / "AIDA-FPS-Studio.exe").is_file()
            assert version() == VERSION
        finally:
            kernel.CloseHandle(lock)
        checks.append("locked_application_blocks_update_and_uninstall")
        result = subprocess.run([str(old), "/S"], check=False)
        assert result.returncode == 2 and version() == VERSION
        checks.append("downgrade_blocked")
        shortcut = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs"
        assert (shortcut / f"{name}.lnk").is_file()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            "Software\\Classes\\" + project_class + "\\shell\\open\\command") as h:
            assert str(install) in winreg.QueryValueEx(h, "")[0]
        checks.append("shortcut_and_isolated_association")
    finally:
        if (install / "Uninstall.exe").is_file():
            subprocess.run([str(install / "Uninstall.exe"), "/S"], check=True)
            for _ in range(100):
                if not install.exists():
                    break
                time.sleep(.1)
    assert not install.exists()
    if args.full_payload:
        try:
            subprocess.run([str(new), "/S"], check=True)
            assert version() == VERSION
            subprocess.run([str(install / "AIDA-FPS-Studio.exe"), "--self-test",
                            str(staging / "fresh-current-self-test")], check=True)
            checks.append("fresh_current_full_payload")
        finally:
            if (install / "Uninstall.exe").is_file():
                subprocess.run([str(install / "Uninstall.exe"), "/S"], check=True)
                for _ in range(100):
                    if not install.exists():
                        break
                    time.sleep(.1)
        assert not install.exists()
    assert project.read_bytes() == b"user project must be preserved"
    checks.append("user_project_preserved")
    checks.append("uninstall")
    (staging / "validation.json").write_text(json.dumps({
        "identity": name, "checks": checks,
        "scope": "production script, real payload" if args.full_payload
        else "production script, fixture payload",
    }, indent=2), encoding="utf-8")
    print(json.dumps(checks))


if __name__ == "__main__":
    main()
