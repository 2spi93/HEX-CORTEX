# HEX-CORTEX Local Harness V2 — Operator Manual

Date: 2026-10-09

## Scope

HEX-CORTEX is local-first: canonical source remains GitHub; executable work
happens on the operator's PC. No remote deployment or shared infrastructure
is part of the roadmap. Existing legacy code remains for audit/history only.

## Install and verify (PowerShell in a local clone)

    git pull --ff-only origin main
    python -m pip install -e ".[dev]"
    ruff check .
    python -m pytest

The above test command validates Python contracts, not GPU health or local
Ollama availability. Never claim that a model actually ran based on CI tests.

## Harness Core V2

    hexcortex-harness --project-root . --approve-read

The local kernel has bounded Session, Task, Budget, Capability, Tool contracts,
a measured bandit model router and SHA-256 replay receipts. A task cannot
run a mutating tool. No raw prompts or outputs appear in durable receipts.

The read-only manifest command is denied if --approve-read is missing.

To call ONE installed localhost Ollama model with explicit consent:

    hexcortex-harness --project-root . --model qwen2.5-coder:7b --approve-model --instruction "Explain CanonicalSpine" --max-tokens 768 --timeout 60

The model name shown is illustrative. Install or select a local model before
using it; the CLI cannot install one. Requests go only to localhost and
the adapter unloads the model immediately after inference.

## Benchmark V2

The legacy 13-question battery was a smoke test. The V2 fingerprint binds
the evaluation suite, model name and digest, quantization, local hardware
identifier and heldout results; latency and throughput are collected when
the runtime returns those fields. Raw prompts/responses are not persisted.

    hexcortex-benchmark-v2 --model qwen2.5-coder:7b --digest sha256:ACTUAL_DIGEST --quantization Q4_K_M --hardware ryzen9900x-cpu --registry receipts/fingerprints_v2.jsonl

Replace model, digest, quantization and hardware with verified actual values.
This is a synthetic experimental prior, NOT a certification of real repository
bugfix performance. To rank multiple candidate models, the new local harness
requires fingerprints matching each model digest and the hardware, unless
the operator explicitly requests --allow-unmeasured.

    hexcortex-harness --approve-model --model qwen2.5-coder:7b --model llama3.2:3b --model-digest qwen2.5-coder:7b=sha256:ACTUAL_DIGEST_1 --model-digest llama3.2:3b=sha256:ACTUAL_DIGEST_2 --hardware ryzen9900x-cpu --fingerprint-registry receipts/fingerprints_v2.jsonl --instruction "Review this local plan"

## MCP Skills: opt-in

Export already-approved active SkillRecord entries to portable SKILL.md:

    hexcortex-skills .hex-cortex/skills.jsonl .local-skills

The input JSONL path is illustrative and must exist. No skill executes during
export. To expose a vetted local directory of skills through MCP in PowerShell:

    $env:HEX_CORTEX_SKILLS_DIRECTORY = (Resolve-Path .local-skills).Path
    hexcortex-mcp

The modern adapter supports server/discover, skills/list, skills/get and
resources/read, with SHA-256 digests and a bounded resource manifest. No
third-party skill receives automatic permission or activation. The currently
supported catalog intentionally only publishes documentary formats.

## MCP Tasks: opt-in local persisted completed results

    $env:HEX_CORTEX_TASK_STORE = (Join-Path (Get-Location) ".hex-cortex/tasks.sqlite")
    hexcortex-mcp

A client negotiating io.modelcontextprotocol/tasks can receive an immediate,
durably persisted completed task handle instead of an inline tool result.
tasks/get, tasks/update and tasks/cancel are available, and completed tasks
remain terminal. This is NOT an asynchronous execution scheduler.

## A2A adapter: in-process / stdin only

    hexcortex-a2a-local --project-root .

This command consumes newline-separated JSON-RPC requests on stdin.
Supported method subset: SendMessage, GetTask, CancelTask. The only action
is an explicitly permitted local read-only repo manifest (with --approve-read).
A2A network transport, push, streaming and remote discovery are NOT claimed.

## GTIXT boundary

The offline helper inspect_gtixt_snapshot accepts only explicitly approved
snapshots with project_id=GTIXT and schema version 1. Supported read-only
capabilities: health, runtime_summary, blockers, latest_artifacts,
evidence_coverage, open_tasks and capability_map.

No account, database, secret, pricing, index score, memory or GTIXT deployment
is accessed. Nothing is imported into HEX-CORTEX memory without a separate
review.

## Validation levels

1. Code exists in GitHub
2. CI/Ruff/pytest pass
3. Operator has an installed local model and compatible fingerprints
4. End-to-end result quality/latency is measured on the actual machine
5. Mutating autonomous execution remains disabled by default

See:
- https://skills.extensions.modelcontextprotocol.io/specification/stable/skills
- https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks
- https://a2a-protocol.org/latest/specification/
