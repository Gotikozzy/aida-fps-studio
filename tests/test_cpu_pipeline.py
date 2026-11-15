from __future__ import annotations

from threading import Event, get_ident
from threading import enumerate as threads

import pytest

from dg_fps.jobs.cancellation import CancellationToken, JobCancelled
from dg_fps.jobs.cpu_pipeline import cpu_lookahead


def test_order_and_producer_owns_iterator_cleanup():
    owner = []

    def source():
        owner.append(get_ident())
        try:
            yield from range(30)
        finally:
            owner.append(get_ident())

    with cpu_lookahead(
        source, check_cancelled=lambda: None, size_bytes=lambda _: 3, max_items=3, max_bytes=5
    ) as values:
        assert list(values) == list(range(30))
    assert owner[0] == owner[1] != get_ident()
    assert not any(t.name == "aida-cpu-lookahead" for t in threads())


def test_producer_error_preserves_preceding_items_and_closes():
    closed = Event()

    def source():
        try:
            yield 1
            yield 2
            raise ValueError("decode failed")
        finally:
            closed.set()

    with cpu_lookahead(source, check_cancelled=lambda: None, size_bytes=lambda _: 1) as values:
        assert next(values) == 1
        assert next(values) == 2
        with pytest.raises(ValueError, match="decode failed"):
            next(values)
    assert closed.is_set()


@pytest.mark.parametrize("cancel", [False, True])
def test_consumer_failure_or_cancellation_unblocks_full_producer(cancel):
    token = CancellationToken()
    full = Event()
    closed = Event()

    def source():
        try:
            for number in range(20):
                if number == 2:
                    full.set()
                yield number
        finally:
            closed.set()

    with pytest.raises(JobCancelled if cancel else RuntimeError), cpu_lookahead(
        source,
        check_cancelled=token.raise_if_cancelled,
        size_bytes=lambda _: 100,
        max_items=2,
        max_bytes=100,
    ) as values:
        assert next(values) == 0
        assert full.wait(5)
        if cancel:
            token.cancel()
            next(values)
        else:
            raise RuntimeError("encoder failed")
    assert closed.is_set()
    assert not any(t.name == "aida-cpu-lookahead" for t in threads())


def test_byte_budget_applies_even_before_item_count_is_full():
    produced = []
    blocked = Event()

    def source():
        for number in range(10):
            produced.append(number)
            if number == 1:
                blocked.set()
            yield number

    with cpu_lookahead(
        source, check_cancelled=lambda: None, size_bytes=lambda _: 8, max_items=10, max_bytes=10
    ) as values:
        assert blocked.wait(5)
        # One queued and one in-flight item; a third cannot be requested yet.
        assert produced == [0, 1]
        assert list(values) == list(range(10))
