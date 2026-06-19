from hex_cortex.memory.cortex_action import CORTEX_ACTION_FILENAME
from hex_cortex.memory.cortex_action import build_cortex_action_proposals
from hex_cortex.memory.cortex_action import build_default_action_candidates
from hex_cortex.memory.cortex_action import summarize_cortex_action_proposals


def test_default_action_candidates_cover_gap_and_review() -> None:
    actions = build_default_action_candidates(
        goal_record=_goal(),
        current_state=_state(),
    )
    ids = {action["action_id"] for action in actions}

    assert "acquire_missing_capabilities" in ids
    assert "increase_confidence" in ids
    assert "hold_and_review" in ids


def test_action_proposal_ranks_lower_cost_candidate(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_action_proposals(
        profile,
        goal_record=_goal(),
        current_state=_state(),
        candidate_actions=_candidates(),
        top_k=2,
    )

    record = payload["proposal_records"][0]
    assert record["proposal_allowed"] is True
    assert record["candidate_count"] == 2
    assert record["ranked_actions"][0]["action_id"] == "observe_missing"
    assert record["ranked_actions"][0]["total_cost"] < record[
        "ranked_actions"
    ][1]["total_cost"]
    assert record["recommended_action_id"] == "observe_missing"
    assert record["recommended_requires_operator"] is True
    assert record["recommendation_allowed"] is True
    assert record["action_executed"] is False
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["next_action"] == "request_operator_for_action"

    summary = summarize_cortex_action_proposals(
        profile / CORTEX_ACTION_FILENAME
    )
    assert summary["latest_proposal_allowed"] is True
    assert summary["latest_recommended_action_id"] == "observe_missing"


def test_action_proposal_can_recommend_readonly_output(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    actions = [
        {
            "action_id": "analyze_locally",
            "output_id": "generate_plan",
            "expected_capabilities": ["voice_input"],
            "confidence_delta": 0.2,
            "risk_penalty": 0.05,
            "surprise_score": 0.05,
            "horizon_steps": 1,
        }
    ]

    payload = build_cortex_action_proposals(
        profile,
        goal_record=_goal(),
        current_state=_state(),
        candidate_actions=actions,
    )

    record = payload["proposal_records"][0]
    assert record["recommended_action_id"] == "analyze_locally"
    assert record["recommended_requires_operator"] is False
    assert record["next_action"] == "review_action_proposal"


def test_action_proposal_blocks_invalid_candidates(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    invalid = [
        {
            "action_id": "duplicate",
            "output_id": "unknown_output",
            "expected_capabilities": "bad",
            "confidence_delta": 2.0,
            "risk_penalty": -1.0,
            "surprise_score": 2.0,
            "horizon_steps": 0,
        },
        {
            "action_id": "duplicate",
            "output_id": "write_text",
            "expected_capabilities": [],
            "horizon_steps": 1,
        },
    ]

    payload = build_cortex_action_proposals(
        profile,
        goal_record=_goal(),
        current_state=_state(),
        candidate_actions=invalid,
    )

    record = payload["proposal_records"][0]
    assert record["proposal_allowed"] is False
    assert "action_0_output_unknown" in record["blockers"]
    assert "action_0_capabilities_invalid" in record["blockers"]
    assert "action_0_confidence_delta_invalid" in record["blockers"]
    assert "action_0_risk_penalty_invalid" in record["blockers"]
    assert "action_0_surprise_score_invalid" in record["blockers"]
    assert "action_0_horizon_invalid" in record["blockers"]
    assert "duplicate_action_ids" in record["blockers"]
    assert record["ranked_actions"] == []
    assert record["next_action"] == "repair_action_proposal"


def test_action_proposal_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    kwargs = {
        "goal_record": _goal(),
        "current_state": _state(),
        "candidate_actions": _candidates(),
    }

    first = build_cortex_action_proposals(profile, **kwargs)
    second = build_cortex_action_proposals(profile, **kwargs)

    assert first["proposal_count"] == 1
    assert second["proposal_count"] == 1
    assert first["proposal_records"][0]["proposal_hash"] == second[
        "proposal_records"
    ][0]["proposal_hash"]


def _goal() -> dict[str, object]:
    return {
        "goal_allowed": True,
        "goal_id": "understand_dashboard",
        "goal_hash": "goal-hash",
        "desired_capabilities": ["screen_vision", "voice_input"],
        "target_confidence": 0.8,
        "max_horizon_steps": 8,
        "max_total_cost": 0.5,
    }


def _state() -> dict[str, object]:
    return {
        "state_allowed": True,
        "state_hash": "state-hash",
        "capabilities": ["screen_vision"],
        "average_confidence": 0.6,
    }


def _candidates() -> list[dict[str, object]]:
    return [
        {
            "action_id": "observe_missing",
            "output_id": "request_tool",
            "expected_capabilities": ["voice_input"],
            "confidence_delta": 0.2,
            "risk_penalty": 0.1,
            "surprise_score": 0.1,
            "horizon_steps": 1,
        },
        {
            "action_id": "hold",
            "output_id": "write_text",
            "expected_capabilities": [],
            "confidence_delta": 0.0,
            "risk_penalty": 0.0,
            "surprise_score": 0.0,
            "horizon_steps": 1,
        },
    ]
