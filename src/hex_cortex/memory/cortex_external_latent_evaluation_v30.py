"""External action-conditioned latent trajectory audit and comparable CPU evaluation.

Strictly read-only. A declared data origin is NOT independently attested.
The expected encoder is the already-existing frozen-encoder/compact predictor
contract. No dataset fetch, model download, GPU, checkpoint writing,
automatic promotion or physical device action is performed.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from hex_cortex.memory.cortex_world_model_eval import (
    build_world_model_dataset_manifest,
    evaluate_world_model_candidate,
)

_SPLITS = ("train", "validation", "test")
_MAX_ROWS = 1000
_MAX_BYTES = 8_000_000


def _hash(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        .encode("utf-8")
    ).hexdigest()


def _vector(obj: object, *, minimum: int = 1, maximum: int = 2048) -> list[float]:
    if (
        not isinstance(obj, list) or not minimum <= len(obj) <= maximum
        or any(type(v) not in (int, float) or not math.isfinite(v)
               or abs(v) > 100_000 for v in obj)
    ):
        raise ValueError("external_latent_invalid_bounded_numeric_vector")
    return [float(value) for value in obj]


def _name(value: object, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 100:
        raise ValueError(f"external_latent_invalid_{field}")
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"external_latent_invalid_{field}")
    return value


def audit_external_latent_trajectories(
    records: Sequence[dict[str, object]],
    *, expected_encoder_hash: str | None = None,
    min_test_environments: int = 2,
) -> dict[str, object]:
    """No training; independently grouped episodic partitions.

    Assumes the operator has independently converted observations to vectors.
    Checks structural consistency, distinct episodes/environments and
    leakage patterns, never certifies external dataset provenance.
    """
    if not isinstance(records, (tuple, list)) or not 6 <= len(records) <= _MAX_ROWS:
        raise ValueError("external_latent_row_count_invalid")
    if not 1 <= min_test_environments <= 10:
        raise ValueError("external_latent_environment_requirement_invalid")
    parsed: list[dict[str, object]] = []
    dim_pair: tuple[int, int] | None = None
    encoder_refs: set[str] = set()
    episode_splits: dict[tuple[str, str], str] = {}
    environment_splits: dict[tuple[str, str], set[str]] = defaultdict(set)
    times: dict[tuple[str, str], list[float]] = defaultdict(list)
    sample_ids: set[str] = set()
    all_transition_hashes: set[str] = set()
    for entry in records:
        if not isinstance(entry, dict) or set(entry) != {
            "sample_id", "source_dataset", "episode_id", "environment_id",
            "split", "timestamp_seconds", "encoder_descriptor_hash",
            "state_latent", "action", "next_state_latent",
        }:
            raise ValueError("external_latent_record_schema_invalid")
        sample_id = _name(entry["sample_id"], "sample_id")
        if sample_id in sample_ids:
            raise ValueError("external_latent_duplicate_sample_id")
        sample_ids.add(sample_id)
        source = _name(entry["source_dataset"], "source_dataset")
        episode = _name(entry["episode_id"], "episode_id")
        environment = _name(entry["environment_id"], "environment_id")
        split = entry["split"]
        if split not in _SPLITS:
            raise ValueError("external_latent_split_invalid")
        encoder = _name(entry["encoder_descriptor_hash"], "encoder_descriptor_hash")
        if len(encoder) != 64 or any(c not in "0123456789abcdef" for c in encoder):
            raise ValueError("external_latent_encoder_sha256_invalid")
        encoder_refs.add(encoder)
        start = _vector(entry["state_latent"], minimum=2)
        target = _vector(entry["next_state_latent"], minimum=2)
        action = _vector(entry["action"], maximum=64)
        if len(start) != len(target):
            raise ValueError("external_latent_target_dimension_mismatch")
        sizes = len(start), len(action)
        if dim_pair is not None and sizes != dim_pair:
            raise ValueError("external_latent_inconsistent_dimensions")
        dim_pair = sizes
        timestamp = entry["timestamp_seconds"]
        if type(timestamp) not in (float, int) or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("external_latent_timestamp_invalid")
        episode_key = (source, episode)
        if episode_key in episode_splits and episode_splits[episode_key] != split:
            raise ValueError("external_latent_episode_crosses_splits")
        episode_splits[episode_key] = split
        environment_splits[(source, environment)].add(split)
        times[episode_key].append(float(timestamp))
        # Exact duplicate action/state/next-state tuples across samples or
        # domains are potential replay leakage, even if IDs differ.
        signature = _hash([start, action, target])
        if signature in all_transition_hashes:
            raise ValueError("external_latent_duplicate_transition")
        all_transition_hashes.add(signature)
        parsed.append({
            "sample_id": sample_id, "source_dataset": source,
            "episode_id": episode, "environment_id": environment,
            "split": split, "timestamp_seconds": float(timestamp),
            "encoder_descriptor_hash": encoder,
            "state_latent": start, "action": action,
            "next_state_latent": target,
            "source_transition_hash": signature,
        })
    if len(encoder_refs) != 1:
        raise ValueError("external_latent_mixed_encoders")
    if expected_encoder_hash is not None and encoder_refs != {expected_encoder_hash}:
        raise ValueError("external_latent_encoder_candidate_mismatch")
    for stamp_list in times.values():
        if len(stamp_list) != len(set(stamp_list)):
            raise ValueError("external_latent_duplicate_timestamp_in_episode")
    for seen_splits in environment_splits.values():
        if len(seen_splits) > 1:
            raise ValueError("external_latent_environment_crosses_splits")
    counts = {split: sum(p["split"] == split for p in parsed) for split in _SPLITS}
    groups = {
        split: len({(r["source_dataset"], r["episode_id"])
                   for r in parsed if r["split"] == split})
        for split in _SPLITS
    }
    test_envs = {(r["source_dataset"], r["environment_id"])
                 for r in parsed if r["split"] == "test"}
    blockers = []
    if any(count < 1 for count in counts.values()):
        blockers.append("all_splits_required")
    if groups["train"] < 2 or groups["test"] < 2:
        blockers.append("multiple_independent_episodes_required")
    if len(test_envs) < min_test_environments:
        blockers.append("independent_test_environments_insufficient")
    if counts["test"] < 2:
        blockers.append("test_sample_count_insufficient")
    existing_manifest = build_world_model_dataset_manifest([
        {
            "sample_id": row["sample_id"], "split": row["split"],
            "state_hash": _hash(row["state_latent"]),
            "action_hash": _hash(row["action"]),
            "next_state_hash": _hash(row["next_state_latent"]),
        }
        for row in parsed
    ])
    if not existing_manifest["manifest_allowed"]:
        blockers.extend(existing_manifest["blockers"])
    return {
        "status": "external_latent_audit_pass" if not blockers else "external_latent_audit_blocked",
        "audit_allowed": not blockers,
        "blockers": sorted(set(blockers)),
        "sample_count": len(parsed), "split_counts": counts,
        "episode_group_counts": groups,
        "test_environment_count": len(test_envs),
        "encoder_descriptor_hash": next(iter(encoder_refs)),
        "latent_dim": dim_pair[0] if dim_pair else None,
        "action_dim": dim_pair[1] if dim_pair else None,
        "existing_world_model_manifest_hash": existing_manifest["manifest_hash"],
        "external_manifest_hash": _hash([
            {k: v for k, v in row.items()
             if k not in ("state_latent", "action", "next_state_latent")}
            for row in parsed
        ]),
        "records": parsed,  # in-memory for evaluation ONLY; never print
        "independent_source_attested": False,
        "real_world_origin_verified": False,
        "raw_vectors_persisted": False,
        "model_called": False,
        "files_written": False,
        "automatic_promotion": False,
    }


def evaluate_external_latent_predictions(
    audit: dict[str, object],
    *,
    predictor: Callable[[list[float], list[float]], list[float]],
    predictor_kind: str = "operator_supplied_callable",
    candidate_weights_verified: bool = False,
) -> dict[str, object]:
    if audit.get("audit_allowed") is not True:
        raise ValueError("external_latent_audit_must_pass_before_evaluation")
    if not callable(predictor):
        raise ValueError("external_latent_predictor_required")
    test = [row for row in audit["records"] if row["split"] == "test"]
    losses: dict[str, list[float]] = {"identity": [], "candidate": []}
    by_env: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for row in test:
        start = row["state_latent"]
        target = row["next_state_latent"]
        prediction = _vector(predictor(list(start), list(row["action"])), minimum=2)
        if len(prediction) != len(target):
            raise ValueError("external_latent_prediction_dim_mismatch")
        baseline = sum((a - b) ** 2 for a, b in zip(start, target, strict=True)) / len(target)
        candidate = sum((a - b) ** 2 for a, b in zip(prediction, target, strict=True)) / len(target)
        if not all(math.isfinite(value) for value in (baseline, candidate)):
            raise ValueError("external_latent_loss_not_finite")
        losses["identity"].append(baseline)
        losses["candidate"].append(candidate)
        by_env[(row["source_dataset"], row["environment_id"])].append(
            (baseline, candidate)
        )
    mean_base = sum(losses["identity"]) / len(test)
    mean_candidate = sum(losses["candidate"]) / len(test)
    legacy = evaluate_world_model_candidate(
        baseline={"prediction_error": mean_base},
        candidate={"prediction_error": mean_candidate},
        required_metrics=["prediction_error"],
        max_regression_fraction=0.0,
        minimum_improvement_fraction=0.01,
    )
    env_rows = [
        {
            "environment_hash": _hash([source, env]),
            "count": len(pairs),
            "identity_mse": round(sum(pair[0] for pair in pairs) / len(pairs), 10),
            "candidate_mse": round(sum(pair[1] for pair in pairs) / len(pairs), 10),
            "candidate_worse": sum(pair[1] for pair in pairs) >
            sum(pair[0] for pair in pairs) + 1e-12,
        }
        for (source, env), pairs in sorted(by_env.items())
    ]
    regressions = sum(row["candidate_worse"] for row in env_rows)
    return {
        "status": "heldout_latent_comparison_recorded",
        "predictor_kind": predictor_kind,
        "candidate_weights_verified": candidate_weights_verified,
        "existing_world_candidate_evaluation": legacy,
        "identity_mse": round(mean_base, 10),
        "candidate_mse": round(mean_candidate, 10),
        "test_count": len(test),
        "test_environment_results": env_rows,
        "regressed_environment_count": regressions,
        "qualified_for_manual_review": bool(
            candidate_weights_verified and legacy["promotion_allowed"] and
            regressions == 0
        ),
        "independent_test_origin_attested": False,
        "encoder_semantic_equivalence_attested": False,
        "real_world_generalization_proven": False,
        "model_activated": False, "files_written": False,
        "physical_action_executed": False,
    }


def read_external_latent_jsonl(path: Path, *, approved: bool = False) -> list[dict[str, object]]:
    if not approved:
        raise PermissionError("external_latent_file_read_requires_approval")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
        raise ValueError("external_latent_input_file_denied")
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                raise ValueError("external_latent_empty_line")
            if len(line) > 100_000:
                raise ValueError("external_latent_line_too_large")
            try:
                record = json.loads(line)
            except (ValueError, UnicodeError) as exc:
                raise ValueError("external_latent_invalid_jsonl") from exc
            records.append(record)
            if len(records) > _MAX_ROWS:
                raise ValueError("external_latent_too_many_rows")
    return records
