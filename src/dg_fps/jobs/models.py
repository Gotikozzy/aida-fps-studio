from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from dg_fps.core.enums import JobStatus


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class JobRecord:
    id: str
    name: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    message: str = ""
    error: str | None = None
    traceback: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
