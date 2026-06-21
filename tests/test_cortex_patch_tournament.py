import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_patch_tournament import rank_patch_candidates


def _cand(patch_id: str, **over: object) -> dict[str, object]:
    base = {
        "patch_id": patch_id,
        "tests_total": 10,
        "tests_passed": 10,
        "regressions": 0,
        "lint_clean": True,
        "types_clean": True,
        "adversarial_refuted": False,
        "diff_size_lines": 20,
    }
    base.update(over)
    return base


def test_picks_eligible_patch() -> None:
    result = rank_patch_candidates([_cand("a"), _cand("b", tests_passed=8)])
    assert result["status"] == "ready"
    assert result["winner_patch_id"] == "a"
    assert result["eligible_count"] == 1


def test_compactness_breaks_ties_between_equal_quality() -> None:
    result = rank_patch_candidates([_cand("big", diff_size_lines=400), _cand("small", diff_size_lines=10)])
    assert result["winner_patch_id"] == "small"


def test_regression_disqualifies_even_with_all_tests_green() -> None:
    result = rank_patch_candidates([_cand("regress", regressions=1)])
    assert result["status"] == "blocked"
    assert result["winner_patch_id"] is None
    assert "introduces_regressions" in result["ranked"][0]["failed_gates"]


def test_adversarial_refuted_disqualifies() -> None:
    result = rank_patch_candidates([_cand("refuted", adversarial_refuted=True)])
    assert result["status"] == "blocked"
    assert "adversarial_refuted" in result["ranked"][0]["failed_gates"]


def test_failing_tests_disqualify() -> None:
    result = rank_patch_candidates([_cand("partial", tests_passed=9)])
    assert result["status"] == "blocked"
    assert "tests_not_all_green" in result["ranked"][0]["failed_gates"]


def test_lint_and_types_rank_above_dirty_but_correct() -> None:
    clean = _cand("clean")
    dirty = _cand("dirty", lint_clean=False, types_clean=False)
    result = rank_patch_candidates([dirty, clean])
    assert result["winner_patch_id"] == "clean"
    # Both are eligible (tests green, no regressions, not refuted).
    assert result["eligible_count"] == 2


def test_receipt_hashes_diff_and_never_stores_raw(tmp_path: Path) -> None:
    receipt = tmp_path / "tourney.jsonl"
    rank_patch_candidates(
        [_cand("a", diff="--- secret diff body ---\n+payload")],
        receipt_path=receipt,
    )
    text = receipt.read_text(encoding="utf-8")
    assert "secret diff body" not in text
    row = json.loads(text.splitlines()[0])
    assert row["raw_diff_persisted"] is False
    assert len(row["ranked"][0]["diff_hash"]) == 64


def test_invalid_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        rank_patch_candidates([])
    with pytest.raises(ValueError):
        rank_patch_candidates([{"patch_id": "x", "tests_total": 5, "tests_passed": 9}])
    with pytest.raises(ValueError):
        rank_patch_candidates([{"tests_total": 1, "tests_passed": 1}])
