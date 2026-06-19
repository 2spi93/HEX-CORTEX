from hex_cortex.memory.cortex_pick import CORTEX_PICK_FILENAME
from hex_cortex.memory.cortex_pick import build_cortex_pick
from hex_cortex.memory.cortex_pick import summarize_cortex_picks


def test_manual_pick_can_prepare_next_receipt(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_pick(
        profile,
        proposal_record=_proposal(requires_operator=False),
        mode="manual",
    )

    record = payload["pick_records"][0]
    assert record["pick_allowed"] is True
    assert record["action_id"] == "analyze_locally"
    assert record["ready_for_next_receipt"] is True
    assert record["action_executed"] is False
    assert record["tool_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["next_action"] == "prepare_manual_receipt"

    summary = summarize_cortex_picks(profile / CORTEX_PICK_FILENAME)
    assert summary["latest_pick_allowed"] is True
    assert summary["latest_action_id"] == "analyze_locally"


def test_sensitive_manual_pick_waits_for_operator(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_pick(
        profile,
        proposal_record=_proposal(requires_operator=True),
        mode="manual",
        approved=False,
    )

    record = payload["pick_records"][0]
    assert record["pick_allowed"] is True
    assert record["requires_operator"] is True
    assert record["ready_for_next_receipt"] is False
    assert record["next_action"] == "request_operator_for_next_receipt"


def test_sensitive_manual_pick_accepts_operator_approval(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_pick(
        profile,
        proposal_record=_proposal(requires_operator=True),
        mode="manual",
        approved=True,
    )

    record = payload["pick_records"][0]
    assert record["pick_allowed"] is True
    assert record["ready_for_next_receipt"] is True
    assert record["next_action"] == "prepare_manual_receipt"


def test_auto_safe_pick_accepts_non_sensitive_action(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_pick(
        profile,
        proposal_record=_proposal(requires_operator=False),
        mode="auto_safe",
        auto_safe=True,
    )

    record = payload["pick_records"][0]
    assert record["pick_allowed"] is True
    assert record["ready_for_next_receipt"] is True
    assert record["next_action"] == "prepare_auto_safe_receipt"


def test_auto_safe_pick_blocks_sensitive_action(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_pick(
        profile,
        proposal_record=_proposal(requires_operator=True),
        mode="auto_safe",
        auto_safe=True,
    )

    record = payload["pick_records"][0]
    assert record["pick_allowed"] is False
    assert "auto_safe_sensitive_action_forbidden" in record["blockers"]
    assert record["next_action"] == "repair_action_pick"


def test_pick_blocks_unknown_action(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_pick(
        profile,
        proposal_record=_proposal(requires_operator=False),
        action_id="unknown",
    )

    record = payload["pick_records"][0]
    assert record["pick_allowed"] is False
    assert "action_not_found" in record["blockers"]


def test_pick_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    kwargs = {
        "proposal_record": _proposal(requires_operator=False),
        "mode": "manual",
    }

    first = build_cortex_pick(profile, **kwargs)
    second = build_cortex_pick(profile, **kwargs)

    assert first["pick_count"] == 1
    assert second["pick_count"] == 1
    assert first["pick_records"][0]["pick_hash"] == second[
        "pick_records"
    ][0]["pick_hash"]


def _proposal(*, requires_operator: bool) -> dict[str, object]:
    action = {
        "action_id": "analyze_locally",
        "output_id": "generate_plan",
        "requires_operator": requires_operator,
        "within_cost_budget": True,
        "decision": "accept_candidate",
        "total_cost": 0.1,
        "predicted_state_hash": "predicted-state-hash",
    }
    return {
        "proposal_allowed": True,
        "proposal_hash": "proposal-hash",
        "goal_id": "goal-id",
        "source_state_hash": "state-hash",
        "recommended_action_id": "analyze_locally",
        "ranked_actions": [action],
    }
