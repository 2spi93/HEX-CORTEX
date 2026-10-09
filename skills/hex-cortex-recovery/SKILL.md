---
name: hex-cortex-recovery
description: Recover or audit HEX-CORTEX GitHub branches, tests, MCP integration and local environment without deploying to a server or changing production state.
---

# HEX-CORTEX repository recovery

Use when the operator asks to resume, compare branches, verify the local setup or repair the harness after inactivity.

## Workflow

1. Read `docs/RECOVERY_AUDIT_2026_10.md` and current Git branch state.
2. Compare any divergent branches with `main`; never blindly merge or delete them.
3. Inspect the smallest relevant module and existing unit tests before editing.
4. Use a dedicated branch; preserve the canonical spine, local memory and receipts.
5. Run targeted pytest, full pytest and Ruff; report actual results, not expected counts.
6. Use the dual-era read-only MCP stdio interface for compatibility checks.
7. Distinguish source present, tested, configured, operational and deployed.

## Boundaries

No remote deployment, destructive shell operation, credential import, production mutation, hidden network calls or skill execution without explicit operator authorization. Do not claim that a dry run is live.
