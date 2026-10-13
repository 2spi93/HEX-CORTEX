"""CPU-only residual learning study on transparent synthetic operator data."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hex_cortex.memory.cortex_universal_world_loop_v26 import simulate_world_transition
from hex_cortex.memory.cortex_world_residual_learning_v27 import (
    fit_bounded_world_residual, simulate_with_reviewed_bias,
)


def _public_demo() -> list[dict[str, object]]:
    observations = []
    for index in range(8):
        state = {
            "x": float(index * 2), "y": float(index),
            "vx": 1.5, "vy": 0.25,
        }
        action = {"ax": 0.0, "ay": 0.0}
        dt = 2.0
        raw = simulate_world_transition(
            state=state, action=action, dt_seconds=dt, approved=True
        )["predicted_state"]
        # Deterministic hidden bias for the toy simulated environment only.
        actual = {
            "x": raw["x"] + .5 * .4 * dt ** 2,
            "y": raw["y"] + .5 * -.2 * dt ** 2,
            "vx": raw["vx"] + .4 * dt,
            "vy": raw["vy"] - .2 * dt,
        }
        observations.append({
            "id": f"demo-transition-{index}",
            "split": "train" if index < 4 else "test",
            "state": state, "action": action, "dt_seconds": dt,
            "observed_next_state": actual,
        })
    return observations


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded toy CPU world-model correction with disjoint test split."
    )
    parser.add_argument("--approve-fit", action="store_true")
    parser.add_argument("--approve-trial-apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "model_calls": 0,
            "training_performed": False, "files_read": False,
            "files_written": False, "gpu_used": False,
        }))
        return 0
    if not args.approve_fit:
        print(json.dumps({
            "status": "blocked", "reason": "world_learning_approval_required",
            "learning_performed": False, "files_written": False,
        }))
        return 2
    try:
        report = fit_bounded_world_residual(
            transitions=_public_demo(), approved=True,
        )
    except (ValueError, TypeError, OverflowError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    if args.approve_trial_apply:
        report["illustrative_approved_application"] = simulate_with_reviewed_bias(
            candidate=report,
            state={"x": 100.0, "y": 20.0, "vx": 1.5, "vy": .25},
            action={"ax": 0.0, "ay": 0.0},
            dt_seconds=2.0,
            approved=True,
        )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
