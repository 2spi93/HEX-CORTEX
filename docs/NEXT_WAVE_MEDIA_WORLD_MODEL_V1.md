# Media Runtime and World Model v1

This package follows the runtime, research, and federation integration wave.

## Safety boundaries

- Media generation is disabled by default.
- Local media calls require an explicit flag and operator approval.
- Media endpoints are restricted to explicit localhost HTTP endpoints.
- Prompts and workflow payloads are represented by hashes in receipts.
- Latent experiments use hash-only storage.
- Dataset manifests reference observations by hashes rather than embedding raw data.
- Model candidates remain inactive until evaluation and human review.

## Media runtime

`cortex_media_runtime.py` provides:

- local service descriptors for image, video, and 3D tasks;
- health receipts;
- bounded dimensions, frame counts, seeds, and workflow identifiers;
- prompt and workflow hashes;
- reviewed workflow submission contracts;
- no raw prompt, response, or workflow persistence.

Offline planning example:

```powershell
hexcortex-wave media-plan generate_image "A compact system diagram"
```

A real local call also requires a reviewed API workflow, the network flag, and operator approval.

## Latent world-model lab

`cortex_latent_lab.py` and `cortex_latent_experiment.py` define a compact action-conditioned transition contract:

```text
state_t + action_t -> predicted_state_t+1
```

The baseline includes fixed dimensions, bounded horizons, deterministic transitions, multi-step rollout, prediction error, surprise scoring, and hash-only receipts.

```powershell
hexcortex-wave latent-spec --latent-dim 8 --action-dim 4 --horizons 1,4,16
hexcortex-wave latent-demo --latent-dim 4 --action-dim 2
```

This baseline validates contracts and metrics. It does not claim to be a trained visual world model.

## Training and evaluation contract

`cortex_world_model_eval.py` provides:

- hash-referenced dataset manifests;
- mandatory train, validation, and test splits;
- bounded run plans;
- candidate-versus-baseline evaluation;
- fail-closed baseline retention when a required metric regresses.

The run-plan constructor never starts a run and never writes a checkpoint.

## Audit and validation

```powershell
python -m pip install -e ".[dev]"
python -m pytest
ruff check .

hexcortex-wave audit --project-root .
hexcortex-wave media-plan generate_image "A test diagram"
hexcortex-wave latent-spec
hexcortex-wave latent-demo
```

The audit is filesystem-only. It does not probe a process, network endpoint, model, or GPU.

## Next operational steps

1. Health-check a local ComfyUI service.
2. Review one API-format workflow per approved media capability.
3. Connect a frozen external encoder behind an adapter contract.
4. Collect hash-referenced state, action, and next-state samples.
5. Implement bounded runs from the run-plan contract.
6. Compare every candidate with a frozen baseline before human review.
