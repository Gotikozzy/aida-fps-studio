from __future__ import annotations

import math

from PySide6.QtCore import QLocale, QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from dg_fps.presentation.content_targets import capture_supports_target, capture_target_limit
from dg_fps.ui.i18n import localize


class TargetSelector(QWidget):
    changed = Signal()

    def __init__(self, value: float | None = None, parent=None) -> None:
        super().__init__(parent)
        self.capture_rate: float | None = None
        self.combo = QComboBox()
        self.combo.addItem(localize("Automático — cadência observada"), None)
        for target in (30, 40, 60, 120):
            self.combo.addItem(f"{target} FPS", float(target))
        self.combo.addItem(localize("Personalizada"), -1)
        self.custom = QDoubleSpinBox()
        self.custom.setLocale(QLocale.c())
        self.custom.setRange(1, 1000)
        self.custom.setDecimals(2)
        self.custom.setSuffix(" FPS")
        self.custom.setValue(value or 60)
        self.combo.setCurrentIndex(
            self.combo.findData(value) if value in (None, 30, 40, 60, 120) else 5
        )
        self.custom.setVisible(self.combo.currentData() == -1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.custom)
        self.combo.currentIndexChanged.connect(self._changed)
        self.custom.valueChanged.connect(self._custom_changed)

    def _changed(self) -> None:
        self.custom.setVisible(self.combo.currentData() == -1)
        self._update_custom_limit(preserve=False)
        self.changed.emit()

    def _custom_changed(self) -> None:
        if self.is_compatible():
            self._update_custom_limit(preserve=False)
        self.changed.emit()

    def _update_custom_limit(self, *, preserve: bool) -> None:
        maximum = (
            1000
            if self.capture_limit is None
            else min(1000, max(1, math.floor(self.capture_limit * 100) / 100))
        )
        if preserve and self.combo.currentData() == -1:
            maximum = max(maximum, self.custom.value())
        with QSignalBlocker(self.custom):
            self.custom.setMaximum(maximum)

    @property
    def capture_limit(self) -> float | None:
        if self.capture_rate is None:
            return None
        return capture_target_limit(self.capture_rate) or 0.0

    def set_capture_rate(self, rate: float | None) -> None:
        self.capture_rate = rate
        for index in range(1, self.combo.count()):
            value = self.combo.itemData(index)
            allowed = self.supports_target(1 if value == -1 else value)
            self.combo.model().item(index).setEnabled(allowed)
        self._update_custom_limit(preserve=True)

    def supports_target(self, target: float | None) -> bool:
        return (
            target is None
            or self.capture_rate is None
            or capture_supports_target(self.capture_rate, target)
        )

    def is_compatible(self) -> bool:
        return self.supports_target(self.value())

    def value(self) -> float | None:
        return self.custom.value() if self.combo.currentData() == -1 else self.combo.currentData()

    def set_value(self, value: float | None) -> None:
        position = self.combo.findData(value)
        with QSignalBlocker(self.combo), QSignalBlocker(self.custom):
            self.combo.setCurrentIndex(position if position >= 0 else self.combo.findData(-1))
            if value is not None:
                self.custom.setMaximum(max(1000, value))
                self.custom.setValue(value)
        self.custom.setVisible(self.combo.currentData() == -1)
        self._update_custom_limit(preserve=True)
        self.changed.emit()


class SegmentTargetsDialog(QDialog):
    def __init__(
        self,
        labels: list[str],
        choices: dict[str, float | None],
        default,
        parent,
        *,
        capture_rate: float | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(localize("Metas por trecho"))
        self.resize(520, 360)
        layout = QVBoxLayout(self)
        note = QLabel(localize("Referência de apresentação; não altera a medição."))
        note.setWordWrap(True)
        layout.addWidget(note)
        if capture_rate is not None:
            capture_limit = capture_target_limit(capture_rate)
            text = (
                f"Limite da captura: {capture_limit:g} FPS"
                if capture_limit
                else "Taxa da captura indisponível. Use Automático."
            )
            limit = QLabel(localize(text))
            layout.addWidget(limit)
        content = QWidget()
        form = QFormLayout(content)
        self.selectors = {}
        for label in labels:
            selector = TargetSelector(choices.get(label, default))
            selector.set_capture_rate(capture_rate)
            self.selectors[label] = selector
            form.addRow(localize(label), selector)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)

        def validate():
            ok.setEnabled(all(selector.is_compatible() for selector in self.selectors.values()))

        for selector in self.selectors.values():
            selector.changed.connect(validate)
        validate()

    def values(self) -> dict[str, float | None]:
        return {label: selector.value() for label, selector in self.selectors.items()}
