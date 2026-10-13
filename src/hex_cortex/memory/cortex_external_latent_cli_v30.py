"""Operator-gated local external latent audit and optional real CPU checkpoint.

No download, training, GPU, file write, activation, or hardware control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_compact_external_adapter_v30 import (
    evaluate_local_compact_on_external,
)
from hex_cortex.memory.cortex_external_latent_evaluation_v30 import (
    audit_external_latent_trajectories,
    read_external_latent_jsonl,
)


def _synthetic_example() -> list[dict[str, object]]:
    encoder = hashlib.sha256(b"synthetic-encoder-demo-only").hexdigest()
    examples = []
    for split, number, env in [
        ("train", 0, "lab-a"), ("train", 1, "lab-b"),
        ("validation", 2, "lab-c"),
        ("test", 3, "lab-d"), ("test", 4, "lab-e"),
        ("test", 5, "lab-d"),
    ]:
        examples.append({
            "sample_id": f"synthetic-{number}",
            "source_dataset": "synthetic_v30_example_not_real",
            "episode_id": f"episode-{number}",
            "environment_id": env,
            "split": split, "timestamp_seconds": float(number),
            "encoder_descriptor_hash": encoder,
            "state_latent": [float(number), 0.5],
            "action": [float(number) / 10],
            "next_state_latent": [float(number) + .1, 0.75],
        })
    return examples


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assess independently grouped latent trajectories and real compact weights."
    )
    parser.add_argument("--jsonl", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--approve-inference", action="store_true")
    parser.add_argument("--synthetic-example", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "file_reads": 0,
            "model_calls": 0, "files_written": False,
            "network_called": False, "gpu_requested": False,
        }, sort_keys=True))
        return 0
    if args.synthetic_example and (args.jsonl or args.candidate or args.approve_inference):
        parser.error("--synthetic-example cannot be combined with actual data/model inference")
    if not args.synthetic_example and not args.jsonl:
        parser.error("provide --jsonl or --synthetic-example")
    if args.approve_inference and (not args.candidate or not args.approve_read):
        parser.error("--approve-inference requires --candidate and --approve-read")
    if args.candidate and not args.approve_inference:
        parser.error("--candidate requires --approve-inference")
    if args.jsonl and not args.approve_read:
        print(json.dumps({
            "status": "blocked", "reason": "external_latent_file_read_requires_approval",
            "model_calls": 0,
        }))
        return 2
    try:
        records = (
            _synthetic_example() if args.synthetic_example else
            read_external_latent_jsonl(args.jsonl, approved=True)
        )
        audit = audit_external_latent_trajectories(records)
        public = {k: v for k, v in audit.items() if k != "records"}
        public["synthetic_example_only"] = bool(args.synthetic_example)
        if args.approve_inference and audit["audit_allowed"]:
            public["comparison"] = evaluate_local_compact_on_external(
                audit, candidate_manifest_path=args.candidate, approved=True
            )
        elif args.approve_inference:
            public["comparison"] = {"status": "blocked", "reason": "external_dataset_audit_failed"}
    except (ValueError, OSError, PermissionError, OverflowError, RuntimeError) as exc:
        print(json.dumps({
            "status": "blocked", "reason": str(exc),
            "files_written": False,
        }))
        return 2
    print(json.dumps(public, sort_keys=True, ensure_ascii=False))
    return 0 if audit["audit_allowed"] and (
        not args.approve_inference or public["comparison"]["status"] == "heldout_latent_comparison_recorded"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
