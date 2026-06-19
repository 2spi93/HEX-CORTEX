# Surprise And Prediction Error V1

Status: cold deterministic implementation.

## Purpose

Compare a ready transition prediction with a later allowed world-state and produce a bounded prediction-error receipt.

## Comparable features

The V1 score compares:

- predicted capabilities versus observed capabilities,
- predicted average confidence versus observed average confidence.

Transition and state hashes are retained for lineage. They are not directly scored because they are generated from different contracts and would otherwise create false permanent surprise.

## Error score

The bounded score is:

- 70 percent capability-set error,
- 30 percent absolute confidence error.

Default levels:

- low: score less than or equal to 0.20,
- medium: score above 0.20 and below 0.50,
- high: score greater than or equal to 0.50.

## Learning signals

- low -> `no_update`,
- medium -> `bounded_update`,
- high -> `priority_update`.

## Safety properties

- no model call,
- no network call,
- no raw state persistence,
- blocked transitions are rejected,
- blocked observed states are rejected,
- invalid confidence values are rejected,
- invalid thresholds are rejected,
- identical comparisons are idempotent.

## Architecture position

This layer creates an explicit correction signal but does not train or mutate a model.

The next stage may store temporally ordered episodes containing state, action, prediction, observation, error, and repair signal.
