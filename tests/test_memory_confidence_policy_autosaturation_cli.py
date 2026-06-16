import json

from hex_cortex.memory.confidence_policy_autosaturation_cli import main
from hex_cortex.memory.confidence_policy_telemetry import (
    record_memory_confidence_policy_telemetry_profile,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_policy_autosaturation_cli_preview_and_apply(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(title="memory", body="body", confidence=0.8, access_count=1)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])
    record_memory_confidence_policy_telemetry_profile(profile)

    exit_code = main([str(profile), "--stability-window", "1", "--pretty"])
    preview = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert preview["eligible"] is True
    assert preview["marker_written"] is False

    exit_code = main([str(profile), "--stability-window", "1", "--apply"])
    applied = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert applied["marker_written"] is True

    exit_code = main([str(profile), "--inspect-marker", "--pretty"])
    marker = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert marker["exists"] is True
    assert marker["marker"]["stability_state"] == "confidence_policy_stable"
