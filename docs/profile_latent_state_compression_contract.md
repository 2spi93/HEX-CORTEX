# Profile Latent State Compression Contract

## Status

Opened as `PROFILE_LATENT_STATE_COMPRESSION_V4_6`.

## Purpose

LatentStateCompression converts the latest planning state into a compact symbolic latent state. This is the bridge from operator JSONL traces toward a small local latent planning space.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_latent_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_latent_cli .hex-cortex --summary --pretty
```

## Latent file

```text
.hex-cortex/latent-state.jsonl
```

## Sources

```text
world-state-candidate.jsonl
world-state-skill-score.jsonl
action-cost.jsonl
```

## Fields

```text
latent_id
created_at
profile_path
source_candidate_id
source_score_id
source_cost_id
latent_version
tokens
vector
vector_dim
compression_score
suggested_skill
candidate_action
action_score
verdict
reasons
```

## v4.6 symbolic vector

```text
state_value
action_value
risk_value
inverse_cost
action_score
skill_score
confidence
verdict_value
```

## Verdicts

```text
latent_state_valid
latent_state_watch
latent_state_blocked
latent_missing_action_cost
```

## Rule

The compressed latent state is valid when the source action cost is valid and the compression score is high enough.

## Future path

```text
v4.7 skill registry integration
v4.8 planner decision packet
v4.9 replay learning from latent states
```
