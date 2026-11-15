"""Replay immutable pair evidence through old/new scope policies; never rewrites projects."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

from dg_fps.analyzers.cadence import _mark_scope_changes, _summarize_decoded_runs
from dg_fps.media.timestamp_index import TimestampIndex
from dg_fps.presentation.content_targets import ContentReference
from dg_fps.presentation.second_timeline import build_second_timeline
from dg_fps.projects import result_from_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("scope_baseline", args.baseline)
    assert spec and spec.loader
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    comparisons = []
    for report in args.reports:
        llm = json.loads(report.read_text("utf-8"))
        source = Path(llm["provenance"]["analysis_file"])
        data = source.read_bytes()
        document = json.loads(data)
        result = result_from_document(document, Path(document["source"]["path"]))
        raw = []
        scope_keys = {
            "scope_policy", "scope_cell_count", "scope_warning", "scope_confirmation",
            "reference_region_count", "cadence_witness", "raw_local_visual_advance",
        }
        for sample in result.samples:
            params = sample.flow_parameters or {}
            # Reconstruct only the old scope layer's changes, retaining all pair evidence.
            state = sample.signal_state
            if state == "partial_hold":
                assert params.get("scope_warning") == (
                    "persistent_local_only_motion_after_scene_motion")
                state = "observable"
            raw.append(replace(
                sample, signal_state=state, cadence_repeated=None,
                flow_parameters={k: v for k, v in params.items() if k not in scope_keys},
            ))
        old, new = baseline._mark_scope_changes(raw), _mark_scope_changes(raw)
        assert [(s.signal_state, s.presentation_repeated) for s in old] == [
            (s.signal_state, s.presentation_repeated) for s in result.samples
        ], "Stored decisions do not match this scope baseline"
        for a, b in zip(raw, new, strict=True):
            for key in ("frame_index", "timestamp_seconds", "pts", "time_base", "repeated",
                        "similarity_to_previous", "flow_support_ratio", "flow_confidence",
                        "flow_magnitude_px", "mean_absolute_difference", "timestamp_valid"):
                assert getattr(a, key) == getattr(b, key), key
        old_summary = _summarize_decoded_runs(old, result.summary.container_fps)
        new_summary = _summarize_decoded_runs(new, result.summary.container_fps)
        bounds = {s["segment"]: tuple(s["source_seconds"]) for s in llm["segments"]}
        references = {
            s["segment"]: ContentReference(
                s["references"]["effective_presentation"]["target_fps"], "manual", "validation",
            ) for s in llm["segments"]
        }
        seconds = build_second_timeline(
            tuple(new), TimestampIndex([]), references, result.summary.container_fps,
            range_bounds=bounds,
        )
        row = {
            "source": document["source"]["filename"], "frames": len(raw),
            "old_states": dict(Counter(s.signal_state for s in old)),
            "new_states": dict(Counter(s.signal_state for s in new)),
            "old_summary": asdict(old_summary), "new_summary": asdict(new_summary),
            "changed_scene_decisions": sum(
                (a.signal_state, a.presentation_repeated)
                != (b.signal_state, b.presentation_repeated)
                for a, b in zip(old, new, strict=True)),
            "raw_pair_evidence_unchanged": True,
            "input_unchanged": data == source.read_bytes(),
            "input_sha256": hashlib.sha256(data).hexdigest(),
            "per_second": {label: [s.to_dict() for s in rows] for label, rows in seconds.items()},
            "limitation": (
                "Classification replay; not a fresh decode or ground-truth FPS validation"
            ),
        }
        comparisons.append(row)
        print(row["source"], row["old_states"], "->", row["new_states"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(comparisons, indent=2, ensure_ascii=False), "utf-8")


if __name__ == "__main__":
    main()
