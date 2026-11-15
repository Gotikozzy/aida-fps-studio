from __future__ import annotations

from threading import Event, Lock


class JobCancelled(Exception):
    """Internal control-flow exception raised when a job is cancelled."""


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._committed = False

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._event.is_set() and not self._committed

    def cancel(self) -> bool:
        with self._lock:
            if self._committed:
                return False
            self._event.set()
            return True

    def mark_committed(self) -> None:
        """An already published, verified artifact is a completed result."""
        with self._lock:
            self._committed = True

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise JobCancelled
