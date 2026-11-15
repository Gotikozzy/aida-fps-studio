from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from dg_fps.core.enums import JobStatus
from dg_fps.jobs.cancellation import CancellationToken
from dg_fps.jobs.models import JobRecord
from dg_fps.jobs.worker import JobTask, JobWorker

LOGGER = logging.getLogger(__name__)


class JobManager(QObject):
    job_changed = Signal(object)
    job_completed = Signal(str, object)
    job_failed = Signal(str, str)
    job_cancelled = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        max_threads: int | None = None,
        pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent)
        self._pool = pool if pool is not None else QThreadPool(self)
        if max_threads is not None:
            self._pool.setMaxThreadCount(max_threads)
        self._records: dict[str, JobRecord] = {}
        self._tokens: dict[str, CancellationToken] = {}
        self._workers: dict[str, JobWorker] = {}
        self._shutting_down = False

    def submit(self, name: str, task: JobTask) -> str:
        if self._shutting_down:
            raise RuntimeError("O gerenciador de trabalhos está sendo encerrado")
        job_id = str(uuid4())
        record = JobRecord(id=job_id, name=name)
        token = CancellationToken()
        worker = JobWorker(job_id, task, token)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.completed.connect(self._on_completed)
        worker.signals.failed.connect(self._on_failed)
        worker.signals.cancelled.connect(self._on_cancelled)
        self._records[job_id] = record
        self._tokens[job_id] = token
        self._workers[job_id] = worker
        record.status = JobStatus.RUNNING
        record.started_at = datetime.now(UTC)
        self.job_changed.emit(record)
        self._pool.start(worker)
        return job_id

    def record(self, job_id: str) -> JobRecord:
        return self._records[job_id]

    def cancel(self, job_id: str) -> bool:
        token = self._tokens.get(job_id)
        record = self._records.get(job_id)
        if token is None or record is None or record.status != JobStatus.RUNNING:
            return False
        if not token.cancel():
            return False
        record.message = "Cancellation requested"
        self.job_changed.emit(record)
        return True

    def shutdown(self, *, wait: bool = False) -> None:
        self._shutting_down = True
        for token in self._tokens.values():
            token.cancel()
        if wait:
            self._pool.waitForDone()
            self._tokens.clear()
            self._workers.clear()

    @Slot(str, int, str)
    def _on_progress(self, job_id: str, progress: int, message: str) -> None:
        record = self._records[job_id]
        record.progress = max(0, min(99, progress))
        record.message = message
        self.job_changed.emit(record)

    @Slot(str, object)
    def _on_completed(self, job_id: str, result: object) -> None:
        record = self._records[job_id]
        record.status = JobStatus.COMPLETED
        record.progress = 100
        record.finished_at = datetime.now(UTC)
        self.job_changed.emit(record)
        self.job_completed.emit(job_id, result)
        self._release(job_id)

    @Slot(str, str, str)
    def _on_failed(self, job_id: str, error: str, traceback_text: str) -> None:
        record = self._records[job_id]
        record.status = JobStatus.FAILED
        record.error = error
        record.traceback = traceback_text
        LOGGER.error("Job '%s' failed: %s\n%s", record.name, error, traceback_text)
        record.finished_at = datetime.now(UTC)
        self.job_changed.emit(record)
        self.job_failed.emit(job_id, error)
        self._release(job_id)

    @Slot(str)
    def _on_cancelled(self, job_id: str) -> None:
        record = self._records[job_id]
        record.status = JobStatus.CANCELLED
        record.finished_at = datetime.now(UTC)
        self.job_changed.emit(record)
        self.job_cancelled.emit(job_id)
        self._release(job_id)

    def _release(self, job_id: str) -> None:
        self._tokens.pop(job_id, None)
        self._workers.pop(job_id, None)
