import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from test_content_targets import observations

from dg_fps.analyzers.cadence import (
    CadenceParameters,
    CadenceSummary,
    content_cadence_readings,
)
from dg_fps.media.timestamp_index import FrameTimestamp, TimestampIndex
from dg_fps.presentation.content_targets import ContentReference, content_references
from dg_fps.presentation.frame_timeline import build_frame_timeline
from dg_fps.presentation.second_timeline import build_second_timeline
from dg_fps.reports.llm_report import write_llm_report


def fixture():
    result = observations(120, ((6, 40, "observable"),))
    result.samples = tuple(
        replace(
            s,
            cadence_repeated=s.repeated,
            repeated=False if s.frame_index % 15 == 1 else s.repeated,
        )
        for s in result.samples
    )
    index = TimestampIndex(
        [
            FrameTimestamp(
                s.frame_index,
                0,
                s.frame_index,
                None,
                "1/120",
                s.timestamp_seconds,
                False,
                None,
                False,
            )
            for s in result.samples
        ]
    )
    result.summary = CadenceSummary(720, 288, 432, 0.6, 120, 48, 0, 6, content_fps=40)
    result.segment_summaries = {"A": result.summary}
    result.parameters = CadenceParameters()
    result.source_path = Path("capture120.mp4")
    result.analyzer_id, result.analyzer_version = "frame_cadence", "0.6.0"
    result.limitations, result.events = (), ()
    return result, index


def test_raw_local_changes_do_not_corrupt_any_public_cadence_consumer():
    result, index = fixture()
    before = [asdict(s) for s in result.samples]
    refs = content_references(result)
    assert refs["A"].target_fps == 40
    readings = content_cadence_readings(result.samples)
    assert all(
        r.content_fps == pytest.approx(40) for r in readings.values() if r.content_fps is not None
    )
    frames = build_frame_timeline(result, refs)["A"]
    assert all(p.measured_fps == pytest.approx(40) for p in frames if p.measured_fps is not None)
    assert all(
        p.frame_time_ms == pytest.approx(25) for p in frames if p.frame_time_origin == "measured"
    )
    seconds = build_second_timeline(result.samples, index, refs, 120)["A"]
    assert all(s.measured_fps == pytest.approx(40) for s in seconds if s.measured_fps is not None)
    assert [asdict(s) for s in result.samples] == before


def test_real_irregular_periods_are_preserved_with_40_updates_per_second():
    result, _ = fixture()
    result.samples = tuple(
        replace(s, repeated=s.frame_index % 6 not in (0, 2), cadence_repeated=None)
        for s in result.samples
    )
    refs = {"A": ContentReference(40, "manual", "user_reference")}
    times = {
        round(p.frame_time_ms, 3)
        for p in build_frame_timeline(result, refs)["A"]
        if p.frame_time_origin == "measured"
    }
    assert times == {16.667, 33.333}


def test_llm_report_has_measurements_decisions_reference_and_no_sample_mutation(tmp_path):
    result, index = fixture()
    before = [asdict(s) for s in result.samples]
    analysis = tmp_path / "analysis.json"
    analysis.write_text('{"evidence":"original"}', encoding="utf-8")
    output = tmp_path / "llm_report.json"
    report = write_llm_report(result, index, output, analysis)
    assert json.loads(output.read_text("utf-8")) == json.loads(json.dumps(report))
    segment = report["segments"][0]
    assert segment["references"]["automatic_inference"]["target_fps"] == 40
    assert segment["closed_scene_update_periods_ms"]["median"] == pytest.approx(25)
    assert segment["closed_scene_update_periods_ms"]["p99"] == pytest.approx(25)
    assert segment["decisions"]["local_changes_rejected_as_scene_updates"] > 0
    assert segment["measurement"]["qualified_second_fps_min"] == pytest.approx(40)
    assert report["llm_reporting_guidance"]["suggested_max_words"] == 120
    assert [asdict(s) for s in result.samples] == before
    assert analysis.read_text("utf-8") == '{"evidence":"original"}'
    schema = json.loads(Path("schemas/llm_report.schema.json").read_text("utf-8"))
    assert set(schema["required"]) <= report.keys()
    assert (
        segment["measurement"]["summary"]["complete_period_count"]
        == (segment["closed_scene_update_periods_ms"]["count"])
    )
    manual = {"A": ContentReference(60, "manual", "user_reference")}
    changed = write_llm_report(result, index, output, analysis, manual)
    assert changed["segments"][0]["references"]["effective_presentation"]["origin"] == "manual"
    assert changed["segments"][0]["measurement"] == segment["measurement"]


def test_llm_unknown_has_null_measurement_and_separate_display_reference(tmp_path):
    result, index = fixture()
    result.samples = tuple(replace(s, signal_state="dark_unobservable") for s in result.samples)
    path = tmp_path / "analysis.json"
    path.write_text("{}", encoding="utf-8")
    report = write_llm_report(result, index, tmp_path / "llm_report.json", path)
    segment = report["segments"][0]
    assert segment["measurement"]["observable_coverage"] == 0
    assert segment["closed_scene_update_periods_ms"]["median"] is None
    assert all(
        s["measured_fps"] is None and s["displayed_fps"] == 120 for s in segment["per_second"]
    )


def test_reused_automatic_references_preserve_report_with_manual_override(tmp_path, monkeypatch):
    result, index = fixture()
    analysis = tmp_path / "analysis.json"
    analysis.write_text("{}", encoding="utf-8")
    automatic = content_references(result)
    manual = {"A": ContentReference(60, "manual", "user_reference")}
    original = write_llm_report(result, index, tmp_path / "before.json", analysis, manual)

    def unexpected(*args):
        pytest.fail("Automatic references were already calculated for this immutable session")

    monkeypatch.setattr("dg_fps.reports.llm_report.content_references", unexpected)
    reused = write_llm_report(
        result,
        index,
        tmp_path / "after.json",
        analysis,
        manual,
        automatic_references=automatic,
    )
    original.pop("generated_at", None)
    reused.pop("generated_at", None)
    assert original == reused
