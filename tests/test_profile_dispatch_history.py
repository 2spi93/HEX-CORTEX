from hex_cortex.memory.profile_dispatch_history import (
    ProfileDispatchHistoryJsonlStore,
    record_profile_dispatch_history,
    summarize_profile_dispatch_history,
)


def test_profile_dispatch_history_records_and_summarizes(tmp_path) -> None:
    profile = tmp_path / "profile"
    report = {
        "status": "ready",
        "decision": "allow",
        "reason": "ready",
        "next_action": "run_cortex_pipeline",
        "next_reason": "ready_to_run",
        "dispatch_status": "executed",
        "dispatch_reason": "done",
        "pipeline_result": {
            "task_id": "task_a",
            "mode": "reflex",
            "clock_completed": True,
            "persisted_event_count": 1,
            "persisted_memory_count": 1,
        },
    }

    payload = record_profile_dispatch_history(profile, report)
    summary = summarize_profile_dispatch_history(profile / "profile-dispatch.jsonl")
    records = ProfileDispatchHistoryJsonlStore(profile / "profile-dispatch.jsonl").load()

    assert payload["record_type"] == "profile_dispatch_history"
    assert payload["history_count"] == 1
    assert summary["executed_count"] == 1
    assert summary["skipped_count"] == 0
    assert summary["latest_task_id"] == "task_a"
    assert records[0].dispatch_status == "executed"
