# Profile World State Skill Score Contract

## Status

Opened as `PROFILE_WORLD_STATE_SKILL_SCORE_V4_4`.

## Purpose

WorldStateSkillScore converts the latest evaluated world-state candidate into a suggested operator skill.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_skill_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_skill_cli .hex-cortex --summary --pretty
```

## Score file

```text
.hex-cortex/world-state-skill-score.jsonl
```

## Fields

```text
score_id
created_at
profile_path
candidate_id
evaluation_id
candidate_action
suggested_skill
skill_score
skill_reason
world_verdict
predicted_risk
predicted_cost
confidence
```

## Skill mapping v4.4

```text
review_watch_reasons -> operator_watch_review
repair_profile_readiness -> profile_readiness_repair
observe_pipeline_result -> pipeline_result_observer
build_trace -> cognitive_trace_builder
fallback -> operator_state_inspector
```

## Rule

The skill score is derived from the world-state evaluation score, predicted risk, and candidate confidence. A valid low-risk world candidate should produce a high skill score.

## Future path

```text
v4.5 action cost model
v4.6 latent state compression
v4.7 skill registry integration
```
