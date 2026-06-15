# Environment Strategy v0.1

HEX-CORTEX must be built local-first.

The project is experimental and will involve routing, local inference, memory stores, workers, logs, and eventually GPU-backed serving. Running unstable experiments directly on a shared server that already hosts other projects is not acceptable.

## Decision

```text
Local machine = laboratory
Existing server = staging / stable runtime later
```

## Local development

Use local development for:

- architecture work
- Python package development
- tests
- small model experiments
- schema evolution
- local memory experiments
- benchmark prototypes

The local version must run without GPU.

## Server usage

Use the server only after the core is stable and containerized.

Allowed server roles:

- staging API
- stable demo runtime
- lightweight inference node if isolated
- persistent memory after schema stabilization
- monitoring endpoint

Forbidden early server roles:

- heavy training
- uncontrolled model downloads
- unbounded GPU workers
- shared database mutation without backups
- background jobs without resource limits

## Deployment rules

Any server deployment must include:

- Docker isolation
- explicit ports
- separate volumes
- healthcheck
- CPU and memory limits
- logs
- rollback path

## Degraded mode

Every core component must have a degraded path.

Examples:

- no GPU → use deterministic cells and mock inference
- no vector DB → use in-memory or SQLite fallback
- no model server → route only to rule-based cells
- no external tools → return evidence_missing, not fake confidence

## First environment target

```text
Python 3.11+
FastAPI later
Pydantic contracts
pytest
local-only core kernel
```

GPU, model servers, and persistent vector memory are later phases.
