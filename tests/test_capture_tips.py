from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from dg_fps.ui.capture_tips import CHANNEL_URL, CaptureTips
from dg_fps.ui.main_window import FPSWindow


def test_home_tips_expand_without_navigating_and_translate(qtbot, tmp_path, monkeypatch):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    tips = window.welcome.findChild(CaptureTips)
    assert any(
        label.pixmap() is not None and not label.pixmap().isNull()
        for label in tips.findChild(QWidget, "captureFeature").findChildren(QLabel)
    )
    headers = tips.findChildren(QPushButton, "captureTipHeader")
    bodies = tips.findChildren(QWidget, "captureTipBody")
    assert len(headers) == len(bodies) == 5
    assert all(button.isVisible() and button.accessibleName() for button in headers)
    assert all(not body.isVisible() for body in bodies)
    assert all(
        any(
            label.pixmap() is not None and not label.pixmap().isNull()
            for label in body.findChildren(QLabel)
        )
        for body in bodies
    )
    headers[0].click()
    assert bodies[0].isVisible()
    headers[1].click()
    assert not bodies[0].isVisible() and bodies[1].isVisible()
    window.language_box.setCurrentIndex(window.language_box.findData("en"))
    assert headers[1].accessibleName() == "Record from your console"
    assert "Space" in headers[1].accessibleDescription()
    assert bodies[1].isVisible()
    headers[1].click()
    assert not any(body.isVisible() for body in bodies)
    assert window.workspaces.currentIndex() == window.home_index
    assert window.recent_list.isVisible()

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    tips.findChild(QPushButton, "captureTipsChannel").click()
    assert opened == [CHANNEL_URL]
    window.close()


def test_home_actions_and_tips_are_readable_and_keyboard_operable(qtbot, tmp_path):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="en")
    qtbot.addWidget(window)
    window.resize(1000, 760)
    window.show()
    assert window.findChild(QPushButton, "homeNewAnalysis").text() == "New analysis"
    assert window.findChild(QPushButton, "homeOpenProject").text() == "Open project…"
    assert window.panel._analyze.text() == "Analyze ranges"
    tips = window.welcome.findChild(CaptureTips)
    header, body = tips._cards[0]
    header.setFocus()
    qtbot.keyClick(header, Qt.Key.Key_Space)
    assert body.isVisible()
    assert "expanded" in header.accessibleDescription()
    qtbot.keyClick(header, Qt.Key.Key_Space)
    assert not body.isVisible()
    window.language_box.setCurrentIndex(window.language_box.findData("pt"))
    assert "selecionado" in window.fps_value.toolTip()
    assert window.findChild(QPushButton, "homeOpenProject").text() == "Abrir projeto…"
    window.close()
