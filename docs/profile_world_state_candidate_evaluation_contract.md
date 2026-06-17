# Profile World State Candidate Evaluation Contract

## Status

Opened as `PROFILE_WORLD_STATE_CANDIDATE_EVALUATION_V4_3`.

## Purpose

WorldStateCandidateEvaluation scores the latest local world-state hypothesis before it is used for planning or skill selection.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_world_score_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_world_score_cli .hex-cortex --summary --pretty
```

## Evaluation file

```text
.hex-cortex/world-state-candidate-evaluation.jsonl
```

## Scores

```text
transition_score
risk_score
cost_score
confidence_score
overall_score
```

## Verdicts

```text
world_candidate_valid
world_candidate_watch
world_candidate_blocked
world_candidate_missing
```

## Rule

A world-state candidate is valid when the predicted state transition matches the candidate action, risk is acceptable, cost is acceptable, and confidence is high enough.

## Future path

```text
v4.4 skill scoring from world-state candidates
v4.5 action cost model
v4.6 latent state compression
```
