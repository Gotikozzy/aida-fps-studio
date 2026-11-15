from __future__ import annotations

import gc
import weakref

import numpy as np
import pytest

from dg_fps.backends import RecoveringBackend
from dg_fps.vision.optical_flow import nvidia_native


@pytest.fixture
def native(monkeypatch, tmp_path):
    class Library:
        creates = 0
        destroys = []
        calls = 0
        fail = False

        def dg_nvof_set_device(self, index):
            pass

        def dg_nvof_engine_create(self, index):
            self.creates += 1
            return 42

        def dg_nvof_engine_destroy(self, handle):
            self.destroys.append(handle)

        def dg_nvof_last_error(self):
            return b"device lost"

        def dg_nvof_engine_compute_gray8(self, handle, a, b, w, h, out, size, ow, oh, grid):
            assert handle == 42
            self.calls += 1
            if self.fail:
                return -1
            ow._obj.value, oh._obj.value, grid._obj.value = (w + 3) // 4, (h + 3) // 4, 4
            np.ctypeslib.as_array(out, shape=(size,))[:] = self.calls
            return 0

    library = Library()
    monkeypatch.setattr(nvidia_native, "_load_library", lambda _: library)
    monkeypatch.setattr(nvidia_native, "_probe", lambda _: "Test GPU")
    return nvidia_native.NvidiaNativeBackend(tmp_path / "test.dll"), library


def test_lazy_resources_reused_and_outputs_owned(native):
    backend, library = native
    rgb = np.zeros((32, 32, 3), np.uint8)
    assert library.creates == 0
    first = backend.compute(rgb, rgb)
    second = backend.compute(rgb, rgb)
    assert library.creates == 1 and library.calls == 2
    assert np.all(first.vectors == 1) and np.all(second.vectors == 2)
    backend.close()
    backend.close()
    assert library.destroys == [42]
    with pytest.raises(nvidia_native.NvidiaOpticalFlowError, match="closed"):
        backend.compute(rgb, rgb)
    assert library.creates == 1


def test_finalizer_releases_abandoned_backend(native):
    backend, library = native
    # Pytest retains fixture values until teardown; abandon a separate instance.
    backend = type(backend)(backend._library_path)
    rgb = np.zeros((32, 32, 3), np.uint8)
    backend.compute(rgb, rgb)
    reference = weakref.ref(backend)
    del backend
    del native
    gc.collect()
    assert reference() is None
    assert library.destroys == [42]


def test_gray_cache_reuses_reverse_pair_and_detects_mutation(native, monkeypatch):
    backend, _ = native
    original = nvidia_native.cv2.cvtColor
    converted = []

    def convert(rgb, code):
        converted.append(rgb.copy())
        return original(rgb, code)

    monkeypatch.setattr(nvidia_native.cv2, "cvtColor", convert)
    a = np.zeros((32, 32, 3), np.uint8)
    b = np.full_like(a, 42)
    backend.compute(a, b)
    backend.compute(b, a)
    assert len(converted) == 2
    a[:] = 200
    backend.compute(a, b)
    assert len(converted) == 3
    assert np.array_equal(backend._gray_input(a), original(a, nvidia_native.cv2.COLOR_RGB2GRAY))
    assert len(backend._gray_inputs) <= 2
    backend.close()
    assert backend._gray_inputs == []


def test_validation_happens_before_gpu_allocation(native):
    backend, library = native
    with pytest.raises(ValueError):
        backend.compute(np.zeros((32, 32), np.uint8), np.zeros((32, 32), np.uint8))
    assert library.creates == 0
    backend.close()
    assert library.destroys == []


def test_fallback_releases_gpu_and_preserves_failure(native):
    primary, library = native
    backend = RecoveringBackend(primary)
    library.fail = True
    rgb = np.zeros((32, 32, 3), np.uint8)
    for _ in range(2):
        result = backend.compute(rgb, rgb)
        assert result.backend_id == "opencv_farneback_cpu"
        assert result.parameters["fallback_reason"] == "device lost"
    backend.close()
    assert library.calls == 1 and library.destroys == [42]


@pytest.mark.parametrize("cancel", [False, True])
def test_service_releases_backend_on_success_or_cancel(sample_video, tmp_path, monkeypatch, cancel):
    from dg_fps.analyzers.base import AnalysisFrameRange
    from dg_fps.jobs.cancellation import CancellationToken, JobCancelled
    from dg_fps.media.media_probe import MediaProbe
    from dg_fps.media.timestamp_index import TimestampIndex
    from dg_fps.service import FPSService
    from dg_fps.vision.optical_flow.opencv_cpu import OpenCVFarnebackBackend

    class Backend(OpenCVFarnebackBackend):
        closed = 0

        def close(self):
            self.closed += 1

    backend = Backend()
    monkeypatch.setattr("dg_fps.service.select_backend", lambda *_: backend)
    if cancel:

        def cancelled(*_):
            raise JobCancelled()

        monkeypatch.setattr("dg_fps.service.CadenceAnalyzer.analyze", cancelled)

    def analyze():
        return FPSService().analyze(
            sample_video,
            MediaProbe().probe(sample_video),
            TimestampIndex.build(sample_video),
            (AnalysisFrameRange(0, 3, "A"),),
            tmp_path / "reports",
            "cpu",
            None,
            CancellationToken(),
            lambda *_: None,
        )

    if cancel:
        with pytest.raises(JobCancelled):
            analyze()
    else:
        analyze()
    assert backend.closed == 1
