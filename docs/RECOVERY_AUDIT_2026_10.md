# HEX-CORTEX Recovery Audit — 2026-10-09

## Source of truth and scope

- Repository: `2spi93/HEX-CORTEX`.
- Baseline: `main` at `7166669dc465b8bcf60e3bce716d440f864e88e2` (2026-07-07).
- Recovery branch: `recovery-harness-v2-2026-10`.
- The operator reports HEX-CORTEX was removed from the server. No remote deployment is assumed and none is performed by this recovery.
- This is a **repository/static inspection**, not a live runtime, GPU, MCP-client, or end-to-end production certification.
- The legacy README describes v0.1 and is not authoritative for the current codebase. See `pyproject.toml`, `docs/ARCHITECTURE_WIRING_AUDIT_V1.md`, current source, and tests for capability inventory.

## What exists in main at baseline

- Canonical event spine, persistent memory and replay, cognitive clock, health-aware routing, skill registry, world-model-related modules, observer and media contracts.
- CLI scripts for agent, coding, research, server, world training, environment routing, cognitive genome/loop, and local model benchmarking.
- The `hexcortex-mcp` stdio server implements the legacy initialization handshake, with read-only diagnostics and measured intelligence tools.
- `hexcortex-benchmark` runs local Ollama prompts and stores deterministic result fingerprints, but its test suite is small and is **not** a comprehensive capability benchmark.
- The local coding execution path and model adapters are permission-gated and environment-dependent.

## Branch safety and evidence

Comparison against baseline main:

| Branch | Ahead | Behind | Action |
|---|---:|---:|---|
| `wave3` | 30 | 377 | Preserve; inspect unique files before any cherry-pick |
| `media-world-model-training-v1` | 7 | 353 | Preserve; inspect world-model changes before any cherry-pick |
| `screen-lab-policy-v2` | 0 | 13 | Stale; not a suitable doctor default |
| `parallel-runtime-research-federation-v1` | 0 | 353 | Integrated historically; do not re-merge blindly |

**No force push, branch deletion, or automatic merge** is authorized. Unique ahead commits may be obsolete or conflict with current main; review individually.

## Defects found and treatment

| Finding | Severity | Treatment |
|---|---|---|
| Environment doctor expects stale `screen-lab-policy-v2` | P0 | Change default to `main`, retain `--expected-branch` override |
| README and CLAUDE.md lag actual implemented surfaces | P0 | Add prominent current-status notice and update maintenance rules |
| MCP stdio handles only legacy handshake | P1 | Add stateless 2026-07-28 dispatch while preserving legacy tests |
| Skills are internal records, not standard portable artifacts | P1 | Add active-only Agent Skills exporter, no execution/import/activation |
| CI evidence workflow installs package without dev test dependencies and pipes pytest through tee | P0 | Install dev extras; propagate pytest exit code; run Ruff |
| No source-backed modern harness definition | P1 | Add harness architecture and gated rollout |
| Measured-intelligence benchmark is narrow | P2 | Add domain/hardware/held-out quality and cost benchmarks later |
| A2A and long-running Tasks do not have native production adapters | P2 | Contract, conformance and sandbox evaluation before deployment |

## Readiness levels

- **Code present**: file/function exists in GitHub.
- **Tested**: test suite or required targeted tests demonstrably passed.
- **Configured**: model, dependency, endpoint, secrets and policy are in place.
- **Operational**: real scoped end-to-end run with evidence.
- **Deployed**: intentionally installed on a host with monitoring and rollback.

A contract or a positive dry-run receipt is **not** proof that a model, GUI, remote agent or hardware provider has run.

## Local validation for checkout

```powershell
git fetch origin
git switch recovery-harness-v2-2026-10
git pull --ff-only origin recovery-harness-v2-2026-10
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
hexcortex-doctor --expected-branch recovery-harness-v2-2026-10 --collect-tests
```

Verify the code, not only the count of passing tests. For real model benchmarks choose one healthy localhost model and verify memory pressure. Do not copy unreviewed JSONL runtime state or secrets from a former server.

## No server deployment

GitHub and a local checkout are the deployment-neutral source. Remote adapters and A2A workers are optional later. GTIXT remains independent and read-only at first.

## Sources

- MCP release: https://blog.modelcontextprotocol.io/posts/2026-07-28/
- MCP version negotiation: https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning
- Agent Skills: https://agentskills.io/specification
- A2A: https://a2a-protocol.org/
