# V27 — Structured Coding and Verified World Residual Learning

## Results motivating the integration

Operator machine V26: 1921 pytest tests passed; Ruff PASS. Actual
CPU Qwen2.5:3b answered the world simulator read-only advisory. Actual
Qwen2.5-coder:7b returned a response that failed the existing
StructuredCodePlan validator; no patch or command was executed.

## Coding improvement

LocalOllamaBrain now supports opt-in native Ollama JSON schema output,
defaulting to no formatting request for other callers. The coding CLI
passes the existing StructuredCodePlan JSON schema, supplies a complete
JSON example and enum list, and uses 1536 tokens by default. A rejected
response is represented by expurgated plan-error type and digest. Model
inference runs within one real approved LocalHarness/CognitiveClock call.

The model sees ONLY AST metadata by default. Sharing the complete Python
source requires an additional explicit approval, and a limited secret
scan; neither a successful JSON parse nor the secret scan proves correctness
or complete safety. Code edits, terminal commands and external providers
are not authorized.

## World learning improvement

V27 adds bounded constant acceleration bias fitting on approved 2D
transitions. It checks train/test identity, requires at least 3 training
and 3 different test transitions, and reports normalized baseline and
candidate mean squared errors, improvement and regressions. A candidate
for MANUAL review needs at least 10% improvement and zero regressions.
An additional approval lets the user apply the candidate to an entirely
virtual new trajectory. Nothing is auto-promoted or written to disk.

These test data are synthetic, not independent real-world measurements.
This is real low-dimensional CPU parameter fitting, NOT the existing
trained DINOv2/latent predictor, general intelligence or robust causal
world modelling.

## V26 sensor provenance correction

The built-in example has x=0, vx=2m/s, predicts x=4m after 2s and
compares an ILLUSTRATIVE fictitious state x=3m for a 1m residual. This
was previously called an operator-measured value in the model prompt.
Now the receipt and prompt explicitly mark it as an illustrative fixture,
not real sensor evidence.

The world CLI also accepts numeric user-supplied state/action/duration
and optionally an entire observed next state; incomplete observations
are refused. A custom state without a next observation does not
fabricate a residual.

## Windows PowerShell — every command on ONE physical line

Update and validate:

~~~powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
~~~

Repeat the previously invalid Qwen Coder result with JSON-schema output:

~~~powershell
python -m hex_cortex.memory.cortex_code_review_cli_v26 --project-root . --file src/hex_cortex/memory/cortex_universal_world_loop_v26.py --model qwen2.5-coder:7b --approve-read --approve-model --max-tokens 1536
~~~

Optional substantive code review: explicitly disclose source to local
Ollama with the additional flag shown here. No patch is applied.

~~~powershell
python -m hex_cortex.memory.cortex_code_review_cli_v26 --project-root . --file src/hex_cortex/memory/cortex_universal_world_loop_v26.py --model qwen2.5-coder:7b --approve-read --approve-model --approve-share-source --max-tokens 1536
~~~

Learn residual correction and try it on a fresh synthetic trajectory
without a model call, GPU, file write or real device:

~~~powershell
python -m hex_cortex.memory.cortex_world_residual_cli_v27 --approve-fit --approve-trial-apply
~~~

World simulation default illustrative fixture, no Ollama:

~~~powershell
python -m hex_cortex.memory.cortex_universal_world_cli_v26 --project-root . --approve-observe --approve-simulate
~~~

Custom operator state without pretending to measure next state:

~~~powershell
python -m hex_cortex.memory.cortex_universal_world_cli_v26 --project-root . --approve-observe --approve-simulate --state-x 10 --state-vx 3 --dt-seconds 2
~~~

Optional actual operator-provided next state for residual comparison:

~~~powershell
python -m hex_cortex.memory.cortex_universal_world_cli_v26 --project-root . --approve-observe --approve-simulate --state-x 10 --state-vx 3 --dt-seconds 2 --observed-x 15 --observed-y 0 --observed-vx 3 --observed-vy 0
~~~

## Still missing

Validated real ASR, calibrated image understanding, a trained and
held-out evaluated visual latent world predictor, sensor time stamps,
action-conditioned world modelling at scale, independent coding patch
review and sandbox execution, human/device safe control and general model
transfer evidence remain separate milestones. A successful CI run is a
software integration result, NOT proof of real-world competence or safety.
