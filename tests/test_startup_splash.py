from __future__ import annotations

import pytest
from PySide6.QtCore import QElapsedTimer, Qt
from PySide6.QtWidgets import QWidget

from dg_fps.ui import splash as startup


@pytest.mark.parametrize("startup_ms", [0, 100])
def test_splash_waits_for_both_startup_and_minimum_time(qapp, qtbot, monkeypatch, startup_ms):
    minimum_ms = 80
    monkeypatch.setattr(startup, "MINIMUM_SPLASH_MS", minimum_ms)
    screen = qapp.primaryScreen()
    splash = startup.StartupSplash(screen)
    window = QWidget()
    window.resize(300, 200)
    qtbot.addWidget(splash)
    qtbot.addWidget(window)
    opened = []

    splash.start()
    visible_for = QElapsedTimer()
    visible_for.start()
    center = screen.availableGeometry().center()
    assert (splash.frameGeometry().center() - center).manhattanLength() <= 2
    qtbot.mouseClick(splash, Qt.MouseButton.LeftButton)
    assert splash.isVisible()
    if startup_ms:
        qtbot.wait(startup_ms)
    assert not window.isVisible()

    splash.reveal_when_ready(window, lambda: opened.append(visible_for.elapsed()))
    if not startup_ms:
        assert splash.isVisible()
        assert not window.isVisible()
        assert splash._messages[-1] == "Preparing the workspace..."
    else:
        assert opened
    qtbot.waitUntil(lambda: bool(opened))
    assert opened[0] >= minimum_ms - 1
    assert window.isVisible() and not splash.isVisible()
    assert (window.frameGeometry().center() - center).manhattanLength() <= 2
