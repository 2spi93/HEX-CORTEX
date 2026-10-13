"""V43 actual integrated Router/Workspace/Clock/CanonicalSpine circuit tests."""
from __future__ import annotations

import json

import pytest

from hex_cortex.memory.cortex_visual_cognitive_circuit_cli_v43 import main
from hex_cortex.memory.cortex_visual_cognitive_circuit_v43 import (
    run_visual_cognitive_circuit_v43,
)
from hex_cortex.memory.cortex_visual_to_canonical_spine_v42 import (
    integrate_v41_with_canonical_spine_v42,
)
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore
from test_cortex_object_memory_staging_v41 import _valid_inspection

_LEDGER = "receipts/v42_canonical_spine/visual_predictions.jsonl"


def _ready(root):
    pytest.importorskip("PIL.Image")
    _valid_inspection(root)
    result = integrate_v41_with_canonical_spine_v42(
        project_root=root, approved_read=True, persist=True, approved_write=True,
    )
    assert result["status"] == "canonical_spine_visual_predictions_persisted"


def test_no_approval_denies_before_any_io(tmp_path):
    result = run_visual_cognitive_circuit_v43(project_root=tmp_path)
    assert result["status"] == "blocked"
    assert result["files_read"] is False
    assert not list(tmp_path.iterdir())


def test_actual_cognitive_circuit_in_memory_from_verifiable_mask_pixels(tmp_path):
    _ready(tmp_path)
    before = (tmp_path / _LEDGER).read_bytes()
    result = run_visual_cognitive_circuit_v43(
        project_root=tmp_path, approved_read=True, approved_execution=True,
    )
    assert result["status"] == "visual_cognitive_circuit_verified_in_memory"
    assert result["source_mask_count"] == 3
    assert result["verified_cell_count"] == 1
    assert result["selected_cells"] == ["visual_evidence"]
    assert result["cognitive_spine_integrity"] is True
    assert len(result["real_source_v42_event_ids"]) == 3
    assert result["semantic_quality_independently_verified"] is False
    assert result["same_object_across_frames_verified"] is False
    assert result["world_model_improvement_attested"] is False
    assert result["model_used"] is False
    assert result["files_written"] is False
    assert (tmp_path / _LEDGER).read_bytes() == before


def test_persistence_requires_permission_and_creates_real_clock_events(tmp_path):
    _ready(tmp_path)
    denied = run_visual_cognitive_circuit_v43(
        project_root=tmp_path, approved_read=True, approved_execution=True,
        persist_circuit=True,
    )
    assert denied["reason"] == "v43_write_approval_required"
    spine_before = CanonicalSpineJsonlStore(tmp_path / _LEDGER).load()
    first_count = len(spine_before.events)
    done = run_visual_cognitive_circuit_v43(
        project_root=tmp_path, approved_read=True, approved_execution=True,
        persist_circuit=True, approved_write=True,
    )
    assert done["status"] == "visual_cognitive_circuit_events_persisted"
    assert done["files_written"] is True
    reloaded = CanonicalSpineJsonlStore(tmp_path / _LEDGER).load()
    assert reloaded.verify_integrity().ok
    assert len(reloaded.events) > first_count
    assert done["circuit_replay_events_written"] == len(reloaded.events) - first_count
    assert any(e.event_type == "clock.started" for e in reloaded.events)
    again = run_visual_cognitive_circuit_v43(
        project_root=tmp_path, approved_read=True, approved_execution=True,
        persist_circuit=True, approved_write=True,
    )
    assert again["status"] == "cognitive_circuit_task_already_recorded"
    assert again["files_written"] is False
    assert len(CanonicalSpineJsonlStore(tmp_path / _LEDGER).load().events) == len(reloaded.events)


def test_refuses_missing_real_v42_spine(tmp_path):
    pytest.importorskip("PIL.Image")
    _valid_inspection(tmp_path)
    with pytest.raises(ValueError, match="v43_v42_durable_spine_required"):
        run_visual_cognitive_circuit_v43(
            project_root=tmp_path, approved_read=True, approved_execution=True,
        )


def test_corrupt_real_mask_is_rejected_before_cognitive_circuit(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    _ready(tmp_path)
    inspection = tmp_path / "receipts/v40_mask_inspection"
    png = next(p for p in inspection.rglob("*.png") if not p.name.endswith(".preview.png"))
    with Image.open(png) as source:
        mask = source.convert("L")
    mask.putpixel((3, 3), 0)
    mask.save(png)
    with pytest.raises(ValueError, match="v41_prediction_pixel_integrity_failed"):
        run_visual_cognitive_circuit_v43(
            project_root=tmp_path, approved_read=True, approved_execution=True,
        )


def test_corrupted_spine_cannot_execute(tmp_path):
    _ready(tmp_path)
    file = tmp_path / _LEDGER
    lines = file.read_text(encoding="utf-8").splitlines()
    data = json.loads(lines[0])
    data["payload"]["predicted_mask_sha256"] = "0" * 64
    lines[0] = json.dumps(data)
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid.*spine"):
        run_visual_cognitive_circuit_v43(
            project_root=tmp_path, approved_read=True, approved_execution=True,
        )


def test_cli_dry_run_and_required_execution_approval(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main(["--project-root", str(tmp_path), "--approve-read"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "v43_execution_approval_required"
    assert not list(tmp_path.iterdir())
