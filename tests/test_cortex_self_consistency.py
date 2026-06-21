import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_self_consistency import aggregate_self_consistency
from hex_cortex.memory.cortex_self_consistency import aggregate_verification_votes


def test_majority_vote_reaches_consensus() -> None:
    result = aggregate_self_consistency(["42", "42", "42", "41", "42"])
    assert result["status"] == "verified"
    assert result["decision"] == "consensus_reached"
    assert result["winner_count"] == 4
    assert result["agreement_ratio"] == 0.8
    assert result["consensus_answer"] == "42"


def test_consensus_answer_is_not_persisted_in_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "votes.jsonl"
    aggregate_self_consistency(
        ["secret answer", "secret answer", "other"],
        receipt_path=receipt_path,
    )
    text = receipt_path.read_text(encoding="utf-8")
    # No raw model response text leaks into the persisted receipt.
    assert "secret answer" not in text
    assert "other" not in text
    row = json.loads(text.splitlines()[0])
    assert row["raw_response_persisted"] is False
    assert "consensus_answer" not in row
    assert len(row["winner_cluster_hash"]) == 64


def test_tie_fails_closed() -> None:
    result = aggregate_self_consistency(["a", "b"])
    assert result["status"] == "no_consensus"
    assert result["decision"] == "consensus_tied"
    assert result["tie"] is True


def test_below_threshold_fails_closed() -> None:
    # Plurality winner at 0.4 < 0.5 threshold -> no consensus.
    result = aggregate_self_consistency(["a", "a", "b", "c", "d"], agreement_threshold=0.5)
    assert result["winner_count"] == 2
    assert result["status"] == "no_consensus"
    assert result["decision"] == "consensus_below_threshold"


def test_numeric_mode_clusters_formatting_variants() -> None:
    result = aggregate_self_consistency(
        ["1,000", "1000", " 1000 ", "999"],
        mode="numeric",
    )
    assert result["winner_count"] == 3
    assert result["cluster_count"] == 2
    assert result["status"] == "verified"


def test_numeric_mode_does_not_merge_decimal_comma() -> None:
    # "3,14" must not be misread as the thousands form of 314.
    result = aggregate_self_consistency(["3,14", "314", "314"], mode="numeric")
    assert result["cluster_count"] == 2
    assert result["winner_count"] == 2


def test_confidence_grows_with_sample_size() -> None:
    small = aggregate_self_consistency(["x"])
    large = aggregate_self_consistency(["x"] * 20)
    assert small["agreement_ratio"] == 1.0
    assert large["agreement_ratio"] == 1.0
    # Unanimous, but the larger sample earns a higher lower-bound confidence.
    assert small["confidence_wilson_lower"] < large["confidence_wilson_lower"]
    assert 0.0 < small["confidence_wilson_lower"] < 0.5


def test_weighted_vote_lets_reliability_overturn_a_count_majority() -> None:
    # Three samples say "a" (low-reliability brains), two say "b" (high). By
    # plain count "a" wins 3-2; weighted by reliability "b" should win.
    samples = ["a", "a", "a", "b", "b"]
    weights = [0.2, 0.2, 0.2, 0.9, 0.9]
    weighted = aggregate_self_consistency(samples, sample_weights=weights)
    plain = aggregate_self_consistency(samples)
    assert plain["consensus_answer"] == "a"
    assert weighted["consensus_answer"] == "b"
    assert weighted["weighted"] is True


def test_weighted_effective_sample_size_is_below_raw_count() -> None:
    # Highly uneven weights -> Kish effective N well under the 5 raw samples,
    # so the weighted confidence is appropriately humbler than a naive count.
    result = aggregate_self_consistency(
        ["x"] * 5,
        sample_weights=[1.0, 0.05, 0.05, 0.05, 0.05],
    )
    assert result["agreement_ratio"] == 1.0
    assert result["effective_sample_count"] < 5.0
    assert result["effective_sample_count"] > 1.0


def test_unweighted_path_unchanged_when_weights_omitted() -> None:
    result = aggregate_self_consistency(["q", "q", "q"])
    assert result["weighted"] is False
    assert result["effective_sample_count"] == 3.0
    assert result["total_weight"] == 3.0


def test_weighted_voting_rejects_bad_weights() -> None:
    with pytest.raises(ValueError):
        aggregate_self_consistency(["a", "b"], sample_weights=[1.0])
    with pytest.raises(ValueError):
        aggregate_self_consistency(["a"], sample_weights=[-1.0])
    with pytest.raises(ValueError):
        aggregate_self_consistency(["a"], sample_weights=[0.0])
    with pytest.raises(ValueError):
        aggregate_self_consistency(["a"], sample_weights=[True])  # type: ignore[list-item]


def test_invalid_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        aggregate_self_consistency([])
    with pytest.raises(ValueError):
        aggregate_self_consistency(["a"], mode="bogus")
    with pytest.raises(ValueError):
        aggregate_self_consistency([1, 2])  # type: ignore[list-item]


def test_adversarial_verification_majority_refute_kills_claim() -> None:
    verdicts = [
        {"refuted": True, "lens": "correctness"},
        {"refuted": True, "lens": "security"},
        {"refuted": False, "lens": "repro"},
    ]
    result = aggregate_verification_votes(verdicts)
    assert result["status"] == "refuted"
    assert result["refuted_count"] == 2
    assert result["lenses"] == ["correctness", "repro", "security"]


def test_adversarial_verification_minority_refute_survives() -> None:
    verdicts = [
        {"refuted": False},
        {"refuted": False},
        {"refuted": True},
    ]
    result = aggregate_verification_votes(verdicts)
    assert result["status"] == "survived"
    assert result["decision"] == "claim_survived_verification"
    assert result["lenses"] == ["unspecified"]


def test_adversarial_verification_writes_receipt_without_raw_text(tmp_path: Path) -> None:
    receipt_path = tmp_path / "verify.jsonl"
    aggregate_verification_votes([{"refuted": False}], receipt_path=receipt_path)
    row = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["record_type"] == "cortex_adversarial_verification_v1"
    assert row["raw_response_persisted"] is False
    assert len(row["event_hash"]) == 64


def test_adversarial_verification_rejects_malformed_verdicts() -> None:
    with pytest.raises(ValueError):
        aggregate_verification_votes([])
    with pytest.raises(ValueError):
        aggregate_verification_votes([{"lens": "x"}])
    with pytest.raises(ValueError):
        aggregate_verification_votes([{"refuted": "yes"}])
