from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QEventLoop, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPixmap, QScreen
from PySide6.QtWidgets import QApplication, QSplashScreen, QStyle, QWidget
from shiboken6 import isValid

from dg_fps import __version__

LOGGER = logging.getLogger(__name__)
MINIMUM_SPLASH_MS = 5_000


def _center(window: QWidget, screen: QScreen) -> None:
    window.move(
        QStyle.alignedRect(
            Qt.LayoutDirection.LeftToRight,
            Qt.AlignmentFlag.AlignCenter,
            window.frameSize(),
            screen.availableGeometry(),
        ).topLeft()
    )


class StartupSplash(QSplashScreen):
    def __init__(self, screen: QScreen) -> None:
        self._screen = screen
        available = screen.availableGeometry()
        limit = QSize(min(960, int(available.width() * 0.9)), int(available.height() * 0.9))
        artwork = QPixmap(str(Path(__file__).resolve().parents[1] / "assets" / "startup.png"))
        if artwork.isNull():
            artwork = QPixmap(960, 540)
            artwork.fill(QColor("#080c11"))
        pixmap = artwork.scaled(
            limit, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        super().__init__(screen, pixmap, Qt.WindowType.WindowStaysOnTopHint)
        self._messages: deque[str] = deque(maxlen=4)
        self._visible_for = QElapsedTimer()
        self._reveal = QTimer(self)
        self._reveal.setSingleShot(True)
        self._reveal.setTimerType(Qt.TimerType.PreciseTimer)
        _center(self, screen)

    def start(self) -> None:
        self.show()
        self.report("Starting AIDA FPS Studio...")
        self._visible_for.start()

    def report(self, message: str) -> None:
        LOGGER.info("%s", message)
        self._messages.append(message)
        self.repaint()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def reveal_when_ready(self, window: QWidget, on_shown: Callable[[], None]) -> None:
        def reveal() -> None:
            screen = self._screen if isValid(self._screen) else QApplication.primaryScreen()
            window.setScreen(screen)
            window.resize(window.size().boundedTo(screen.availableGeometry().size()))
            _center(window, screen)
            window.show()
            _center(window, screen)
            self.finish(window)
            on_shown()

        remaining = MINIMUM_SPLASH_MS - self._visible_for.elapsed()
        if remaining > 0:
            self.report("Preparing the workspace...")
            self._reveal.timeout.connect(reveal)
            self._reveal.start(max(0, MINIMUM_SPLASH_MS - self._visible_for.elapsed()))
        else:
            reveal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        event.accept()

    def drawContents(self, painter: QPainter) -> None:
        scale = self.width() / 960
        panel = QRectF(self.width() * 0.06, self.height() * 0.045, 390 * scale, 102 * scale)
        painter.fillRect(panel, QColor(5, 9, 14, 250))
        painter.fillRect(
            QRectF(panel.left(), panel.top(), 2 * scale, panel.height()), QColor("#f7952a")
        )
        x = panel.left() + 12 * scale
        font = QFont("Consolas")
        font.setPixelSize(max(9, round(14 * scale)))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#f8fafc"))
        painter.drawText(QPointF(x, panel.top() + 21 * scale), f"AIDA FPS Studio {__version__}")
        font.setPixelSize(max(8, round(12 * scale)))
        font.setBold(False)
        painter.setFont(font)
        for row, message in enumerate(self._messages):
            color = "#a5eef5" if row == len(self._messages) - 1 else "#a7b2bf"
            painter.setPen(QColor(color))
            painter.drawText(QPointF(x, panel.top() + (39 + 16 * row) * scale), f"> {message}")
