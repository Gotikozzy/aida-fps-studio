from __future__ import annotations

import hashlib
import io
import struct
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from zipfile import ZipFile

import pytest
from PySide6.QtWidgets import QMessageBox

from dg_fps import updates
from dg_fps.ui.main_window import FPSWindow


def executable() -> bytes:
    data = bytearray(128)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    return bytes(data)


def package(release, name=None, payload=None) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(name or release.filename.replace(".zip", ".exe"),
                         executable() if payload is None else payload)
    return output.getvalue()


@contextmanager
def server_for(monkeypatch, payload, checksum):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            data = checksum if self.path.endswith(".sha256") else payload
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            with suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(data)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        monkeypatch.setattr(updates, "SITE_URL", f"http://127.0.0.1:{server.server_port}")
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        try:
            yield requests
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("legacy", [False, True])
def test_verified_download_and_exact_installer(qtbot, qapp, tmp_path, monkeypatch, legacy):
    base = updates.UpdateRelease("99.0.0")
    data = package(base)
    digest = hashlib.sha256(data).hexdigest()
    release = base if legacy else updates.UpdateRelease(base.version, digest, len(data))
    checksum = f"{digest}  {base.filename}\n".encode("ascii")
    with server_for(monkeypatch, data, checksum) as requests:
        download = updates.UpdateDownload(release, tmp_path, qapp)
        with qtbot.waitSignal(download.succeeded, timeout=5000) as signal:
            download.start()
        path = signal.args[0]
        assert path.read_bytes() == data
        assert not list(tmp_path.glob("*.part"))
        installer = updates.prepare_installer(path, release, Event())
        assert installer.read_bytes() == executable()
        assert len(requests) == (2 if legacy else 1)


@pytest.mark.parametrize("failure", ["hash", "size", "wrong-checksum-filename"])
def test_invalid_package_never_becomes_an_installer(qtbot, qapp, tmp_path, monkeypatch, failure):
    base = updates.UpdateRelease("99.0.0")
    data = package(base)
    digest = hashlib.sha256(data).hexdigest()
    release = updates.UpdateRelease(base.version, "0" * 64 if failure == "hash" else digest,
                                    len(data) + (1 if failure == "size" else 0))
    if failure == "wrong-checksum-filename":
        release = base
    with server_for(monkeypatch, data, f"{digest}  wrong.zip".encode()):
        download = updates.UpdateDownload(release, tmp_path, qapp)
        with qtbot.waitSignal(download.failed, timeout=5000) as signal:
            download.start()
        assert signal.args == ["integrity"]
        assert not list(tmp_path.iterdir())


def test_cancel_during_download_removes_partial_file(qtbot, qapp, tmp_path, monkeypatch):
    release = updates.UpdateRelease("99.0.0", "0" * 64)
    with server_for(monkeypatch, b"a" * 100_000, b""):
        download = updates.UpdateDownload(release, tmp_path, qapp)
        download.progress.connect(lambda *_: download.cancel())
        with qtbot.waitSignal(download.cancelled, timeout=5000):
            download.start()
        assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["../outside.exe", "/outside.exe", "other.exe"])
def test_archive_paths_cannot_escape_update_directory(tmp_path, name):
    release = updates.UpdateRelease("99.0.0")
    path = tmp_path / release.filename
    path.write_bytes(package(release, name))
    with pytest.raises(ValueError):
        updates.prepare_installer(path, release, Event())
    assert list(tmp_path.iterdir()) == [path]


def test_cancelled_preparation_and_non_executable_are_rejected(tmp_path):
    release = updates.UpdateRelease("99.0.0")
    path = tmp_path / release.filename
    path.write_bytes(package(release))
    cancelled = Event()
    cancelled.set()
    with pytest.raises(InterruptedError):
        updates.prepare_installer(path, release, cancelled)
    path.write_bytes(package(release, payload=b"not an executable"))
    with pytest.raises(ValueError):
        updates.prepare_installer(path, release, Event())
    assert list(tmp_path.iterdir()) == [path]


def test_manifest_does_not_delegate_download_to_an_untrusted_url():
    release = updates.manifest_release(
        b'{"version":"99.0.0","download":"https://example.invalid/bad.zip"}'
    )
    assert release.url == updates.SITE_URL + "/static/aida/" + release.filename
    for raw in (b'{"version":"99.0.0","sha256":"bad"}',
                b'{"version":"99.0.0","size":true}',
                b'{"version":"../../bad"}'):
        with pytest.raises(ValueError):
            updates.manifest_release(raw)


def test_cancel_project_save_does_not_launch_update(qtbot, tmp_path, monkeypatch):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    window.show()
    window.source = tmp_path / "video.mp4"
    window._dirty = True
    window._pending_update_installer = tmp_path / "setup.exe"
    launches = []
    monkeypatch.setattr(updates, "launch_installer", lambda *args: launches.append(args))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window.close()
    assert window._pending_update_installer is None and not launches
    window.source = None
    window._dirty = False
    window.close()


def test_handoff_uses_argument_list_and_parent_process_id(tmp_path, monkeypatch):
    path = tmp_path / "installer with spaces.exe"
    path.write_bytes(executable())
    calls = []
    monkeypatch.setattr(updates.subprocess, "Popen", lambda args, **kw: calls.append((args, kw)))
    updates.launch_installer(path, 1234)
    assert calls == [([str(path), "/UPDATEPID=1234"], {"close_fds": True})]


def test_consented_update_downloads_prepares_and_closes_before_install(
    qtbot, tmp_path, monkeypatch
):
    from dg_fps.ui import update_flow

    base = updates.UpdateRelease("99.0.0")
    data = package(base)
    release = updates.UpdateRelease(base.version, hashlib.sha256(data).hexdigest(), len(data))
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    window.show()
    monkeypatch.setattr(update_flow, "user_cache_path", lambda *_: tmp_path / "update-cache")
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    launches = []
    monkeypatch.setattr(updates, "launch_installer", lambda *args: launches.append(args))
    with server_for(monkeypatch, data, b""):
        window._update_flow = update_flow.UpdateFlow(window)
        window._update_flow.offer(release)
        qtbot.waitUntil(lambda: bool(launches), timeout=5000)
        assert launches[0][0].read_bytes() == executable()
        assert not window.isVisible()
        assert not window._update_flow.busy


def test_update_offer_waits_for_current_operation(qtbot, tmp_path, monkeypatch):
    from dg_fps.ui.update_flow import UpdateFlow

    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    window.show()
    flow = UpdateFlow(window)
    questions = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: (
        questions.append(args[2]) or QMessageBox.StandardButton.No
    ))
    window._media_loading = True
    flow.pending = updates.UpdateRelease("99.0.0")
    flow._offer()
    assert not questions and flow.pending is not None
    window._media_loading = False
    flow.timer.stop()
    flow._offer()
    assert len(questions) == 1 and not flow.busy
    window.close()
