# Registered Adapters V1

Status: cold implementation notes.

## What changed

This stage registers the real local units behind explicit names:

- `lc.build`
- `a.build`
- `b.build`
- `c.build`
- `r.describe`

## Why this matters

HEX-CORTEX can now expose several module tools at once through `cortex_bus`, without giving the model arbitrary access to every callable.

This creates a controlled adapter layer similar in spirit to tool registries, but stricter:

- each unit has a name,
- each unit has a compact description,
- each unit declares whether it mutates receipts,
- each unit declares whether operator approval is required,
- unknown names are blocked by the bus,
- duplicate names are rejected when registries are combined.

## Safe default plan

`build_cortex_registry_plan(profile)` runs only:

1. `lc.build`,
2. `a.build`,
3. `r.describe`.

It does not execute a model call.

## Operator path

For the first real local run:

1. create the registry,
2. run the safe default plan,
3. create a runner using `cortex_r.build_cortex_r`,
4. call `b.build` or `c.build` only with `OPERATOR_APPROVE_A1`,
5. inspect receipts.

## Not included yet

- automatic discovery,
- remote tools,
- background plans,
- unrestricted parallel execution,
- raw output persistence.
