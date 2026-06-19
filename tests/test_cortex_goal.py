from hex_cortex.memory.cortex_goal import CORTEX_COST_FILENAME
from hex_cortex.memory.cortex_goal import CORTEX_GOAL_FILENAME
from hex_cortex.memory.cortex_goal import build_cortex_goal
from hex_cortex.memory.cortex_goal import evaluate_cortex_cost
from hex_cortex.memory.cortex_goal import summarize_cortex_costs


def test_cortex_goal_builds_canonical_record(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_goal(
        profile,
        goal_id="understand_dashboard",
        desired_capabilities=["voice_input", "screen_vision", "voice_input"],
        target_confidence=0.8,
        max_horizon_steps=8,
        max_total_cost=0.5,
        priority=0.9,
    )

    record = payload["goal_records"][0]
    assert record["goal_allowed"] is True
    assert record["desired_capabilities"] == [
        "screen_vision",
        "voice_input",
    ]
    assert record["target_confidence"] == 0.8
    assert record["next_action"] == "evaluate_goal_cost"
    assert isinstance(record["goal_hash"], str)
    assert (profile / CORTEX_GOAL_FILENAME).exists()


def test_cortex_goal_blocks_invalid_contract(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_goal(
        profile,
        goal_id="",
        desired_capabilities=[],
        target_confidence=1.2,
        max_horizon_steps=0,
        max_total_cost=-0.1,
        priority=2.0,
    )

    record = payload["goal_records"][0]
    assert record["goal_allowed"] is False
    assert "missing_goal_id" in record["blockers"]
    assert "desired_capabilities_invalid" in record["blockers"]
    assert "target_confidence_out_of_range" in record["blockers"]
    assert "max_horizon_steps_out_of_range" in record["blockers"]
    assert "max_total_cost_out_of_range" in record["blockers"]
    assert "priority_out_of_range" in record["blockers"]


def test_cortex_cost_accepts_satisfied_candidate(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    goal = _goal(profile, max_total_cost=0.5)

    payload = evaluate_cortex_cost(
        profile,
        goal_record=goal,
        candidate_state=_state(
            capabilities=["screen_vision", "voice_input"],
            confidence=0.9,
        ),
        risk_penalty=0.1,
        surprise_score=0.1,
        horizon_steps=1,
    )

    record = payload["cost_records"][0]
    assert record["cost_allowed"] is True
    assert record["missing_capabilities"] == []
    assert record["goal_satisfied"] is True
    assert record["within_cost_budget"] is True
    assert record["decision"] == "accept_candidate"
    assert record["progress_score"] == 1.0
    assert record["total_cost"] == 0.0688
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["raw_state_persisted"] is False
    assert record["next_action"] == "propose_actions"

    summary = summarize_cortex_costs(profile / CORTEX_COST_FILENAME)
    assert summary["latest_cost_allowed"] is True
    assert summary["latest_decision"] == "accept_candidate"


def test_cortex_cost_continues_planning_within_budget(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    goal = _goal(profile, max_total_cost=0.8)

    payload = evaluate_cortex_cost(
        profile,
        goal_record=goal,
        candidate_state=_state(
            capabilities=["screen_vision"],
            confidence=0.7,
        ),
        risk_penalty=0.1,
        surprise_score=0.2,
        horizon_steps=2,
    )

    record = payload["cost_records"][0]
    assert record["cost_allowed"] is True
    assert record["missing_capabilities"] == ["voice_input"]
    assert record["goal_satisfied"] is False
    assert record["within_cost_budget"] is True
    assert record["decision"] == "continue_planning"
    assert 0.0 < record["progress_score"] < 1.0


def test_cortex_cost_rejects_candidate_above_budget(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    goal = _goal(profile, max_total_cost=0.1)

    payload = evaluate_cortex_cost(
        profile,
        goal_record=goal,
        candidate_state=_state(capabilities=[], confidence=0.2),
        risk_penalty=1.0,
        surprise_score=1.0,
        horizon_steps=8,
    )

    record = payload["cost_records"][0]
    assert record["cost_allowed"] is True
    assert record["within_cost_budget"] is False
    assert record["decision"] == "reject_candidate"
    assert record["total_cost"] > 0.1


def test_cortex_cost_supports_predicted_transition_state(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    goal = _goal(profile, max_total_cost=0.8)
    predicted = {
        "transition_allowed": True,
        "transition_hash": "transition-hash",
        "predicted_state_hash": "predicted-state-hash",
        "predicted_capabilities": ["screen_vision", "voice_input"],
        "predicted_average_confidence": 0.85,
    }

    payload = evaluate_cortex_cost(
        profile,
        goal_record=goal,
        candidate_state=predicted,
        horizon_steps=3,
    )

    record = payload["cost_records"][0]
    assert record["cost_allowed"] is True
    assert record["candidate_state_hash"] == "predicted-state-hash"
    assert record["goal_satisfied"] is True
    assert record["decision"] == "accept_candidate"


def test_cortex_cost_blocks_invalid_weights(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    goal = _goal(profile, max_total_cost=0.8)

    payload = evaluate_cortex_cost(
        profile,
        goal_record=goal,
        candidate_state=_state(
            capabilities=["screen_vision"],
            confidence=0.8,
        ),
        weights={
            "goal_gap": 0.5,
            "risk": 0.5,
            "uncertainty": 0.5,
            "surprise": 0.5,
            "horizon": 0.5,
        },
    )

    record = payload["cost_records"][0]
    assert record["cost_allowed"] is False
    assert "cost_weights_sum_invalid" in record["blockers"]
    assert record["decision"] == "blocked"
    assert record["next_action"] == "repair_goal_cost_input"


def test_cortex_goal_and_cost_are_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    first_goal = _goal_payload(profile)
    second_goal = _goal_payload(profile)
    assert first_goal["goal_count"] == 1
    assert second_goal["goal_count"] == 1

    goal = first_goal["goal_records"][0]
    kwargs = {
        "goal_record": goal,
        "candidate_state": _state(
            capabilities=["screen_vision", "voice_input"],
            confidence=0.9,
        ),
    }
    first_cost = evaluate_cortex_cost(profile, **kwargs)
    second_cost = evaluate_cortex_cost(profile, **kwargs)
    assert first_cost["cost_count"] == 1
    assert second_cost["cost_count"] == 1
    assert (
        first_cost["cost_records"][0]["cost_hash"]
        == second_cost["cost_records"][0]["cost_hash"]
    )


def _goal(
    profile,
    *,
    max_total_cost: float,
) -> dict[str, object]:
    return build_cortex_goal(
        profile,
        goal_id="understand_dashboard",
        desired_capabilities=["screen_vision", "voice_input"],
        target_confidence=0.8,
        max_horizon_steps=8,
        max_total_cost=max_total_cost,
        priority=0.9,
    )["goal_records"][0]


def _goal_payload(profile):
    return build_cortex_goal(
        profile,
        goal_id="understand_dashboard",
        desired_capabilities=["screen_vision", "voice_input"],
        target_confidence=0.8,
        max_horizon_steps=8,
        max_total_cost=0.5,
        priority=0.9,
    )


def _state(
    *,
    capabilities: list[str],
    confidence: float,
) -> dict[str, object]:
    return {
        "state_allowed": True,
        "state_hash": "state-hash",
        "capabilities": capabilities,
        "average_confidence": confidence,
    }
