"""V42 end-to-end existing CanonicalSpine with verified V41 pixel fixtures.

All CI vision masks are injected deterministic fixtures, not actual MobileSAM
execution or third-party truth labels.
"""
from __future__ import annotations

import json

import pytest

from hex_cortex.memory.cortex_visual_to_canonical_spine_cli_v42 import main
from hex_cortex.memory.cortex_visual_to_canonical_spine_v42 import (
    integrate_v41_with_canonical_spine_v42,
)
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore
from test_cortex_object_memory_staging_v41 import _valid_inspection

_LEDGER = "receipts/v42_canonical_spine/visual_predictions.jsonl"


def _prepare(root):
    pytest.importorskip("PIL.Image")
    _valid_inspection(root)


def test_v42_no_permission_no_file_or_model(tmp_path):
    result = integrate_v41_with_canonical_spine_v42(project_root=tmp_path)
    assert result["status"] == "blocked"
    assert result["files_read"] is False
    assert result["files_written"] is False
    assert not list(tmp_path.iterdir())


def test_v42_read_only_stages_real_canonical_events_without_persistence(tmp_path):
    _prepare(tmp_path)
    result = integrate_v41_with_canonical_spine_v42(
        project_root=tmp_path, approved_read=True,
    )
    assert result["status"] == "canonical_spine_visual_predictions_staged_in_memory"
    assert result["candidate_count"] == 3
    assert result["new_event_count"] == 3
    assert result["spine_integrity_ok"] is True
    assert result["canonical_event_ids"] == []
    assert result["human_reference_mask_iou_available"] is False
    assert result["future_same_object_tracking_attested"] is False
    assert result["world_model_prediction_compared_to_baseline"] is False
    assert result["files_written"] is False
    assert not (tmp_path / _LEDGER).exists()


def test_v42_explicit_persist_real_hash_chain_and_idempotent_retry(tmp_path):
    _prepare(tmp_path)
    denied = integrate_v41_with_canonical_spine_v42(
        project_root=tmp_path, approved_read=True, persist=True,
    )
    assert denied["status"] == "blocked"
    assert denied["reason"] == "v42_write_approval_required"
    assert not (tmp_path / _LEDGER).exists()

    approved = integrate_v41_with_canonical_spine_v42(
        project_root=tmp_path, approved_read=True, persist=True, approved_write=True,
    )
    assert approved["status"] == "canonical_spine_visual_predictions_persisted"
    assert approved["new_event_count"] == 3
    assert approved["files_written"] is True
    assert len(approved["canonical_event_ids"]) == 3
    spine = CanonicalSpineJsonlStore(tmp_path / _LEDGER).load()
    assert spine.verify_integrity().ok
    assert len(spine.events) == 3
    assert all(e.event_type == "vision.object_mask_predicted.v42" for e in spine.events)
    assert all(e.confidence is None for e in spine.events)
    assert all(e.payload["independent_human_iou"] is None for e in spine.events)
    assert all(e.payload["eligible_for_skill_or_model_promotion"] is False for e in spine.events)

    again = integrate_v41_with_canonical_spine_v42(
        project_root=tmp_path, approved_read=True, persist=True, approved_write=True,
    )
    assert again["new_event_count"] == 0
    assert again["idempotent_existing_event_count"] == 3
    assert again["files_written"] is False
    assert len(CanonicalSpineJsonlStore(tmp_path / _LEDGER).load().events) == 3


def test_v42_forged_spine_event_payload_denied(tmp_path):
    _prepare(tmp_path)
    integrate_v41_with_canonical_spine_v42(
        project_root=tmp_path, approved_read=True, persist=True, approved_write=True,
    )
    path = tmp_path / _LEDGER
    lines = path.read_text(encoding="utf-8").splitlines()
    item = json.loads(lines[0])
    item["payload"]["eligible_for_skill_or_model_promotion"] = True
    lines[0] = json.dumps(item)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid canonical spine|integrity"):
        integrate_v41_with_canonical_spine_v42(
            project_root=tmp_path, approved_read=True, persist=True, approved_write=True,
        )


def test_v42_refuses_tampered_mask_from_v41(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    output, _ = _valid_inspection(tmp_path)
    png = tmp_path / output["records"][0]["objects"][0]["mask_png"]
    with Image.open(png) as src:
        image = src.convert("L")
    image.putpixel((3, 3), 0)
    image.save(png)
    with pytest.raises(ValueError, match="v41_prediction_pixel_integrity_failed"):
        integrate_v41_with_canonical_spine_v42(
            project_root=tmp_path, approved_read=True, persist=True, approved_write=True,
        )
    assert not (tmp_path / _LEDGER).exists()


def test_v42_dry_run_cli_never_reads_source(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["spine_event_created"] is False
    assert main(["--project-root", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "v42_read_approval_required"
    assert not list(tmp_path.iterdir())
