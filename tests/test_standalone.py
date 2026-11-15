from __future__ import annotations

import importlib
import json
import pkgutil
import sys

import av
import numpy as np
import pytest

import dg_fps
from dg_fps.analyzers.base import AnalysisFrameRange
from dg_fps.backends import RecoveringBackend, select_backend
from dg_fps.jobs.cancellation import CancellationToken, JobCancelled
from dg_fps.media.media_probe import MediaProbe
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.cadence_video import CadenceVideoExporter
from dg_fps.presentation.video_encoder import EncoderUnavailable
from dg_fps.service import FPSService
from dg_fps.vision.optical_flow.opencv_cpu import OpenCVFarnebackBackend


def session_for(source, output):
    service = FPSService()
    index = TimestampIndex.build(source)
    session = service.analyze(
        source,
        MediaProbe().probe(source),
        index,
        (AnalysisFrameRange(0, 3, "A"), AnalysisFrameRange(6, 9, "B")),
        output,
        "cpu",
        None,
        CancellationToken(),
        lambda *_: None,
    )
    return service, session


def test_all_modules_import_without_parent_or_ai():
    for module in pkgutil.walk_packages(dg_fps.__path__, "dg_fps."):
        if module.name != "dg_fps.__main__":
            importlib.import_module(module.name)
    assert not any(
        name.startswith(("dg_graphics_analyzer", "torch", "transformers")) for name in sys.modules
    )


def test_cpu_does_not_load_nvidia_and_auto_recovers(monkeypatch, tmp_path):
    def fail(*_):
        raise AssertionError("CPU must not initialize NVIDIA")

    monkeypatch.setattr("dg_fps.vision.optical_flow.nvidia_native.NvidiaNativeBackend", fail)
    monkeypatch.setattr("dg_fps.backends.bundled_library_path", lambda: tmp_path / "missing.dll")
    assert isinstance(select_backend("cpu", tmp_path / "missing.dll"), OpenCVFarnebackBackend)
    assert isinstance(select_backend("auto", tmp_path / "missing.dll"), OpenCVFarnebackBackend)
    with pytest.raises(RuntimeError, match="NVIDIA"):
        select_backend("nvidia")


def test_failed_flow_is_disabled_and_recorded():
    class Broken(OpenCVFarnebackBackend):
        count = 0

        def compute(self, *_):
            self.count += 1
            raise RuntimeError("GPU unavailable")

    primary = Broken()
    backend = RecoveringBackend(primary)
    rgb = np.zeros((32, 32, 3), np.uint8)
    for _ in range(2):
        field = backend.compute(rgb, rgb)
        assert field.parameters["fallback_reason"] == "GPU unavailable"
        assert field.backend_id == "opencv_farneback_cpu"
    assert primary.count == 1


def test_analysis_does_not_export_and_preserves_provenance(sample_video, tmp_path):
    _, session = session_for(sample_video, tmp_path / "reports")
    document = json.loads(session.reports.analysis_json.read_text(encoding="utf-8"))
    assert not list((tmp_path / "reports").rglob("*.mp4"))
    assert document["frames"][1]["pts"] is not None
    assert document["frames"][1]["time_base"]
    assert document["frames"][1]["flow_backend"]
    assert document["analyzer"]["version"] == "0.9.0"
    llm = json.loads(session.reports.llm_report_json.read_text(encoding="utf-8"))
    assert (
        llm["measurement_contract"]["shared_update_decision"] == "contextual_presentation_repeated"
    )
    assert llm["provenance"]["analysis_file"] == str(session.reports.analysis_json.resolve())


@pytest.mark.parametrize(
    "failure", [EncoderUnavailable("no GPU"), av.error.ExternalError(1, "device lost")]
)
@pytest.mark.parametrize("language", ["pt", "en"])
def test_cpu_export_and_gpu_failure_fallback(
    qapp, sample_video, tmp_path, monkeypatch, failure, language
):
    service, session = session_for(sample_video, tmp_path / "reports")
    real_export = CadenceVideoExporter.export
    modes = []

    def export(self, *args, **kwargs):
        modes.append(kwargs["encoding_mode"])
        if kwargs["encoding_mode"] == "nvidia":
            args[3].write_bytes(b"partial hardware export")
            raise failure
        return real_export(self, *args, **kwargs)

    monkeypatch.setattr(CadenceVideoExporter, "export", export)
    output = tmp_path / "result.mp4"
    asset = service.export(
        session, output, "nvidia", CancellationToken(), lambda *_: None, language=language
    )
    assert modes == ["nvidia", "cpu"]
    with av.open(str(output)) as video:
        frames = list(video.decode(video=0))
    assert len(frames) == 8
    seconds = [float(frame.pts * frame.time_base) for frame in frames]
    index = session.timestamp_index
    # MKV uses a millisecond time base: preserve its actual times, not ideal 30 Hz.
    offset = index[4].seconds - index[0].seconds
    expected = [index[i].seconds - index[0].seconds for i in range(4)]
    expected += [offset + index[i].seconds - index[6].seconds for i in range(6, 10)]
    assert seconds == pytest.approx(expected, abs=1 / 90000)
    assert "CPU" in asset.codec
    mapping_path = next(tmp_path.glob("result_*_assets/frames.json"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert [value["source"]["index"] for value in mapping["frames"]] == [0, 1, 2, 3, 6, 7, 8, 9]
    assert mapping["fallback_reason"] == str(failure)
    assert asset.language == mapping["video_language"] == language
    assert asset.branding == mapping["branding"] == "AIDA"
    assert all(path.is_file() for path in asset.keyframe_paths)
    assert not list(tmp_path.glob(".dg-fps-*"))


@pytest.mark.parametrize("cancel_after_render", [False, True])
def test_cancel_preserves_existing_export(qapp, sample_video, tmp_path, cancel_after_render):
    service, session = session_for(sample_video, tmp_path / "reports")
    output = tmp_path / "result.mp4"
    output.write_bytes(b"existing export")
    token = CancellationToken()
    if not cancel_after_render:
        token.cancel()

    def progress(value, message):
        if cancel_after_render and value == 90:
            token.cancel()

    with pytest.raises(JobCancelled):
        service.export(session, output, "cpu", token, progress)
    assert output.read_bytes() == b"existing export"
    assert not list(tmp_path.glob(".dg-fps-*"))


def test_changed_source_or_original_output_is_rejected(sample_video, tmp_path):
    service, session = session_for(sample_video, tmp_path / "reports")
    with pytest.raises(ValueError, match="original"):
        service.export(session, sample_video, "cpu", CancellationToken(), lambda *_: None)
    with sample_video.open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(RuntimeError, match="alterado"):
        service.export(session, tmp_path / "out.mp4", "cpu", CancellationToken(), lambda *_: None)


def test_invalid_overlapping_ranges_are_rejected(sample_video, tmp_path):
    service = FPSService()
    with pytest.raises(ValueError, match="sobrepor"):
        service.analyze(
            sample_video,
            MediaProbe().probe(sample_video),
            TimestampIndex.build(sample_video),
            (AnalysisFrameRange(0, 5, "A"), AnalysisFrameRange(4, 7, "B")),
            tmp_path,
            "cpu",
            None,
            CancellationToken(),
            lambda *_: None,
        )
