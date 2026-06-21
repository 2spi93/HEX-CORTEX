from pathlib import Path

from hex_cortex.memory.cortex_cognitive_brain_registry import append_brain_phenotype
from hex_cortex.memory.cortex_cognitive_brain_registry import project_brain_registry
from hex_cortex.memory.cortex_cognitive_brain_registry import select_cognitive_brain


def _append(
    ledger: Path,
    *,
    brain_id: str,
    model_id: str,
    family: str,
    runtime: str,
    node: str,
    scope: str,
    coding_score: float,
    research_score: float,
    reliability: float,
    latency: float,
    cost: float,
) -> dict[str, object]:
    return append_brain_phenotype(
        ledger,
        brain_id=brain_id,
        model_id=model_id,
        model_family=family,
        runtime_id=runtime,
        node_id=node,
        provider_scope=scope,
        domain_scores={
            "coding": coding_score,
            "research": research_score,
            "general": min(coding_score, research_score),
        },
        reliability_score=reliability,
        latency_ms=latency,
        normalized_cost=cost,
        baseline_hash="a" * 64,
        parameter_class="12b",
        quantization="q4",
    )


def test_brain_registry_hashes_raw_model_and_node_identifiers(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    payload = _append(
        ledger,
        brain_id="windows-coding",
        model_id="private-model-identifier",
        family="local-coder",
        runtime="windows.ollama",
        node="private-windows-node",
        scope="local",
        coding_score=0.8,
        research_score=0.5,
        reliability=0.9,
        latency=1000.0,
        cost=0.05,
    )

    text = ledger.read_text(encoding="utf-8")
    assert payload["raw_model_identifier_persisted"] is False
    assert payload["raw_node_identifier_persisted"] is False
    assert "private-model-identifier" not in text
    assert "private-windows-node" not in text


def test_selector_chooses_domain_specialist_not_largest_or_named_model(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _append(
        ledger,
        brain_id="windows-coding",
        model_id="model-a",
        family="coder",
        runtime="windows.ollama",
        node="windows",
        scope="local",
        coding_score=0.9,
        research_score=0.45,
        reliability=0.9,
        latency=900.0,
        cost=0.05,
    )
    _append(
        ledger,
        brain_id="kali-research",
        model_id="model-b",
        family="general-reasoner",
        runtime="kali.ollama",
        node="kali",
        scope="private_remote",
        coding_score=0.65,
        research_score=0.92,
        reliability=0.88,
        latency=1400.0,
        cost=0.08,
    )

    coding = select_cognitive_brain(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
    )
    research = select_cognitive_brain(
        ledger,
        task_domain="research",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
    )

    assert coding["status"] == "ready"
    assert coding["selected_brain_id"] == "windows-coding"
    assert research["status"] == "ready"
    assert research["selected_brain_id"] == "kali-research"


def test_secret_context_excludes_all_nonlocal_brains(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _append(
        ledger,
        brain_id="local-safe",
        model_id="local",
        family="local",
        runtime="windows.ollama",
        node="windows",
        scope="local",
        coding_score=0.7,
        research_score=0.6,
        reliability=0.9,
        latency=1000.0,
        cost=0.05,
    )
    _append(
        ledger,
        brain_id="private-kali",
        model_id="kali",
        family="local",
        runtime="kali.ollama",
        node="kali",
        scope="private_remote",
        coding_score=0.95,
        research_score=0.95,
        reliability=0.95,
        latency=800.0,
        cost=0.05,
    )
    _append(
        ledger,
        brain_id="remote-teacher",
        model_id="teacher",
        family="frontier",
        runtime="remote.api",
        node="remote",
        scope="metered_remote",
        coding_score=1.0,
        research_score=1.0,
        reliability=1.0,
        latency=500.0,
        cost=1.0,
    )

    payload = select_cognitive_brain(
        ledger,
        task_domain="coding",
        context_sensitivity="secret",
        maximum_latency_ms=5000.0,
        cost_pressure=0.0,
        remote_allowed=True,
    )

    assert payload["selected_brain_id"] == "local-safe"
    excluded = {row["brain_id"]: row["reason"] for row in payload["exclusions"]}
    assert excluded["private-kali"] == "secret_context_requires_local_brain"
    assert excluded["remote-teacher"] == "secret_context_requires_local_brain"


def test_selector_fails_closed_when_no_brain_meets_threshold(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _append(
        ledger,
        brain_id="weak-local",
        model_id="weak",
        family="local",
        runtime="windows.ollama",
        node="windows",
        scope="local",
        coding_score=0.1,
        research_score=0.1,
        reliability=0.2,
        latency=4900.0,
        cost=0.4,
    )

    payload = select_cognitive_brain(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
        minimum_acceptable_score=0.7,
    )

    assert payload["status"] == "blocked"
    assert payload["selected_brain_id"] is None
    assert payload["silent_fallback_allowed"] is False
    assert payload["blockers"] == ["best_brain_below_acceptance_threshold"]


def test_phenotype_stores_uncertainty_signals(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    record = append_brain_phenotype(
        ledger,
        brain_id="windows-coding",
        model_id="model-a",
        model_family="coder",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"coding": 0.8, "research": 0.6, "general": 0.6},
        reliability_score=0.85,
        latency_ms=1000.0,
        normalized_cost=0.05,
        baseline_hash="a" * 64,
        reliability_ci95=0.07,
        error_rate=0.02,
    )

    assert record["reliability_ci95"] == 0.07
    assert record["error_rate"] == 0.02


def test_selector_prefers_stable_brain_over_uncertain_higher_scorer(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    # Unstable star: highest raw coding score but a wide CI and some call errors.
    append_brain_phenotype(
        ledger,
        brain_id="unstable-star",
        model_id="model-a",
        model_family="coder",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"coding": 0.90, "research": 0.5, "general": 0.5},
        reliability_score=0.90,
        latency_ms=900.0,
        normalized_cost=0.05,
        baseline_hash="a" * 64,
        reliability_ci95=0.30,
        error_rate=0.10,
    )
    # Steady performer: slightly lower raw score but tight CI and no errors.
    append_brain_phenotype(
        ledger,
        brain_id="steady-performer",
        model_id="model-b",
        model_family="coder",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"coding": 0.80, "research": 0.5, "general": 0.5},
        reliability_score=0.88,
        latency_ms=900.0,
        normalized_cost=0.05,
        baseline_hash="b" * 64,
        reliability_ci95=0.02,
        error_rate=0.0,
    )

    selection = select_cognitive_brain(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
    )

    assert selection["status"] == "ready"
    # Without risk awareness the unstable star (0.90) would win on raw score.
    assert selection["selected_brain_id"] == "steady-performer"
    by_id = {row["brain_id"]: row for row in selection["candidates"]}
    assert by_id["unstable-star"]["robust_competence"] < by_id["unstable-star"]["domain_competence"]


def test_legacy_phenotype_without_uncertainty_scores_unchanged(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    append_brain_phenotype(
        ledger,
        brain_id="legacy",
        model_id="model-a",
        model_family="coder",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"coding": 0.8, "research": 0.5, "general": 0.5},
        reliability_score=0.9,
        latency_ms=900.0,
        normalized_cost=0.05,
        baseline_hash="a" * 64,
    )

    selection = select_cognitive_brain(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
    )
    candidate = selection["candidates"][0]
    # Neutral defaults: robust competence equals raw competence for legacy rows.
    assert candidate["reliability_ci95"] == 0.0
    assert candidate["error_rate"] == 0.0
    assert candidate["robust_competence"] == candidate["domain_competence"]


def test_registry_uses_latest_phenotype_per_brain(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _append(
        ledger,
        brain_id="windows-coding",
        model_id="old-model",
        family="old-family",
        runtime="windows.ollama",
        node="windows",
        scope="local",
        coding_score=0.4,
        research_score=0.4,
        reliability=0.5,
        latency=2000.0,
        cost=0.05,
    )
    _append(
        ledger,
        brain_id="windows-coding",
        model_id="new-model",
        family="new-family",
        runtime="windows.ollama",
        node="windows",
        scope="local",
        coding_score=0.9,
        research_score=0.6,
        reliability=0.9,
        latency=900.0,
        cost=0.05,
    )

    registry = project_brain_registry(ledger)
    assert registry["brain_count"] == 1
    assert registry["event_count"] == 2
    assert registry["brains"]["windows-coding"]["model_family"] == "new-family"
