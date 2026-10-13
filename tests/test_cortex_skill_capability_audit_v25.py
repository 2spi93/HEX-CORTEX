"""Read-only skill inventory never mistakes declared entries for model evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_procedural_skill_evidence_v25 import revoke_skill
from hex_cortex.memory.cortex_skill_capability_audit_cli_v25 import main
from hex_cortex.memory.cortex_skill_capability_audit_v25 import audit_skill_profile


def test_empty_profile_is_safe_and_does_not_create_files(tmp_path: Path) -> None:
    before = list(tmp_path.iterdir())
    report = audit_skill_profile(tmp_path)
    assert report["status"] == "read_only_skill_inventory"
    assert report["candidate_records"] == 0
    assert report["library_records"] == 0
    assert report["latest_declared_active_skills"] == []
    assert report["automatic_activation_performed"] is False
    assert report["actual_model_skill_gain_independently_attested"] is False
    assert report["model_called"] is False
    assert before == list(tmp_path.iterdir())


def test_audit_sees_explicit_revocation_without_activating(
    tmp_path: Path,
) -> None:
    revoke_skill(
        project_root=tmp_path, skill_id="multiply_decomposition",
        reason="observed regression", approved=True,
    )
    report = audit_skill_profile(tmp_path)
    statuses = {
        row["skill_id"]: row["status"]
        for row in report["procedural_skill_trial_statuses"]
    }
    assert statuses["multiply_decomposition"] == "revoked"
    assert report["latest_declared_active_skills"] == []
    assert report["automatic_activation_performed"] is False


def test_audit_rejects_symlinked_profile_records(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    foreign = tmp_path / "foreign"
    foreign.write_text("{}\n", encoding="utf-8")
    try:
        (root / "cortex-skill-library.jsonl").symlink_to(foreign)
    except (NotImplementedError, OSError):
        pytest.skip("symlink privileges unavailable")
    with pytest.raises(ValueError, match="skill_profile_unsafe_record_file"):
        audit_skill_profile(root)


def test_cli_dry_run_and_empty_profile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = ["--profile", str(tmp_path)]
    assert main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "read_only_skill_inventory"
    assert report["files_modified"] is False
