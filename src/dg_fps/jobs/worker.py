from __future__ import annotations

import traceback
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from dg_fps.jobs.cancellation import CancellationToken, JobCancelled

ProgressReporter = Callable[[int, str], None]
JobTask = Callable[[CancellationToken, ProgressReporter], object]


class WorkerSignals(QObject):
    progress = Signal(str, int, str)
    completed = Signal(str, object)
    failed = Signal(str, str, str)
    cancelled = Signal(str)


class JobWorker(QRunnable):
    def __init__(self, job_id: str, task: JobTask, token: CancellationToken) -> None:
        super().__init__()
        self.job_id = job_id
        self.task = task
        self.token = token
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.token.raise_if_cancelled()
            result = self.task(self.token, self._report)
            self.token.raise_if_cancelled()
        except JobCancelled:
            self.signals.cancelled.emit(self.job_id)
        except Exception as exc:
            self.signals.failed.emit(self.job_id, str(exc), traceback.format_exc())
        else:
            self.signals.completed.emit(self.job_id, result)

    def _report(self, progress: int, message: str = "") -> None:
        self.token.raise_if_cancelled()
        # Only a returned result can complete a job; rendering 100% is not a commit.
        normalized = max(0, min(99, progress))
        self.signals.progress.emit(self.job_id, normalized, message)
