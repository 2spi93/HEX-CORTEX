from hex_cortex.memory.cortex_auto_plan import evaluate_cortex_auto_plan
from hex_cortex.memory.cortex_registry import build_cortex_registry
from hex_cortex.memory.cortex_registry import build_cortex_registry_plan


def test_auto_plan_allows_safe_registered_plan(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    registry = build_cortex_registry()
    plan = build_cortex_registry_plan(profile)

    payload = evaluate_cortex_auto_plan(
        registry=registry,
        plan=plan,
        operator_intent_known=True,
        plan_known=True,
        preference_match=1.0,
        stability_score=1.0,
        registered_unit_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["auto_plan_allowed"] is True
    assert payload["trusted_plan"] is True
    assert payload["next_action"] == "run_via_cortex_bus"
    assert all(decision["allowed"] is True for decision in payload["decisions"])


def test_auto_plan_allows_operator_unit_only_when_trusted() -> None:
    registry = build_cortex_registry()
    plan = [{"name": "b.build", "kwargs": {}}]

    payload = evaluate_cortex_auto_plan(
        registry=registry,
        plan=plan,
        operator_intent_known=True,
        plan_known=True,
        preference_match=1.0,
        stability_score=1.0,
        registered_unit_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["auto_plan_allowed"] is True
    assert payload["trusted_plan"] is True
    assert payload["decisions"][0]["allowed"] is True


def test_auto_plan_blocks_operator_unit_when_not_trusted() -> None:
    registry = build_cortex_registry()
    plan = [{"name": "b.build", "kwargs": {}}]

    payload = evaluate_cortex_auto_plan(
        registry=registry,
        plan=plan,
        operator_intent_known=False,
        plan_known=True,
        preference_match=1.0,
        stability_score=1.0,
        registered_unit_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["auto_plan_allowed"] is False
    assert payload["trusted_plan"] is False
    assert "operator_intent_unknown" in payload["blockers"]
    assert "step_0:auto_safe_requires_trusted_plan_for_operator_units" in payload["blockers"]


def test_auto_plan_blocks_unknown_unit() -> None:
    payload = evaluate_cortex_auto_plan(
        registry={},
        plan=[{"name": "missing.unit", "kwargs": {}}],
        operator_intent_known=True,
        plan_known=True,
        preference_match=1.0,
        stability_score=1.0,
        registered_unit_rate=1.0,
        receipt_rate=1.0,
    )

    assert payload["auto_plan_allowed"] is False
    assert "step_0:unknown_unit_requires_registration" in payload["blockers"]
