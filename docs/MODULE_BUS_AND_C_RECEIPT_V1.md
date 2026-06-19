# Module Bus And C Receipt V1

Status: cold implementation notes.

## What changed

This stage adds:

- `cortex_c.py`: a chained receipt that runs lc -> a -> b with an injected runner.
- `cortex_bus.py`: an explicit registry for running several module units in one plan.

## Why explicit registry

HEX-CORTEX should not auto-discover every callable in the repository.

Explicit registration gives:

- smaller tool surface,
- clearer descriptions,
- predictable permissions,
- easier auditing,
- safer multi-module plans.

## Multi-module rule

Several modules may be used in one plan only if each unit is explicitly registered.

Unknown unit names are blocked.
Duplicate unit names are blocked when registries are combined.

## Relationship to MCP-style systems

MCP-style systems standardize tool access. HEX-CORTEX keeps the same idea but adds local receipts, operator gates, and compact module metadata before activation.

## Activation path

1. `cortex_lc`: local target receipt.
2. `cortex_a`: safe shape receipt.
3. `cortex_r`: local runner adapter.
4. `cortex_b`: operator-approved runner receipt.
5. `cortex_c`: chained final receipt.
6. `cortex_bus`: multi-module plan support.

## Not included yet

- automatic tool discovery,
- background runs,
- unrestricted parallel execution,
- remote tool execution,
- raw output persistence.
