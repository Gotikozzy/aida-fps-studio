from __future__ import annotations

from PySide6.QtCore import QObject, QThreadPool

from dg_fps.jobs.job_manager import JobManager

_SHARED_POOL: QThreadPool | None = None


def _gpu_pool() -> QThreadPool:
    # Controllers are created on the UI thread; the pool outlives them.
    global _SHARED_POOL
    if _SHARED_POOL is None:
        _SHARED_POOL = QThreadPool()
        _SHARED_POOL.setMaxThreadCount(1)
    return _SHARED_POOL


class GPUQueue(JobManager):
    """One GPU task at a time across all controllers."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent, pool=_gpu_pool())
