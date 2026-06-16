import json

from hex_cortex.memory.profile_dispatch_history import (
    ProfileDispatchHistoryJsonlStore,
    ProfileDispatchHistoryRecord,
)
from hex_cortex.memory.profile_dispatch_history_cli import main


def test_profile_dispatch_history_cli_outputs_summary(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    ProfileDispatchHistoryJsonlStore(profile / "profile-dispatch.jsonl").save([
        ProfileDispatchHistoryRecord(
            profile_path=str(profile),
            status="ready",
            decision="allow",
            reason="ready",
            next_action="run_cortex_pipeline",
            next_reason="ready_to_run",
            dispatch_status="executed",
            dispatch_reason="done",
            task_id="task_a",
            pipeline_mode="reflex",
            clock_completed=True,
            persisted_event_count=1,
            persisted_memory_count=1,
        )
    ])

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["inspect_type"] == "profile_dispatch_history"
    assert payload["executed_count"] == 1
    assert payload["latest_task_id"] == "task_a"
