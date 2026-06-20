from hex_cortex.memory.cortex_cognitive_genome import build_homeostasis_decision


def test_high_cost_pressure_avoids_remote_teacher() -> None:
    payload = build_homeostasis_decision(
        uncertainty=0.8,
        recurrence_count=1,
        deterministic_verification_available=True,
        local_verification_failed=True,
        cost_pressure=0.95,
        regression_risk=0.5,
    )

    assert "run_deterministic_verifier" in payload["selected_actions"]
    assert "consult_remote_teacher" not in payload["selected_actions"]
    assert payload["weight_mutation_selected"] is False
