# State Transition Prediction V1

Status: cold deterministic implementation.

## Purpose

Predict a compact next-state contract from:

- an allowed current world-state,
- an explicit action context,
- a bounded horizon.

## Inputs

- source `state_hash`,
- current capabilities,
- current average confidence,
- `action_id`,
- optional expected capabilities,
- optional confidence delta,
- horizon from 1 to 32 steps.

## Outputs

- predicted capabilities,
- predicted average confidence,
- predicted state hash,
- action-context hash,
- transition receipt hash.

## Safety properties

- no model call,
- no network call,
- no raw state persistence,
- blocked source states are rejected,
- missing action IDs are rejected,
- invalid horizons are rejected,
- repeated identical transitions are idempotent.

## Architecture position

This is a symbolic deterministic baseline, not a learned world model.

The next stage will compare the predicted state against a later observed state and produce prediction error and surprise receipts.
