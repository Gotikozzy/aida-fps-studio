"""Restore workspace proportions only after Qt has a usable, visible geometry."""

from __future__ import annotations

import math
from collections.abc import Sequence

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QSplitter

HORIZONTAL = (280, 850, 310)
VERTICAL = (600, 235)


def weights(value: object, fallback: Sequence[int]) -> list[float]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != len(fallback)
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float))
            or not math.isfinite(v) or v < 0 for v in value
        )
        or sum(value) <= 0
    ):
        value = fallback
    total = sum(value)
    return [v / total for v in value]


def fitted_sizes(total: int, ratios: Sequence[float], minimums: Sequence[int]) -> list[int]:
    """Keep the requested proportions, redistributing only space below usable minima."""
    total = max(0, total)
    if total < sum(minimums):
        ratios = weights(minimums, minimums)
        result = [int(total * r) for r in ratios]
    else:
        result = [0] * len(ratios)
        pending = set(range(len(ratios)))
        remaining = total
        while pending:
            scale = sum(ratios[i] for i in pending)
            shares = {i: remaining * (ratios[i] / scale if scale else 1 / len(pending))
                      for i in pending}
            limited = [i for i in pending if shares[i] < minimums[i]]
            if not limited:
                for i in pending:
                    result[i] = int(shares[i])
                break
            for i in limited:
                result[i] = minimums[i]
                remaining -= minimums[i]
                pending.remove(i)
    result[max(range(len(result)), key=lambda i: result[i])] += total - sum(result)
    return result


class WorkspaceLayout(QObject):
    def __init__(self, horizontal: QSplitter, vertical: QSplitter, settings: dict) -> None:
        super().__init__(horizontal)
        self.horizontal, self.vertical = horizontal, vertical
        saved = settings.get("workspace_layout")
        saved = saved if isinstance(saved, dict) and saved.get("version") == 1 else {}
        self._horizontal = weights(saved.get("horizontal", settings.get("panel_sizes")), HORIZONTAL)
        self._vertical = weights(saved.get("vertical"), VERTICAL)
        self._applying = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.apply)
        for splitter in (horizontal, vertical):
            splitter.setChildrenCollapsible(False)
            splitter.installEventFilter(self)
            splitter.splitterMoved.connect(self._moved)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Show, QEvent.Type.Resize) and not self._applying:
            self._timer.start(0)
        return False

    def _moved(self, _position: int, _index: int) -> None:
        splitter = self.sender()
        if self._applying or not splitter.isVisible():
            return
        if splitter is self.horizontal:
            self._horizontal = weights(splitter.sizes(), HORIZONTAL)
        else:
            self._vertical = weights(splitter.sizes(), VERTICAL)

    def apply(self) -> None:
        if not self.horizontal.isVisible():
            return
        self._applying = True
        try:
            for splitter, ratios, minimums in (
                (self.horizontal, self._horizontal, (240, 320, 285)),
                (self.vertical, self._vertical, (260, 150)),
            ):
                extent = splitter.width() if splitter is self.horizontal else splitter.height()
                extent -= splitter.handleWidth() * (splitter.count() - 1)
                splitter.setSizes(fitted_sizes(extent, ratios, minimums))
        finally:
            self._applying = False

    def reset(self) -> None:
        self._horizontal = weights(HORIZONTAL, HORIZONTAL)
        self._vertical = weights(VERTICAL, VERTICAL)
        self.apply()

    def snapshot(self) -> dict:
        # Preserve the user's intent, not a temporary clamp on a smaller screen or hidden tab.
        return {"version": 1, "horizontal": list(self._horizontal),
                "vertical": list(self._vertical)}
