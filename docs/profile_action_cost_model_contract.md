# Profile Action Cost Model Contract

## Status

Opened as `PROFILE_ACTION_COST_MODEL_V4_5`.

## Purpose

ActionCostModel decomposes the latest world-state skill score into explicit action costs before planning or dispatch.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_action_cost_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_action_cost_cli .hex-cortex --summary --pretty
```

## Cost file

```text
.hex-cortex/action-cost.jsonl
```

## Cost components

```text
cognitive_cost
operator_cost
risk_cost
time_cost
overall_cost
action_score
```

## Verdicts

```text
action_cost_valid
action_cost_watch
action_cost_blocked
action_cost_missing_skill_score
```

## Rule

The action score is derived from skill score, confidence, and inverse total cost. A low-cost, low-risk, high-confidence skill should produce `action_cost_valid`.

## Future path

```text
v4.6 latent state compression
v4.7 skill registry integration
v4.8 planner decision packet
```
