"""Bounded CPU lookahead; GPU operations stay on the consuming job thread."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Condition, Thread


@contextmanager
def cpu_lookahead[T](
    factory: Callable[[], Iterator[T]],
    *,
    check_cancelled: Callable[[], None],
    size_bytes: Callable[[T], int],
    max_items: int = 2,
    max_bytes: int = 64 * 1024 * 1024,
) -> Iterator[Iterator[T]]:
    """Preserve order/errors and join the producer on every exit.

    Bounds apply to queued items. One oversized item may occupy an empty queue;
    the producer and consumer can each additionally own one item in flight.
    The producer creates, advances and closes its iterator on the same thread.
    """
    if max_items < 1 or max_bytes < 1:
        raise ValueError("Lookahead limits must be positive")
    condition = Condition()
    pending: deque[tuple[T, int]] = deque()
    queued_bytes = 0
    stopped = False
    finished = False
    failure: BaseException | None = None

    def produce() -> None:
        nonlocal queued_bytes, finished, failure
        source = None
        try:
            source = factory()
            while True:
                with condition:
                    while not stopped and len(pending) >= max_items:
                        condition.wait()
                    if stopped:
                        return
                check_cancelled()
                try:
                    value = next(source)
                except StopIteration:
                    return
                weight = max(0, size_bytes(value))
                with condition:
                    while not stopped and pending and queued_bytes + weight > max_bytes:
                        condition.wait()
                    if stopped:
                        return
                    pending.append((value, weight))
                    queued_bytes += weight
                    condition.notify_all()
        except BaseException as exc:
            failure = exc
        finally:
            try:
                if source is not None and (close := getattr(source, "close", None)) is not None:
                    close()
            except BaseException as exc:
                if failure is None:
                    failure = exc
            with condition:
                finished = True
                condition.notify_all()

    def consume() -> Iterator[T]:
        nonlocal queued_bytes
        while True:
            check_cancelled()
            with condition:
                while not pending and not finished:
                    condition.wait(timeout=0.05)
                    check_cancelled()
                if not pending:
                    if failure is not None:
                        raise failure
                    return
                value, weight = pending.popleft()
                queued_bytes -= weight
                condition.notify_all()
            yield value

    producer = Thread(target=produce, name="aida-cpu-lookahead")
    producer.start()
    try:
        yield consume()
    finally:
        with condition:
            stopped = True
            pending.clear()
            condition.notify_all()
        producer.join()
