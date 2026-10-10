# HEX-CORTEX — Local Critic & Docker Sandbox V4

## Perimeter

All execution is **local**. This module never deploys to or contacts a VPS.
The default behavior is **AST-only with no execution of model-generated code**.
Docker execution is strictly opt-in. It works with a locally available
Docker Desktop **Linux containers** engine; it is not a requirement for the
normal HEX-CORTEX control plane.

## Fix: a model that does not exist is not a 0/4 score

The old command accepted `NOM_DU_MODELE` as though it were an installed
model. It attempted calls that failed and then incorrectly showed 0/4.
V4 checks the exact name against localhost Ollama `/api/tags` before the
benchmark starts and automatically reads the model's real digest and
quantization. A missing model gives `model_not_installed` and exit code 2.

Run the real installed model (example from operator's `ollama list`):

    ollama list
    ollama show qwen2.5-coder:7b
    hexcortex-repo-eval --model-id qwen2.5-coder:7b --approve-model --timeout 180 --max-tokens 1800

You no longer need to invent `--digest` or `--quantization` for a live
Ollama run; their defaults are `auto`, populated from the local runtime.
If explicitly specified, both values must match the local model metadata.

Live model calls returning no responses now fail with
`all_model_calls_failed` instead of printing 0/4. Partial failed calls
are counted separately as `model_call_failures`, with
`model_call_failed` rather than `candidate_rejected`.

For an offline `--responses` JSON run, explicitly provide an identity
(`--digest`, `--quantization`) because there is no Ollama preflight.

## Two independent verification levels

1. **Static (default)**: the established restricted AST interpreter
   validates small, pure Python repair proposals and scores 15 deterministic
   functional inputs per case without executing model-generated code.
2. **Docker tests (optional)**: only a candidate that *passes the strict
   AST validator* may be materialized in a disposable host temp folder and
   run in a local Docker container. Test cases are created by trusted code,
   not by the model. Actual Python imports and function calls are exercised
   inside the container. Results from both rails stay separate.

The independent critic reports `static_passed`, `sandbox_executed`,
`sandbox_passed`, and `verdict`. Even when both pass,
`trusted=false`, `allowed_to_modify_checkout=false`, and
`routing_prior_authorized=false`.

## Prepare optional local Docker

Docker Desktop must run Linux containers on the same PC. It must not be
configured to a remote Docker daemon. Do not use `DOCKER_HOST` overrides.

Docker does **not** automatically pull an image during evaluation.
A pre-approved local image named `python:3.11-slim` must already exist:

    docker context inspect
    docker image inspect python:3.11-slim

Only after reviewing the image and if absent, the operator may choose to
install it separately:

    docker pull python:3.11-slim

Then explicitly authorize local runtime testing:

    hexcortex-repo-eval --model-id qwen2.5-coder:7b --approve-model --approve-docker --timeout 180 --max-tokens 1800

The last command calls Ollama four times, with additional Docker runtime
tests only for candidates that have passed the static gate.

## Execution guardrails

- **No project checkout mount**: only a fresh temporary directory of
  allowlisted synthetic exercise files. Its mount is read-only.
- `--network=none`; `--pull=never`; `--read-only`;
  `--cap-drop=ALL`; `--security-opt=no-new-privileges`;
  `--pids-limit=64`; `--memory=256m`; `--cpus=1`;
  `--user=65534:65534`; and small no-exec `/tmp` tmpfs.
- No Docker socket mount, privileged flag, shell expansion or host network.
- Docker context is checked before invoking the image: remote SSH/TCP
  contexts are refused. `DOCKER_HOST` overrides are denied.
- Failed, missing, unavailable or remote engines produce a
  **blocked** result, never a false model quality score.
- The runner uses a hard timeout, attempts force cleanup on timeout,
  and deletes the temporary copy when finished.
- No raw candidate source or generated prompt in the returned report.

**Security limitation:** ordinary Docker Desktop containers reduce
exposure but are not a formal security boundary against genuinely hostile
programs or Docker daemon vulnerabilities. If stronger isolation is
required, prefer dedicated VM isolation; Docker Desktop Business enhanced
isolation also has feature/host prerequisites. No autonomous execution
permissions should be inferred from passing V4.

## Scope limitations

These exercises remain deliberately small, public and synthetically
constructed. Docker verifies the same prepared cases under CPython; it does
NOT benchmark arbitrary repositories, dependency installation, complete
development workflows, or general-purpose repair agents. Genuine external
held-out repair sets and richer independent critique remain follow-ups.

Docker documentation:
- https://docs.docker.com/engine/containers/run/
- https://docs.docker.com/enterprise/security/hardened-desktop/enhanced-container-isolation
