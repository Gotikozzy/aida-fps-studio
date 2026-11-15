from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel

from dg_fps import updates
from dg_fps.ui import about
from dg_fps.ui.about import AboutDialog
from dg_fps.ui.main_window import FPSWindow


def test_startup_check_is_nonblocking_and_offline_is_quiet(qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import QObject, Signal

    class Checker(QObject):
        succeeded = Signal(str)
        failed = Signal(str)
        release = None

        def start(self):
            self.started = True

    monkeypatch.setattr(updates, "UpdateCheck", Checker)
    from dg_fps.ui import update_flow

    monkeypatch.setattr(update_flow, "UpdateCheck", Checker)
    offers = []
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *args: (
        offers.append(args[2]) or QMessageBox.StandardButton.No
    ))
    w = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(w)
    w.show()
    w._start_update_check()
    assert w._startup_update.started and w.job_id is None
    w._startup_update.failed.emit("unreachable")
    assert not w.update_notice.isVisible() and w.workspaces.isEnabled()
    w._startup_update.succeeded.emit("0.0.1")
    assert not offers
    w._startup_update.succeeded.emit("99.0.0")
    qtbot.waitUntil(lambda: len(offers) == 1)
    assert "99.0.0" in offers[0] and "download" in offers[0]
    assert not w._update_flow.busy  # Declining neither downloads nor closes the Studio.
    w.close()


@pytest.mark.parametrize(
    ("code", "payload", "message"),
    [
        (200, b'{"version":"0.10.0"}', "Version 0.10.0 is available on the AIDA website."),
        (200, b'{"version":"0.8.0"}', "No update available."),
        (404, b"", "The update check is not yet available on the server."),
        (200, b'{"version":"unknown"}', "The server returned invalid version information."),
        (200, b" " * 4097, "The server returned invalid version information."),
    ],
)
def test_about_links_and_manual_update_check(qtbot, tmp_path, monkeypatch, code, payload, message):
    requests = []
    monkeypatch.setattr(about, "__version__", "0.8.0")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(code)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        monkeypatch.setattr(
            updates, "UPDATE_URL", f"http://127.0.0.1:{server.server_port}/aida/update.json"
        )
        worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        try:
            window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
            qtbot.addWidget(window)
            next(
                action
                for action in window.findChildren(QAction)
                if action.text() == "About AIDA FPS Studio"
            ).trigger()
            dialog = window.findChild(AboutDialog)
            assert dialog is not None and dialog.isVisible()
            labels = [label.text() for label in dialog.findChildren(QLabel)]
            assert any(f'href="{updates.SITE_URL}"' in label for label in labels)
            assert any(f'href="{updates.AIDA_URL}"' in label for label in labels)
            assert not requests
            dialog._check_button.click()
            qtbot.waitUntil(lambda: dialog._status.text() == message)
            assert dialog._check_button.isEnabled()
            assert requests == ["/aida/update.json"]
            dialog.close()
            window.close()
        finally:
            server.shutdown()
            worker.join()
