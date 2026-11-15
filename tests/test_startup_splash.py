from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from dg_fps.ui import splash as startup


@pytest.mark.parametrize("startup_ms", [0, 30, 100])
def test_splash_gates_readiness_and_schedules_remaining_minimum(
    qapp, qtbot, monkeypatch, startup_ms
):
    minimum_ms = 80
    monkeypatch.setattr(startup, "MINIMUM_SPLASH_MS", minimum_ms)
    screen = qapp.primaryScreen()
    splash = startup.StartupSplash(screen)

    class Clock:
        milliseconds = 0

        def start(self):
            self.milliseconds = 0

        def elapsed(self):
            return self.milliseconds

    # Verify the requested deadline, rather than the VM's sub-millisecond clock
    # alignment. No application timer, rendering or measurement code is modified.
    clock = Clock()
    splash._visible_for = clock
    assert splash._reveal.timerType() == Qt.TimerType.PreciseTimer
    assert splash._reveal.isSingleShot()
    window = QWidget()
    window.resize(300, 200)
    qtbot.addWidget(splash)
    qtbot.addWidget(window)
    opened = []

    splash.start()
    center = screen.availableGeometry().center()
    assert (splash.frameGeometry().center() - center).manhattanLength() <= 2
    qtbot.mouseClick(splash, Qt.MouseButton.LeftButton)
    assert splash.isVisible()
    clock.milliseconds = startup_ms
    assert not window.isVisible()

    splash.reveal_when_ready(window, lambda: opened.append(splash._visible_for.elapsed()))
    if startup_ms < minimum_ms:
        assert splash.isVisible()
        assert not window.isVisible()
        assert splash._messages[-1] == "Preparing the workspace..."
        assert splash._reveal.isActive()
        assert splash._reveal.interval() == minimum_ms - startup_ms
        clock.milliseconds = minimum_ms
        splash._reveal.stop()
        splash._reveal.timeout.emit()
    else:
        assert opened
        assert not splash._reveal.isActive()
    qtbot.waitUntil(lambda: bool(opened))
    assert opened[0] >= minimum_ms
    assert window.isVisible() and not splash.isVisible()
    assert (window.frameGeometry().center() - center).manhattanLength() <= 2
