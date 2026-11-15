from __future__ import annotations

import errno
from pathlib import Path

import av
import pytest
from test_standalone import session_for

from dg_fps.jobs.cancellation import CancellationToken, JobCancelled
from dg_fps.jobs.job_manager import JobManager
from dg_fps.presentation.cadence_video import CadenceVideoExporter
from dg_fps.presentation.export_verification import ExportVerificationError


def test_one_hundred_only_after_destination_is_readable(qapp, sample_video, tmp_path):
    service, session = session_for(sample_video, tmp_path / "reports")
    output = tmp_path / "saída com espaços" / "vídeo.mp4"
    progress = []

    def report(value, message):
        progress.append(value)
        if value < 97:
            assert not output.exists()
        if value == 100:
            with av.open(str(output)) as video:
                assert len(list(video.decode(video=0))) == 8

    asset = service.export(session, output, "cpu", CancellationToken(), report)
    assert asset.path == output.resolve() and not asset.warnings
    assert progress[-1] == 100 and progress.count(100) == 1
    assert {90, 91, 94, 97, 99, 100}.issubset(progress)
    assert progress == sorted(progress)


@pytest.mark.parametrize("corruption", [b"", b"not a valid MP4"])
def test_invalid_staging_file_never_replaces_existing_video(
    qapp, sample_video, tmp_path, monkeypatch, corruption
):
    service, session = session_for(sample_video, tmp_path / "reports")
    output = tmp_path / "video.mp4"
    output.write_bytes(b"previous export")
    original = CadenceVideoExporter.export

    def corrupt(self, *args, **kwargs):
        asset = original(self, *args, **kwargs)
        asset.path.write_bytes(corruption)
        return asset

    monkeypatch.setattr(CadenceVideoExporter, "export", corrupt)
    progress = []
    with pytest.raises(ExportVerificationError):
        service.export(session, output, "cpu", CancellationToken(), lambda n, _: progress.append(n))
    assert output.read_bytes() == b"previous export" and 100 not in progress
    assert not list(tmp_path.glob(".dg-fps-*"))


@pytest.mark.parametrize("stage", ["flush", "replace"])
def test_disk_failure_does_not_report_success_or_leave_published_assets(
    qapp, sample_video, tmp_path, monkeypatch, stage
):
    service, session = session_for(sample_video, tmp_path / "reports")
    output = tmp_path / "video.mp4"
    output.write_bytes(b"previous export")
    original_replace = Path.replace

    def flush_failed(_):
        raise OSError(errno.ENOSPC, "Disk full")

    def replace_failed(path, target):
        if path.name == "video.mp4" and Path(target) == output:
            raise PermissionError("Destination locked")
        return original_replace(path, target)

    if stage == "flush":
        monkeypatch.setattr("dg_fps.service.synchronize_file", flush_failed)
    else:
        monkeypatch.setattr(Path, "replace", replace_failed)
    progress = []
    with pytest.raises((OSError, RuntimeError)):
        service.export(session, output, "cpu", CancellationToken(), lambda n, _: progress.append(n))
    assert output.read_bytes() == b"previous export" and 100 not in progress
    assert not list(tmp_path.glob("video_*_assets"))
    assert not list(tmp_path.glob(".dg-fps-*"))


def test_report_failure_returns_saved_video_with_explicit_warning(
    qapp, sample_video, tmp_path, monkeypatch
):
    service, session = session_for(sample_video, tmp_path / "reports")
    output = tmp_path / "video.mp4"

    def failed(*args, **kwargs):
        raise PermissionError("Reports unavailable")

    monkeypatch.setattr(service.writer, "register_asset", failed)
    progress = []
    asset = service.export(
        session, output, "cpu", CancellationToken(), lambda n, _: progress.append(n)
    )
    assert asset.path.is_file() and progress[-1] == 100
    assert asset.warnings and str(output) in asset.warnings[0]
    with av.open(str(output)) as video:
        assert len(list(video.decode(video=0))) == 8
    assert next(tmp_path.glob("video_*_assets/frames.json")).is_file()


@pytest.mark.parametrize("cancel_at", [91, 94, 97])
def test_cancel_before_commit_preserves_existing_video(qapp, sample_video, tmp_path, cancel_at):
    service, session = session_for(sample_video, tmp_path / "reports")
    output = tmp_path / "video.mp4"
    output.write_bytes(b"previous export")
    token = CancellationToken()
    progress = []

    def report(value, message):
        progress.append(value)
        if value == cancel_at:
            token.cancel()

    with pytest.raises(JobCancelled):
        service.export(session, output, "cpu", token, report)
    assert output.read_bytes() == b"previous export" and 100 not in progress


def test_cancel_after_commit_cannot_discard_saved_result(qapp, sample_video, tmp_path):
    service, session = session_for(sample_video, tmp_path / "reports")
    output = tmp_path / "video.mp4"
    token = CancellationToken()
    declined = []

    def report(value, message):
        if value >= 99:
            assert output.is_file()
            declined.append(token.cancel())

    asset = service.export(session, output, "cpu", token, report)
    assert asset.path.is_file() and declined == [False, False]
    token.raise_if_cancelled()


def test_disk_full_in_gpu_mode_is_not_retried_as_cpu(qapp, sample_video, tmp_path, monkeypatch):
    service, session = session_for(sample_video, tmp_path / "reports")
    calls = []

    def failed(*args, **kwargs):
        calls.append(kwargs["encoding_mode"])
        raise av.error.PermissionError(errno.ENOSPC, "Disk full")

    monkeypatch.setattr(CadenceVideoExporter, "export", failed)
    with pytest.raises(RuntimeError, match="Disk full"):
        service.export(
            session, tmp_path / "video.mp4", "nvidia", CancellationToken(), lambda *_: None
        )
    assert calls == ["nvidia"]


def test_encoder_flush_failure_never_reaches_completion(qapp, sample_video, tmp_path, monkeypatch):
    from dataclasses import replace

    from dg_fps.presentation.video_encoder import add_video_stream

    service, session = session_for(sample_video, tmp_path / "reports")
    output = tmp_path / "video.mp4"
    output.write_bytes(b"previous export")

    def fail_flush(container, **kwargs):
        selection = add_video_stream(container, **kwargs)

        class Stream:
            def encode(self, frame=None):
                if frame is None:
                    raise av.error.ExternalError(1, "Encoder flush failed")
                return selection.stream.encode(frame)

        return replace(selection, stream=Stream())

    monkeypatch.setattr("dg_fps.presentation.cadence_video.add_video_stream", fail_flush)
    progress = []
    with pytest.raises(av.error.FFmpegError, match="Encoder flush failed"):
        service.export(session, output, "cpu", CancellationToken(), lambda n, _: progress.append(n))
    assert output.read_bytes() == b"previous export" and 100 not in progress


def test_running_job_cannot_emit_one_hundred_before_failure(qtbot):
    manager = JobManager()
    values, failed = [], []
    manager.job_changed.connect(lambda record: values.append(record.progress))
    manager.job_failed.connect(lambda *args: failed.append(args))

    def task(token, report):
        report(100, "Render complete")
        raise OSError("Final write failed")

    manager.submit("Export", task)
    qtbot.waitUntil(lambda: bool(failed), timeout=5000)
    assert 99 in values and 100 not in values
    manager.shutdown(wait=True)


def test_worker_returns_committed_result_despite_late_cancellation(qtbot):
    manager = JobManager()
    completed, cancelled = [], []
    manager.job_completed.connect(lambda *args: completed.append(args))
    manager.job_cancelled.connect(cancelled.append)

    def task(token, report):
        token.cancel()  # Cancellation races the filesystem commit.
        token.mark_committed()
        report(100, "Saved")
        return "verified file"

    job = manager.submit("Export", task)
    qtbot.waitUntil(lambda: bool(completed), timeout=5000)
    assert completed[0] == (job, "verified file") and not cancelled
    assert manager.record(job).progress == 100
    manager.shutdown(wait=True)
