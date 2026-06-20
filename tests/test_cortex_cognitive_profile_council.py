from hex_cortex.memory.cortex_cognitive_genome import build_profile_council


def test_high_uncertainty_mutation_uses_diverse_council() -> None:
    payload = build_profile_council(
        failure_class="planning_error",
        novelty=0.9,
        uncertainty=0.9,
        mutation_requested=True,
    )

    assert payload["independent_views_required"] is True
    assert payload["evidence_weighted_adjudication_required"] is True
    assert payload["majority_vote_allowed"] is False
    assert "causalist" in payload["selected_profiles"]
    assert "constitutional_judge" in payload["selected_profiles"]
