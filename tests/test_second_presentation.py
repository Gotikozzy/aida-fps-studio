from __future__ import annotations

from dataclasses import asdict, replace

import pytest
from test_content_targets import observations

from dg_fps.jobs.cancellation import JobCancelled
from dg_fps.media.timestamp_index import FrameTimestamp, TimestampIndex
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.presentation.second_timeline import build_second_timeline, second_key, timecode


def timeline(result, target=60, capture=60):
    samples = result.samples
    index = TimestampIndex(
        [
            FrameTimestamp(
                s.frame_index,
                0,
                s.frame_index,
                None,
                "1/60000",
                s.timestamp_seconds,
                False,
                None,
                False,
            )
            for s in samples
        ]
    )
    refs = {s.segment: ContentReference(target, "manual", "user_reference") for s in samples}
    return build_second_timeline(samples, index, refs, capture)


@pytest.mark.parametrize(
    "capture,content",
    [(60, 60), (60, 30), (60, 40), (59.94, 29.97), (59.94, 59.94), (120, 60), (120, 120)],
)
def test_measured_seconds_are_based_on_period_durations(capture, content):
    result = observations(capture, ((4, content, "observable"),))
    before = [asdict(sample) for sample in result.samples]
    seconds = timeline(result, target=content, capture=capture)["A"]
    complete = [s for s in seconds if s.end_seconds - s.start_seconds > 0.9]
    assert len(complete) >= 3
    assert all(s.origin == "measured" for s in complete)
    assert all(s.measured_fps == pytest.approx(content, abs=0.6) for s in complete)
    assert [asdict(sample) for sample in result.samples] == before


def test_an_isolated_unknown_does_not_erase_the_entire_second():
    result = observations(sections=((3, 30, "observable"),))
    samples = list(result.samples)
    samples[40] = replace(samples[40], signal_state="uncertain_change")
    result.samples = tuple(samples)
    second = timeline(result, target=30)["A"][0]
    assert second.origin == "measured" and second.coverage >= 0.9
    assert second.measured_fps == pytest.approx(30)
    assert second.update_equivalents < 30  # The rejected gap was never filled as measured.


def test_unknown_seconds_use_explicit_reference_with_separate_audit():
    result = observations(sections=((3, 30, "observable"),))
    result.samples = tuple(
        replace(s, signal_state="uncertain_change") if 60 <= s.frame_index < 120 else s
        for s in result.samples
    )
    seconds = timeline(result)["A"]
    unknown = seconds[1]
    assert unknown.measured_fps is None and unknown.displayed_fps == 60
    assert unknown.origin == "reference" and unknown.coverage == 0
    assert seconds[2].measured_fps == pytest.approx(30)


def test_missing_reference_is_not_replaced_by_capture_rate():
    result = observations(sections=((2, 0, "dark_unobservable"),))
    seconds = timeline(result, target=None)["A"]
    assert all(s.measured_fps is None and s.displayed_fps is None for s in seconds)
    assert all(s.origin == "none" for s in seconds)


def test_confirmed_closed_hold_remains_in_the_measured_duration():
    result = observations(sections=((4, 60, "observable"),))
    result.samples = tuple(
        replace(s, repeated=True) if 60 <= s.frame_index < 120 else s for s in result.samples
    )
    seconds = timeline(result)["A"]
    assert seconds[1].origin == "measured"
    assert seconds[1].measured_fps < 2  # Do not discard this duration and show 60.


def test_unclosed_hold_is_not_extrapolated_from_prior_fast_updates():
    result = observations(sections=((3, 60, "observable"),))
    result.samples = tuple(
        replace(s, repeated=True) if s.frame_index >= 60 else s for s in result.samples
    )
    seconds = timeline(result)["A"]
    assert seconds[1].measured_fps is None and seconds[1].origin == "reference"
    assert seconds[1].open_hold_seconds > 0.9
    assert seconds[1].to_dict()["reason"] == "open_hold"


def test_period_contributions_are_conserved_across_second_boundaries():
    result = observations(sections=((3, 30, "observable"),))
    seconds = timeline(result, target=30)["A"]
    advances = [s for s in result.samples if not s.presentation_repeated and s.frame_index > 0]
    assert sum(s.update_equivalents for s in seconds) == pytest.approx(len(advances) - 1)
    assert sum(s.period_seconds for s in seconds) == pytest.approx(
        advances[-1].timestamp_seconds - advances[0].timestamp_seconds
    )


def test_different_ranges_do_not_share_periods_or_chart_time():
    result = observations(sections=((4, 30, "observable"),))
    result.samples = tuple(
        replace(s, segment="B") if s.frame_index >= 120 else s for s in result.samples
    )
    seconds = timeline(result)
    assert [s.second for s in seconds["A"]] == [0, 1]
    assert [s.second for s in seconds["B"]] == [2, 3]


def test_second_preparation_respects_cancellation():
    result = observations()
    index = TimestampIndex(
        [
            FrameTimestamp(
                s.frame_index,
                0,
                s.frame_index,
                None,
                "1/60",
                s.timestamp_seconds,
                False,
                None,
                False,
            )
            for s in result.samples
        ]
    )

    def cancelled():
        raise JobCancelled()

    with pytest.raises(JobCancelled):
        build_second_timeline(result.samples, index, {}, 60, cancelled)


def test_clock_labels_use_source_seconds_not_frame_count():
    assert second_key(147.65) == 147
    assert timecode(147.65) == "00:02:27"
    assert timecode(3671.2) == "01:01:11"
