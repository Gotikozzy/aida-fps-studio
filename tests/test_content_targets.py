from __future__ import annotations

from fractions import Fraction
from types import SimpleNamespace

import pytest

from dg_fps.analyzers.cadence import CadenceSample
from dg_fps.presentation.content_targets import (
    ContentReference,
    content_references,
    nearby_target,
    reference_state,
    resolve_references,
)


def observations(capture=60, sections=((6, 30, "observable"),)):
    samples = []
    for duration, content, state in sections:
        start = len(samples)
        rate = Fraction(str(content)) / Fraction(str(capture))
        for offset in range(round(capture * duration)):
            frame = start + offset
            previous = ((offset - 1) * rate.numerator) // rate.denominator
            current = (offset * rate.numerator) // rate.denominator
            samples.append(
                CadenceSample(
                    "A",
                    frame,
                    frame / capture,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    current == previous,
                    signal_state=state,
                )
            )
    return SimpleNamespace(samples=tuple(samples), segment_summaries={"A": None})


@pytest.mark.parametrize(
    "fps,capture,target",
    [
        (26.99, 60, None),
        (27, 60, 30),
        (29.8, 60, 30),
        (30, 60, 30),
        (36.99, 60, None),
        (37, 60, 40),
        (40, 60, 40),
        (56.99, 60, None),
        (57, 60, 60),
        (59.94, 59.94, 60),
        (61, 120, None),
        (62, 120, None),
        (64.99, 120, None),
        (65, 120, 120),
        (90, 120, 120),
        (119.88, 120, 120),
        (70, 60, None),
        (None, 60, None),
        (float("nan"), 60, None),
    ],
)
def test_reference_bands_do_not_round_measurements(fps, capture, target):
    assert nearby_target(fps, capture) == target


@pytest.mark.parametrize(
    "capture,content,expected",
    [
        (60, 30, 30),
        (59.94, 29.97, 30),
        (60, 40, 40),
        (60, 60, 60),
        (120, 61, 60),
        (120, 62, None),
        (120, 90, 120),
        (120, 120, 120),
    ],
)
def test_sustained_cadence_selects_content_reference(capture, content, expected):
    result = observations(capture, ((6, content, "observable"),))
    original = tuple(result.samples)
    reference = content_references(result)["A"]
    assert reference.target_fps == expected
    assert result.samples == original
    assert reference.origin == "inferred"


def test_capture_sixty_content_thirty_is_near_thirty():
    reference = content_references(observations())["A"]
    assert reference.target_fps == 30
    assert reference_state(29.8, reference, 60) == "near_reference"
    manual = ContentReference(60, "manual", "user_reference")
    assert reference_state(29.8, manual, 60) == "below_reference"


def test_black_and_holds_cannot_vote_for_a_target():
    result = observations(sections=((6, 60, "dark_unobservable"), (6, 30, "observable")))
    assert content_references(result)["A"].target_fps == 30
    assert (
        content_references(observations(sections=((6, 0, "observable"),)))["A"].target_fps is None
    )


def test_sustained_second_mode_is_ambiguous_instead_of_lowering_reference():
    result = observations(sections=((6, 60, "observable"), (6, 30, "observable")))
    reference = content_references(result)["A"]
    assert reference.target_fps is None and reference.status == "mixed_modes"
    assert reference.candidates == (30, 60)


def test_short_clip_and_disconnected_bursts_do_not_establish_reference():
    assert (
        content_references(observations(sections=((1, 30, "observable"),)))["A"].target_fps is None
    )
    bursts = tuple(
        (1, 30, "observable") if i % 2 else (1, 0, "dark_unobservable") for i in range(10)
    )
    assert content_references(observations(sections=bursts))["A"].target_fps is None


def test_manual_override_and_capture_limit_are_explicit():
    automatic = content_references(observations())
    selected = resolve_references(automatic, 60, {"A": 120})
    assert selected["A"].origin == "manual"
    assert reference_state(30, selected["A"], 60) == "capture_limited"
    assert automatic["A"].target_fps == 30
    assert resolve_references(automatic, 60, {"A": None}) == automatic


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_manual_reference_rejected(value):
    with pytest.raises(ValueError):
        resolve_references(content_references(observations()), value, {})


def test_ui_target_changes_preserve_analysis_and_translate(
    qtbot, sample_video, tmp_path, monkeypatch
):
    import json

    from dg_fps.ui.main_window import FPSWindow

    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language="pt")
    qtbot.addWidget(window)
    window.open_source(sample_video)
    qtbot.waitUntil(lambda: window.timeline.frame_count == 12, timeout=15000)
    window.panel.mark_in(0, 0)
    window.panel.mark_out(11, 11 / 30)
    window.panel._add_range()
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window.panel.request_analysis()
    qtbot.waitUntil(lambda: window.session is not None, timeout=20000)
    session = window.session
    original = session.reports.analysis_json.read_bytes()
    window.content_target.combo.setCurrentIndex(window.content_target.combo.findData(30.0))
    assert session.reports.analysis_json.read_bytes() == original
    path = session.reports.project_directory / "content_reference.json"
    assert json.loads(path.read_text("utf-8"))["segments"]["Trecho 1"]["origin"] == "manual"
    window.language_box.setCurrentIndex(window.language_box.findData("en"))
    assert "Content references (display)" in window.panel.summary_text
    assert "inferida" not in window.panel.summary_text
    assert session.reports.analysis_json.read_bytes() == original
    window.close()


def test_export_records_frozen_reference_without_changing_measurements(
    qapp, sample_video, tmp_path
):
    import json

    from test_standalone import session_for

    from dg_fps.jobs.cancellation import CancellationToken
    from dg_fps.presentation.cadence_video import CadenceVideoExporter

    service, session = session_for(sample_video, tmp_path / "reports")
    measured = session.analysis
    references = {
        label: ContentReference(30, "manual", "user_reference")
        for label in measured.segment_summaries
    }
    exporter = CadenceVideoExporter("en", references)
    references.clear()
    assert exporter.references and all(
        item.target_fps == 30 for item in exporter.references.values()
    )
    service.export(
        session,
        tmp_path / "reference.mp4",
        "cpu",
        CancellationToken(),
        lambda *_: None,
        language="en",
        references=exporter.references,
    )
    mapping = json.loads(next(tmp_path.glob("reference_*_assets/frames.json")).read_text("utf-8"))
    assert all(
        item["target_fps"] == 30 and item["origin"] == "manual"
        for item in mapping["content_references"].values()
    )
    assert session.analysis == measured and len(mapping["frames"]) == 8
