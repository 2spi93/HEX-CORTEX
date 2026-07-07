"""Bandit router — routing that learns from receipts.

Every executed task ends in an outcome receipt: model X succeeded or failed on
domain Y. This module turns those outcomes into routing intelligence with a
deterministic upper-confidence-bound rule: exploit the model with the best
observed success rate, but grant unexplored models an optimism bonus so the
kernel keeps measuring instead of freezing on first impressions. Benchmark
fingerprints (cortex_model_benchmark) seed the prior for cold starts.

Deterministic on purpose — no random sampling, so every routing decision is
replayable from the same stats. Pure and cold: stats in, ranking out.
"""

from __future__ import annotations

from math import log, sqrt

_STATS_TYPE = "cortex_routing_stats_v1"
_DECISION_TYPE = "cortex_bandit_routing_decision_v1"

# One virtual success and one virtual failure keep early rates conservative.
_PRIOR_WEIGHT = 2.0


def empty_routing_stats() -> dict[str, object]:
    """Return a fresh, empty routing statistics record."""

    return {"stats_type": _STATS_TYPE, "models": {}}


def update_routing_outcome(
    stats: dict[str, object],
    *,
    model_id: str,
    domain: str,
    success: bool,
) -> dict[str, object]:
    """Fold one task outcome into the stats. Pure: returns a new record."""

    if stats.get("stats_type") != _STATS_TYPE:
        raise ValueError("stats record has wrong type")
    if not model_id.strip() or not domain.strip():
        raise ValueError("model_id and domain must not be empty")

    models = {
        known_model: {known_domain: dict(cell) for known_domain, cell in domains.items()}
        for known_model, domains in stats["models"].items()  # type: ignore[union-attr]
    }
    cell = models.setdefault(model_id, {}).setdefault(domain, {"successes": 0, "failures": 0})
    cell["successes" if success else "failures"] += 1
    return {"stats_type": _STATS_TYPE, "models": models}


def _cell(stats: dict[str, object], model_id: str, domain: str) -> dict[str, int]:
    models = stats.get("models", {})
    return models.get(model_id, {}).get(domain, {"successes": 0, "failures": 0})  # type: ignore[union-attr]


def rank_models(
    stats: dict[str, object],
    *,
    domain: str,
    candidates: list[str],
    benchmark_priors: dict[str, float] | None = None,
    exploration_weight: float = 1.0,
) -> dict[str, object]:
    """Rank candidate models for one domain with a deterministic UCB rule.

    score = observed_rate (smoothed, seeded by the benchmark prior)
          + exploration_weight * sqrt(ln(total_trials + e) / trials_for_model)

    The bonus shrinks as a model accumulates trials, so measurement converges
    to pure exploitation exactly as fast as the evidence justifies.
    """

    if stats.get("stats_type") != _STATS_TYPE:
        raise ValueError("stats record has wrong type")
    if not domain.strip():
        raise ValueError("domain must not be empty")
    if not candidates:
        raise ValueError("candidates must not be empty")
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidates must be unique")
    if exploration_weight < 0.0:
        raise ValueError("exploration_weight must be >= 0")
    priors = benchmark_priors or {}
    if not all(0.0 <= value <= 1.0 for value in priors.values()):
        raise ValueError("benchmark priors must be within [0, 1]")

    total_trials = sum(
        _cell(stats, model_id, domain)["successes"] + _cell(stats, model_id, domain)["failures"]
        for model_id in candidates
    )

    ranking = []
    for model_id in candidates:
        cell = _cell(stats, model_id, domain)
        trials = cell["successes"] + cell["failures"]
        prior = priors.get(model_id, 0.5)
        # Smoothed rate: the benchmark prior acts as _PRIOR_WEIGHT virtual trials.
        rate = (cell["successes"] + prior * _PRIOR_WEIGHT) / (trials + _PRIOR_WEIGHT)
        bonus = exploration_weight * sqrt(log(total_trials + 2.718281828) / (trials + 1))
        ranking.append(
            {
                "model_id": model_id,
                "observed_successes": cell["successes"],
                "observed_failures": cell["failures"],
                "smoothed_rate": round(rate, 10),
                "exploration_bonus": round(bonus, 10),
                "score": round(rate + bonus, 10),
            }
        )

    # Deterministic tie-break on model_id keeps decisions replayable.
    ranking.sort(key=lambda row: (-row["score"], row["model_id"]))
    selected = ranking[0]["model_id"]
    reason = (
        "exploration_bonus_dominant"
        if ranking[0]["exploration_bonus"] > ranking[0]["smoothed_rate"]
        else "observed_rate_dominant"
    )
    return {
        "decision_type": _DECISION_TYPE,
        "domain": domain,
        "selected_model": selected,
        "ranking": ranking,
        "total_domain_trials": total_trials,
        "reasons": [reason],
        "model_call_performed": False,
        "next_action": "route_task_to_selected_model_then_report_outcome",
    }
