from __future__ import annotations

import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QWidget

from dg_fps.ui.main_window import FPSWindow
from dg_fps.ui.workspace_layout import HORIZONTAL, WorkspaceLayout, fitted_sizes, weights


@pytest.mark.parametrize("invalid", [None, [], [1, 2], [0, 0, 0], [-1, 2, 3],
                                     ["240", 850, 300], [True, 2, 3], [float("nan"), 2, 3]])
def test_invalid_preferences_fall_back(invalid):
    assert weights(invalid, HORIZONTAL) == weights(HORIZONTAL, HORIZONTAL)


def test_legacy_squeezed_panels_are_repaired_without_discarding_valid_ratios():
    sizes = fitted_sizes(1572, weights([215, 1303, 54], HORIZONTAL), [240, 320, 285])
    assert sizes[0] >= 240 and sizes[2] >= 285 and sum(sizes) == 1572
    assert fitted_sizes(1200, [.25, .5, .25], [240, 320, 285]) == [300, 600, 300]


def test_resize_preserves_user_intent_and_vertical_preference(qtbot):
    vertical = QSplitter(Qt.Orientation.Vertical)
    horizontal = QSplitter(Qt.Orientation.Horizontal)
    for _ in range(3):
        horizontal.addWidget(QWidget())
    vertical.addWidget(horizontal)
    vertical.addWidget(QWidget())
    controller = WorkspaceLayout(horizontal, vertical, {"workspace_layout": {
        "version": 1, "horizontal": [.25, .5, .25], "vertical": [.6, .4]}})
    qtbot.addWidget(vertical)
    vertical.resize(1400, 900)
    vertical.show()
    qtbot.waitUntil(lambda: horizontal.sizes()[0] > 300)
    original = controller.snapshot()
    vertical.resize(900, 650)
    qtbot.waitUntil(lambda: horizontal.sizes()[2] >= 285)
    assert controller.snapshot() == original
    vertical.resize(1400, 900)
    qtbot.waitUntil(lambda: horizontal.sizes()[0] > 300)
    assert controller.snapshot() == original
    horizontal.setSizes([400, 600, 380])
    horizontal.splitterMoved.emit(400, 1)
    assert controller.snapshot()["horizontal"] == weights(horizontal.sizes(), HORIZONTAL)
    vertical.setSizes([500, 390])
    vertical.splitterMoved.emit(500, 1)
    assert controller.snapshot()["vertical"] == weights(vertical.sizes(), [600, 235])


def test_window_restores_after_hidden_home_and_persists_both_dividers(qtbot, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.json").write_text(json.dumps({"panel_sizes": [215, 1303, 54]}))
    window = FPSWindow(data_directory=data, cache_directory=tmp_path / "cache")
    qtbot.addWidget(window)
    window.resize(1300, 850)
    window.show()
    assert window.workspaces.currentIndex() == window.home_index
    window.workspaces.setCurrentIndex(0)
    qtbot.waitUntil(lambda: window.main_splitter.sizes()[2] >= 285)
    assert window.main_splitter.sizes()[0] >= 240
    window.main_splitter.setSizes([320, 600, 330])
    window.main_splitter.splitterMoved.emit(320, 1)
    window.vertical_splitter.setSizes([440, 260])
    window.vertical_splitter.splitterMoved.emit(440, 1)
    expected = window.workspace_layout.snapshot()
    window.workspaces.setCurrentIndex(window.home_index)
    window._store_preferences()
    saved = json.loads((data / "settings.json").read_text())
    assert saved["workspace_layout"] == expected
    window.workspaces.setCurrentIndex(0)
    qtbot.waitUntil(lambda: window.main_splitter.sizes()[0] >= 240)
    assert window.workspace_layout.snapshot() == expected
    window.workspace_layout.reset()
    assert window.workspace_layout.snapshot()["horizontal"] == weights(HORIZONTAL, HORIZONTAL)
    assert window.vertical_splitter.sizes()[1] >= 150
    window.close()
