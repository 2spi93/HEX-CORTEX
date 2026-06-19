# Auto Web Stability V1

Status: cold implementation notes.

## What changed

This stage adds five concepts:

- `web.describe`: a known read-only web research adapter descriptor.
- `web.search`: an injectable read-only web search unit with mandatory citations.
- `CortexMode.AUTO_SAFE`: a policy mode that can run registered safe units without prompting every time.
- `stability.compute`: a small stability score that proposes rebalancing when quality drops.
- `trusted_plan`: a score for when operator intent, plan, preferences, stability, units, and receipts are aligned.
- `evaluate_cortex_auto_plan`: a dry evaluator that decides whether a plan may run automatically.

## Unknown names stay blocked

Unknown names must stay blocked.

A blocked unknown name does not prevent web research. It prevents phantom tools.

The correct path is:

1. register `web.describe`,
2. inject and register `web.search`,
3. require citations,
4. require source quality,
5. require recency for fast-changing claims,
6. block raw page persistence by default.

## Auto-safe mode

`AUTO_SAFE` may run registered read-only units automatically.

Operator units can run automatically only when the plan is trusted.

A trusted plan requires:

- operator intent known,
- plan known,
- preference match,
- stability score,
- registered unit rate,
- receipt rate.

`evaluate_cortex_auto_plan` does not execute tools. It only returns:

- whether the plan is trusted,
- whether each step is allowed,
- blockers,
- the next action.

This lets HEX-CORTEX behave more like a coding agent while preserving receipts and gates.

## Stability loop

`stability.compute` watches:

- success rate,
- error rate,
- unknown unit rate,
- citation rate,
- receipt rate.

When quality drops, the system proposes repairs:

- add failure fixtures,
- register or reject unknown units,
- increase citation coverage,
- increase receipt coverage.

## Adinkra-inspired note

Adinkras and doubly even binary codes are not copied as physics into HEX-CORTEX.

They inspire a structural principle:

- local constraints,
- parity-like checks,
- quotienting large state spaces into governed equivalence classes,
- error-detecting receipts,
- self-correction by constraint violation.

The implementation is practical software governance, not a claim of fundamental physics.
