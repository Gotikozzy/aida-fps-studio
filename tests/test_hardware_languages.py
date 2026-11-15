from __future__ import annotations

import json

import numpy as np
import pytest

from dg_fps import hardware
from dg_fps.backends import select_backend
from dg_fps.hardware import GPUCheck, HardwareCheck, check_hardware
from dg_fps.jobs.cancellation import CancellationToken, JobCancelled
from dg_fps.ui.i18n import CATALOG, localize, set_language, system_language
from dg_fps.ui.main_window import FPSWindow


@pytest.mark.parametrize(
    "name,expected",
    [("pt_BR", "pt"), ("pt_PT", "pt"), ("en_US", "en"), ("de_DE", "en"), ("ja_JP", "en")],
)
def test_system_language(name, expected):
    assert system_language(name) == expected


def test_catalog_round_trip_and_dynamic_text():
    for pt, en in CATALOG.items():
        if "{" in pt:
            continue
        set_language("en")
        assert localize(pt) == en
        set_language("pt")
        assert localize(en) == pt
    set_language("en")
    assert localize("Trecho 2: frames 7–10  (00:00:00.100–00:00:00.200)").startswith("Segment 2:")
    assert localize("FPS do conteúdo: inconclusivo") == "Content FPS: inconclusive"
    set_language("pt")
    assert localize("Content FPS: inconclusive") == "FPS do conteúdo: inconclusivo"


def test_missing_driver_never_initializes_gpu(monkeypatch, tmp_path):
    library = tmp_path / "bridge.dll"
    library.touch()
    monkeypatch.setattr(hardware, "driver_available", lambda: False)
    monkeypatch.setattr(
        hardware, "probe_nvenc", lambda *_: pytest.fail("No driver must skip NVENC")
    )
    result = check_hardware(CancellationToken(), lambda *_: None, library)
    assert result.bridge_found and not result.optical_flow and not result.nvenc
    assert result.reason == "driver_missing"


def test_missing_bridge_does_not_disable_encoding(monkeypatch, tmp_path):
    monkeypatch.setattr(hardware, "driver_available", lambda: True)
    monkeypatch.setattr(hardware, "probe_nvenc", lambda *_: True)
    result = check_hardware(CancellationToken(), lambda *_: None, tmp_path / "missing.dll")
    assert not result.bridge_found and not result.optical_flow
    assert result.nvenc and result.reason == "bridge_missing"


def test_gpu_features_are_checked_independently_and_all_devices_tried(monkeypatch, tmp_path):
    library = tmp_path / "bridge.dll"
    library.touch()
    monkeypatch.setattr(hardware, "driver_available", lambda: True)
    monkeypatch.setattr(hardware, "probe_nvenc", lambda *_: True)
    monkeypatch.setattr("dg_fps.vision.optical_flow.nvidia_native.device_count", lambda *_: 2)

    class Backend:
        gpu_name = "Test GPU"
        closed = []

        def __init__(self, path, device_index):
            self.index = device_index

        def verify(self):
            if self.index == 0:
                raise RuntimeError("Optical Flow unsupported")

        def close(self):
            self.closed.append(self.index)

    monkeypatch.setattr("dg_fps.vision.optical_flow.nvidia_native.NvidiaNativeBackend", Backend)
    result = check_hardware(CancellationToken(), lambda *_: None, library)
    assert [gpu.optical_flow for gpu in result.gpus] == [False, True]
    assert result.optical_flow and result.nvenc
    assert Backend.closed == [0, 1]
    assert select_backend("auto", library).primary.index == 1
    assert Backend.closed == [0, 1, 0]


def test_hardware_cancel_is_not_swallowed():
    token = CancellationToken()
    token.cancel()
    with pytest.raises(JobCancelled):
        check_hardware(token, lambda *_: None)


def test_hardware_button_is_async_and_translates_results(qtbot, tmp_path, monkeypatch):
    result = HardwareCheck(True, True, (GPUCheck("Test GPU", 0, True),), False, "")
    monkeypatch.setattr("dg_fps.ui.main_window.check_hardware", lambda *_: result)
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.show()
    window._show_preferences()
    window._test_hardware()
    assert window.preferences.isVisible() and not window.process_dialog.isVisible()
    assert window.hardware_dialog.isVisible()
    assert not window.hardware_button.isEnabled()
    qtbot.waitUntil(lambda: window.hardware_result is not None, timeout=5000)
    assert window.preferences.isVisible()
    assert not window.hardware_dialog.isVisible()
    assert "Análise com NVIDIA: Disponível" in window.hardware_status.toPlainText()
    assert not window.panel.isEnabled()  # no source was opened
    window.language_box.setCurrentIndex(window.language_box.findData("en"))
    assert window.file_label.text() == "No video open"
    assert "NVIDIA analysis: Available" in window.hardware_status.toPlainText()
    assert "NVIDIA export: Unavailable" in window.hardware_status.toPlainText()
    assert window.hardware_button.isEnabled()
    window.close()
    prefs = json.loads((tmp_path / "data/settings.json").read_text(encoding="utf-8"))
    assert prefs["language"] == "en"
    reopened = FPSWindow(tmp_path / "data", tmp_path / "cache")
    qtbot.addWidget(reopened)
    assert reopened.open_button.accessibleName() == "Open video"
    reopened.close()


def test_first_launch_uses_system_language(qtbot, tmp_path):
    window = FPSWindow(tmp_path / "data", tmp_path / "cache")
    qtbot.addWidget(window)
    assert window.language_box.currentData() == "system"
    assert window.open_button.accessibleName() == (
        "Abrir vídeo" if system_language() == "pt" else "Open video"
    )
    window.close()


def test_native_verify_rejects_empty_motion():
    from dg_fps.vision.optical_flow.base import OpticalFlowField
    from dg_fps.vision.optical_flow.nvidia_native import NvidiaNativeBackend, NvidiaOpticalFlowError

    class Empty:
        def compute(self, *_):
            return OpticalFlowField(
                "test",
                "1",
                np.zeros((192, 320, 2), np.float32),
                np.zeros((192, 320), np.float32),
                {},
            )

    with pytest.raises(NvidiaOpticalFlowError, match="invalid"):
        NvidiaNativeBackend.verify(Empty())
