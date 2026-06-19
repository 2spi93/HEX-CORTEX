# Local Active Model Ramp V1

Status: cold plan.

This is the fastest safe path toward local active model mode.

## Definition of local active model mode

A local model is active only when HEX-CORTEX can perform an operator-approved advisory call against a local backend and persist a redacted receipt.

Active does not mean unlimited autonomy.

## Supported backend targets

Initial backend targets:

- mock,
- Ollama localhost,
- llama.cpp local path or localhost server,
- local OpenAI-compatible API on localhost.

## Ramp stages

### Stage 0 — Current state

Ready:

- config plan,
- config dry run,
- local contract,
- final local-only step,
- tests and lint green.

### Stage 1 — Backend presence check

Goal: verify the local backend exists without sending a user prompt.

Allowed evidence:

- service metadata,
- model list,
- version endpoint,
- localhost-only status,
- timeout result.

Blocked evidence:

- completions,
- raw prompt storage,
- raw model output storage,
- filesystem mutation,
- background scheduling.

### Stage 2 — First advisory call

Goal: one tiny non-sensitive prompt.

Rules:

- local backend only,
- no tools,
- no shell,
- no repo mutation,
- no secrets,
- no raw answer persistence,
- persist only redacted summary and hashes,
- output must match a fixed schema.

### Stage 3 — Expert routing

Goal: route requests to expert domains.

Domains:

- coding,
- research,
- geometry and universe,
- architecture,
- skill curation,
- defensive audit,
- hardware planning,
- mobile cockpit.

### Stage 4 — Learning from failures and successes

Goal: produce improvement proposals from evidence.

The model may propose:

- new skill candidate,
- preset candidate,
- doc update,
- test fixture,
- routing rule,
- confidence threshold.

The model may not auto-install or auto-execute the proposal.

### Stage 5 — Scheduled read-only curator

Goal: periodic local review of receipts and tests.

Allowed:

- read-only summaries,
- duplicate detection,
- stale skill detection,
- failure clustering,
- cost/latency notes.

Requires separate operator approval.

## Hard stop rules

Stop immediately if:

- backend is not localhost,
- response contains secret-like data,
- tool tries to mutate repo during advisory call,
- any shell action is requested,
- raw prompt or raw response persistence is attempted,
- tests or lint fail,
- confidence is below threshold.

## Next implementation target

`local_backend_presence_check_v1`

This should be a cold/dry-run capable module first. The actual localhost check must be a separate operator-approved step.
