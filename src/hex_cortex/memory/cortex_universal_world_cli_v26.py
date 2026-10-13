"""Run approved local multimodal -> toy world -> residual -> optional Qwen.

No microphone or camera capture, no physical execution, no network except
an explicit operator-approved localhost Ollama call, CPU-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_universal_sensing_v26 import (
    observe_local_file, observe_telemetry, observe_transcript,
)
from hex_cortex.memory.cortex_universal_world_loop_v26 import (
    run_universal_world_advisory,
)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Offline CPU world simulation with opt-in local sensory files and Qwen."
    )
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--image", type=Path)
    p.add_argument("--audio", type=Path)
    p.add_argument("--code", type=Path)
    p.add_argument("--transcript")
    p.add_argument("--model")
    p.add_argument("--endpoint", default="http://127.0.0.1:11434")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--max-tokens", type=int, default=160)
    p.add_argument("--show-answer", action="store_true")
    p.add_argument("--approve-observe", action="store_true")
    p.add_argument("--approve-simulate", action="store_true")
    p.add_argument("--approve-model", action="store_true")
    p.add_argument("--state-x", type=float)
    p.add_argument("--state-y", type=float)
    p.add_argument("--state-vx", type=float)
    p.add_argument("--state-vy", type=float)
    p.add_argument("--action-ax", type=float)
    p.add_argument("--action-ay", type=float)
    p.add_argument("--dt-seconds", type=float)
    p.add_argument("--observed-x", type=float)
    p.add_argument("--observed-y", type=float)
    p.add_argument("--observed-vx", type=float)
    p.add_argument("--observed-vy", type=float)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "files_written": False, "model_calls": 0, "gpu_requested": False,
            "hardware_polled": False, "physical_action_executed": False,
            "planned_modalities": ["telemetry"] + [
                k for k in ("image", "audio", "code", "transcript")
                if getattr(args, k) is not None
            ],
        }, sort_keys=True))
        return 0
    if not args.approve_observe or not args.approve_simulate:
        print(json.dumps({"status": "blocked",
                          "reason": "observation_and_simulation_approvals_required",
                          "model_calls": 0}))
        return 2
    if args.approve_model and not args.model:
        p.error("--approve-model requires --model")
    try:
        root = args.project_root.resolve(strict=True)
        state = {
            "x": 0.0 if args.state_x is None else args.state_x,
            "y": 0.0 if args.state_y is None else args.state_y,
            "vx": 2.0 if args.state_vx is None else args.state_vx,
            "vy": 0.0 if args.state_vy is None else args.state_vy,
        }
        action = {
            "ax": 0.0 if args.action_ax is None else args.action_ax,
            "ay": 0.0 if args.action_ay is None else args.action_ay,
        }
        dt_seconds = 2.0 if args.dt_seconds is None else args.dt_seconds
        observed_parts = (args.observed_x, args.observed_y, args.observed_vx, args.observed_vy)
        if any(value is not None for value in observed_parts) and not all(
            value is not None for value in observed_parts
        ):
            raise ValueError("world_observed_state_requires_all_four_coordinates")
        customized = any(
            value is not None for value in (
                args.state_x, args.state_y, args.state_vx, args.state_vy,
                args.action_ax, args.action_ay, args.dt_seconds,
            )
        )
        if all(value is not None for value in observed_parts):
            observed = {
                "x": args.observed_x, "y": args.observed_y,
                "vx": args.observed_vx, "vy": args.observed_vy,
            }
            observation_origin = "operator_supplied"
        elif customized:
            observed = None
            observation_origin = "operator_supplied"
        else:
            observed = {"x": 3.0, "y": 0.0, "vx": 2.0, "vy": 0.0}
            observation_origin = "illustrative_fixture"
        observations = [observe_telemetry(state=state, approved=True)]
        for modality in ("image", "audio", "code"):
            path = getattr(args, modality)
            if path is not None:
                observations.append(observe_local_file(
                    path=path, root=root, modality=modality, approved=True,
                ))
        if args.transcript is not None:
            observations.append(observe_transcript(text=args.transcript, approved=True))
        brain = (
            LocalOllamaBrain(
                endpoint=args.endpoint, timeout_seconds=args.timeout,
                max_predict_tokens=args.max_tokens, num_gpu=0,
            )
            if args.approve_model else None
        )
        output = run_universal_world_advisory(
            project_root=root, observations=observations,
            state=state,
            action=action,
            dt_seconds=dt_seconds,
            actual_next_state=observed,
            observation_origin=observation_origin,
            model_id=args.model if args.approve_model else None,
            brain=brain,
            approve_simulation=True, approve_model=args.approve_model,
        )
    except (OSError, ValueError, PermissionError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    answer = output.pop("model_answer", None)
    output["model_answer_sha256"] = (
        hashlib.sha256(answer.encode()).hexdigest() if isinstance(answer, str) else None
    )
    if args.show_answer and args.approve_model:
        output["model_answer"] = answer
    print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    return 0 if output["status"] in {"simulated_advisory", "complete"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
