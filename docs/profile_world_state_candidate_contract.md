# Profile World State Candidate Contract

## Status

Opened as `PROFILE_WORLD_STATE_CANDIDATE_V4_2`.

## Purpose

WorldStateCandidate converts the latest evaluated public trace into a compact local world-state hypothesis.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_world_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_world_cli .hex-cortex --summary --pretty
```

## Candidate file

```text
.hex-cortex/world-state-candidate.jsonl
```

## Fields

```text
candidate_id
created_at
profile_path
trace_id
evaluation_id
current_state
expected_state
candidate_action
predicted_risk
predicted_cost
confidence
source_verdict
```

## v4.2 rule

The candidate is not yet a neural latent JEPA world model. It is the local symbolic bridge toward one: trace plus evaluation becomes a predicted operator state transition.

## Future path

```text
v4.3 candidate evaluation
v4.4 skill scoring from world state
v4.5 action cost model
v4.6 latent state compression
```
