# Adapter Execution Gateway V1

Status: implemented behind registered adapters, policy gates, route receipts, and adapter receipts.

## Purpose

The gateway is the single execution boundary between a selected HEX-CORTEX action and an injected runtime adapter.

It accepts:

- a ready route receipt,
- a ready lane or adapter receipt,
- a registered adapter,
- a hashed request,
- a policy mode,
- explicit network and local-process permissions,
- optional secret references,
- an optional idempotency key.

## Policy modes

- `manual`: execution requires operator approval.
- `assisted`: effect-capable or operator-gated adapters are refused.
- `auto_safe`: execution requires a trusted plan and an adapter explicitly marked auto-safe.

## Hard gates

The gateway rejects:

- unknown adapters,
- route/adapter lane mismatch,
- invalid or blocked receipts,
- missing operator approval,
- missing trusted-plan status,
- network access without explicit permission,
- local-process access without explicit permission,
- adapters not declared auto-safe,
- invalid execution modes.

## Receipts and privacy

The persisted record contains hashes and summaries only.

It does not persist:

- raw requests,
- raw results,
- secret values,
- adapter handler objects.

Only secret reference names may be recorded.

## Idempotency

Identical execution contracts produce the same gateway hash. A repeated call returns the existing receipt and does not invoke the adapter a second time.

## Registered transport families

The current code provides factories for:

- Ollama on localhost,
- local OpenAI-compatible servers such as llama.cpp server,
- injected project adapters,
- injected service adapters,
- injected hardware adapters,
- cited read-only web research adapters.

## Timeout boundary

Network adapters enforce their own bounded timeout. The generic callable gateway records the adapter timeout contract but does not attempt to interrupt an arbitrary Python callable.

## MCP boundary

The MCP stdio server is intentionally read-only in V1. It exposes diagnostics, manifests, surface audits, runtime facts, and the read plan. It does not expose `exec.call`.

This preserves a human-controlled boundary while Claude Code and Codex integration is first validated.
