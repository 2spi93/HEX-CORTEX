# HEX-CORTEX Harness Core V2 — architecture and rollout

**Scope change 2026-10-09:** the founder removed all distant infrastructure
from the roadmap. Read [local operator manual](LOCAL_HARNESS_V2_OPERATOR.md).
The old optional deployment proposals below are historical, not planned.

## Contractual architecture

```text
Operators / Codex / Claude Code / CLI / IDE
                 |
          Surface adapters
           /     |      \
          MCP   Local    A2A (local)
           \     |      /
           HARNESS CONTROL PLANE
     Budget / Router / Planner / Critic
     Permission gates / Evaluation
                 |
           SESSION PLANE
      CanonicalSpine / task identity
      receipts / snapshots / memory
                 |
             BRAIN PLANE
       model registry + measured routing
       Ollama/llama.cpp/frontier (gated)
                 |
             HANDS PLANE
     worktree / sandbox / browser / tools
      local worktree and consent only
```

**Harness owns process policy, NOT model weights.** No tool or model receives implicit rights to mutate repositories, deploy services, publish content, access production accounts or cross projects.

## Boundary contracts

| Plane | Receives | Returns | Must not do |
|---|---|---|---|
| Session | task id, event lineage | projection, receipts, snapshots | rewrite canonical history |
| Harness | goal, budget, permissions | route/plan, evaluation, approval decision | silently escalate privileges |
| Brain | bounded task/context | model output and measured usage | own credentials or state mutation |
| Hands | explicit allowlisted operation | result + receipt + artifacts | execute unlisted or cross-root actions |
| MCP adapter | versioned requests, tool schemas | read-only results (initially) | expose mutation without policy |
| A2A local adapter | signed, bounded task envelope | result reference and evidence | exchange raw project memory |

The existing `CognitiveClock`, `CellRegistry`, `CanonicalSpine`, gateway and local adapters remain reusable. Do not rewrite them merely to match new terminology.

## Protocol migration

1. Preserve the 2025 stdio handshake for existing Codex/Claude clients.
2. Add stateless 2026-07-28 `server/discover`, `tools/list`, `tools/call` with per-request metadata, correct result types and cache hints.
3. Run protocol interoperability and failure tests. The stdio adapter is a stepping stone, not an HTTP production server.
4. Evaluate the official MCP Python SDK v2 for future HTTP, MRTR, authorization and extension use; avoid custom protocol reimplementation beyond scoped stdio.
5. Enable Tasks / MCP Skills only after conformance tests and a clear operator authorization model.

## Skills: portable not automatically trusted

- The historical `SkillRecord` JSONL remains the canonical internal evidence source.
- Export `SkillStatus.ACTIVE` records with validated names to `SKILL.md` directories.
- No automatic import, execution, installation, trust promotion or permission inheritance.
- Review provenance, licenses and any bundled code/scripts before installing a third-party skill.
- Future: bidirectional IR + manifest and lineage mapping, conflict detection, signature or digest, versioning.

## Measured model intelligence V2

The legacy 13-question suite is only a smoke test. A production-quality fingerprint must bind:

```text
(model id, digest, quantization, host/hardware, runtime, task domain,
 evaluation version, dataset split, latency, throughput, memory usage,
 quality outcomes, failure rate, observed calibration)
```

Add held-out repo bug-fix tasks, tool-use contract compliance, multi-file reasoning, minimal patches, retrieval correctness, confidence calibration, risk/safety scopes and throughput/VRAM/cost. Prevent training-test leakage. Compare same prompts, equivalent context and deterministic scoring.

## Subagent boundaries

- The `ThalamicRouter` selects only a small number of healthy specialists.
- Each specialist receives a bounded context packet and only task-relevant tools.
- The parent aggregates citations and test artifacts, not private reasoning traces.
- Limit concurrency, retries, wall time, output tokens and external side effects.
- Critic disagreement should trigger verification, not infinite debate.

## Permissions and deployment

- Default automatic: read current repo, pure planning, inspect, unit tests, Ruff.
- Gated: model calls, network access, installing dependencies, worktree creation or patch application.
- Strong gate: secrets, deploy, publish, pushes to protected branches, any service mutation.
- Never assume previous remote credentials or server deployment remain available.
- The host decides actual permissions; an LLM instruction cannot enforce containment by itself.

## GTIXT boundary

GTIXT owns its product truth, scores, ledgers, proprietary datasets and deployments.
Initial bridge is seven read-only capabilities: health, runtime summary, blockers, latest artifacts, evidence coverage, open tasks, capability map. No merging memories or cross-project automation until a security and privacy review.

## Milestones / non-claims

| Milestone | Acceptance criterion |
|---|---|
| R0 — recovery | checkpoint and branch audit, outdated doctor and docs corrected |
| R1 — protocol | old and modern MCP tests pass against stdio |
| R2 — skills | exporter creates valid SKILL.md; candidate/quarantined blocked |
| R3 — quality | CI Ruff/pytest signal and artifacts verified on PR |
| R4 — harness modularization | explicit plane contracts and end-to-end bounded task replay |
| R5 — intelligence | representative real-model benchmarks and calibration compare baselines |
| R6 — federation | A2A/MCP Tasks conformance and sandboxed remote worker |
| R7 — optional deployment | isolated service, health checks, rollback, telemetry; never shared-host by default |

R0-R3 are the first implementable recovery increment. R4-R7 are **not** operational just because they are documented.

## References

- https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx
- https://agentskills.io/specification
- https://a2a-protocol.org/
