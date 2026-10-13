"""Exact shared frames imply connected source groups and contaminated splits."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_visual_leakage_graph_v32 import (
    inspect_visual_overlap_graph,
)
from hex_cortex.memory.cortex_visual_leakage_cli_v32 import main
from test_cortex_active_world_integrity_v31 import _build_fixture


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _row(i: int, split: str, current: str, nxt: str) -> dict:
    return {
        "sample_id": f"e{i}", "split": split,
        "current_image_hash": _h(current),
        "next_image_hash": _h(nxt),
        "current_image_ref": "do_not_disclose_source_name.png",
    }


def test_graph_detects_direct_and_transitive_split_contamination() -> None:
    rows = [
        _row(0, "train", "a", "b"),
        _row(1, "train", "b", "c"),
        _row(2, "validation", "c", "d"),
        _row(3, "test", "e", "f"),
        _row(4, "test", "g", "h"),
    ]
    result = inspect_visual_overlap_graph(rows, approved=True)
    assert result["status"] == "visual_leakage_detected"
    assert result["image_connected_component_count"] == 3
    assert result["largest_component_size"] == 3
    assert result["components_spanning_splits"] == 1
    assert result["exact_cross_split_image_count"] == 1
    assert result["records_in_cross_split_components"] == 3
    assert result["overlap_images"][0]["line_numbers"] == [2, 3]
    assert result["overlap_images"][0]["splits"] == ["train", "validation"]
    assert result["cross_split_components"][0]["line_numbers"] == [1, 2, 3]
    assert result["retroactive_resplit_valid_for_current_checkpoint"] is False
    assert result["requires_new_independent_holdout"] is True
    assert "do_not_disclose_source_name" not in json.dumps(result)
    assert _h("c") not in json.dumps(result)
    assert result["files_written"] is False


def test_graph_with_disjoint_images_cannot_certify_real_world() -> None:
    rows = [
        _row(0, "train", "a", "b"),
        _row(1, "validation", "c", "d"),
        _row(2, "test", "e", "f"),
    ]
    result = inspect_visual_overlap_graph(rows, approved=True)
    assert result["status"] == "no_exact_image_overlap_detected"
    assert result["existing_split_is_image_disjoint"] is True
    assert result["original_episode_or_environment_provenance_attested"] is False
    assert result["retroactive_resplit_valid_for_current_checkpoint"] is False
    assert result["new_source_grouped_split_structurally_possible"] is True


def test_connected_group_with_only_two_components_needs_new_sources() -> None:
    rows = [
        _row(0, "train", "a", "b"),
        _row(1, "validation", "b", "c"),
        _row(2, "test", "d", "e"),
    ]
    result = inspect_visual_overlap_graph(rows, approved=True)
    assert result["image_connected_component_count"] == 2
    assert result["new_source_grouped_split_structurally_possible"] is False


@pytest.mark.parametrize("rows,error", [
    ([{"sample_id": "a", "split": "test",
       "current_image_hash": "bad", "next_image_hash": _h("b")}],
     "visual_graph_invalid_sha256_image_hash"),
    ([{"sample_id": "a", "split": "other",
       "current_image_hash": _h("a"), "next_image_hash": _h("b")}],
     "visual_graph_invalid_split"),
    ([{"sample_id": "a", "split": "train",
       "current_image_hash": _h("a"), "next_image_hash": _h("b")},
      {"sample_id": "a", "split": "test",
       "current_image_hash": _h("c"), "next_image_hash": _h("d")}],
     "visual_graph_invalid_or_duplicate_sample_id"),
])
def test_fail_closed_on_bad_input(rows: list[dict], error: str) -> None:
    with pytest.raises(ValueError, match=error):
        inspect_visual_overlap_graph(rows, approved=True)


def test_observation_only_requires_approval() -> None:
    r = inspect_visual_overlap_graph([_row(0, "train", "a", "b")])
    assert r["status"] == "blocked"
    assert r["records_inspected"] == 0


def test_cli_dry_run_and_real_read_without_mutation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    state = _build_fixture(tmp_path)
    all_records = [
        json.loads(line) for line in
        (state / "transitions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    shared = all_records[0]["next_image_hash"]
    all_records[4]["current_image_hash"] = shared
    for row in all_records:
        row["record_hash"] = hashlib.sha256(json.dumps(
            {k: v for k, v in row.items() if k not in ("record_hash", "next_action")},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
    source = state / "transitions.jsonl"
    source.write_text(
        "".join(json.dumps(row) + "\n" for row in all_records),
        encoding="utf-8",
    )
    from hex_cortex.memory.cortex_observed_transition_dataset import (
        build_transition_dataset_manifest,
    )
    manifest = build_transition_dataset_manifest(
        all_records, min_train=2, min_validation=1,
    )
    (state / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8",
    )
    original = source.read_bytes()
    args = ["--project-root", str(tmp_path)]
    assert main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main(args) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
    assert main([*args, "--approve-read"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "visual_leakage_detected"
    assert report["artifact_chain_verified_before_graph"] is True
    assert report["exact_cross_split_image_count"] == 1
    assert report["overlap_images"][0]["line_numbers"] == [1, 5]
    assert source.read_bytes() == original
    assert report["files_written"] is False


def test_copied_filename_not_used_as_independent_source_proof() -> None:
    a = _row(0, "train", "same-frame", "different-next")
    b = deepcopy(a)
    b["sample_id"] = "e1"
    b["split"] = "test"
    b["current_image_ref"] = "renamed.png"
    report = inspect_visual_overlap_graph([a, b], approved=True)
    assert report["status"] == "visual_leakage_detected"
    assert report["exact_cross_split_image_count"] == 2
