import json

from hex_cortex.memory.confidence_policy_drain_cli import main
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_policy_drain_cli_preview_and_apply(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    memory = MemoryRecord(title="memory", body="body", confidence=0.55)
    LocalMemoryJsonlStore(profile / "memory.jsonl").save([memory])

    exit_code = main([
        str(profile),
        "--saturation-threshold",
        "0.6",
        "--pretty",
    ])
    preview = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert preview["dry_run"] is True
    assert preview["policy_exhausted"] is False

    exit_code = main([
        str(profile),
        "--saturation-threshold",
        "0.6",
        "--stability-window",
        "1",
        "--max-iterations",
        "2",
        "--max-total-operations",
        "1",
        "--max-total-positive-delta",
        "0.05",
        "--apply",
    ])
    applied = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert applied["policy_exhausted"] is True
    assert applied["stable"] is True
    assert applied["marker_written"] is True
