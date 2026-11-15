"""Time-based navigation while the authoritative frame index is being prepared."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from dg_fps.media.navigation_preview import NavigationFrame
from dg_fps.ui.i18n import localize


class OpeningPreview(QWidget):
    time_requested = Signal(float)
    cancel_requested = Signal()
    retry_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("openingPreview")
        self._span: tuple[float, float] | None = None
        self._frames: tuple[NavigationFrame, ...] = ()
        self._cancelled = False
        self.heading = QLabel()
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.position = QLabel()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderReleased.connect(self._seek)
        self.buttons: list[QToolButton] = []
        strip = QHBoxLayout()
        for number in range(6):
            button = QToolButton()
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            button.setIconSize(QSize(120, 68))
            button.setMinimumHeight(108)
            button.clicked.connect(lambda checked=False, number=number: self._choose(number))
            self.buttons.append(button)
            strip.addWidget(button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.cancel = QPushButton()
        self.cancel.clicked.connect(self.cancel_requested)
        self.retry = QPushButton()
        self.retry.clicked.connect(self.retry_requested)
        self.retry.hide()
        status = QHBoxLayout()
        status.addWidget(self.progress, 1)
        status.addWidget(self.cancel)
        status.addWidget(self.retry)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.heading)
        layout.addWidget(self.description)
        layout.addLayout(strip)
        layout.addWidget(self.slider)
        layout.addWidget(self.position)
        layout.addLayout(status)
        self.reset(None)

    def retranslate(self) -> None:
        self.heading.setText(
            localize(
                "Prévia disponível · preparando índice preciso"
                if not self._cancelled
                else "Prévia disponível · indexação interrompida"
            )
        )
        self.description.setText(
            localize(
                "Miniaturas representativas. Marcas, análise e exportação serão liberadas "
                "quando a indexação terminar."
            )
        )
        self.cancel.setText(localize("Cancelar indexação"))
        self.retry.setText(localize("Preparar índice novamente"))
        self.progress.setFormat(localize("Índice preciso: %p%"))
        self.slider.setAccessibleName(localize("Navegar por tempo durante a indexação"))
        self.slider.setToolTip(
            localize("Prévia representativa; o tempo da imagem pode diferir do pedido")
        )

    def reset(self, span: tuple[float, float] | None) -> None:
        self._span = span
        self._frames = ()
        self._cancelled = False
        self.progress.setValue(0)
        self.cancel.setEnabled(True)
        self.retry.hide()
        self.slider.setEnabled(span is not None)
        self.slider.setValue(0)
        self.position.clear()
        for button in self.buttons:
            button.setIcon(QIcon())
            button.setText("…")
            button.setEnabled(False)
        self.retranslate()

    def set_frames(self, frames: tuple[NavigationFrame, ...]) -> None:
        self._frames = frames[:6]
        for button, frame in zip(self.buttons, self._frames, strict=False):
            height, width, _ = frame.rgb.shape
            image = QImage(
                frame.rgb.data, width, height, frame.rgb.strides[0], QImage.Format.Format_RGB888
            ).copy()
            button.setIcon(QIcon(QPixmap.fromImage(image)))
            button.setText(f"{frame.seconds:.3f} s")
            button.setToolTip(localize(f"Imagem em {frame.seconds:.3f} s"))
            button.setEnabled(True)

    def set_position(self, requested: float, actual: float) -> None:
        if self._span is not None and not self.slider.isSliderDown():
            start, duration = self._span
            self.slider.setValue(max(0, min(1000, round((requested - start) / duration * 1000))))
        self.position.setText(localize(f"Pedido: {requested:.3f} s · imagem: {actual:.3f} s"))

    def interrupted(self) -> None:
        self._cancelled = True
        self.cancel.setEnabled(False)
        self.retry.show()
        self.retranslate()

    def _seek(self) -> None:
        if self._span is not None:
            start, duration = self._span
            self.time_requested.emit(start + duration * min(self.slider.value(), 999) / 1000)

    def _choose(self, number: int) -> None:
        if number < len(self._frames):
            self.time_requested.emit(self._frames[number].seconds)
