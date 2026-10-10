"""V21 honest model-vs-CORTEX paired evaluation, and latent contract test."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hex_cortex.core.cortex_jepa_latent_contract_v21 import (
    LatentWorldObservation,
    score_latent_prediction,
)
from hex_cortex.core.cortex_paired_science_benchmark_cli_v21 import main
from hex_cortex.core.cortex_paired_science_benchmark_v21 import (
    PairedEvaluation,
    ScienceEvalItem,
    evaluate_paired_model_amplification,
)


def _fixture() -> PairedEvaluation:
    root = Path(__file__).resolve().parents[1]
    return PairedEvaluation.model_validate_json(
        (root / "examples" / "paired_science_v21_synthetic.json").read_text(
            encoding="utf-8"
        )
    )


def test_synthetic_scores_are_never_presented_as_real_model_gain():
    out = evaluate_paired_model_amplification(_fixture(), operator_approved=True)
    assert out["status"] == "scored"
    assert out["sample_size"] == 3
    assert out["baseline_correct"] == 1
    assert out["cortex_correct"] == 3
    assert out["cortex_only_correct"] == 2
    assert out["baseline_only_correct"] == 0
    assert out["delta_correct"] == 2
    assert out["mcnemar_exact_two_sided_p"] == "1/2"
    assert out["capture_mode"] == "synthetic_fixture"
    assert out["real_model_amplification_measured"] is False
    assert out["real_model_calls_independently_attested"] is False
    assert out["causal_effect_certified"] is False
    assert out["model_called"] is False
    assert out["physical_action_authorized"] is False
    assert out["totals"]["baseline"]["latency_ms"] == 300
    assert out["totals"]["cortex"]["latency_ms"] == 420


def test_explicit_denial_without_io_or_scoring():
    out = evaluate_paired_model_amplification(_fixture())
    assert out["status"] == "blocked"
    assert out["model_called"] is False
    assert out["input_read"] is False


@pytest.mark.parametrize(("field", "replacement", "reason"), [
    ("model_id", "different-model", "bench_model_configuration_mismatch"),
    ("provider", "another-provider", "bench_model_configuration_mismatch"),
    ("model_revision", "different-revision", "bench_model_configuration_mismatch"),
    ("settings_sha256", "0" * 64, "bench_model_configuration_mismatch"),
    ("task_sha256", "0" * 64, "bench_task_input_hash_mismatch"),
    ("capture_kind", "operator_supplied", "bench_model_configuration_mismatch"),
])
def test_mismatched_provider_or_task_arms_are_refused(field, replacement, reason):
    fixture = _fixture()
    obs = list(fixture.observations)
    obs[1] = obs[1].model_copy(update={field: replacement})
    with pytest.raises(ValidationError, match=reason):
        PairedEvaluation.model_validate({
            **fixture.model_dump(mode="json"),
            "observations": [r.model_dump(mode="json") for r in obs],
        })


def test_unmatched_or_duplicate_items_denied():
    f = _fixture()
    with pytest.raises(ValidationError, match="bench_missing_or_duplicate_arm"):
        PairedEvaluation.model_validate({
            **f.model_dump(mode="json"),
            "observations": [r.model_dump(mode="json") for r in f.observations[:-1]],
        })
    with pytest.raises(ValidationError, match="bench_duplicate_task"):
        PairedEvaluation.model_validate({
            **f.model_dump(mode="json"),
            "items": [f.items[0].model_dump(mode="json")] * 2,
        })


def test_rational_gold_answer_is_prevalidated():
    original = _fixture().items[0].model_dump(mode="json")
    original["expected"] = "import('os')"
    with pytest.raises(ValidationError, match="bench_expected_not_rational"):
        ScienceEvalItem.model_validate(original)


def test_operator_supplied_responses_are_unattested_not_certified():
    f = _fixture()
    items = f.model_dump(mode="json")
    for row in items["observations"]:
        row["capture_kind"] = "operator_supplied"
    report = evaluate_paired_model_amplification(
        PairedEvaluation.model_validate(items), operator_approved=True,
    )
    assert report["capture_mode"] == "operator_supplied_unattested"
    assert report["real_model_amplification_measured"] is False
    assert report["evidence_is_external_and_unverified"] is True
    assert report["real_model_calls_independently_attested"] is False
    assert report["causal_effect_certified"] is False


def test_all_discordant_cases_exact_mcnemar_probability():
    f = _fixture()
    data = f.model_dump(mode="json")
    # Three baseline-only wins: exactly 1/4 two-sided under the paired null.
    for o in data["observations"]:
        if o["task_id"] == "math_demo":
            o["response"] = "1/2" if o["arm"] == "baseline" else "1/3"
        elif o["task_id"] == "physics_demo":
            o["response"] = "2" if o["arm"] == "baseline" else "1"
        elif o["task_id"] == "chemistry_demo":
            o["response"] = (
                "2 H2 + O2 -> 2 H2O" if o["arm"] == "baseline"
                else "2 H2 + O2 -> H2O"
            )
    result = evaluate_paired_model_amplification(
        PairedEvaluation.model_validate(data), operator_approved=True,
    )
    assert result["baseline_only_correct"] == 3
    assert result["cortex_only_correct"] == 0
    assert result["mcnemar_exact_two_sided_p"] == "1/4"


def test_report_order_and_redaction_are_stable():
    f = _fixture()
    a = evaluate_paired_model_amplification(f, operator_approved=True)
    revised = f.model_copy(update={"observations": list(reversed(f.observations))})
    b = evaluate_paired_model_amplification(revised, operator_approved=True)
    assert a == b
    serial = json.dumps(a)
    assert "2 H2 + O2" not in serial
    assert "import('os')" not in serial


def test_cli_reads_synthetic_fixture_and_never_calls_model(capsys):
    root = Path(__file__).resolve().parents[1]
    file = root / "examples" / "paired_science_v21_synthetic.json"
    assert main(["--pairs", str(file), "--approve-read", "--pretty"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "scored"
    assert result["model_called"] is False
    assert result["real_model_amplification_measured"] is False


def test_cli_denies_read_without_approval(tmp_path: Path, capsys):
    assert main(["--pairs", str(tmp_path / "absent.json")]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["files_read"] is False


def test_cli_bad_file_and_symlink_denied(tmp_path: Path, capsys):
    file = tmp_path / "test.json"
    file.write_text("not-json", encoding="utf-8")
    assert main(["--pairs", str(file), "--approve-read"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
    link = tmp_path / "test-link.json"
    try:
        link.symlink_to(file)
    except OSError:
        pytest.skip("symlinks unavailable on this Windows runner")
    assert main(["--pairs", str(link), "--approve-read"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def _latent(predict=("1/2", "3/2"), observed=("1", "1")):
    return LatentWorldObservation(
        observation_id="synthetic-transition",
        encoder_identity_sha256="a" * 64,
        predictor_identity_sha256="b" * 64,
        horizon_steps=1,
        predicted_latent=predict,
        observed_latent=observed,
        origin="synthetic_fixture",
    )


def test_latent_prediction_exact_error_and_no_neural_model_claim():
    result = score_latent_prediction(_latent(), operator_approved=True)
    assert result["status"] == "scored_latent_prediction"
    assert result["mean_absolute_latent_error"] == "1/2"
    assert result["mean_squared_latent_error"] == "1/4"
    assert result["model_called"] is False
    assert result["learned_jepa_model_loaded"] is False
    assert result["physical_action_authorized"] is False


@pytest.mark.parametrize(("prediction", "observation"), [
    (("0",), ("1", "2")),
    (("1.5",), ("1",)),
    (("import('os')",), ("1",)),
])
def test_latent_contract_rejects_malformed_or_unsafe_dimensions(prediction, observation):
    with pytest.raises((ValidationError, ValueError)):
        _latent(predict=prediction, observed=observation)


def test_latent_scoring_also_requires_permission():
    result = score_latent_prediction(_latent())
    assert result["status"] == "blocked"
    assert result["model_called"] is False


def test_zero_latent_error_in_64_dimensional_simulation():
    values = tuple(str(i % 7) for i in range(64))
    result = score_latent_prediction(
        _latent(predict=values, observed=values),
        operator_approved=True,
    )
    assert result["embedding_dimensions"] == 64
    assert result["mean_squared_latent_error"] == "0"
