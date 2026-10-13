# HEX-CORTEX V26 — Universal cognitive runtime, CPU first

The mission is a model-interchangeable **universal cognitive exoskeleton**,
not a calculator or coding-only product. V26 connects several already-present
components and tests live local paths without asserting that uninstalled
models or physical peripherals have become operational.

## Integrated paths

| Field | Wired path | Limitation |
|---|---|---|
| Mathematics | ExactMathCell + bounded methods + Harness | Procedural V25 Qwen study **0/4 both arms** |
| Physics/chemistry | Idealized science cells, verifiable memory | No physical validation or reaction feasibility |
| Vision | PNG metadata; opt-in cached DINOv2 CPU embedding | No object recognition or caption generation |
| Voice/audio | WAV metadata, operator-supplied transcripts | No automatic ASR or TTS |
| Voice control | Bilingual allowlisted transcripts -> virtual object | No microphone or real actuator |
| Coding | Python AST -> optional CPU Qwen -> existing StructuredCodePlan validator | No patch, shell, or code execution |
| Object control | Existing hardware-adapter registry -> simulated 2D cart | Real device dispatch is DENIED |
| World model | Multimodal receipts -> idealized 2D prediction -> operator-observation residual -> optional actual Harness + Brain | Not an active trained latent world model |

**Important existing project assets:** DINOv2 frozen encoder,
CompactWorldModel, ActionDiscriminativeWorldModel, world-model training and
evaluation, guarded world decision routing, CanonicalSpine, ReplayEngine,
CognitiveClock, skill library and Gateway. These exist but the advanced
latent model still needs local weights, validated datasets and tested runtime.

## Architecture

Observation receipts are source-hashed and keep raw images/audio out of
Spine. Approved telemetry establishes a typed initial state. A **CPU-only
idealized kinematic** simulation predicts x,y,vx,vy. A separate
operator-supplied next state gives a measurable position/velocity residual.
An optionally authorized local model receives only approved metadata,
the prediction and residual, and provides read-only advice. Model-generated
advice is NOT externally verified science and is not a physical command.

File/source access, model calls, simulation and disclosure all have
separate approval gates. Nothing opens a microphone, runs shell commands,
controls motors, writes receipts or downloads model weights implicitly.

## Commands (each is a single physical Windows PowerShell line)

Synchronize + full validation:

~~~powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
~~~

Read-only capability status, optional package detection but no model calls:

~~~powershell
python -m hex_cortex.memory.cortex_universal_capability_probe_v26
~~~

Dry-run universal world, zero actual operations:

~~~powershell
python -m hex_cortex.memory.cortex_universal_world_cli_v26 --project-root . --dry-run
~~~

Approved mathematical **world simulation only**: initial x=0,
vx=2m/s, after 2s predicts x=4m; an illustrative separate
observation x=3m generates a 1m positional residual.

~~~powershell
python -m hex_cortex.memory.cortex_universal_world_cli_v26 --project-root . --approve-observe --approve-simulate
~~~

Same simulation + one real CPU Qwen advisory response:

~~~powershell
python -m hex_cortex.memory.cortex_universal_world_cli_v26 --project-root . --model qwen2.5:3b --approve-observe --approve-simulate --approve-model --show-answer
~~~

French operator voice **text**, simulated virtual cart only:

~~~powershell
python -m hex_cortex.memory.cortex_voice_simulation_cli_v26 --transcript "simule le mouvement" --approve-transcript --approve-simulation
~~~

Approved read-only static code inspection (no model or patch):

~~~powershell
python -m hex_cortex.memory.cortex_code_review_cli_v26 --project-root . --file src/hex_cortex/memory/cortex_universal_world_loop_v26.py --approve-read
~~~

Optional real CPU Qwen Coder structured plan; **AST metadata only** is
sent unless an extra source-disclosure permission is supplied.

~~~powershell
python -m hex_cortex.memory.cortex_code_review_cli_v26 --project-root . --file src/hex_cortex/memory/cortex_universal_world_loop_v26.py --model qwen2.5-coder:7b --approve-read --approve-model
~~~

Cached frozen DINOv2 vision **dry run**:

~~~powershell
python -m hex_cortex.memory.cortex_local_vision_cli_v26 --project-root . --image receipts/example.png --dry-run
~~~

For real DINOv2: a local selected PNG, Pillow/Transformers/Torch and a
**previously cached** model are required. Explicit read and encode
approvals are required. No automatic download, GPU, online image
recognition or semantic caption is involved. Vision processing yields a
numerical embedding hash, not a scene description.

## Current research and engineering gaps

Real ASR/TTS, robust scene/object detection, computer perception,
multi-sensor calibration and timestamps, trained/persisted latent world
predictors, true causal action models, operator-safe robotics with
independent interlocks, code changes in a sandbox, and wider biology/
engineering/scientific cells remain separate work. No physical actuation
will be implemented without a dedicated safety contract and controls.
Success in a sandbox does not prove real-world device safety.

Never infer general intelligence gain from successful module integration
alone: compare an unchanged model with/without each tool on independently
held-out tasks including latency, error, cost and regressions.
