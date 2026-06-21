"""Unit tests for the operator-approved live brain benchmark harness.

The benchmark calls a live model, but its task ground-truth, grading, and
statistics are pure functions. These tests lock those in without any network
call, so a regression in the scoring logic is caught offline.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "bench_brain", Path(__file__).resolve().parent.parent / "scripts" / "bench_brain.py"
)
assert _SPEC is not None and _SPEC.loader is not None
bench_brain = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bench_brain)


def test_each_domain_has_at_least_thirty_tasks() -> None:
    assert len(bench_brain.build_coding_tasks()) >= 30
    assert len(bench_brain.build_general_tasks()) >= 30
    assert len(bench_brain.RESEARCH_TASKS) >= 30


def test_tasks_are_well_formed_triples() -> None:
    every = (
        bench_brain.build_coding_tasks()
        + bench_brain.build_general_tasks()
        + list(bench_brain.RESEARCH_TASKS)
    )
    for prompt, expected, is_numeric in every:
        assert isinstance(prompt, str) and prompt
        assert isinstance(expected, str) and expected
        assert isinstance(is_numeric, bool)
        if is_numeric:
            float(expected)  # every numeric ground-truth must parse


def test_grade_numeric_is_comma_and_symbol_insensitive() -> None:
    assert bench_brain.grade("The answer is 1,234.", "1234", True) == 1
    assert bench_brain.grade("$0.05", "0.05", True) == 1
    assert bench_brain.grade("It is 99", "100", True) == 0
    assert bench_brain.grade("no number here", "42", True) == 0


def test_grade_text_is_normalized_substring() -> None:
    assert bench_brain.grade("  Tokyo  ", "tokyo", False) == 1
    assert bench_brain.grade("The capital is Paris.", "paris", False) == 1
    assert bench_brain.grade("London", "paris", False) == 0


def test_ground_truth_values_are_correct() -> None:
    coding = dict((p, e) for p, e, _ in bench_brain.build_coding_tasks())
    # 1^2+..+10^2 = 385
    assert coding["Reply with ONLY the integer: the sum 1^2+2^2+...+10^2."] == "385"
    # 6! = 720
    assert coding["Reply with ONLY the value of 6 factorial."] == "720"


def test_summary_reports_mean_stdev_and_ci() -> None:
    mean, sd, ci = bench_brain._summary([0.8, 0.9, 1.0])
    assert mean == 0.9
    assert sd > 0
    assert ci > 0
    mean1, sd1, ci1 = bench_brain._summary([0.7])
    assert (mean1, sd1, ci1) == (0.7, 0.0, 0.0)


def test_percentile_orders_values() -> None:
    assert bench_brain._percentile([10, 20, 30, 40], 50) in (20.0, 30.0)
    assert bench_brain._percentile([10, 20, 30, 40], 95) == 40.0
    assert bench_brain._percentile([], 95) == 0.0
